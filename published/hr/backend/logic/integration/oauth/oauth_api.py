"""API для OAuth интеграций"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from apps.google_oauth.models import (
    GoogleOAuthAccount, SyncSettings, ScorecardPathSettings, 
    SlotsSettings, Invite, HRScreening, QuestionTemplate
)
from apps.google_oauth.serializers import (
    GoogleOAuthAccountSerializer, SyncSettingsSerializer,
    ScorecardPathSettingsSerializer, SlotsSettingsSerializer,
    InviteSerializer, HRScreeningSerializer, QuestionTemplateSerializer,
    GoogleOAuthCallbackSerializer, GoogleSyncRequestSerializer,
    GoogleCalendarEventSerializer, GoogleDriveFileSerializer,
    GoogleSheetSerializer, GoogleStatsSerializer
)
from logic.integration.oauth.oauth_services import (
    GoogleOAuthService, GoogleCalendarService, 
    GoogleDriveService, GoogleSheetsService
)

User = get_user_model()


class GoogleOAuthAccountViewSet(BaseAPIViewSet):
    """ViewSet для управления Google OAuth аккаунтами"""
    
    queryset = GoogleOAuthAccount.objects.all()
    serializer_class = GoogleOAuthAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание OAuth аккаунта с привязкой к пользователю"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def disconnect(self, request):
        """Отключить Google аккаунт"""
        try:
            oauth_account = get_object_or_404(
                GoogleOAuthAccount, user=request.user
            )
            oauth_service = GoogleOAuthService(request.user)
            success = oauth_service.revoke_access()
            
            if success:
                response_data = UnifiedResponseHandler.success_response(
                    {'status': 'disconnected'},
                    "Google аккаунт отключен"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка отключения Google аккаунта",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def test_connection(self, request):
        """Тестирование подключения к Google API"""
        try:
            oauth_service = GoogleOAuthService(request.user)
            success, message = oauth_service.test_connection()
            
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


class SyncSettingsViewSet(BaseAPIViewSet):
    """ViewSet для управления настройками синхронизации"""
    
    queryset = SyncSettings.objects.all()
    serializer_class = SyncSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание настроек с привязкой к пользователю"""
        serializer.save(user=self.request.user)


class ScorecardPathSettingsViewSet(BaseAPIViewSet):
    """ViewSet для управления настройками путей scorecard"""
    
    queryset = ScorecardPathSettings.objects.all()
    serializer_class = ScorecardPathSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание настроек с привязкой к пользователю"""
        serializer.save(user=self.request.user)


class SlotsSettingsViewSet(BaseAPIViewSet):
    """ViewSet для управления настройками слотов"""
    
    queryset = SlotsSettings.objects.all()
    serializer_class = SlotsSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание настроек с привязкой к пользователю"""
        serializer.save(user=self.request.user)


class InviteViewSet(BaseAPIViewSet):
    """ViewSet для управления приглашениями"""
    
    queryset = Invite.objects.all()
    serializer_class = InviteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание приглашения с привязкой к пользователю"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def sync_to_calendar(self, request, pk=None):
        """Синхронизация приглашения с календарем"""
        try:
            invite = self.get_object()
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            calendar_service = GoogleCalendarService(oauth_account)
            result = calendar_service.create_event_from_invite(invite)
            
            if result['success']:
                response_data = UnifiedResponseHandler.success_response(
                    result,
                    "Приглашение синхронизировано с календарем"
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


class HRScreeningViewSet(BaseAPIViewSet):
    """ViewSet для управления HR скринингами"""
    
    queryset = HRScreening.objects.all()
    serializer_class = HRScreeningSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание HR скрининга с привязкой к пользователю"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def analyze_with_gemini(self, request):
        """Анализ HR скрининга с помощью Gemini AI"""
        try:
            # Проверяем наличие API ключа Gemini
            if not request.user.gemini_api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ Gemini не настроен",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем текст для анализа
            text = request.data.get('text', '').strip()
            if not text:
                response_data = UnifiedResponseHandler.error_response(
                    "Текст для анализа не может быть пустым",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Используем Gemini для анализа
            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(request.user.gemini_api_key)
            
            prompt = f"""
            Проанализируй следующий текст HR скрининга и извлеки:
            - Информацию о кандидате
            - Оценки и комментарии
            - Рекомендации
            - Следующие шаги
            
            Текст: {text}
            
            Ответь в формате JSON.
            """
            
            result = gemini_service.generate_response(prompt)
            
            if result['success']:
                response_data = UnifiedResponseHandler.success_response(
                    {
                        'analysis': result['response'],
                        'raw_response': result.get('raw_response', {})
                    },
                    "Анализ HR скрининга завершен"
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


class QuestionTemplateViewSet(BaseAPIViewSet):
    """ViewSet для управления шаблонами вопросов"""
    
    queryset = QuestionTemplate.objects.all()
    serializer_class = QuestionTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Создание шаблона с привязкой к пользователю"""
        serializer.save(user=self.request.user)


class GoogleSyncViewSet(BaseAPIViewSet):
    """ViewSet для синхронизации данных с Google"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def sync_all(self, request):
        """Синхронизация всех данных с Google"""
        try:
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            results = {}
            
            # Синхронизация календаря
            calendar_service = GoogleCalendarService(oauth_account)
            results['calendar'] = calendar_service.sync_events()
            
            # Синхронизация Drive
            drive_service = GoogleDriveService(oauth_account)
            results['drive'] = drive_service.sync_files()
            
            # Синхронизация Sheets
            sheets_service = GoogleSheetsService(oauth_account)
            results['sheets'] = sheets_service.sync_sheets()
            
            response_data = UnifiedResponseHandler.success_response(
                results,
                "Синхронизация данных завершена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Получить статистику Google сервисов"""
        try:
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            calendar_service = GoogleCalendarService(oauth_account)
            drive_service = GoogleDriveService(oauth_account)
            sheets_service = GoogleSheetsService(oauth_account)
            
            stats = {
                'calendar_events': calendar_service.get_events_count(),
                'drive_files': drive_service.get_files_count(),
                'sheets': sheets_service.get_sheets_count(),
                'last_sync': oauth_account.last_sync_at,
                'connected_at': oauth_account.created_at,
                'scopes': oauth_account.scopes,
            }
            
            response_data = UnifiedResponseHandler.success_response(
                stats,
                "Статистика Google сервисов получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

