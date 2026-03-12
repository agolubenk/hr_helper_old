"""API views для Google OAuth приложения - расширенные версии"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import (
    GoogleOAuthAccount, SyncSettings, ScorecardPathSettings, 
    SlotsSettings, Invite, HRScreening, QuestionTemplate
)
from .serializers import (
    GoogleOAuthAccountSerializer, SyncSettingsSerializer,
    ScorecardPathSettingsSerializer, SlotsSettingsSerializer,
    InviteSerializer, HRScreeningSerializer, QuestionTemplateSerializer,
    GoogleOAuthCallbackSerializer, GoogleSyncRequestSerializer,
    GoogleCalendarEventSerializer, GoogleDriveFileSerializer,
    GoogleSheetSerializer, GoogleStatsSerializer
)
from logic.integration.oauth.oauth_api import (
    GoogleOAuthAccountViewSet as LogicGoogleOAuthAccountViewSet,
    SyncSettingsViewSet as LogicSyncSettingsViewSet,
    ScorecardPathSettingsViewSet as LogicScorecardPathSettingsViewSet,
    SlotsSettingsViewSet as LogicSlotsSettingsViewSet,
    InviteViewSet as LogicInviteViewSet,
    HRScreeningViewSet as LogicHRScreeningViewSet,
    QuestionTemplateViewSet as LogicQuestionTemplateViewSet,
    GoogleSyncViewSet as LogicGoogleSyncViewSet
)
from logic.base.response_handler import UnifiedResponseHandler

User = get_user_model()


class GoogleOAuthAccountViewSet(LogicGoogleOAuthAccountViewSet):
    """ViewSet для управления Google OAuth аккаунтами - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def start_oauth(self, request):
        """Начать процесс OAuth авторизации"""
        try:
            from logic.integration.oauth.oauth_services import GoogleOAuthService
            oauth_service = GoogleOAuthService(request.user)
            auth_url, _ = oauth_service.get_authorization_url()
            
            if auth_url:
                response_data = UnifiedResponseHandler.success_response(
                    {'auth_url': auth_url},
                    "URL авторизации получен"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка получения URL авторизации",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncSettingsViewSet(LogicSyncSettingsViewSet):
    """ViewSet для управления настройками синхронизации - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]


class ScorecardPathSettingsViewSet(LogicScorecardPathSettingsViewSet):
    """ViewSet для управления настройками путей scorecard - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]


class SlotsSettingsViewSet(LogicSlotsSettingsViewSet):
    """ViewSet для управления настройками слотов - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]


class InviteViewSet(LogicInviteViewSet):
    """ViewSet для управления приглашениями - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'interview_type']
    search_fields = ['candidate_name', 'candidate_email', 'interviewer_name']
    ordering_fields = ['interview_date', 'created_at']
    ordering = ['-interview_date']


class HRScreeningViewSet(LogicHRScreeningViewSet):
    """ViewSet для управления HR скринингами - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'score']
    search_fields = ['candidate_name', 'candidate_email', 'interviewer_name']
    ordering_fields = ['interview_date', 'created_at']
    ordering = ['-interview_date']


class QuestionTemplateViewSet(LogicQuestionTemplateViewSet):
    """ViewSet для управления шаблонами вопросов - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['category']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class GoogleSyncViewSet(LogicGoogleSyncViewSet):
    """ViewSet для синхронизации данных с Google - расширенная версия"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def sync_calendar(self, request):
        """Синхронизация только календаря"""
        try:
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            from logic.integration.oauth.oauth_services import GoogleCalendarService
            calendar_service = GoogleCalendarService(oauth_account)
            result = calendar_service.sync_events()
            
            response_data = UnifiedResponseHandler.success_response(
                result,
                "Синхронизация календаря завершена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def sync_drive(self, request):
        """Синхронизация только Drive"""
        try:
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            from logic.integration.oauth.oauth_services import GoogleDriveService
            drive_service = GoogleDriveService(oauth_account)
            result = drive_service.sync_files()
            
            response_data = UnifiedResponseHandler.success_response(
                result,
                "Синхронизация Drive завершена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def sync_sheets(self, request):
        """Синхронизация только Sheets"""
        try:
            oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
            
            from logic.integration.oauth.oauth_services import GoogleSheetsService
            sheets_service = GoogleSheetsService(oauth_account)
            result = sheets_service.sync_sheets()
            
            response_data = UnifiedResponseHandler.success_response(
                result,
                "Синхронизация Sheets завершена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)