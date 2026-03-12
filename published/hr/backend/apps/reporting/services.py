"""
Сервисы для анализа календарных событий и генерации отчетов
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q

from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
from apps.vacancies.models import Vacancy
from apps.interviewers.models import Interviewer
from apps.google_oauth.models import Invite, GoogleOAuthAccount
from apps.reporting.models import CalendarEvent

User = get_user_model()


class CalendarEventAnalyzer:
    """Анализатор календарных событий для определения типа интервью и вакансии"""
    
    def __init__(self, user: User):
        """
        Инициализация анализатора
        
        Args:
            user: Пользователь для доступа к Google Calendar API
        """
        self.user = user
        self.oauth_service = GoogleOAuthService(user)
        self.calendar_service = GoogleCalendarService(self.oauth_service)
        
        # Загружаем все вакансии для сопоставления заголовков
        self.vacancies = Vacancy.objects.filter(is_active=True).select_related('recruiter')
        self._build_vacancy_title_map()
    
    def _get_current_week_start(self) -> datetime:
        """Получает начало текущей недели (понедельник 00:00:00)"""
        now = timezone.now()
        days_since_monday = now.weekday()
        week_start = now - timedelta(days=days_since_monday)
        return week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _sync_recruiter_events(
        self,
        recruiter: User,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Синхронизирует события календаря рекрутера
        
        Логика:
        - Для событий до текущей недели: берем из БД
        - Для текущей недели: всегда берем через API и обновляем БД
        
        Returns:
            Список проанализированных событий
        """
        current_week_start = self._get_current_week_start()
        
        # Получаем OAuth аккаунт рекрутера
        try:
            recruiter_oauth = GoogleOAuthAccount.objects.get(user=recruiter)
        except GoogleOAuthAccount.DoesNotExist:
            print(f"⚠️ Рекрутер {recruiter.username} не имеет подключенного Google OAuth аккаунта")
            # Если нет OAuth аккаунта, пытаемся получить события только из БД
            try:
                db_events = CalendarEvent.objects.filter(
                    recruiter=recruiter,
                    start_time__gte=start_date,
                    start_time__lte=end_date
                ).order_by('start_time')
                
                all_events = []
                for db_event in db_events:
                    attendees_list = []
                    for attendee in db_event.attendees or []:
                        attendees_list.append({
                            'email': attendee.get('email', ''),
                            'displayName': attendee.get('name', attendee.get('email', ''))
                        })
                    
                    event_dict = {
                        'id': db_event.event_id,
                        'summary': db_event.title,
                        'start': {'dateTime': db_event.start_time.isoformat()},
                        'end': {'dateTime': db_event.end_time.isoformat()},
                        'attendees': attendees_list,
                        'description': db_event.description or '',
                        'location': db_event.location or '',
                    }
                    analyzed = self.analyze_event(event_dict)
                    all_events.append(analyzed)
                
                return all_events
            except Exception as e:
                print(f"❌ Ошибка получения событий из БД: {e}")
                return []
        
        # Создаем сервис для работы с календарем рекрутера
        recruiter_oauth_service = GoogleOAuthService(recruiter)
        recruiter_calendar_service = GoogleCalendarService(recruiter_oauth_service)
        
        all_events = []
        
        # 1. События до текущей недели - берем из БД
        if start_date < current_week_start:
            db_end_date = min(end_date, current_week_start - timedelta(seconds=1))
            db_events = CalendarEvent.objects.filter(
                recruiter=recruiter,
                start_time__gte=start_date,
                start_time__lte=db_end_date
            ).order_by('start_time')
            
            print(f"📦 Получено {db_events.count()} событий из БД для рекрутера {recruiter.username}")
            
            for db_event in db_events:
                # Преобразуем модель в формат для анализа
                # Преобразуем участников из БД в формат Google Calendar API
                attendees_list = []
                for attendee in db_event.attendees or []:
                    attendees_list.append({
                        'email': attendee.get('email', ''),
                        'displayName': attendee.get('name', attendee.get('email', ''))
                    })
                
                event_dict = {
                    'id': db_event.event_id,
                    'summary': db_event.title,
                    'start': {'dateTime': db_event.start_time.isoformat()},
                    'end': {'dateTime': db_event.end_time.isoformat()},
                    'attendees': attendees_list,
                    'description': db_event.description or '',
                    'location': db_event.location or '',
                }
                analyzed = self.analyze_event(event_dict)
                all_events.append(analyzed)
        
        # 2. События текущей недели - всегда через API
        api_start_date = max(start_date, current_week_start)
        if api_start_date <= end_date:
            days_ahead = (end_date - api_start_date).days + 1
            
            print(f"🌐 Запрашиваем события через API для рекрутера {recruiter.username} с {api_start_date} на {days_ahead} дней")
            
            # Получаем события через API
            api_events = recruiter_calendar_service.get_events(
                calendar_id='primary',
                days_ahead=days_ahead,
                force_refresh=True
            )
            
            print(f"🌐 Получено {len(api_events)} событий через API для рекрутера {recruiter.username}")
            
            # Сохраняем/обновляем события в БД
            for event in api_events:
                event_start = self._parse_event_time(event.get('start'))
                if not event_start or event_start < current_week_start:
                    continue  # Пропускаем события не текущей недели
                
                # Анализируем событие
                analyzed = self.analyze_event(event)
                
                # Сохраняем в БД
                self._save_event_to_db(recruiter, event, analyzed)
                
                all_events.append(analyzed)
        
        return all_events
    
    def _save_event_to_db(self, recruiter: User, event: Dict, analyzed: Dict):
        """Сохраняет событие в БД"""
        try:
            event_id = event.get('id')
            if not event_id:
                return
            
            start_time = analyzed['start_time']
            end_time = analyzed['end_time']
            
            if not start_time or not end_time:
                return
            
            # Извлекаем участников
            attendees = []
            for attendee in event.get('attendees', []):
                attendees.append({
                    'email': attendee.get('email', ''),
                    'name': attendee.get('displayName', attendee.get('email', ''))
                })
            
            # Получаем время обновления из Google
            google_updated = None
            if 'updated' in event:
                try:
                    google_updated = datetime.fromisoformat(event['updated'].replace('Z', '+00:00'))
                except:
                    pass
            
            # Создаем или обновляем событие
            calendar_event, created = CalendarEvent.objects.update_or_create(
                event_id=event_id,
                defaults={
                    'recruiter': recruiter,
                    'title': event.get('summary', ''),
                    'start_time': start_time,
                    'end_time': end_time,
                    'attendees': attendees,
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'google_updated_at': google_updated,
                }
            )
            
            if created:
                print(f"✅ Сохранено новое событие в БД: {calendar_event.title}")
            else:
                print(f"🔄 Обновлено событие в БД: {calendar_event.title}")
                
        except Exception as e:
            print(f"❌ Ошибка сохранения события в БД: {e}")
    
    def _build_vacancy_title_map(self):
        """Строит карту соответствия заголовков инвайтов и вакансий"""
        self.vacancy_by_invite_title = {}
        self.vacancy_by_tech_invite_title = {}
        
        for vacancy in self.vacancies:
            if vacancy.invite_title:
                # Нормализуем заголовок для сравнения
                normalized_title = self._normalize_title(vacancy.invite_title)
                if normalized_title not in self.vacancy_by_invite_title:
                    self.vacancy_by_invite_title[normalized_title] = []
                self.vacancy_by_invite_title[normalized_title].append(vacancy)
            
            if vacancy.tech_invite_title:
                normalized_title = self._normalize_title(vacancy.tech_invite_title)
                if normalized_title not in self.vacancy_by_tech_invite_title:
                    self.vacancy_by_tech_invite_title[normalized_title] = []
                self.vacancy_by_tech_invite_title[normalized_title].append(vacancy)
    
    def _normalize_title(self, title: str) -> str:
        """Нормализует заголовок для сравнения (убирает лишние пробелы, приводит к нижнему регистру)"""
        if not title:
            return ""
        return " ".join(title.lower().split())
    
    def _match_vacancy_by_title(self, event_title: str) -> Tuple[Optional[Vacancy], str]:
        """
        Определяет вакансию и тип интервью по заголовку события
        
        Returns:
            Tuple[Vacancy или None, тип: 'screening' или 'interview' или 'unknown']
        """
        normalized_event_title = self._normalize_title(event_title)
        
        # Сначала проверяем технические интервью (более специфичные)
        for normalized_title, vacancies in self.vacancy_by_tech_invite_title.items():
            if normalized_title in normalized_event_title or normalized_event_title in normalized_title:
                # Если найдено несколько вакансий с одинаковым заголовком, берем первую
                # В будущем можно улучшить логику сопоставления
                return vacancies[0], 'interview'
        
        # Затем проверяем скрининги
        for normalized_title, vacancies in self.vacancy_by_invite_title.items():
            if normalized_title in normalized_event_title or normalized_event_title in normalized_title:
                return vacancies[0], 'screening'
        
        return None, 'unknown'
    
    def analyze_event(self, event: Dict) -> Dict:
        """
        Анализирует одно событие календаря
        
        Returns:
            Dict с полями:
            - vacancy: объект Vacancy или None
            - event_type: 'screening', 'interview' или 'unknown'
            - recruiter: рекрутер или None
            - interviewer: интервьюер или None
            - start_time: datetime начала события
            - end_time: datetime окончания события
        """
        event_title = event.get('summary', '')
        start_time = self._parse_event_time(event.get('start'))
        end_time = self._parse_event_time(event.get('end'))
        
        vacancy, event_type = self._match_vacancy_by_title(event_title)
        
        # Определяем рекрутера
        recruiter = vacancy.recruiter if vacancy else None
        
        # Пытаемся определить интервьюера по участникам события
        interviewer = self._extract_interviewer_from_event(event)
        
        # Извлекаем всех участников
        attendees = []
        for attendee in event.get('attendees', []):
            attendees.append({
                'email': attendee.get('email', ''),
                'name': attendee.get('displayName', attendee.get('email', ''))
            })
        
        # Вычисляем длительность
        duration_minutes = None
        if start_time and end_time:
            delta = end_time - start_time
            duration_minutes = int(delta.total_seconds() / 60)
        
        return {
            'vacancy': vacancy,
            'event_type': event_type,
            'recruiter': recruiter,
            'interviewer': interviewer,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'attendees': attendees,
            'event_id': event.get('id'),
            'event_title': event_title,
        }
    
    def _parse_event_time(self, time_data: Dict) -> Optional[datetime]:
        """Парсит время события из формата Google Calendar API"""
        if not time_data:
            return None
        
        # Может быть 'dateTime' или 'date' (для событий на весь день)
        if 'dateTime' in time_data:
            try:
                return datetime.fromisoformat(time_data['dateTime'].replace('Z', '+00:00'))
            except:
                pass
        
        if 'date' in time_data:
            try:
                return datetime.fromisoformat(time_data['date']).replace(tzinfo=timezone.utc)
            except:
                pass
        
        return None
    
    def _extract_interviewer_from_event(self, event: Dict) -> Optional[Interviewer]:
        """Извлекает интервьюера из события по участникам"""
        attendees = event.get('attendees', [])
        
        for attendee in attendees:
            email = attendee.get('email', '').lower()
            if email:
                try:
                    interviewer = Interviewer.objects.filter(
                        email__iexact=email,
                        is_active=True
                    ).first()
                    if interviewer:
                        return interviewer
                except:
                    pass
        
        return None
    
    def get_events_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
        recruiter: Optional[User] = None,
        calendar_id: str = 'primary'
    ) -> List[Dict]:
        """
        Получает события календаря за указанный период
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
            recruiter: Рекрутер, чей календарь нужно получить (если None - используется текущий пользователь)
            calendar_id: ID календаря (по умолчанию 'primary')
        
        Returns:
            Список проанализированных событий
        """
        # Если указан рекрутер, используем его календарь с синхронизацией
        if recruiter:
            return self._sync_recruiter_events(recruiter, start_date, end_date)
        
        # Иначе используем календарь текущего пользователя (старая логика)
        days_ahead = (end_date - start_date).days + 1
        
        events = self.calendar_service.get_events(
            calendar_id=calendar_id,
            days_ahead=days_ahead,
            force_refresh=False
        )
        
        analyzed_events = []
        for event in events:
            analyzed = self.analyze_event(event)
            
            if analyzed['start_time']:
                event_start = analyzed['start_time']
                
                if timezone.is_naive(start_date):
                    start_date = timezone.make_aware(start_date)
                if timezone.is_naive(end_date):
                    end_date = timezone.make_aware(end_date)
                if timezone.is_naive(event_start):
                    event_start = timezone.make_aware(event_start)
                
                if start_date <= event_start <= end_date:
                    analyzed_events.append(analyzed)
        
        return analyzed_events


