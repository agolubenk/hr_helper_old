from django.db.models import Avg, Count, Q, F, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    HiringRequest, RecruitmentMetrics, DemandForecast, RecruiterCapacity,
    VacancySLA
)
from django.contrib.auth import get_user_model

User = get_user_model()


class MetricsService:
    """Сервис для расчета всех метрик"""
    
    @staticmethod
    def calculate_recruitment_metrics(period_start, period_end, 
                                      vacancy=None, grade=None, project=None):
        """Рассчитать метрики найма за период"""
        
        # Фильтруем заявки по дате открытия
        requests = HiringRequest.objects.filter(
            opening_date__range=[period_start, period_end]
        )
        
        if vacancy:
            requests = requests.filter(vacancy=vacancy)
        if grade:
            requests = requests.filter(grade=grade)
        if project:
            requests = requests.filter(project=project)
        
        # Закрытые заявки (включая переходящие - открытые в периоде, закрытые в периоде или позже)
        closed_requests = requests.filter(
            status='closed', 
            closed_date__isnull=False,
            closed_date__gte=period_start  # Закрыты в периоде или позже
        )
        
        # Заявки, закрытые в периоде (независимо от даты открытия)
        closed_in_period = HiringRequest.objects.filter(
            status='closed',
            closed_date__isnull=False,
            closed_date__range=[period_start, period_end]
        )
        
        if vacancy:
            closed_in_period = closed_in_period.filter(vacancy=vacancy)
        if grade:
            closed_in_period = closed_in_period.filter(grade=grade)
        if project:
            closed_in_period = closed_in_period.filter(project=project)
        
        # === TIME-TO-OFFER ===
        # Используем переходящие заявки, если есть, иначе - закрытые в периоде
        requests_for_time_calc = closed_requests if closed_requests.exists() else closed_in_period
        
        if requests_for_time_calc.exists():
            time_to_offer_values = []
            for req in requests_for_time_calc:
                days = (req.closed_date - req.opening_date).days
                time_to_offer_values.append(days)
            
            avg_time_to_offer = sum(time_to_offer_values) / len(time_to_offer_values)
            median_time_to_offer = sorted(time_to_offer_values)[len(time_to_offer_values) // 2]
        else:
            avg_time_to_offer = 0
            median_time_to_offer = 0
        
        # === HIRING VELOCITY ===
        weeks = (period_end - period_start).days / 7
        hiring_velocity = closed_in_period.count() / weeks if weeks > 0 else 0
        
        # === DAYS BEHIND SCHEDULE ===
        # Поскольку deadline теперь свойство, считаем в Python
        delays = []
        for req in requests_for_time_calc:
            if req.deadline and req.closed_date:
                if req.closed_date > req.deadline:
                    delay = (req.closed_date - req.deadline).days
                    delays.append(delay)
        avg_days_behind = sum(delays) / len(delays) if delays else 0
        
        # === SLA COMPLIANCE ===
        if requests_for_time_calc.exists():
            on_time_count = 0
            overdue_count = 0
            for req in requests_for_time_calc:
                if req.deadline and req.closed_date:
                    if req.closed_date <= req.deadline:
                        on_time_count += 1
                    else:
                        overdue_count += 1
            sla_compliance = (on_time_count / requests_for_time_calc.count()) * 100
        else:
            sla_compliance = 0
            overdue_count = 0
        
        # === КРИТИЧЕСКИЕ ЗАЯВКИ ===
        # Заявки с приоритетом "Критический"
        critical_count = requests.filter(priority=1).count()  # 1 = Критический
        
        # Создаем/обновляем метрики
        metrics, created = RecruitmentMetrics.objects.update_or_create(
            period_type='custom',
            period_start=period_start,
            period_end=period_end,
            vacancy=vacancy,
            grade=grade,
            project=project or '',
            defaults={
                'avg_time_to_offer': round(avg_time_to_offer, 2),
                'median_time_to_offer': round(median_time_to_offer, 2),
                'hires_count': closed_in_period.count(),  # Закрытые в периоде
                'hiring_velocity_weekly': round(hiring_velocity, 2),
                'avg_days_behind_schedule': round(avg_days_behind, 2),
                'overdue_requests_count': overdue_count,
                'sla_compliance_rate': round(sla_compliance, 2),
                'total_requests': requests.count(),  # Открытые в периоде
                'closed_requests': closed_requests.count(),  # Открытые в периоде и закрытые
                'active_requests': closed_requests.count() + requests.filter(status__in=['in_progress', 'planned']).count(),  # Переходящие + открытые в периоде (стартовавшие)
                'in_progress_requests': requests.filter(status='in_progress').count(),  # Заявки в процессе
                'planned_requests': requests.filter(status='planned').count(),  # Планируемые заявки
                'cancelled_requests': requests.filter(status='cancelled').count(),
                'critical_requests_count': critical_count,  # Критические заявки
            }
        )
        
        return metrics
    
    @staticmethod
    def forecast_demand(vacancy, grade=None, forecast_period='next_month'):
        """Прогнозирование потребности на основе истории"""
        
        # Определяем период прогноза
        today = timezone.now().date()
        if forecast_period == 'next_month':
            forecast_start = today + timedelta(days=30)
            forecast_end = forecast_start + timedelta(days=30)
            lookback_days = 90  # анализируем последние 3 месяца
        elif forecast_period == 'next_quarter':
            forecast_start = today + timedelta(days=90)
            forecast_end = forecast_start + timedelta(days=90)
            lookback_days = 365  # анализируем год
        else:  # next_year
            forecast_start = today + timedelta(days=365)
            forecast_end = forecast_start + timedelta(days=365)
            lookback_days = 730  # 2 года
        
        # Исторические данные
        history_start = today - timedelta(days=lookback_days)
        historical_requests = HiringRequest.objects.filter(
            vacancy=vacancy,
            opening_date__range=[history_start, today]
        )
        
        if grade:
            historical_requests = historical_requests.filter(grade=grade)
        
        # Средняя потребность за период
        if lookback_days >= 365:
            periods_count = lookback_days / 365
        elif lookback_days >= 90:
            periods_count = lookback_days / 90
        else:
            periods_count = lookback_days / 30
        
        avg_demand_per_period = historical_requests.count() / periods_count if periods_count > 0 else 0
        
        # Сезонность (упрощенно - можно улучшить)
        current_month = today.month
        if current_month in [1, 2, 8, 9]:  # Активные месяцы найма
            seasonality = 1.2
        elif current_month in [12, 7]:  # Праздники
            seasonality = 0.7
        else:
            seasonality = 1.0
        
        # Прогноз
        forecasted_demand = int(avg_demand_per_period * seasonality)
        confidence = 70 if historical_requests.count() > 10 else 50
        
        # Создаем прогноз
        forecast = DemandForecast.objects.create(
            forecast_period=forecast_period,
            forecast_start=forecast_start,
            forecast_end=forecast_end,
            vacancy=vacancy,
            grade=grade,
            forecasted_demand=forecasted_demand,
            confidence_level=confidence,
            seasonality_factor=seasonality,
            created_by=None,  # Можно передать пользователя из контекста
        )
        
        return forecast
    
    @staticmethod
    def calculate_recruiter_capacity(recruiter, period_start, period_end):
        """Рассчитать мощность рекрутера"""
        
        # Активные заявки
        active = HiringRequest.objects.filter(
            created_by=recruiter,
            status__in=['planned', 'in_progress'],
            opening_date__lte=period_end
        ).count()
        
        # Запланированные (будущие)
        planned = HiringRequest.objects.filter(
            created_by=recruiter,
            status='planned',
            opening_date__gt=period_end
        ).count()
        
        # Закрытые за период
        closed = HiringRequest.objects.filter(
            created_by=recruiter,
            status='closed',
            closed_date__range=[period_start, period_end]
        ).count()
        
        # Среднее время на заявку
        closed_requests = HiringRequest.objects.filter(
            created_by=recruiter,
            status='closed',
            closed_date__range=[period_start, period_end]
        )
        
        if closed_requests.exists():
            time_values = []
            for req in closed_requests:
                days = (req.closed_date - req.opening_date).days
                time_values.append(days)
            avg_time = sum(time_values) / len(time_values)
            success_rate = (closed / (closed + active)) * 100 if (closed + active) > 0 else 0
        else:
            avg_time = 0
            success_rate = 0
        
        # Создаем/обновляем capacity
        capacity, created = RecruiterCapacity.objects.update_or_create(
            recruiter=recruiter,
            period_start=period_start,
            defaults={
                'period_end': period_end,
                'active_requests_count': active,
                'planned_requests_count': planned,
                'closed_requests_count': closed,
                'avg_time_per_request': round(avg_time, 2),
                'success_rate': round(success_rate, 2),
            }
        )
        
        capacity.calculate_capacity()
        return capacity
    
    @staticmethod
    def get_team_capacity_summary(period_start=None, period_end=None):
        """Общая статистика по команде рекрутеров"""
        
        # Получаем всех пользователей (в реальной системе нужно фильтровать по группе рекрутеров)
        recruiters = User.objects.all()[:5]  # Ограничиваем для демо
        
        # Если период не указан, используем последние 30 дней
        if not period_start or not period_end:
            today = timezone.now().date()
            period_start = today - timedelta(days=30)
            period_end = today
        
        summary = {
            'total_recruiters': recruiters.count(),
            'overloaded_count': 0,
            'avg_capacity_utilization': 0,
            'total_active_requests': 0,
            'recruiters': []
        }
        
        utilizations = []
        for recruiter in recruiters:
            capacity = MetricsService.calculate_recruiter_capacity(
                recruiter, period_start, period_end
            )
            
            if capacity.is_overloaded:
                summary['overloaded_count'] += 1
            
            utilizations.append(float(capacity.capacity_utilization))
            summary['total_active_requests'] += capacity.active_requests_count
            
            summary['recruiters'].append({
                'recruiter': recruiter,
                'capacity': capacity,
            })
        
        if utilizations:
            summary['avg_capacity_utilization'] = round(
                sum(utilizations) / len(utilizations), 2
            )
        
        return summary
    
    @staticmethod
    def get_monthly_metrics():
        """Получить метрики за текущий месяц"""
        today = timezone.now().date()
        period_start = today.replace(day=1)
        next_month = period_start + timedelta(days=32)
        period_end = next_month.replace(day=1) - timedelta(days=1)
        
        return MetricsService.calculate_recruitment_metrics(period_start, period_end)
    
    @staticmethod
    def get_quarterly_metrics():
        """Получить метрики за текущий квартал"""
        today = timezone.now().date()
        
        # Определяем квартал
        quarter = (today.month - 1) // 3 + 1
        quarter_start_month = (quarter - 1) * 3 + 1
        
        period_start = today.replace(month=quarter_start_month, day=1)
        
        # Конец квартала
        if quarter == 4:
            period_end = today.replace(month=12, day=31)
        else:
            next_quarter_month = quarter_start_month + 3
            period_end = today.replace(month=next_quarter_month, day=1) - timedelta(days=1)
        
        return MetricsService.calculate_recruitment_metrics(period_start, period_end)
    
    @staticmethod
    def get_period_dates(period_type):
        """Получить даты начала и конца для различных периодов"""
        today = timezone.now().date()
        
        if period_type == 'current_month':
            # Текущий месяц
            period_start = today.replace(day=1)
            next_month = period_start + timedelta(days=32)
            period_end = next_month.replace(day=1) - timedelta(days=1)
            
        elif period_type == 'current_quarter':
            # Текущий квартал
            quarter = (today.month - 1) // 3 + 1
            quarter_start_month = (quarter - 1) * 3 + 1
            period_start = today.replace(month=quarter_start_month, day=1)
            
            if quarter == 4:
                period_end = today.replace(month=12, day=31)
            else:
                next_quarter_month = quarter_start_month + 3
                period_end = today.replace(month=next_quarter_month, day=1) - timedelta(days=1)
                
        elif period_type == 'last_month':
            # Прошлый месяц
            first_this_month = today.replace(day=1)
            period_end = first_this_month - timedelta(days=1)
            period_start = period_end.replace(day=1)
            
        elif period_type == 'last_quarter':
            # Прошлый квартал
            current_quarter = (today.month - 1) // 3 + 1
            if current_quarter == 1:
                last_quarter = 4
                last_quarter_year = today.year - 1
            else:
                last_quarter = current_quarter - 1
                last_quarter_year = today.year
                
            quarter_start_month = (last_quarter - 1) * 3 + 1
            period_start = today.replace(year=last_quarter_year, month=quarter_start_month, day=1)
            
            if last_quarter == 4:
                period_end = today.replace(year=last_quarter_year, month=12, day=31)
            else:
                next_quarter_month = quarter_start_month + 3
                period_end = today.replace(year=last_quarter_year, month=next_quarter_month, day=1) - timedelta(days=1)
                
        elif period_type == 'last_6_months':
            # Последние 6 месяцев
            period_start = today - timedelta(days=180)
            period_end = today
            
        elif period_type == 'last_year':
            # Прошлый год
            period_start = today.replace(year=today.year - 1, month=1, day=1)
            period_end = today.replace(year=today.year - 1, month=12, day=31)
            
        elif period_type == 'current_year':
            # Текущий год
            period_start = today.replace(month=1, day=1)
            period_end = today.replace(month=12, day=31)
            
        elif period_type == 'all_time':
            # Все время
            period_start = today.replace(year=2020, month=1, day=1)  # Начало отслеживания
            period_end = today
            
        elif period_type == 'custom':
            # Кастомный период - нужно передавать даты отдельно
            # Пока возвращаем текущий квартал
            return MetricsService.get_period_dates('current_quarter')
            
        else:
            # По умолчанию - текущий квартал
            return MetricsService.get_period_dates('current_quarter')
            
        return period_start, period_end
