"""API для работы с Huntflow"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from logic.utilities.context_helpers import PermissionHelper
from apps.huntflow.models import HuntflowCache, HuntflowLog
from apps.huntflow.serializers import (
    HuntflowCacheSerializer, HuntflowLogSerializer, HuntflowLogCreateSerializer,
    HuntflowStatsSerializer, HuntflowApiRequestSerializer
)


class HuntflowCacheViewSet(BaseAPIViewSet):
    """
    ViewSet для просмотра кэша Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    ИСТОЧНИКИ ДАННЫЕ: HuntflowCache, HuntflowCacheSerializer
    ОБРАБОТКА: Управление кэшем Huntflow
    ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с данными кэша
    СВЯЗИ: BaseAPIViewSet, UnifiedResponseHandler
    ФОРМАТ: DRF API responses
    """
    queryset = HuntflowCache.objects.all()
    serializer_class = HuntflowCacheSerializer
    
    def get_queryset(self):
        """Фильтрация queryset"""
        queryset = super().get_queryset()
        # Для кэша нет специфических прав доступа
        return queryset
    
    @action(detail=False, methods=['post'], url_path='clear-cache')
    def clear_cache(self, request):
        """
        Очистка кэша
        
        ВХОДЯЩИЕ ДАННЫЕ: request
        ИСТОЧНИКИ ДАННЫЕ: HuntflowCache
        ОБРАБОТКА: Очистка всего кэша Huntflow
        ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с результатом очистки
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: DRF Response
        """
        try:
            deleted_count = HuntflowCache.objects.all().count()
            HuntflowCache.objects.all().delete()
            
            response_data = UnifiedResponseHandler.success_response(
                {'deleted_count': deleted_count},
                "Кэш успешно очищен"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='expired')
    def expired(self, request):
        """Получение истекших записей кэша"""
        try:
            from django.utils import timezone
            expired_cache = self.get_queryset().filter(
                expires_at__isnull=False,
                expires_at__lt=timezone.now()
            )
            
            serializer = HuntflowCacheSerializer(expired_cache, many=True)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Найдено {len(serializer.data)} истекших записей кэша"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HuntflowLogViewSet(BaseAPIViewSet):
    """
    ViewSet для просмотра логов Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    ИСТОЧНИКИ ДАННЫЕ: HuntflowLog, HuntflowLogSerializer
    ОБРАБОТКА: Управление логами Huntflow
    ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с данными логов
    СВЯЗИ: BaseAPIViewSet, UnifiedResponseHandler
    ФОРМАТ: DRF API responses
    """
    queryset = HuntflowLog.objects.all()
    serializer_class = HuntflowLogSerializer
    
    def get_queryset(self):
        """Фильтрация queryset"""
        queryset = super().get_queryset()
        # Для логов нет специфических прав доступа
        return queryset
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """
        Статистика по логам
        
        ВХОДЯЩИЕ ДАННЫЕ: request
        ИСТОЧНИКИ ДАННЫЕ: HuntflowLog
        ОБРАБОТКА: Подсчет статистики по логам Huntflow
        ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response со статистикой логов
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: DRF Response
        """
        try:
            queryset = self.get_queryset()
            
            # Основная статистика
            total_logs = queryset.count()
            
            # Статистика по типам операций
            from django.db.models import Count
            by_log_type = dict(
                queryset.values('log_type')
                .annotate(count=Count('id'))
                .values_list('log_type', 'count')
            )
            
            # Статистика по статус кодам
            by_status_code = dict(
                queryset.values('status_code')
                .annotate(count=Count('id'))
                .values_list('status_code', 'count')
            )
            
            # Статистика по пользователям
            by_user = dict(
                queryset.values('user__username')
                .annotate(count=Count('id'))
                .values_list('user__username', 'count')
            )
            
            # Последние логи
            recent_logs = queryset.order_by('-created_at')[:10]
            recent_serializer = HuntflowLogSerializer(recent_logs, many=True)
            
            stats_data = {
                'total_logs': total_logs,
                'by_log_type': by_log_type,
                'by_status_code': by_status_code,
                'by_user': by_user,
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
    
    @action(detail=False, methods=['get'], url_path='errors')
    def errors(self, request):
        """Получение логов с ошибками"""
        try:
            error_logs = self.get_queryset().filter(
                status_code__gte=400
            ).order_by('-created_at')
            
            serializer = HuntflowLogSerializer(error_logs, many=True)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Найдено {len(serializer.data)} ошибок"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HuntflowApiRequestViewSet(BaseAPIViewSet):
    """
    ViewSet для выполнения API запросов к Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы (POST)
    ИСТОЧНИКИ ДАННЫЕ: HuntflowApiRequestSerializer, HuntflowCandidateService
    ОБРАБОТКА: Выполнение API запросов к Huntflow
    ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с результатами API запросов
    СВЯЗИ: BaseAPIViewSet, UnifiedResponseHandler
    ФОРМАТ: DRF API responses
    """
    serializer_class = HuntflowApiRequestSerializer
    
    def get_queryset(self):
        """Для API запросов нет queryset"""
        return HuntflowLog.objects.none()
    
    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection(self, request):
        """
        Тестирование подключения к Huntflow API
        
        ВХОДЯЩИЕ ДАННЫЕ: request.user
        ИСТОЧНИКИ ДАННЫЕ: HuntflowCandidateService
        ОБРАБОТКА: Тестирование подключения к Huntflow API
        ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response с результатом теста
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: DRF Response
        """
        try:
            from logic.integration.huntflow.huntflow_candidates import HuntflowCandidateService
            
            user = request.user
            huntflow_service = HuntflowCandidateService(user)
            
            connection_result = huntflow_service.test_connection()
            
            if connection_result:
                response_data = UnifiedResponseHandler.success_response(
                    {'connection_status': 'connected'},
                    "Подключение к Huntflow API успешно"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось подключиться к Huntflow API",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='get-accounts')
    def get_accounts(self, request):
        """Получение списка организаций"""
        try:
            from apps.huntflow.services import HuntflowService
            
            user = request.user
            huntflow_service = HuntflowService(user)
            
            accounts = huntflow_service.get_accounts()
            
            if accounts:
                response_data = UnifiedResponseHandler.success_response(
                    accounts,
                    "Список организаций получен"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось получить список организаций",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='get-vacancies')
    def get_vacancies(self, request):
        """Получение списка вакансий"""
        try:
            from apps.huntflow.services import HuntflowService
            
            user = request.user
            account_id = request.data.get('account_id')
            
            if not account_id:
                response_data = UnifiedResponseHandler.error_response(
                    "Не указан ID организации",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            huntflow_service = HuntflowService(user)
            vacancies = huntflow_service.get_vacancies(account_id)
            
            if vacancies:
                response_data = UnifiedResponseHandler.success_response(
                    vacancies,
                    "Список вакансий получен"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось получить список вакансий",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='get-candidates')
    def get_candidates(self, request):
        """Получение списка кандидатов"""
        try:
            from apps.huntflow.services import HuntflowService
            
            user = request.user
            account_id = request.data.get('account_id')
            
            if not account_id:
                response_data = UnifiedResponseHandler.error_response(
                    "Не указан ID организации",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            huntflow_service = HuntflowService(user)
            candidates = huntflow_service.get_candidates(account_id)
            
            if candidates:
                response_data = UnifiedResponseHandler.success_response(
                    candidates,
                    "Список кандидатов получен"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Не удалось получить список кандидатов",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
