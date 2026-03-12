from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from .models import (
    HiringPlan, HiringPlanPosition, PositionType, PlanPeriodType,
    PositionKPIOKR, PlanKPIOKRBlock, PlanMetrics
)


class HiringPlanService:
    """Базовый сервис для работы с планами найма"""
    
    @staticmethod
    def create_plan(title, description, period_type=None, owner=None):
        """Создание нового плана найма"""
        plan = HiringPlan.objects.create(
            title=title,
            description=description,
            period_type=period_type,
            owner=owner
        )
        
        # Создаем метрики для плана
        PlanMetrics.objects.create(hiring_plan=plan)
        
        return plan
    
    @staticmethod
    def add_position_to_plan(plan, vacancy, headcount_needed, position_type=None, **kwargs):
        """Добавление позиции в план"""
        position = HiringPlanPosition.objects.create(
            hiring_plan=plan,
            vacancy=vacancy,
            headcount_needed=headcount_needed,
            position_type=position_type,
            **kwargs
        )
        
        # Обновляем метрики плана
        plan.update_metrics()
        
        return position
    
    @staticmethod
    def update_position_headcount(position, headcount_hired):
        """Обновление количества нанятых для позиции"""
        position.headcount_hired = headcount_hired
        position.save()
        
        # Обновляем метрики плана
        position.hiring_plan.update_metrics()
        
        return position
    
    @staticmethod
    def get_plan_statistics(plan):
        """Получение статистики по плану"""
        positions = plan.positions.all()
        
        stats = {
            'total_positions': positions.count(),
            'total_headcount_needed': positions.aggregate(
                total=Sum('headcount_needed'))['total'] or 0,
            'total_headcount_hired': positions.aggregate(
                total=Sum('headcount_hired'))['total'] or 0,
            'completion_rate': plan.completion_rate,
            'position_type_stats': positions.values('position_type__name').annotate(
                count=Count('id'),
                headcount_needed=Sum('headcount_needed'),
                headcount_hired=Sum('headcount_hired')
            ),
            'grade_stats': positions.values('grades__name').annotate(
                count=Count('id'),
                headcount_needed=Sum('headcount_needed'),
                headcount_hired=Sum('headcount_hired')
            ).filter(grades__isnull=False),
        }
        
        return stats