class ReportGenerator:
    """Генератор отчетов на основе анализа календарных событий"""
    
    def __init__(self, user: User):
        self.user = user
        self.analyzer = CalendarEventAnalyzer(user)
    
    def _is_recruiter_also_interviewer(self, event: CalendarEvent) -> bool:
        """
        Проверяет, является ли рекрутер (владелец события) также интервьюером
        (его email присутствует среди участников события)
        
        Args:
            event: Событие календаря
            
        Returns:
            True, если рекрутер также является интервьюером, иначе False
        """
        if not event.recruiter or not event.recruiter.email:
            return False
        
        recruiter_email_lower = event.recruiter.email.lower()
        attendees = event.attendees or []
        
        for attendee in attendees:
            if isinstance(attendee, dict):
                attendee_email = attendee.get('email', '').lower()
            elif isinstance(attendee, str):
                attendee_email = attendee.lower()
            else:
                continue
            
            if attendee_email == recruiter_email_lower:
                return True
        
        return False
    
    def generate_company_report(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str = 'daily',
        recruiter_id: Optional[int] = None,
        interviewer_id: Optional[int] = None,
        vacancy_id: Optional[int] = None
    ) -> Dict:
        """
        Генерирует отчет по компании
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
            period: Тип периода ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            recruiter_id: ID рекрутера для фильтрации (опционально)
            interviewer_id: ID интервьюера для фильтрации (опционально)
            vacancy_id: ID вакансии для фильтрации (опционально)
        
        Returns:
            Dict с данными отчета
        """
        # Получаем события из БД для всех рекрутеров
        events = CalendarEvent.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('vacancy', 'recruiter').order_by('start_time')
        
        # Фильтруем по рекрутеру, если указан
        if recruiter_id:
            events = events.filter(recruiter_id=recruiter_id)
        
        # Фильтруем по вакансии, если указана
        if vacancy_id:
            events = events.filter(vacancy_id=vacancy_id)
        
        # Фильтруем по интервьюеру, если указан
        if interviewer_id:
            try:
                from apps.interviewers.models import Interviewer
                interviewer = Interviewer.objects.get(id=interviewer_id)
                interviewer_email_lower = interviewer.email.lower()
                
                filtered_events = []
                for event in events:
                    attendees = event.attendees or []
                    is_participant = False
                    
                    for attendee in attendees:
                        if isinstance(attendee, dict):
                            attendee_email = attendee.get('email', '').lower()
                            if attendee_email == interviewer_email_lower:
                                is_participant = True
                                break
                        elif isinstance(attendee, str):
                            if attendee.lower() == interviewer_email_lower:
                                is_participant = True
                                break
                    
                    if is_participant:
                        filtered_events.append(event)
                
                events = filtered_events
            except Interviewer.DoesNotExist:
                events = []
        
        # Преобразуем в формат для группировки
        events_list = []
        for event in events:
            events_list.append({
                'event_type': event.event_type,
                'vacancy': event.vacancy,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'title': event.title,
                'duration_minutes': event.duration_minutes,
            })
        
        # Группируем по периодам
        grouped_data = self._group_by_period(events_list, start_date, end_date, period)
        
        # Подсчитываем статистику
        if isinstance(events, list):
            total_screenings = sum(1 for e in events if e.event_type == 'screening')
            total_interviews = sum(1 for e in events if e.event_type == 'interview')
            total_time_minutes = sum(e.duration_minutes or 0 for e in events)
        else:
            total_screenings = events.filter(event_type='screening').count()
            total_interviews = events.filter(event_type='interview').count()
            total_time_minutes = sum(event.duration_minutes or 0 for event in events)
        
        # Вычисляем конверсию из скринингов в интервью
        conversion_rate = None
        if total_screenings > 0:
            conversion_rate = round((total_interviews / total_screenings) * 100, 2)
        
        return {
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_screenings': total_screenings,
            'total_interviews': total_interviews,
            'total_time_minutes': total_time_minutes,
            'conversion_rate': conversion_rate,
            'grouped_data': grouped_data,
        }
    
    def generate_recruiter_report(
        self,
        recruiter: User,
        start_date: datetime,
        end_date: datetime,
        period: str = 'daily',
        interviewer_id: Optional[int] = None
    ) -> Dict:
        """
        Генерирует отчет по рекрутеру на основе данных из БД
        
        Args:
            recruiter: Рекрутер для отчета
            start_date: Начало периода
            end_date: Конец периода
            period: Тип периода ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            interviewer_id: ID интервьюера для фильтрации (опционально)
        
        Returns:
            Dict с данными отчета
        """
        # Получаем события из БД напрямую
        events = CalendarEvent.objects.filter(
            recruiter=recruiter,
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('vacancy').order_by('start_time')
        
        # Фильтруем по интервьюеру, если указан
        if interviewer_id:
            try:
                from apps.interviewers.models import Interviewer
                interviewer = Interviewer.objects.get(id=interviewer_id)
                interviewer_email_lower = interviewer.email.lower()
                
                filtered_events = []
                for event in events:
                    attendees = event.attendees or []
                    is_participant = False
                    
                    for attendee in attendees:
                        if isinstance(attendee, dict):
                            attendee_email = attendee.get('email', '').lower()
                            if attendee_email == interviewer_email_lower:
                                is_participant = True
                                break
                        elif isinstance(attendee, str):
                            if attendee.lower() == interviewer_email_lower:
                                is_participant = True
                                break
                    
                    if is_participant:
                        filtered_events.append(event)
                
                events = filtered_events
            except Interviewer.DoesNotExist:
                events = []
        
        # ИСКЛЮЧАЕМ события, где рекрутер сам является интервьюером
        filtered_events = []
        for event in events:
            if not self._is_recruiter_also_interviewer(event):
                filtered_events.append(event)
        events = filtered_events
        
        # Преобразуем в формат для группировки
        events_list = []
        for event in events:
            events_list.append({
                'event_type': event.event_type,
                'vacancy': event.vacancy,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'title': event.title,
                'duration_minutes': event.duration_minutes,
            })
        
        grouped_data = self._group_by_period(events_list, start_date, end_date, period)
        
        # Подсчитываем статистику
        if isinstance(events, list):
            total_screenings = sum(1 for e in events if e.event_type == 'screening')
            total_interviews = sum(1 for e in events if e.event_type == 'interview')
            total_events = len(events)
            total_time_minutes = sum(e.duration_minutes or 0 for e in events)
            events_for_vacancy = [e for e in events if e.vacancy]
        else:
            total_screenings = events.filter(event_type='screening').count()
            total_interviews = events.filter(event_type='interview').count()
            total_events = events.count()
            total_time_minutes = sum(event.duration_minutes or 0 for event in events)
            events_for_vacancy = events.filter(vacancy__isnull=False).select_related('vacancy')
        
        # Статистика по вакансиям
        vacancy_stats = {}
        for event in events_for_vacancy:
            vacancy_id = event.vacancy.id
            if vacancy_id not in vacancy_stats:
                vacancy_stats[vacancy_id] = {
                    'vacancy': event.vacancy,
                    'screenings': 0,
                    'interviews': 0,
                    'total': 0,
                }
            vacancy_stats[vacancy_id]['total'] += 1
            if event.event_type == 'screening':
                vacancy_stats[vacancy_id]['screenings'] += 1
            elif event.event_type == 'interview':
                vacancy_stats[vacancy_id]['interviews'] += 1
        
        # Вычисляем конверсию из скринингов в интервью
        conversion_rate = None
        if total_screenings > 0:
            conversion_rate = round((total_interviews / total_screenings) * 100, 2)
        
        return {
            'recruiter': recruiter,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_screenings': total_screenings,
            'total_interviews': total_interviews,
            'total_events': total_events,
            'total_time_minutes': total_time_minutes,
            'conversion_rate': conversion_rate,
            'grouped_data': grouped_data,
            'vacancy_stats': list(vacancy_stats.values()),
            'events': events_list,
        }
    
    def generate_recruiters_summary_report(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str = 'monthly'
    ) -> Dict:
        """
        Генерирует сводный отчет по всем рекрутерам с разбивкой по скринингам и интервью
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
            period: Тип периода ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
        
        Returns:
            Dict с данными отчета по всем рекрутерам
        """
        # Получаем всех рекрутеров
        recruiters = User.objects.filter(groups__name='Рекрутер').exclude(username='admin').distinct()
        
        recruiters_data = []
        
        for recruiter in recruiters:
            # Получаем события рекрутера из БД
            events = CalendarEvent.objects.filter(
                recruiter=recruiter,
                start_time__gte=start_date,
                start_time__lte=end_date
            ).select_related('vacancy')
            
            # Подсчитываем статистику
            screenings = events.filter(event_type='screening').count()
            interviews = events.filter(event_type='interview').count()
            total = events.count()
            total_time_minutes = sum(event.duration_minutes or 0 for event in events)
            
            # Статистика по вакансиям
            vacancy_stats = {}
            for event in events.filter(vacancy__isnull=False).select_related('vacancy'):
                vacancy_id = event.vacancy.id
                if vacancy_id not in vacancy_stats:
                    vacancy_stats[vacancy_id] = {
                        'vacancy': event.vacancy,
                        'screenings': 0,
                        'interviews': 0,
                        'total': 0,
                    }
                vacancy_stats[vacancy_id]['total'] += 1
                if event.event_type == 'screening':
                    vacancy_stats[vacancy_id]['screenings'] += 1
                elif event.event_type == 'interview':
                    vacancy_stats[vacancy_id]['interviews'] += 1
            
            recruiters_data.append({
                'recruiter': recruiter,
                'screenings': screenings,
                'interviews': interviews,
                'total': total,
                'total_time_minutes': total_time_minutes,
                'vacancy_stats': list(vacancy_stats.values()),
            })
        
        # Сортируем по общему количеству событий (по убыванию)
        recruiters_data.sort(key=lambda x: x['total'], reverse=True)
        
        # Общая статистика
        total_screenings = sum(r['screenings'] for r in recruiters_data)
        total_interviews = sum(r['interviews'] for r in recruiters_data)
        total_events = sum(r['total'] for r in recruiters_data)
        total_time_minutes = sum(r['total_time_minutes'] for r in recruiters_data)
        
        return {
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'recruiters': recruiters_data,
            'total_screenings': total_screenings,
            'total_interviews': total_interviews,
            'total_events': total_events,
            'total_time_minutes': total_time_minutes,
            'total_recruiters': len(recruiters_data),
        }
    
    def generate_vacancy_report(
        self,
        vacancy: Vacancy,
        start_date: datetime,
        end_date: datetime,
        period: str = 'daily',
        recruiter_id: Optional[int] = None
    ) -> Dict:
        """Генерирует отчет по вакансии"""
        # Получаем события из БД, отфильтрованные по вакансии
        events = CalendarEvent.objects.filter(
            vacancy=vacancy,
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('vacancy', 'recruiter').order_by('start_time')
        
        # Фильтруем по рекрутеру, если указан
        if recruiter_id:
            events = events.filter(recruiter_id=recruiter_id)
        
        # Преобразуем в формат для группировки
        events_list = []
        for event in events:
            events_list.append({
                'event_type': event.event_type,
                'vacancy': event.vacancy,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'title': event.title,
                'duration_minutes': event.duration_minutes,
            })
        
        grouped_data = self._group_by_period(events_list, start_date, end_date, period)
        
        if isinstance(events, list):
            total_screenings = sum(1 for e in events if e.event_type == 'screening')
            total_interviews = sum(1 for e in events if e.event_type == 'interview')
            total_time_minutes = sum(e.duration_minutes or 0 for e in events)
        else:
            total_screenings = events.filter(event_type='screening').count()
            total_interviews = events.filter(event_type='interview').count()
            total_time_minutes = sum(event.duration_minutes or 0 for event in events)
        
        # Вычисляем конверсию из скринингов в интервью
        conversion_rate = None
        if total_screenings > 0:
            conversion_rate = round((total_interviews / total_screenings) * 100, 2)
        
        return {
            'vacancy': vacancy,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_screenings': total_screenings,
            'total_interviews': total_interviews,
            'total_time_minutes': total_time_minutes,
            'conversion_rate': conversion_rate,
            'grouped_data': grouped_data,
        }
    
    def generate_interviewer_report(
        self,
        interviewer: Interviewer,
        start_date: datetime,
        end_date: datetime,
        period: str = 'daily',
        recruiter_id: Optional[int] = None
    ) -> Dict:
        """
        Генерирует отчет по интервьюеру
        
        Получает события из БД, где интервьюер является участником встречи
        (его email присутствует в поле attendees)
        
        Args:
            interviewer: Интервьюер для отчета
            start_date: Начало периода
            end_date: Конец периода
            period: Тип периода ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            recruiter_id: ID рекрутера для фильтрации (опционально)
        """
        # Получаем все события за период
        all_events = CalendarEvent.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('vacancy', 'recruiter').order_by('start_time')
        
        # Фильтруем по рекрутеру, если указан
        if recruiter_id:
            all_events = all_events.filter(recruiter_id=recruiter_id)
        
        # Фильтруем события, где интервьюер является участником
        # ИСКЛЮЧАЕМ события, где рекрутер (владелец) совпадает с интервьюером
        interviewer_email_lower = interviewer.email.lower()
        interviewer_events = []
        
        for event in all_events:
            # Проверяем, есть ли email интервьюера среди участников
            attendees = event.attendees or []
            is_participant = False
            
            for attendee in attendees:
                if isinstance(attendee, dict):
                    attendee_email = attendee.get('email', '').lower()
                    if attendee_email == interviewer_email_lower:
                        is_participant = True
                        break
                elif isinstance(attendee, str):
                    # Если attendee это просто строка (email)
                    if attendee.lower() == interviewer_email_lower:
                        is_participant = True
                        break
            
            # Исключаем события, где рекрутер также является интервьюером
            if is_participant and not self._is_recruiter_also_interviewer(event):
                interviewer_events.append(event)
        
        # Преобразуем в формат для группировки
        events_list = []
        for event in interviewer_events:
            events_list.append({
                'event_type': event.event_type,
                'vacancy': event.vacancy,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'title': event.title,
                'duration_minutes': event.duration_minutes,
                'recruiter': event.recruiter,
            })
        
        grouped_data = self._group_by_period(events_list, start_date, end_date, period)
        
        # Подсчитываем статистику
        total_screenings = sum(1 for e in interviewer_events if e.event_type == 'screening')
        total_interviews = sum(1 for e in interviewer_events if e.event_type == 'interview')
        total_time_minutes = sum(e.duration_minutes or 0 for e in interviewer_events)
        
        # Вычисляем конверсию из скринингов в интервью
        conversion_rate = None
        if total_screenings > 0:
            conversion_rate = round((total_interviews / total_screenings) * 100, 2)
        
        return {
            'interviewer': interviewer,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_screenings': total_screenings,
            'total_interviews': total_interviews,
            'total_time_minutes': total_time_minutes,
            'conversion_rate': conversion_rate,
            'grouped_data': grouped_data,
            'events': events_list,
        }
    
    def _group_by_period(
        self,
        events: List[Dict],
        start_date: datetime,
        end_date: datetime,
        period: str
    ) -> Dict:
        """Группирует события по периодам"""
        grouped = {}
        
        for event in events:
            # Поддерживаем разные форматы данных
            start_time = event.get('start_time')
            if not start_time:
                continue
            
            # Если start_time это datetime объект, получаем date
            if isinstance(start_time, datetime):
                event_date = start_time.date()
            else:
                # Если это строка, пытаемся распарсить
                try:
                    if isinstance(start_time, str):
                        event_date = datetime.fromisoformat(start_time).date()
                    else:
                        continue
                except:
                    continue
            
            if period == 'daily':
                key = event_date.isoformat()
            elif period == 'weekly':
                # Номер недели года
                key = f"{event_date.year}-W{event_date.isocalendar()[1]:02d}"
            elif period == 'monthly':
                key = f"{event_date.year}-{event_date.month:02d}"
            elif period == 'quarterly':
                quarter = (event_date.month - 1) // 3 + 1
                key = f"{event_date.year}-Q{quarter}"
            elif period == 'yearly':
                key = str(event_date.year)
            else:
                key = event_date.isoformat()
            
            if key not in grouped:
                grouped[key] = {
                    'screenings': 0,
                    'interviews': 0,
                    'total_time_minutes': 0,
                    'events': []
                }
            
            # Получаем тип события (может быть в разных форматах)
            event_type = event.get('event_type', 'unknown')
            if isinstance(event_type, str):
                if event_type == 'screening':
                    grouped[key]['screenings'] += 1
                elif event_type == 'interview':
                    grouped[key]['interviews'] += 1
            
            # Суммируем время встречи
            duration_minutes = event.get('duration_minutes', 0)
            if duration_minutes and isinstance(duration_minutes, (int, float)):
                grouped[key]['total_time_minutes'] += int(duration_minutes)
            
            # Не добавляем события в список, чтобы избежать проблем с сериализацией
            # grouped[key]['events'].append(event)
        
        # Удаляем список событий из каждого периода для упрощения сериализации
        for key in grouped:
            if 'events' in grouped[key]:
                del grouped[key]['events']
        
        return grouped

