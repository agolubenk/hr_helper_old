"""API views для Gemini приложения - расширенные версии"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import ChatSession, ChatMessage
from .serializers import (
    ChatSessionSerializer, ChatSessionDetailSerializer, 
    ChatSessionCreateSerializer, ChatMessageSerializer,
    ChatMessageCreateSerializer, GeminiApiRequestSerializer,
    GeminiStatsSerializer
)
from logic.ai_analysis.gemini_api import (
    ChatSessionViewSet as LogicChatSessionViewSet, 
    ChatMessageViewSet as LogicChatMessageViewSet, 
    GeminiApiViewSet as LogicGeminiApiViewSet
)
from logic.base.response_handler import UnifiedResponseHandler

User = get_user_model()


class ChatSessionViewSet(LogicChatSessionViewSet):
    """
    ViewSet для управления сессиями чата с Gemini - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - ChatSession.objects: все сессии чатов
    - ChatSessionSerializer, ChatSessionDetailSerializer, ChatSessionCreateSerializer
    
    ОБРАБОТКА:
    - Наследование от LogicChatSessionViewSet
    - Расширенные методы для работы с сессиями чатов
    - Управление активными сессиями пользователя
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными сессий чатов
    - JSON ответы через UnifiedResponseHandler
    
    СВЯЗИ:
    - Использует: LogicChatSessionViewSet, ChatSessionSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    
    @action(detail=False, methods=['get'])
    def my_sessions(self, request):
        """
        Получить сессии текущего пользователя
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.user: текущий пользователь
        - ChatSession.objects: активные сессии пользователя
        
        ОБРАБОТКА:
        - Проверка аутентификации пользователя
        - Получение активных сессий пользователя
        - Сортировка по дате создания
        - Сериализация данных
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с данными сессий пользователя
        
        СВЯЗИ:
        - Использует: ChatSessionSerializer, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            if not request.user.is_authenticated:
                response_data = UnifiedResponseHandler.error_response("Пользователь не аутентифицирован")
                return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
            
            sessions = ChatSession.objects.filter(user=request.user, is_active=True).order_by('-created_at')
            serializer = ChatSessionSerializer(sessions, many=True)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Сессии получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """
        Получить статистику для дашборда
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.user: текущий пользователь
        - ChatSession.objects: сессии пользователя
        - ChatMessage.objects: сообщения пользователя
        
        ОБРАБОТКА:
        - Проверка аутентификации пользователя
        - Получение статистики по сессиям и сообщениям
        - Подсчет активных сессий, общего количества сообщений
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response со статистикой дашборда
        
        СВЯЗИ:
        - Использует: ChatSession.objects, ChatMessage.objects, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            from logic.ai_analysis.gemini_handlers import StatsApiHandler
            
            # Используем общий обработчик для получения данных дашборда
            dashboard_data = StatsApiHandler.get_dashboard_handler({}, request)
            
            if 'error' in dashboard_data:
                response_data = UnifiedResponseHandler.error_response(dashboard_data['error'])
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            response_data = UnifiedResponseHandler.success_response(
                dashboard_data,
                "Данные дашборда получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_title(self, request, pk=None):
        """
        Обновить название сессии
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - pk: ID сессии для обновления заголовка
        - request.data: данные с новым заголовком
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - URL параметр pk
        - request.data: данные с новым заголовком
        - ChatSession.objects: конкретная сессия
        
        ОБРАБОТКА:
        - Получение сессии по ID
        - Проверка прав доступа
        - Обновление заголовка сессии
        - Сохранение изменений
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с результатом операции
        
        СВЯЗИ:
        - Использует: ChatSession.objects.get(), ChatSession.save(), UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            session = self.get_object()
            new_title = request.data.get('title', '').strip()
            
            if not new_title:
                response_data = UnifiedResponseHandler.error_response(
                    "Название не может быть пустым",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            session.title = new_title
            session.save()
            
            response_data = UnifiedResponseHandler.success_response(
                {'title': new_title},
                "Название сессии обновлено"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatMessageViewSet(LogicChatMessageViewSet):
    """ViewSet для просмотра сообщений чата - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['role', 'session']
    search_fields = ['content']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


class GeminiApiViewSet(LogicGeminiApiViewSet):
    """
    ViewSet для работы с Gemini API - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Gemini API: для работы с AI
    - request.data: данные для API запросов
    
    ОБРАБОТКА:
    - Наследование от LogicGeminiApiViewSet
    - Расширенные методы для работы с Gemini API
    - Управление API ключами пользователей
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с результатами API запросов
    - JSON ответы через UnifiedResponseHandler
    
    СВЯЗИ:
    - Использует: LogicGeminiApiViewSet, Gemini API, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """
        Тестирование подключения к Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.data: данные с API ключом для тестирования
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.data: API ключ для тестирования
        - Gemini API: для проверки подключения
        
        ОБРАБОТКА:
        - Получение API ключа из данных запроса
        - Тестирование подключения к Gemini API
        - Проверка валидности ключа
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с результатом тестирования
        
        СВЯЗИ:
        - Использует: Gemini API, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            api_key = request.data.get('api_key')
            
            if not api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ не указан",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(api_key)
            success, message = gemini_service.test_connection()
            
            if success:
                response_data = UnifiedResponseHandler.success_response(
                    {'connection_status': 'connected'},
                    message
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    message,
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def save_api_key(self, request):
        """
        Сохранение API ключа пользователя
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.data: данные с API ключом для сохранения
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.data: API ключ для сохранения
        - request.user: пользователь для сохранения ключа
        
        ОБРАБОТКА:
        - Получение API ключа из данных запроса
        - Валидация ключа
        - Сохранение ключа в профиле пользователя
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с результатом операции
        
        СВЯЗИ:
        - Использует: request.user.gemini_api_key, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            api_key = request.data.get('api_key')
            
            if not api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ не указан",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Тестируем API ключ перед сохранением
            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(api_key)
            success, message = gemini_service.test_connection()
            
            if success:
                # Сохраняем API ключ
                request.user.gemini_api_key = api_key
                request.user.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    {'api_key_saved': True},
                    "API ключ успешно сохранен и протестирован"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    f"Ошибка тестирования API ключа: {message}",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)