class HiringPlanServiceExtended(HiringPlanService):
    """Расширенный сервис для работы с планами найма"""
    
    @staticmethod
    def create_periodic_plan(title, period_type, description='', owner=None):
        """Создание периодического плана с автоматическим расчетом дат"""
        plan = HiringPlan.objects.create(
            title=title,
            description=description,
            period_type=period_type,
            owner=owner,
            is_auto_generated=True
        )
        
        # Создаем метрики для плана
        PlanMetrics.objects.create(hiring_plan=plan)
        
        return plan
    
    @staticmethod
    def get_plan_sla_compliance(plan):
        """Получение соответствия SLA для плана"""
        positions = plan.positions.filter(
            headcount_hired__gte=F('headcount_needed')
        )
        
        sla_stats = {
            'on_time': 0,
            'warning': 0,
            'critical': 0,
            'overdue': 0,
            'no_sla': 0,
            'total': positions.count()
        }
        
        for position in positions:
            status = position.sla_status
            if status in sla_stats:
                sla_stats[status] += 1
        
        # Рассчитываем проценты
        if sla_stats['total'] > 0:
            for key in ['on_time', 'warning', 'critical', 'overdue', 'no_sla']:
                sla_stats[f'{key}_percent'] = round((sla_stats[key] / sla_stats['total']) * 100, 2)
        else:
            for key in ['on_time', 'warning', 'critical', 'overdue', 'no_sla']:
                sla_stats[f'{key}_percent'] = 0
        
        return sla_stats
    
    @staticmethod
    def get_kpi_okr_summary(plan):
        """Получение сводки KPI/OKR для плана"""
        kpi_okr_list = PositionKPIOKR.objects.filter(hiring_plan=plan)
        
        summary = {
            'total_metrics': kpi_okr_list.count(),
            'kpi_count': kpi_okr_list.filter(metric_type='kpi').count(),
            'okr_count': kpi_okr_list.filter(metric_type='okr').count(),
            'custom_count': kpi_okr_list.filter(metric_type='custom').count(),
            'achieved_count': kpi_okr_list.filter(status='achieved').count(),
            'in_progress_count': kpi_okr_list.filter(status='in_progress').count(),
            'failed_count': kpi_okr_list.filter(status='failed').count(),
            'pending_count': kpi_okr_list.filter(status='pending').count(),
            'average_achievement_rate': 0,
        }
        
        # Рассчитываем средний процент достижения
        achievement_rates = [kpi.achievement_rate for kpi in kpi_okr_list if kpi.actual_value]
        if achievement_rates:
            summary['average_achievement_rate'] = round(sum(achievement_rates) / len(achievement_rates), 2)
        
        # Рассчитываем проценты
        if summary['total_metrics'] > 0:
            summary['achievement_percent'] = round((summary['achieved_count'] / summary['total_metrics']) * 100, 2)
            summary['in_progress_percent'] = round((summary['in_progress_count'] / summary['total_metrics']) * 100, 2)
            summary['failed_percent'] = round((summary['failed_count'] / summary['total_metrics']) * 100, 2)
        else:
            summary['achievement_percent'] = 0
            summary['in_progress_percent'] = 0
            summary['failed_percent'] = 0
        
        return summary
    
    @staticmethod
    def auto_move_unfilled_positions(plan):
        """Автоматическое перемещение незакрытых позиций в следующий период"""
        unfilled_positions = plan.positions.filter(
            is_active=True,
            headcount_hired__lt=F('headcount_needed')
        )
        
        moved_count = 0
        
        # Создаем следующий план, если его нет
        next_plan = plan.next_plans.filter(is_completed=False).first()
        if not next_plan:
            next_plan = HiringPlan.objects.create(
                title=f"{plan.title} - Следующий период",
                description=f"Автоматически созданный план для незакрытых позиций из {plan.title}",
                period_type=plan.period_type,
                previous_plan=plan,
                is_auto_generated=True,
                owner=plan.owner
            )
            PlanMetrics.objects.create(hiring_plan=next_plan)
        
        # Перемещаем позиции
        for position in unfilled_positions:
            remaining_headcount = position.headcount_needed - position.headcount_hired
            
            # Создаем новую позицию в следующем плане
            HiringPlanPosition.objects.create(
                hiring_plan=next_plan,
                vacancy=position.vacancy,
                position_type=position.position_type,
                headcount_needed=remaining_headcount,
                priority=position.priority,
                grades=position.grades.all(),
                specifics=position.specifics,
                notes=f"Перенесено из плана {plan.title}. {position.notes}",
                project=position.project,
                replacement_reason=position.replacement_reason,
                replaced_employee_id=position.replaced_employee_id,
                applied_kpi_okr_blocks=position.applied_kpi_okr_blocks.all()
            )
            
            # Деактивируем старую позицию
            position.is_active = False
            position.save()
            
            moved_count += 1
        
        # Обновляем метрики обоих планов
        plan.update_metrics()
        next_plan.update_metrics()
        
        return moved_count
    
    @staticmethod
    def get_position_type_statistics(plan):
        """Получение статистики по типам позиций"""
        positions = plan.positions.all()
        
        stats = positions.values('position_type__name', 'position_type__type').annotate(
            count=Count('id'),
            headcount_needed=Sum('headcount_needed'),
            headcount_hired=Sum('headcount_hired'),
            avg_priority=Avg('priority')
        ).order_by('-count')
        
        # Добавляем процент выполнения для каждого типа
        for stat in stats:
            if stat['headcount_needed'] > 0:
                stat['completion_rate'] = round((stat['headcount_hired'] / stat['headcount_needed']) * 100, 2)
            else:
                stat['completion_rate'] = 0
        
        return list(stats)
    
    @staticmethod
    def get_replacement_reasons_stats(plan):
        """Получение статистики по причинам замен"""
        positions = plan.positions.filter(
            position_type__type='replacement',
            replacement_reason__isnull=False
        ).exclude(replacement_reason='')
        
        stats = positions.values('replacement_reason').annotate(
            count=Count('id'),
            headcount_needed=Sum('headcount_needed'),
            headcount_hired=Sum('headcount_hired')
        ).order_by('-count')
        
        # Добавляем процент выполнения для каждой причины
        for stat in stats:
            if stat['headcount_needed'] > 0:
                stat['completion_rate'] = round((stat['headcount_hired'] / stat['headcount_needed']) * 100, 2)
            else:
                stat['completion_rate'] = 0
        
        return list(stats)
    
    @staticmethod
    def create_sla_for_position_type(position_type, target_time_to_fill, target_time_to_hire, grade=None):
        """Создание SLA для типа позиции"""
        # Метод удален - PositionSLA больше не используется
        created_sla_count = 0
        
        return created_sla_count
    
    @staticmethod
    def compare_plan_with_kpi_okr(plan):
        """Сравнение плана с KPI/OKR"""
        kpi_okr_list = PositionKPIOKR.objects.filter(hiring_plan=plan)
        
        comparison = {
            'total_metrics': kpi_okr_list.count(),
            'sla_comparisons': [],
            'achievement_vs_target': [],
            'scope_breakdown': {}
        }
        
        # Сравнение с SLA
        for kpi_okr in kpi_okr_list:
            if kpi_okr.sla_value:
                sla_comparison = {
                    'kpi_okr': kpi_okr,
                    'sla_value': kpi_okr.sla_value,
                    'target_value': kpi_okr.target_value,
                    'actual_value': kpi_okr.actual_value,
                    'difference_from_sla': kpi_okr.target_value - kpi_okr.sla_value,
                    'sla_achievement_rate': kpi_okr.sla_achievement_rate
                }
                comparison['sla_comparisons'].append(sla_comparison)
            
            # Достижение vs цель
            achievement_vs_target = {
                'kpi_okr': kpi_okr,
                'target_value': kpi_okr.target_value,
                'actual_value': kpi_okr.actual_value,
                'achievement_rate': kpi_okr.achievement_rate,
                'status': kpi_okr.status
            }
            comparison['achievement_vs_target'].append(achievement_vs_target)
        
        # Разбивка по scope
        scope_stats = kpi_okr_list.values('scope').annotate(
            count=Count('id')
        )
        # Добавляем средний achievement_rate вручную
        for stat in scope_stats:
            scope_kpi_okr = kpi_okr_list.filter(scope=stat['scope'])
            achievement_rates = [kpi.achievement_rate for kpi in scope_kpi_okr if kpi.actual_value]
            stat['avg_achievement'] = round(sum(achievement_rates) / len(achievement_rates), 2) if achievement_rates else 0
        
        comparison['scope_breakdown'] = {stat['scope']: stat for stat in scope_stats}
        
        return comparison
    
    @staticmethod
    def apply_kpi_okr_block_to_plan(block, hiring_plan):
        """Применение блока KPI/OKR к плану (массово)"""
        applicable_positions = block.get_applicable_positions().filter(
            hiring_plan=hiring_plan
        )
        
        applied_count = 0
        
        for position in applicable_positions:
            # Добавляем блок к позиции
            position.applied_kpi_okr_blocks.add(block)
            
            # Создаем KPI/OKR для позиции из блока
            block_kpi_okr = PositionKPIOKR.objects.filter(plan_kpi_okr_block=block)
            
            for kpi_okr in block_kpi_okr:
                PositionKPIOKR.objects.create(
                    vacancy=position.vacancy,
                    grade=position.grades.first() if position.grades.exists() else None,
                    hiring_plan=hiring_plan,
                    scope='vacancy_grade',
                    name=kpi_okr.name,
                    metric_type=kpi_okr.metric_type,
                    description=kpi_okr.description,
                    target_value=kpi_okr.target_value,
                    unit=kpi_okr.unit,
                    sla_value=kpi_okr.sla_value,
                    period_start=kpi_okr.period_start,
                    period_end=kpi_okr.period_end,
                    status='pending'
                )
                applied_count += 1
        
        return applied_count
    
    @staticmethod
    def get_vacancy_kpi_okr_comparison(vacancy, grade=None):
        """Сравнить KPI/OKR vs SLA для вакансии"""
        # Метод обновлен - использует новую модель VacancySLA
        from .models import VacancySLA
        
        sla = VacancySLA.objects.filter(
            vacancy=vacancy,
            grade=grade if grade else None,
            is_active=True
        ).first()
        
        kpi_okr = PositionKPIOKR.objects.filter(
            vacancy=vacancy,
            grade=grade if grade else None,
        )
        
        comparison = {
            'sla': sla,
            'kpi_okr': list(kpi_okr),
            'sla_vs_kpi_okr': []
        }
        
        if sla and kpi_okr:
            for kpi in kpi_okr:
                comparison['sla_vs_kpi_okr'].append({
                    'kpi': kpi,
                    'sla_target': sla.target_time_to_fill,
                    'difference': kpi.target_value - sla.target_time_to_fill
                })
        
        return comparison
    
    @staticmethod
    def generate_plan_report(plan):
        """Генерация отчета по плану"""
        report = {
            'plan_info': {
                'title': plan.title,
                'description': plan.description,
                'period_type': plan.period_type.name if plan.period_type else 'Не указан',
                'created_at': plan.created_at,
                'is_completed': plan.is_completed
            },
            'statistics': HiringPlanService.get_plan_statistics(plan),
            'sla_compliance': HiringPlanServiceExtended.get_plan_sla_compliance(plan),
            'kpi_okr_summary': HiringPlanServiceExtended.get_kpi_okr_summary(plan),
            'position_type_stats': HiringPlanServiceExtended.get_position_type_statistics(plan),
            'replacement_stats': HiringPlanServiceExtended.get_replacement_reasons_stats(plan),
            'kpi_okr_comparison': HiringPlanServiceExtended.compare_plan_with_kpi_okr(plan)
        }
        
        return report