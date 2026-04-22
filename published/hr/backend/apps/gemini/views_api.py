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
    """

    @action(detail=False, methods=['get'])
    def my_sessions(self, request):
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
        try:
            from logic.ai_analysis.gemini_handlers import StatsApiHandler
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
        try:
            session = self.get_object()
            new_title = request.data.get('title', '').strip()

            if not new_title:
                response_data = UnifiedResponseHandler.error_response(
                    "Название не может быть пустым", 400
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
    ViewSet для работы с Gemini API - расширенная версия.
    Поддерживает выбор модели при тестировании и сохранении ключа.
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """
        Тестирование подключения к Gemini API с указанной моделью.

        Принимает:
          api_key  — ключ для проверки
          model    — (опционально) название модели, по умолчанию preferred_ai_model пользователя
        """
        try:
            api_key = request.data.get('api_key')

            if not api_key:
                response_data = UnifiedResponseHandler.error_response("API ключ не указан", 400)
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            model = (
                request.data.get('model')
                or getattr(request.user, 'preferred_ai_model', None)
                or 'gemini-2.0-flash'
            )

            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(api_key, model=model)
            result = gemini_service.test_connection()

            if result.success:
                response_data = UnifiedResponseHandler.success_response(
                    {'connection_status': 'connected', 'model': model},
                    result.data.get('message', 'Подключение успешно')
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    result.data.get('error', 'Ошибка подключения'), 400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def save_api_key(self, request):
        """
        Сохранение API ключа и предпочтительной модели пользователя.

        Принимает:
          api_key  — ключ Gemini
          model    — (опционально) модель для сохранения в preferred_ai_model
        """
        try:
            api_key = request.data.get('api_key')

            if not api_key:
                response_data = UnifiedResponseHandler.error_response("API ключ не указан", 400)
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            model = (
                request.data.get('model')
                or getattr(request.user, 'preferred_ai_model', None)
                or 'gemini-2.0-flash'
            )

            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(api_key, model=model)
            result = gemini_service.test_connection()

            if result.success:
                request.user.gemini_api_key = api_key
                request.user.preferred_ai_model = model
                request.user.save(update_fields=['gemini_api_key', 'preferred_ai_model'])

                response_data = UnifiedResponseHandler.success_response(
                    {'api_key_saved': True, 'model': model},
                    "API ключ успешно сохранен и протестирован"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    f"Ошибка тестирования API ключа: {result.data.get('error', '')}", 400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def available_models(self, request):
        """
        Возвращает список доступных AI-моделей и текущую модель пользователя.
        GET /api/v1/gemini/available_models/
        """
        try:
            from logic.ai_analysis.gemini_services import GeminiService
            response_data = UnifiedResponseHandler.success_response(
                {
                    'models': GeminiService.AVAILABLE_MODELS,
                    'current_model': getattr(request.user, 'preferred_ai_model', GeminiService.DEFAULT_MODEL),
                },
                "Список моделей получен"
            )
            return Response(response_data)
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
