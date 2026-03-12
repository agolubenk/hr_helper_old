"""API для работы с ClickUp"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from logic.utilities.context_helpers import PermissionHelper
from apps.clickup_int.models import ClickUpSettings, ClickUpTask, ClickUpSyncLog, ClickUpBulkImport
from apps.clickup_int.serializers import (
    ClickUpSettingsSerializer, ClickUpTaskSerializer, ClickUpSyncLogSerializer,
    ClickUpBulkImportSerializer, ClickUpStatsSerializer
)


class ClickUpSettingsViewSet(BaseAPIViewSet):
    """
    ViewSet для управления настройками ClickUp
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы (GET, POST, PUT, DELETE, PATCH), request.user
    ИСТОЧНИКИ ДАННЫЕ: ClickUpSettings, ClickUpSettingsSerializer
    ОБРАБОТКА: Управление настройками ClickUp интеграции
    ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с данными настроек
    СВЯЗИ: BaseAPIViewSet, UnifiedResponseHandler
    ФОРМАТ: DRF API responses
    """
    queryset = ClickUpSettings.objects.all()
    serializer_class = ClickUpSettingsSerializer
    
    def get_queryset(self):
        """
        Фильтрация queryset по пользователю
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: ClickUpSettings queryset, request.user
        ОБРАБОТКА: Фильтрация настроек по текущему пользователю
        ВЫХОДЯЩИЕ ДАННЫЕ: Отфильтрованный queryset
        СВЯЗИ: PermissionHelper
        ФОРМАТ: QuerySet
        """
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    def create(self, request, *args, **kwargs):
        """
        Создание настроек ClickUp
        
        ВХОДЯЩИЕ ДАННЫЕ: request.data, request.user
        ИСТОЧНИКИ ДАННЫЕ: POST данные формы настроек
        ОБРАБОТКА: Валидация и создание настроек ClickUp
        ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с созданными настройками
        СВЯЗИ: ClickUpSettingsSerializer, UnifiedResponseHandler
        ФОРМАТ: DRF Response
        """
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Привязываем к текущему пользователю
                serializer.save(user=request.user)
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data, 
                    "Настройки ClickUp успешно созданы"
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
        """Тестирование подключения к ClickUp API"""
        try:
            from apps.clickup_int.services import ClickUpService
            
            user = request.user
            api_key = request.data.get('api_key') or user.clickup_api_key
            
            if not api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ ClickUp не указан",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            clickup_service = ClickUpService(api_key)
            connection_result = clickup_service.test_connection()
            
            if connection_result:
                response_data = UnifiedResponseHandler.success_response(
                    {'connection_status': 'connected'},
                    "Подключение к ClickUp API успешно"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось подключиться к ClickUp API",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClickUpTaskViewSet(BaseAPIViewSet):
    """ViewSet для управления задачами ClickUp"""
    queryset = ClickUpTask.objects.all()
    serializer_class = ClickUpTaskSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    @action(detail=False, methods=['post'], url_path='sync')
    def sync_tasks(self, request):
        """Синхронизация задач с ClickUp"""
        try:
            from apps.clickup_int.services import ClickUpService
            
            user = request.user
            
            if not user.clickup_api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ ClickUp не настроен",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем настройки пользователя
            try:
                settings = ClickUpSettings.objects.get(user=user)
            except ClickUpSettings.DoesNotExist:
                response_data = UnifiedResponseHandler.error_response(
                    "Настройки ClickUp не найдены",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            clickup_service = ClickUpService(user.clickup_api_key)
            sync_result = clickup_service.sync_tasks(
                settings.team_id, 
                settings.space_id, 
                settings.list_id, 
                user
            )
            
            if sync_result:
                response_data = UnifiedResponseHandler.success_response(
                    {'sync_status': 'completed'},
                    "Синхронизация задач завершена успешно"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка при синхронизации задач",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по задачам ClickUp"""
        try:
            queryset = self.get_queryset()
            
            # Основная статистика
            total_tasks = queryset.count()
            
            # Статистика по статусам
            from django.db.models import Count
            by_status = dict(
                queryset.values('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            )
            
            # Статистика по приоритетам
            by_priority = dict(
                queryset.values('priority')
                .annotate(count=Count('id'))
                .values_list('priority', 'count')
            )
            
            # Последние задачи
            recent_tasks = queryset.order_by('-date_updated')[:10]
            recent_serializer = ClickUpTaskSerializer(recent_tasks, many=True)
            
            stats_data = {
                'total_tasks': total_tasks,
                'by_status': by_status,
                'by_priority': by_priority,
                'recent_tasks': recent_serializer.data
            }
            
            response_data = UnifiedResponseHandler.success_response(
                stats_data,
                "Статистика задач получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClickUpSyncLogViewSet(BaseAPIViewSet):
    """ViewSet для просмотра логов синхронизации ClickUp"""
    queryset = ClickUpSyncLog.objects.all()
    serializer_class = ClickUpSyncLogSerializer
    
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
            recent_serializer = ClickUpSyncLogSerializer(recent_logs, many=True)
            
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


class ClickUpBulkImportViewSet(BaseAPIViewSet):
    """ViewSet для управления массовым импортом ClickUp"""
    queryset = ClickUpBulkImport.objects.all()
    serializer_class = ClickUpBulkImportSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        return PermissionHelper.get_user_accessible_objects(queryset, self.request.user, 'user')
    
    def create(self, request, *args, **kwargs):
        """Запуск массового импорта"""
        try:
            user = request.user
            
            if not user.clickup_api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "API ключ ClickUp не настроен",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Создаем запись о массовом импорте
            bulk_import_obj = ClickUpBulkImport.objects.create(
                user=user,
                status='PENDING',
                total_tasks=0
            )
            
            # Здесь должна быть логика запуска Celery задачи
            # bulk_import_clickup_tasks.delay(bulk_import_obj.id)
            
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
