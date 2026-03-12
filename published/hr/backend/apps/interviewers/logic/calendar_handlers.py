"""
Обработчики для работы с календарями интервьюеров
Содержит общую логику для автозаполнения календарей
"""
from typing import Dict, Any, Optional
from django.shortcuts import get_object_or_404

from ..models import Interviewer
from .services import InterviewerCalendarService


class CalendarHandler:
    """Обработчик для работы с календарями"""

    @staticmethod
    def auto_fill_calendar_logic(interviewer_id: Optional[int] = None, 
                                interviewer_email: Optional[str] = None,
                                user=None) -> Dict[str, Any]:
        """
        Общая логика автозаполнения календаря

        Args:
            interviewer_id: ID интервьюера (для существующих)
            interviewer_email: Email интервьюера (для форм)
            user: Пользователь Django

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не указан'
                }

            calendar_service = InterviewerCalendarService(user)

            if interviewer_id:
                # Поиск по ID интервьюера (для существующих интервьюеров)
                interviewer = get_object_or_404(Interviewer, pk=interviewer_id)
                email = interviewer.email

                # Получаем ссылку на календарь
                calendar_link = calendar_service.get_calendar_link_for_interviewer(email)

                if calendar_link:
                    interviewer.calendar_link = calendar_link
                    interviewer.save()

                    return {
                        'success': True,
                        'message': f'Календарь для {interviewer.get_full_name()} успешно обновлен',
                        'calendar_link': calendar_link,
                        'interviewer_name': interviewer.get_full_name()
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Не удалось найти календарь для {email}'
                    }

            elif interviewer_email:
                # Поиск по email (для форм создания/редактирования)
                calendar_link = calendar_service.get_calendar_link_for_interviewer(interviewer_email)

                if calendar_link:
                    return {
                        'success': True,
                        'message': f'Календарь для {interviewer_email} найден',
                        'calendar_link': calendar_link,
                        'email': interviewer_email
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Не удалось найти календарь для {interviewer_email}'
                    }
            else:
                return {
                    'success': False,
                    'error': 'ID интервьюера или email не указан'
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при автозаполнении календаря: {str(e)}'
            }

    @staticmethod
    def auto_fill_all_calendars_logic(user=None) -> Dict[str, Any]:
        """
        Общая логика автозаполнения календарей для всех интервьюеров

        Args:
            user: Пользователь Django

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не указан'
                }

            calendar_service = InterviewerCalendarService(user)
            updated_count = calendar_service.auto_fill_calendar_links()

            return {
                'success': True,
                'message': f'Обновлено {updated_count} интервьюеров',
                'updated_count': updated_count
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при автозаполнении календарей: {str(e)}'
            }

    @staticmethod
    def get_available_calendars_logic(user=None) -> Dict[str, Any]:
        """
        Общая логика получения доступных календарей

        Args:
            user: Пользователь Django

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не указан'
                }

            calendar_service = InterviewerCalendarService(user)
            calendars = calendar_service.get_available_calendars()

            return {
                'success': True,
                'calendars': calendars,
                'count': len(calendars)
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при получении календарей: {str(e)}'
            }

    @staticmethod
    def suggest_calendar_logic(interviewer_email: str, user=None) -> Dict[str, Any]:
        """
        Общая логика предложения подходящего календаря

        Args:
            interviewer_email: Email интервьюера
            user: Пользователь Django

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не указан'
                }

            if not interviewer_email:
                return {
                    'success': False,
                    'error': 'Email интервьюера не указан'
                }

            calendar_service = InterviewerCalendarService(user)
            suggested_calendar = calendar_service.suggest_calendar_for_interviewer(interviewer_email)

            if suggested_calendar:
                return {
                    'success': True,
                    'calendar': suggested_calendar,
                    'message': f'Найден подходящий календарь для {interviewer_email}'
                }
            else:
                return {
                    'success': False,
                    'error': f'Не удалось найти подходящий календарь для {interviewer_email}'
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при поиске календаря: {str(e)}'
            }


class CalendarApiHandler:
    """Обработчик для API endpoints календарей"""

    @staticmethod
    def auto_fill_calendar_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для автозаполнения календаря

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        interviewer_id = data.get('interviewer_id')
        interviewer_email = data.get('interviewer_email')

        return CalendarHandler.auto_fill_calendar_logic(
            interviewer_id, interviewer_email, request.user
        )

    @staticmethod
    def auto_fill_all_calendars_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для автозаполнения всех календарей

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        return CalendarHandler.auto_fill_all_calendars_logic(request.user)

    @staticmethod
    def get_available_calendars_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения доступных календарей

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        return CalendarHandler.get_available_calendars_logic(request.user)

    @staticmethod
    def suggest_calendar_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для предложения календаря

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        interviewer_email = data.get('interviewer_email')
        return CalendarHandler.suggest_calendar_logic(interviewer_email, request.user)

