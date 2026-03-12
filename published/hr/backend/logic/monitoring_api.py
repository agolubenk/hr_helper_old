"""API endpoints для мониторинга системы"""
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from logic.base.api_views import BaseAPIViewSet
from logic.monitoring import migration_monitor, deployment_monitor
from logic.base.response_handler import UnifiedResponseHandler

class HealthCheckViewSet(BaseAPIViewSet):
    """ViewSet для проверки здоровья системы"""
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """Проверка общего состояния системы"""
        try:
            result = migration_monitor.check_system_health()
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Health check failed: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def migration_status(self, request):
        """Получение статуса миграции"""
        try:
            result = migration_monitor.get_migration_status()
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Failed to get migration status: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def module_check(self, request):
        """Проверка конкретного модуля"""
        module_name = request.query_params.get('module')
        if not module_name:
            error_response = UnifiedResponseHandler.error_response("Module name is required")
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = migration_monitor.check_specific_module(module_name)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Module check failed: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeploymentViewSet(BaseAPIViewSet):
    """ViewSet для мониторинга развертывания"""
    
    @action(detail=False, methods=['post'])
    def start_deployment(self, request):
        """Начало процесса развертывания"""
        try:
            deployment_type = request.data.get('type', 'migration')
            result = deployment_monitor.start_deployment(deployment_type)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Failed to start deployment: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def complete_step(self, request):
        """Завершение шага развертывания"""
        try:
            step_name = request.data.get('step_name')
            step_data = request.data.get('step_data', {})
            
            if not step_name:
                error_response = UnifiedResponseHandler.error_response("Step name is required")
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
            
            result = deployment_monitor.complete_step(step_name, step_data)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Failed to complete step: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def fail_step(self, request):
        """Отметка неудачного шага развертывания"""
        try:
            step_name = request.data.get('step_name')
            error_message = request.data.get('error_message', 'Unknown error')
            step_data = request.data.get('step_data', {})
            
            if not step_name:
                error_response = UnifiedResponseHandler.error_response("Step name is required")
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
            
            result = deployment_monitor.fail_step(step_name, error_message, step_data)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Failed to record step failure: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def deployment_status(self, request):
        """Получение статуса развертывания"""
        try:
            result = deployment_monitor.get_deployment_status()
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            error_response = UnifiedResponseHandler.error_response(f"Failed to get deployment status: {str(e)}")
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

