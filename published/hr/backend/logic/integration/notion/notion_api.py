"""API для работы с Notion"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from logic.utilities.context_helpers import PermissionHelper
from apps.notion_int.models import NotionSettings, NotionPage, NotionSyncLog, NotionBulkImport
from apps.notion_int.serializers import (
    NotionSettingsSerializer, NotionPageSerializer, NotionSyncLogSerializer,
    NotionBulkImportSerializer, NotionStatsSerializer
)


class NotionSettingsViewSet(BaseAPIViewSet):
    """ViewSet для управления настройками Notion"""
    queryset = NotionSettings.objects.all()
    serializer_class = NotionSettingsSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    def create(self, request, *args, **kwargs):
        """Создание настроек Notion"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Привязываем к текущему пользователю
                serializer.save(user=request.user)
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data, 
                    "Настройки Notion успешно созданы"
                )
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка валидации данных", 
                    400
                )
                response_data['errors'] = serializer.errors
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection(self, request):
        """Тестирование подключения к Notion API"""
        try:
            from apps.notion_int.services import NotionService
            
            user = request.user
            integration_token = request.data.get('integration_token') or user.notion_integration_token
            
            if not integration_token:
                response_data = UnifiedResponseHandler.error_response(
                    "Integration токен Notion не указан",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            notion_service = NotionService(integration_token)
            connection_result = notion_service.test_connection()
            
            if connection_result:
                response_data = UnifiedResponseHandler.success_response(
                    {'connection_status': 'connected'},
                    "Подключение к Notion API успешно"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось подключиться к Notion API",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotionPageViewSet(BaseAPIViewSet):
    """ViewSet для управления страницами Notion"""
    queryset = NotionPage.objects.all()
    serializer_class = NotionPageSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    @action(detail=False, methods=['post'], url_path='sync')
    def sync_pages(self, request):
        """Синхронизация страниц с Notion"""
        try:
            from apps.notion_int.services import NotionService
            
            user = request.user
            
            if not user.notion_integration_token:
                response_data = UnifiedResponseHandler.error_response(
                    "Integration токен Notion не настроен",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем настройки пользователя
            try:
                settings = NotionSettings.objects.get(user=user)
            except NotionSettings.DoesNotExist:
                response_data = UnifiedResponseHandler.error_response(
                    "Настройки Notion не найдены",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            notion_service = NotionService(user.notion_integration_token)
            sync_result = notion_service.sync_pages(settings.database_id, user)
            
            if sync_result:
                response_data = UnifiedResponseHandler.success_response(
                    {'sync_status': 'completed'},
                    "Синхронизация страниц завершена успешно"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка при синхронизации страниц",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по страницам Notion"""
        try:
            queryset = self.get_queryset()
            
            # Основная статистика
            total_pages = queryset.count()
            
            # Статистика по статусам
            from django.db.models import Count
            by_status = dict(
                queryset.values('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            )
            
            # Последние страницы
            recent_pages = queryset.order_by('-last_edited_time')[:10]
            recent_serializer = NotionPageSerializer(recent_pages, many=True)
            
            stats_data = {
                'total_pages': total_pages,
                'by_status': by_status,
                'recent_pages': recent_serializer.data
            }
            
            response_data = UnifiedResponseHandler.success_response(
                stats_data,
                "Статистика страниц получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotionSyncLogViewSet(BaseAPIViewSet):
    """ViewSet для просмотра логов синхронизации Notion"""
    queryset = NotionSyncLog.objects.all()
    serializer_class = NotionSyncLogSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по логам синхронизации"""
        try:
            queryset = self.get_queryset()
            
            # Основная статистика
            total_logs = queryset.count()
            
            # Статистика по статусам
            from django.db.models import Count
            by_status = dict(
                queryset.values('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            )
            
            # Последние логи
            recent_logs = queryset.order_by('-created_at')[:10]
            recent_serializer = NotionSyncLogSerializer(recent_logs, many=True)
            
            stats_data = {
                'total_logs': total_logs,
                'by_status': by_status,
                'recent_logs': recent_serializer.data
            }
            
            response_data = UnifiedResponseHandler.success_response(
                stats_data,
                "Статистика логов получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotionBulkImportViewSet(BaseAPIViewSet):
    """ViewSet для управления массовым импортом Notion"""
    queryset = NotionBulkImport.objects.all()
    serializer_class = NotionBulkImportSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    def create(self, request, *args, **kwargs):
        """Запуск массового импорта"""
        try:
            user = request.user
            
            if not user.notion_integration_token:
                response_data = UnifiedResponseHandler.error_response(
                    "Integration токен Notion не настроен",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Создаем запись о массовом импорте
            bulk_import_obj = NotionBulkImport.objects.create(
                user=user,
                status='PENDING',
                total_pages=0
            )
            
            # Здесь должна быть логика запуска Celery задачи
            # bulk_import_notion_pages.delay(bulk_import_obj.id)
            
            serializer = self.get_serializer(bulk_import_obj)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Массовый импорт запущен"
            )
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='status')
    def import_status(self, request, pk=None):
        """Получение статуса массового импорта"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Статус импорта получен"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

