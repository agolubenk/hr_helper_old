"""
Обработчики для работы с интервьюерами
Содержит общую логику для views.py и views_api.py
"""
from typing import Dict, Any, Optional
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db.models import Q

from ..models import Interviewer


class InterviewerHandler:
    """Обработчик для работы с интервьюерами"""

    @staticmethod
    def search_interviewers_logic(query: str = '', is_active: Optional[str] = None, 
                                has_calendar: Optional[str] = None) -> Q:
        """
        Общая логика поиска интервьюеров

        Args:
            query: Поисковый запрос
            is_active: Фильтр по активности
            has_calendar: Фильтр по наличию календаря

        Returns:
            Q: QuerySet фильтр
        """
        filter_q = Q()

        # Поиск по тексту
        if query:
            filter_q &= (
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(email__icontains=query)
            )

        # Фильтр по активности
        if is_active is not None:
            if is_active == 'true' or is_active == True:
                filter_q &= Q(is_active=True)
            elif is_active == 'false' or is_active == False:
                filter_q &= Q(is_active=False)

        # Фильтр по наличию календаря
        if has_calendar is not None:
            if has_calendar == 'true' or has_calendar == True:
                filter_q &= Q(calendar_link__isnull=False) & ~Q(calendar_link='')
            elif has_calendar == 'false' or has_calendar == False:
                filter_q &= (Q(calendar_link__isnull=True) | Q(calendar_link=''))

        return filter_q

    @staticmethod
    def toggle_active_logic(interviewer_id: int, user=None) -> Dict[str, Any]:
        """
        Общая логика переключения активности интервьюера

        Args:
            interviewer_id: ID интервьюера
            user: Пользователь Django (для messages)

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            interviewer = get_object_or_404(Interviewer, pk=interviewer_id)
            
            # Переключаем активность
            interviewer.is_active = not interviewer.is_active
            interviewer.save()

            status = 'активирован' if interviewer.is_active else 'деактивирован'
            full_name = interviewer.get_full_name()

            # Добавляем сообщение, если пользователь передан
            if user:
                messages.success(user, f'Интервьюер {full_name} {status}!')

            return {
                'success': True,
                'is_active': interviewer.is_active,
                'message': f'Интервьюер {status}',
                'full_name': full_name
            }

        except Exception as e:
            error_message = f'Ошибка: {str(e)}'
            
            if user:
                messages.error(user, error_message)

            return {
                'success': False,
                'message': error_message
            }

    @staticmethod
    def get_interviewer_by_id(interviewer_id: int) -> Interviewer:
        """
        Получение интервьюера по ID

        Args:
            interviewer_id: ID интервьюера

        Returns:
            Interviewer: Объект интервьюера
        """
        return get_object_or_404(Interviewer, pk=interviewer_id)

    @staticmethod
    def get_active_interviewers():
        """
        Получение активных интервьюеров

        Returns:
            QuerySet: Активные интервьюеры
        """
        return Interviewer.objects.filter(is_active=True)

    @staticmethod
    def get_interviewers_with_calendar():
        """
        Получение интервьюеров с настроенным календарем

        Returns:
            QuerySet: Интервьюеры с календарем
        """
        return Interviewer.objects.filter(
            is_active=True,
            calendar_link__isnull=False
        ).exclude(calendar_link='')

    @staticmethod
    def get_recent_interviewers(limit: int = 5):
        """
        Получение последних добавленных интервьюеров

        Args:
            limit: Максимальное количество

        Returns:
            QuerySet: Последние интервьюеры
        """
        return Interviewer.objects.order_by('-created_at')[:limit]

    @staticmethod
    def calculate_interviewer_stats():
        """
        Расчет статистики по интервьюерам

        Returns:
            Dict[str, Any]: Статистика интервьюеров
        """
        total_interviewers = Interviewer.objects.count()
        active_interviewers = Interviewer.objects.filter(is_active=True).count()
        inactive_interviewers = total_interviewers - active_interviewers
        interviewers_with_calendar = InterviewerHandler.get_interviewers_with_calendar().count()

        return {
            'total_interviewers': total_interviewers,
            'active_interviewers': active_interviewers,
            'inactive_interviewers': inactive_interviewers,
            'interviewers_with_calendar': interviewers_with_calendar
        }


class InterviewerApiHandler:
    """Обработчик для API endpoints интервьюеров"""

    @staticmethod
    def toggle_active_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для переключения активности

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        interviewer_id = data.get('pk') or data.get('id')
        return InterviewerHandler.toggle_active_logic(interviewer_id, request.user)

    @staticmethod
    def search_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для поиска интервьюеров

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат поиска
        """
        query = data.get('q', '')
        is_active = data.get('is_active')
        has_calendar = data.get('has_calendar')

        # Применяем фильтр
        filter_q = InterviewerHandler.search_interviewers_logic(query, is_active, has_calendar)
        
        # Получаем отфильтрованных интервьюеров
        interviewers = Interviewer.objects.filter(filter_q)

        return {
            'success': True,
            'interviewers': interviewers,
            'count': interviewers.count()
        }

    @staticmethod
    def get_active_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения активных интервьюеров

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Активные интервьюеры
        """
        active_interviewers = InterviewerHandler.get_active_interviewers()
        
        return {
            'success': True,
            'interviewers': active_interviewers,
            'count': active_interviewers.count()
        }

    @staticmethod
    def get_with_calendar_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения интервьюеров с календарем

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Интервьюеры с календарем
        """
        interviewers_with_calendar = InterviewerHandler.get_interviewers_with_calendar()
        
        return {
            'success': True,
            'interviewers': interviewers_with_calendar,
            'count': interviewers_with_calendar.count()
        }

    @staticmethod
    def get_stats_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения статистики

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Статистика интервьюеров
        """
        stats = InterviewerHandler.calculate_interviewer_stats()
        recent_interviewers = InterviewerHandler.get_recent_interviewers()

        return {
            'success': True,
            **stats,
            'recent_interviewers': recent_interviewers
        }

