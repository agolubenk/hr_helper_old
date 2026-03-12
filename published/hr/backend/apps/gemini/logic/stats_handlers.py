"""
Обработчики для получения статистики
Содержит общую логику для получения статистики пользователя
"""
from typing import Dict, Any, List
from django.db.models import Count, Sum, Avg
from django.contrib.auth import get_user_model

from ..models import ChatSession, ChatMessage
from .serializers import ChatSessionSerializer

User = get_user_model()


class StatsHandler:
    """Обработчик для получения статистики"""
    
    @staticmethod
    def get_user_sessions(user) -> List[ChatSession]:
        """
        Получение сессий пользователя
        
        Args:
            user: Пользователь Django
            
        Returns:
            List[ChatSession]: Список сессий пользователя
        """
        return ChatSession.objects.filter(user=user)
    
    @staticmethod
    def get_active_sessions(user) -> List[ChatSession]:
        """
        Получение активных сессий пользователя
        
        Args:
            user: Пользователь Django
            
        Returns:
            List[ChatSession]: Список активных сессий
        """
        return ChatSession.objects.filter(
            user=user, 
            is_active=True
        ).order_by('-updated_at')[:10]
    
    @staticmethod
    def get_recent_sessions(user, limit: int = 5) -> List[ChatSession]:
        """
        Получение последних сессий пользователя
        
        Args:
            user: Пользователь Django
            limit: Максимальное количество сессий
            
        Returns:
            List[ChatSession]: Список последних сессий
        """
        return ChatSession.objects.filter(user=user).order_by('-created_at')[:limit]
    
    @staticmethod
    def calculate_session_stats(sessions) -> Dict[str, int]:
        """
        Расчет статистики по сессиям
        
        Args:
            sessions: QuerySet сессий
            
        Returns:
            Dict[str, int]: Статистика сессий
        """
        total_sessions = sessions.count()
        active_sessions = sessions.filter(is_active=True).count()
        
        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions
        }
    
    @staticmethod
    def calculate_message_stats(sessions) -> Dict[str, Any]:
        """
        Расчет статистики по сообщениям
        
        Args:
            sessions: QuerySet сессий
            
        Returns:
            Dict[str, Any]: Статистика сообщений
        """
        # Получаем все сообщения для сессий пользователя
        messages = ChatMessage.objects.filter(session__in=sessions)
        
        total_messages = messages.count()
        total_tokens = messages.aggregate(
            total=Sum('tokens_used')
        )['total'] or 0
        
        # Средние значения
        average_messages_per_session = (
            total_messages / sessions.count() if sessions.count() > 0 else 0
        )
        average_tokens_per_message = (
            total_tokens / total_messages if total_messages > 0 else 0
        )
        
        return {
            'total_messages': total_messages,
            'total_tokens': total_tokens,
            'average_messages_per_session': average_messages_per_session,
            'average_tokens_per_message': average_tokens_per_message
        }
    
    @staticmethod
    def get_user_stats(user) -> Dict[str, Any]:
        """
        Получение полной статистики пользователя
        
        Args:
            user: Пользователь Django
            
        Returns:
            Dict[str, Any]: Полная статистика пользователя
        """
        try:
            # Получаем сессии пользователя
            sessions = StatsHandler.get_user_sessions(user)
            
            # Статистика сессий
            session_stats = StatsHandler.calculate_session_stats(sessions)
            
            # Статистика сообщений
            message_stats = StatsHandler.calculate_message_stats(sessions)
            
            # Последние сессии
            recent_sessions = StatsHandler.get_recent_sessions(user)
            recent_sessions_data = ChatSessionSerializer(
                recent_sessions, many=True
            ).data
            
            # Объединяем всю статистику
            stats = {
                **session_stats,
                **message_stats,
                'recent_sessions': recent_sessions_data
            }
            
            return stats
            
        except Exception as e:
            return {
                'error': f'Ошибка при получении статистики: {str(e)}'
            }
    
    @staticmethod
    def get_dashboard_context(user) -> Dict[str, Any]:
        """
        Получение контекста для дашборда
        
        Args:
            user: Пользователь Django
            
        Returns:
            Dict[str, Any]: Контекст для шаблона
        """
        try:
            # Проверяем наличие API ключа
            has_api_key = bool(user.gemini_api_key)
            
            # Получаем активные сессии
            chat_sessions = StatsHandler.get_active_sessions(user)
            
            context = {
                'has_api_key': has_api_key,
                'chat_sessions': chat_sessions,
                'api_key_configured': has_api_key,
            }
            
            return context
            
        except Exception as e:
            return {
                'error': f'Ошибка при получении контекста дашборда: {str(e)}'
            }


class StatsApiHandler:
    """Обработчик для API endpoints статистики"""
    
    @staticmethod
    def get_stats_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения статистики
        
        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос
            
        Returns:
            Dict[str, Any]: Статистика пользователя
        """
        return StatsHandler.get_user_stats(request.user)
    
    @staticmethod
    def get_dashboard_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик для получения контекста дашборда
        
        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос
            
        Returns:
            Dict[str, Any]: Контекст дашборда
        """
        return StatsHandler.get_dashboard_context(request.user)
