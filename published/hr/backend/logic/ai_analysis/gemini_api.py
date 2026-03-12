"""API для работы с Gemini AI"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from apps.gemini.models import ChatSession, ChatMessage
from apps.gemini.serializers import (
    ChatSessionSerializer, ChatSessionDetailSerializer, 
    ChatSessionCreateSerializer, ChatMessageSerializer,
    ChatMessageCreateSerializer, GeminiApiRequestSerializer,
    GeminiStatsSerializer
)
from logic.ai_analysis.gemini_services import GeminiService
from logic.ai_analysis.gemini_handlers import MessageApiHandler, StatsApiHandler


class ChatSessionViewSet(BaseAPIViewSet):
    """
    ViewSet для управления сессиями чата с Gemini
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы от аутентифицированных пользователей
    ИСТОЧНИКИ ДАННЫХ: База данных (модели ChatSession, ChatMessage), Gemini API
    ОБРАБОТКА: CRUD операции с сессиями чата, отправка сообщений, управление историей
    ВЫХОДЯЩИЕ ДАННЫЕ: JSON ответы с данными сессий и сообщений
    СВЯЗИ: apps.gemini.models, apps.gemini.serializers, logic.ai_analysis.gemini_services
    ФОРМАТ: REST API endpoints с JSON сериализацией
    """
    
    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Фильтрация queryset по пользователю
        
        ВХОДЯЩИЕ ДАННЫЕ: self.request с аутентифицированным пользователем
        ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatSession)
        ОБРАБОТКА: Фильтрация сессий чата по текущему пользователю
        ВЫХОДЯЩИЕ ДАННЫЕ: QuerySet с отфильтрованными сессиями или пустой QuerySet
        СВЯЗИ: apps.gemini.models.ChatSession
        ФОРМАТ: Django QuerySet
        """
        queryset = super().get_queryset()
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            return queryset.filter(user=self.request.user)
        return queryset.none()
    
    def get_serializer_class(self):
        """
        Выбор сериализатора в зависимости от действия
        
        ВХОДЯЩИЕ ДАННЫЕ: self.action (тип действия ViewSet)
        ИСТОЧНИКИ ДАННЫХ: apps.gemini.serializers
        ОБРАБОТКА: Выбор подходящего сериализатора на основе типа действия
        ВЫХОДЯЩИЕ ДАННЫЕ: Класс сериализатора
        СВЯЗИ: apps.gemini.serializers (ChatSessionDetailSerializer, ChatSessionCreateSerializer)
        ФОРМАТ: Python класс
        """
        if self.action == 'retrieve':
            return ChatSessionDetailSerializer
        elif self.action == 'create':
            return ChatSessionCreateSerializer
        return ChatSessionSerializer
    
    def perform_create(self, serializer):
        """
        Создание сессии с привязкой к пользователю
        
        ВХОДЯЩИЕ ДАННЫЕ: serializer с данными для создания сессии
        ИСТОЧНИКИ ДАННЫХ: self.request.user (текущий пользователь)
        ОБРАБОТКА: Сохранение сессии с привязкой к текущему пользователю
        ВЫХОДЯЩИЕ ДАННЫЕ: Созданная сессия чата
        СВЯЗИ: apps.gemini.models.ChatSession
        ФОРМАТ: Django модель
        """
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """
        Отправить сообщение в сессию чата
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP POST запрос с данными сообщения
        ИСТОЧНИКИ ДАННЫХ: request.data (содержимое сообщения), pk (ID сессии)
        ОБРАБОТКА: Создание сообщения пользователя и получение ответа от Gemini AI
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с сообщениями пользователя и ассистента
        СВЯЗИ: logic.ai_analysis.gemini_handlers.MessageApiHandler, apps.gemini.models.ChatMessage
        ФОРМАТ: JSON ответ с данными сообщений
        """
        session = self.get_object()
        serializer = ChatMessageCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Используем общий обработчик для отправки сообщения
                result = MessageApiHandler.send_message_viewset_handler(
                    session, 
                    serializer.validated_data['content'], 
                    request.user
                )
                
                if result['success']:
                    # Получаем созданные сообщения для сериализации
                    user_message = ChatMessage.objects.get(id=result['user_message_id'])
                    assistant_message = ChatMessage.objects.get(id=result['assistant_message_id'])
                    
                    response_data = UnifiedResponseHandler.success_response(
                        {
                            'user_message': ChatMessageSerializer(user_message).data,
                            'assistant_message': ChatMessageSerializer(assistant_message).data
                        },
                        "Сообщение отправлено успешно"
                    )
                    return Response(response_data)
                else:
                    response_data = UnifiedResponseHandler.error_response(
                        result['error'],
                        400
                    )
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                response_data = UnifiedResponseHandler.error_response(str(e))
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        
        response_data = UnifiedResponseHandler.error_response(
            "Ошибка валидации данных",
            400
        )
        response_data['errors'] = serializer.errors
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """
        Получить все сообщения сессии
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP GET запрос с pk сессии
        ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatMessage через сессию)
        ОБРАБОТКА: Получение всех сообщений сессии, отсортированных по времени
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с массивом сообщений
        СВЯЗИ: apps.gemini.models.ChatMessage, apps.gemini.serializers.ChatMessageSerializer
        ФОРМАТ: JSON ответ с данными сообщений
        """
        try:
            session = self.get_object()
            messages = session.messages.all().order_by('timestamp')
            serializer = ChatMessageSerializer(messages, many=True)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Сообщения получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def clear_history(self, request, pk=None):
        """
        Очистить историю сообщений сессии
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP POST запрос с pk сессии
        ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatMessage через сессию)
        ОБРАБОТКА: Удаление всех сообщений сессии
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с подтверждением очистки
        СВЯЗИ: apps.gemini.models.ChatMessage
        ФОРМАТ: JSON ответ с статусом операции
        """
        try:
            session = self.get_object()
            session.messages.all().delete()
            
            response_data = UnifiedResponseHandler.success_response(
                {'status': 'history_cleared'},
                "История сообщений очищена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # @action(detail=False, methods=['get'])
    # def my_sessions(self, request):
    #     """Получить сессии текущего пользователя"""
    #     if not request.user.is_authenticated:
    #         return Response(
    #             UnifiedResponseHandler.error_response("Пользователь не аутентифицирован"),
    #             status=status.HTTP_401_UNAUTHORIZED
    #         )
    #     
    #     sessions = ChatSession.objects.filter(user=request.user, is_active=True).order_by('-created_at')
    #     serializer = ChatSessionSerializer(sessions, many=True)
    #     
    #     return Response(
    #         UnifiedResponseHandler.success_response(serializer.data, "Сессии получены")
    #     )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Получить статистику чатов
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP GET запрос от аутентифицированного пользователя
        ИСТОЧНИКИ ДАННЫХ: База данных (модели ChatSession, ChatMessage)
        ОБРАБОТКА: Получение статистики по чатам пользователя
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON со статистикой чатов
        СВЯЗИ: logic.ai_analysis.gemini_handlers.StatsApiHandler
        ФОРМАТ: JSON ответ со статистическими данными
        """
        try:
            # Используем общий обработчик для получения статистики
            stats = StatsApiHandler.get_stats_handler({}, request)
            
            if 'error' in stats:
                response_data = UnifiedResponseHandler.error_response(stats['error'])
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            response_data = UnifiedResponseHandler.success_response(
                stats,
                "Статистика получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatMessageViewSet(BaseAPIViewSet):
    """
    ViewSet для просмотра сообщений чата
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы от аутентифицированных пользователей
    ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatMessage)
    ОБРАБОТКА: Просмотр сообщений чата пользователя
    ВЫХОДЯЩИЕ ДАННЫЕ: JSON ответы с данными сообщений
    СВЯЗИ: apps.gemini.models.ChatMessage, apps.gemini.serializers.ChatMessageSerializer
    ФОРМАТ: REST API endpoints с JSON сериализацией
    """
    
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer
    
    def get_queryset(self):
        """
        Фильтрация queryset по пользователю
        
        ВХОДЯЩИЕ ДАННЫЕ: self.request с аутентифицированным пользователем
        ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatMessage)
        ОБРАБОТКА: Фильтрация сообщений по сессиям текущего пользователя
        ВЫХОДЯЩИЕ ДАННЫЕ: QuerySet с отфильтрованными сообщениями или пустой QuerySet
        СВЯЗИ: apps.gemini.models.ChatMessage
        ФОРМАТ: Django QuerySet
        """
        queryset = super().get_queryset()
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            return queryset.filter(session__user=self.request.user)
        return queryset.none()
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Получить последние сообщения
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP GET запрос от аутентифицированного пользователя
        ИСТОЧНИКИ ДАННЫХ: База данных (модель ChatMessage через get_queryset)
        ОБРАБОТКА: Получение 20 последних сообщений пользователя
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с массивом последних сообщений
        СВЯЗИ: apps.gemini.serializers.ChatMessageSerializer
        ФОРМАТ: JSON ответ с данными сообщений
        """
        try:
            messages = self.get_queryset().order_by('-timestamp')[:20]
            serializer = self.get_serializer(messages, many=True)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Последние сообщения получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GeminiApiViewSet(BaseAPIViewSet):
    """
    ViewSet для работы с Gemini API
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы от аутентифицированных пользователей
    ИСТОЧНИКИ ДАННЫХ: Gemini API, пользовательские API ключи
    ОБРАБОТКА: Анализ текста, генерация ответов, получение статистики
    ВЫХОДЯЩИЕ ДАННЫЕ: JSON ответы с результатами анализа и генерации
    СВЯЗИ: logic.ai_analysis.gemini_services.GeminiService, logic.ai_analysis.gemini_handlers.StatsApiHandler
    ФОРМАТ: REST API endpoints с JSON сериализацией
    """
    
    @action(detail=False, methods=['post'])
    def analyze_text(self, request):
        """
        Анализ текста с помощью Gemini
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP POST запрос с текстом для анализа
        ИСТОЧНИКИ ДАННЫХ: request.data (текст, тип анализа, max_tokens), request.user.gemini_api_key
        ОБРАБОТКА: Отправка текста в Gemini API для анализа
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с результатами анализа
        СВЯЗИ: logic.ai_analysis.gemini_services.GeminiService, apps.gemini.serializers.GeminiApiRequestSerializer
        ФОРМАТ: JSON ответ с результатами анализа
        """
        serializer = GeminiApiRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Проверяем API ключ пользователя
                if not request.user.gemini_api_key:
                    response_data = UnifiedResponseHandler.error_response(
                        "API ключ Gemini не настроен",
                        400
                    )
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
                gemini_service = GeminiService(request.user.gemini_api_key)
                result = gemini_service.analyze_text(
                    serializer.validated_data['text'],
                    serializer.validated_data.get('analysis_type', 'general'),
                    serializer.validated_data.get('max_tokens', 1000)
                )
                
                if result['success']:
                    response_data = UnifiedResponseHandler.success_response(
                        result,
                        "Анализ текста завершен"
                    )
                    return Response(response_data)
                else:
                    response_data = UnifiedResponseHandler.error_response(
                        result['error'],
                        400
                    )
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                response_data = UnifiedResponseHandler.error_response(str(e))
                return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response_data = UnifiedResponseHandler.error_response(
            "Ошибка валидации данных",
            400
        )
        response_data['errors'] = serializer.errors
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def generate_response(self, request):
        """
        Генерация ответа с помощью Gemini
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP POST запрос с текстом и контекстом для генерации
        ИСТОЧНИКИ ДАННЫХ: request.data (текст, контекст, max_tokens), request.user.gemini_api_key
        ОБРАБОТКА: Отправка запроса в Gemini API для генерации ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON с сгенерированным ответом
        СВЯЗИ: logic.ai_analysis.gemini_services.GeminiService, apps.gemini.serializers.GeminiApiRequestSerializer
        ФОРМАТ: JSON ответ с сгенерированным текстом
        """
        serializer = GeminiApiRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Проверяем API ключ пользователя
                if not request.user.gemini_api_key:
                    response_data = UnifiedResponseHandler.error_response(
                        "API ключ Gemini не настроен",
                        400
                    )
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
                gemini_service = GeminiService(request.user.gemini_api_key)
                result = gemini_service.generate_response(
                    serializer.validated_data['text'],
                    serializer.validated_data.get('context', ''),
                    serializer.validated_data.get('max_tokens', 1000)
                )
                
                if result['success']:
                    response_data = UnifiedResponseHandler.success_response(
                        result,
                        "Ответ сгенерирован"
                    )
                    return Response(response_data)
                else:
                    response_data = UnifiedResponseHandler.error_response(
                        result['error'],
                        400
                    )
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                response_data = UnifiedResponseHandler.error_response(str(e))
                return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response_data = UnifiedResponseHandler.error_response(
            "Ошибка валидации данных",
            400
        )
        response_data['errors'] = serializer.errors
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Получить статистику использования Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ: HTTP GET запрос от аутентифицированного пользователя
        ИСТОЧНИКИ ДАННЫХ: База данных (модели ChatSession, ChatMessage, GeminiApiRequest)
        ОБРАБОТКА: Получение статистики использования Gemini API
        ВЫХОДЯЩИЕ ДАННЫЕ: JSON со статистикой API
        СВЯЗИ: logic.ai_analysis.gemini_handlers.StatsApiHandler
        ФОРМАТ: JSON ответ со статистическими данными
        """
        try:
            # Используем общий обработчик для получения статистики
            stats = StatsApiHandler.get_stats_handler({}, request)
            
            if 'error' in stats:
                response_data = UnifiedResponseHandler.error_response(stats['error'])
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            response_data = UnifiedResponseHandler.success_response(
                stats,
                "Статистика API получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
