"""
Обработчики для работы с сообщениями чата
Содержит общую логику для views.py и views_api.py
"""
import json
from typing import Dict, Any, Optional, Tuple
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status

from ..models import ChatSession, ChatMessage
from .services import GeminiService


class MessageHandler:
    """Обработчик для работы с сообщениями чата"""
    
    @staticmethod
    def validate_message_request(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Валидация запроса на отправку сообщения
        
        Args:
            data: Данные запроса
            
        Returns:
            Tuple[bool, Optional[str]]: (валидность, ошибка)
        """
        session_id = data.get('session_id')
        message = data.get('message', '').strip()
        
        if not session_id:
            return False, 'Неверные параметры запроса: отсутствует session_id'
        
        if not message:
            return False, 'Неверные параметры запроса: отсутствует message'
        
        return True, None
    
    @staticmethod
    def validate_api_key(user) -> Tuple[bool, Optional[str]]:
        """
        Проверка наличия API ключа у пользователя
        
        Args:
            user: Пользователь Django
            
        Returns:
            Tuple[bool, Optional[str]]: (есть ключ, ошибка)
        """
        if not user.gemini_api_key:
            return False, 'API ключ не настроен'
        
        return True, None
    
    @staticmethod
    def get_chat_session(session_id: int, user) -> ChatSession:
        """
        Получение сессии чата с проверкой прав доступа
        
        Args:
            session_id: ID сессии
            user: Пользователь Django
            
        Returns:
            ChatSession: Сессия чата
        """
        return get_object_or_404(ChatSession, id=session_id, user=user)
    
    @staticmethod
    def create_user_message(session: ChatSession, message: str) -> ChatMessage:
        """
        Создание сообщения пользователя
        
        Args:
            session: Сессия чата
            message: Текст сообщения
            
        Returns:
            ChatMessage: Созданное сообщение
        """
        return ChatMessage.objects.create(
            session=session,
            role='user',
            content=message
        )
    
    @staticmethod
    def get_message_history(session: ChatSession, limit: int = 20) -> list:
        """
        Получение истории сообщений для контекста
        
        Args:
            session: Сессия чата
            limit: Максимальное количество сообщений
            
        Returns:
            list: Список сообщений для истории
        """
        history_messages = ChatMessage.objects.filter(
            session=session
        ).order_by('timestamp')[:limit]
        
        history = []
        for msg in history_messages:
            history.append({
                'role': msg.role,
                'content': msg.content
            })
        
        return history
    
    @staticmethod
    def send_to_gemini(message: str, history: list, api_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Отправка сообщения в Gemini API
        
        Args:
            message: Текст сообщения
            history: История сообщений
            api_key: API ключ Gemini
            
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (успех, ответ, метаданные)
        """
        gemini_service = GeminiService(api_key)
        return gemini_service.generate_content(message, history)
    
    @staticmethod
    def create_assistant_message(session: ChatSession, response: str, metadata: Dict[str, Any]) -> ChatMessage:
        """
        Создание сообщения ассистента
        
        Args:
            session: Сессия чата
            response: Ответ от Gemini
            metadata: Метаданные ответа
            
        Returns:
            ChatMessage: Созданное сообщение ассистента
        """
        return ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=response,
            tokens_used=metadata.get('usage_metadata', {}).get('totalTokenCount'),
            response_time=metadata.get('response_time')
        )
    
    @staticmethod
    def update_session_timestamp(session: ChatSession) -> None:
        """
        Обновление времени последнего обновления сессии
        
        Args:
            session: Сессия чата
        """
        session.updated_at = timezone.now()
        session.save()
    
    @staticmethod
    def send_message_to_gemini(session_id: int, message: str, user) -> Dict[str, Any]:
        """
        Общая логика отправки сообщения в Gemini
        
        Args:
            session_id: ID сессии чата
            message: Текст сообщения
            user: Пользователь Django
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            # Валидация запроса
            is_valid, error = MessageHandler.validate_message_request({
                'session_id': session_id,
                'message': message
            })
            if not is_valid:
                return {'success': False, 'error': error}
            
            # Проверка API ключа
            has_key, error = MessageHandler.validate_api_key(user)
            if not has_key:
                return {'success': False, 'error': error}
            
            # Получение сессии
            chat_session = MessageHandler.get_chat_session(session_id, user)
            
            # Создание сообщения пользователя
            user_message = MessageHandler.create_user_message(chat_session, message)
            
            # Получение истории сообщений
            history = MessageHandler.get_message_history(chat_session)
            
            # Отправка к Gemini
            success, response, metadata = MessageHandler.send_to_gemini(
                message, history, user.gemini_api_key
            )
            
            if success:
                # Создание сообщения ассистента
                assistant_message = MessageHandler.create_assistant_message(
                    chat_session, response, metadata
                )
                
                # Обновление времени сессии
                MessageHandler.update_session_timestamp(chat_session)
                
                return {
                    'success': True,
                    'response': response,
                    'user_message_id': user_message.id,
                    'assistant_message_id': assistant_message.id,
                    'metadata': metadata
                }
            else:
                return {'success': False, 'error': response}
                
        except Exception as e:
            return {'success': False, 'error': f'Внутренняя ошибка сервера: {str(e)}'}


class MessageApiHandler:
    """Обработчик для API endpoints сообщений"""
    
    @staticmethod
    def send_message_api_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для отправки сообщения
        
        Args:
            data: Данные запроса
            request: HTTP запрос
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        session_id = data.get('session_id')
        message = data.get('message', '').strip()
        
        return MessageHandler.send_message_to_gemini(session_id, message, request.user)
    
    @staticmethod
    def send_message_viewset_handler(session: ChatSession, content: str, user) -> Dict[str, Any]:
        """
        Обработчик для ViewSet отправки сообщения
        
        Args:
            session: Сессия чата
            content: Содержимое сообщения
            user: Пользователь Django
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        return MessageHandler.send_message_to_gemini(session.id, content, user)
