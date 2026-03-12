from django.contrib.auth import get_user_model
from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
from apps.google_oauth.models import GoogleOAuthAccount
from ..models import Interviewer

User = get_user_model()


class InterviewerCalendarService:
    """Сервис для работы с календарями интервьюеров"""
    
    def __init__(self, user):
        self.user = user
        self.oauth_service = GoogleOAuthService(user)
        self.calendar_service = None
    
    def _get_calendar_service(self):
        """Получить сервис Google Calendar"""
        if not self.calendar_service:
            self.calendar_service = GoogleCalendarService(self.oauth_service)
        return self.calendar_service
    
    def get_calendar_link_for_interviewer(self, interviewer_email):
        """Получить ссылку на календарь интервьюера по email"""
        try:
            # Проверяем, есть ли у пользователя подключенный Google аккаунт
            oauth_account = self.oauth_service.get_oauth_account()
            if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
                return None
            
            # Получаем сервис календаря
            calendar_service = self._get_calendar_service()
            if not calendar_service:
                return None
            
            # Ищем календарь по email
            calendar = calendar_service.get_calendar_by_email(interviewer_email)
            if calendar:
                # Получаем публичную ссылку на календарь
                public_link = calendar_service.get_calendar_public_link(calendar['id'])
                return public_link
            
            return None
            
        except Exception as e:
            print(f"Ошибка получения ссылки на календарь для {interviewer_email}: {e}")
            return None
    
    def auto_fill_calendar_links(self):
        """Автоматически заполнить ссылки на календари для всех интервьюеров без ссылок"""
        try:
            # Получаем всех интервьюеров без ссылки на календарь
            from django.db import models
            interviewers_without_links = Interviewer.objects.filter(
                models.Q(calendar_link__isnull=True) | models.Q(calendar_link='')
            )
            
            updated_count = 0
            
            for interviewer in interviewers_without_links:
                calendar_link = self.get_calendar_link_for_interviewer(interviewer.email)
                if calendar_link:
                    interviewer.calendar_link = calendar_link
                    interviewer.save()
                    updated_count += 1
                    print(f"Обновлена ссылка на календарь для {interviewer.email}: {calendar_link}")
            
            return updated_count
            
        except Exception as e:
            print(f"Ошибка автоматического заполнения ссылок на календари: {e}")
            return 0
    
    def get_available_calendars(self):
        """Получить список доступных календарей"""
        try:
            oauth_account = self.oauth_service.get_oauth_account()
            if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
                return []
            
            calendar_service = self._get_calendar_service()
            if not calendar_service:
                return []
            
            calendars = calendar_service.get_calendars()
            
            # Форматируем список календарей для удобного использования
            formatted_calendars = []
            for calendar in calendars:
                formatted_calendars.append({
                    'id': calendar.get('id'),
                    'summary': calendar.get('summary', 'Без названия'),
                    'description': calendar.get('description', ''),
                    'primary': calendar.get('primary', False),
                    'access_role': calendar.get('accessRole', ''),
                    'public_link': calendar_service.get_calendar_public_link(calendar.get('id'))
                })
            
            return formatted_calendars
            
        except Exception as e:
            print(f"Ошибка получения списка календарей: {e}")
            return []
    
    def suggest_calendar_for_interviewer(self, interviewer_email):
        """Предложить подходящий календарь для интервьюера"""
        try:
            calendars = self.get_available_calendars()
            
            # Ищем календарь с точно совпадающим email
            for calendar in calendars:
                if calendar['id'] == interviewer_email:
                    return calendar
            
            # Ищем календарь с похожим email (домен)
            interviewer_domain = interviewer_email.split('@')[1] if '@' in interviewer_email else ''
            for calendar in calendars:
                if '@' in calendar['id']:
                    calendar_domain = calendar['id'].split('@')[1]
                    if calendar_domain == interviewer_domain:
                        return calendar
            
            # Возвращаем основной календарь, если ничего не найдено
            for calendar in calendars:
                if calendar['primary']:
                    return calendar
            
            return None
            
        except Exception as e:
            print(f"Ошибка поиска подходящего календаря для {interviewer_email}: {e}")
            return None
