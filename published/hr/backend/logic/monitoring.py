"""Мониторинг состояния миграции и системы"""
import time
import logging
import json
import psutil
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.conf import settings
from logic.base.response_handler import UnifiedResponseHandler

logger = logging.getLogger(__name__)

class MigrationMonitor:
    """Мониторинг состояния миграции"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.checks_performed = 0
        self.checks_failed = 0
        self.last_check_time = None
        
    def check_system_health(self) -> Dict[str, Any]:
        """Проверка общего состояния системы"""
        try:
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'system_status': 'healthy',
                'checks': {}
            }
            
            # Проверка Django
            django_status = self._check_django()
            health_status['checks']['django'] = django_status
            
            # Проверка базы данных
            db_status = self._check_database()
            health_status['checks']['database'] = db_status
            
            # Проверка API endpoints
            api_status = self._check_api_endpoints()
            health_status['checks']['api'] = api_status
            
            # Проверка производительности
            perf_status = self._check_performance()
            health_status['checks']['performance'] = perf_status
            
            # Проверка логики модулей
            logic_status = self._check_logic_modules()
            health_status['checks']['logic_modules'] = logic_status
            
            # Определение общего статуса
            all_healthy = all(
                check.get('status') == 'healthy' 
                for check in health_status['checks'].values()
            )
            
            health_status['system_status'] = 'healthy' if all_healthy else 'degraded'
            
            self.checks_performed += 1
            self.last_check_time = datetime.now()
            
            if not all_healthy:
                self.checks_failed += 1
                
            return UnifiedResponseHandler.success_response(
                health_status,
                f"System health check completed. Status: {health_status['system_status']}"
            )
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return UnifiedResponseHandler.error_response(f"Health check failed: {str(e)}")
    
    def _check_django(self) -> Dict[str, Any]:
        """Проверка состояния Django"""
        try:
            # Проверка настроек Django
            debug_mode = getattr(settings, 'DEBUG', False)
            secret_key = getattr(settings, 'SECRET_KEY', '')
            
            return {
                'status': 'healthy',
                'debug_mode': debug_mode,
                'secret_key_configured': bool(secret_key and len(secret_key) > 10),
                'message': 'Django configuration is healthy'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Django check failed: {str(e)}'
            }
    
    def _check_database(self) -> Dict[str, Any]:
        """Проверка состояния базы данных"""
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            return {
                'status': 'healthy',
                'connection': 'active',
                'message': 'Database connection is healthy'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Database check failed: {str(e)}'
            }
    
    def _check_api_endpoints(self) -> Dict[str, Any]:
        """Проверка API endpoints"""
        try:
            endpoints = [
                '/api/v1/finance/grades/',
                '/api/v1/vacancies/vacancies/',
                '/api/v1/huntflow/cache/'
            ]
            
            results = []
            base_url = 'http://127.0.0.1:8000'
            
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=5)
                    results.append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'accessible': response.status_code in [200, 401, 403]  # 401/403 = endpoint exists but needs auth
                    })
                except requests.RequestException:
                    results.append({
                        'endpoint': endpoint,
                        'status_code': None,
                        'accessible': False
                    })
            
            accessible_count = sum(1 for r in results if r['accessible'])
            total_count = len(results)
            
            return {
                'status': 'healthy' if accessible_count == total_count else 'degraded',
                'accessible_endpoints': f"{accessible_count}/{total_count}",
                'results': results,
                'message': f'{accessible_count}/{total_count} API endpoints are accessible'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API endpoints check failed: {str(e)}'
            }
    
    def _check_performance(self) -> Dict[str, Any]:
        """Проверка производительности системы"""
        try:
            # Проверка использования CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Проверка использования памяти
            memory = psutil.virtual_memory()
            
            # Проверка использования диска
            disk = psutil.disk_usage('/')
            
            # Определение статуса на основе метрик
            cpu_ok = cpu_percent < 80
            memory_ok = memory.percent < 85
            disk_ok = disk.percent < 90
            
            overall_healthy = cpu_ok and memory_ok and disk_ok
            
            return {
                'status': 'healthy' if overall_healthy else 'degraded',
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'cpu_ok': cpu_ok,
                'memory_ok': memory_ok,
                'disk_ok': disk_ok,
                'message': f'Performance check: CPU {cpu_percent}%, Memory {memory.percent}%, Disk {disk.percent}%'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Performance check failed: {str(e)}'
            }
    
    def _check_logic_modules(self) -> Dict[str, Any]:
        """Проверка состояния logic модулей"""
        try:
            modules_to_check = [
                'logic.base.api_client',
                'logic.base.response_handler',
                'logic.integration.shared.candidate_operations',
                'logic.integration.shared.gemini_operations',
                'logic.utilities.common_api'
            ]
            
            results = []
            
            for module_name in modules_to_check:
                try:
                    __import__(module_name)
                    results.append({
                        'module': module_name,
                        'status': 'healthy',
                        'importable': True
                    })
                except ImportError as e:
                    results.append({
                        'module': module_name,
                        'status': 'error',
                        'importable': False,
                        'error': str(e)
                    })
            
            healthy_count = sum(1 for r in results if r['status'] == 'healthy')
            total_count = len(results)
            
            return {
                'status': 'healthy' if healthy_count == total_count else 'degraded',
                'healthy_modules': f"{healthy_count}/{total_count}",
                'results': results,
                'message': f'{healthy_count}/{total_count} logic modules are healthy'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Logic modules check failed: {str(e)}'
            }
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Получение статуса миграции"""
        try:
            uptime = datetime.now() - self.start_time
            
            status = {
                'migration_start_time': self.start_time.isoformat(),
                'uptime_seconds': uptime.total_seconds(),
                'checks_performed': self.checks_performed,
                'checks_failed': self.checks_failed,
                'success_rate': ((self.checks_performed - self.checks_failed) / max(self.checks_performed, 1)) * 100,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'status': 'stable' if self.checks_failed == 0 else 'unstable'
            }
            
            return UnifiedResponseHandler.success_response(
                status,
                f"Migration status: {status['status']}, Success rate: {status['success_rate']:.1f}%"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Failed to get migration status: {str(e)}")
    
    def check_specific_module(self, module_name: str) -> Dict[str, Any]:
        """Проверка конкретного модуля"""
        try:
            # Попытка импорта модуля
            module = __import__(module_name)
            
            # Проверка основных классов в модуле
            classes_found = []
            if hasattr(module, '__all__'):
                for item_name in module.__all__:
                    item = getattr(module, item_name)
                    if hasattr(item, '__call__'):
                        classes_found.append(item_name)
            
            return UnifiedResponseHandler.success_response(
                {
                    'module': module_name,
                    'importable': True,
                    'classes_found': classes_found,
                    'module_file': getattr(module, '__file__', 'unknown')
                },
                f"Module {module_name} is healthy"
            )
            
        except ImportError as e:
            return UnifiedResponseHandler.error_response(f"Module {module_name} import failed: {str(e)}")
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Module {module_name} check failed: {str(e)}")


class DeploymentMonitor:
    """Мониторинг процесса развертывания"""
    
    def __init__(self):
        self.deployment_start = datetime.now()
        self.steps_completed = []
        self.steps_failed = []
        self.current_step = None
        
    def start_deployment(self, deployment_type: str = "migration") -> Dict[str, Any]:
        """Начало процесса развертывания"""
        try:
            self.deployment_start = datetime.now()
            self.steps_completed = []
            self.steps_failed = []
            
            logger.info(f"Starting {deployment_type} deployment")
            
            return UnifiedResponseHandler.success_response(
                {
                    'deployment_type': deployment_type,
                    'start_time': self.deployment_start.isoformat(),
                    'status': 'started'
                },
                f"{deployment_type} deployment started"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Failed to start deployment: {str(e)}")
    
    def complete_step(self, step_name: str, step_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Завершение шага развертывания"""
        try:
            step_info = {
                'step': step_name,
                'completed_at': datetime.now().isoformat(),
                'data': step_data or {}
            }
            
            self.steps_completed.append(step_info)
            logger.info(f"Deployment step completed: {step_name}")
            
            return UnifiedResponseHandler.success_response(
                step_info,
                f"Step '{step_name}' completed successfully"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Failed to complete step: {str(e)}")
    
    def fail_step(self, step_name: str, error_message: str, step_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Отметка неудачного шага развертывания"""
        try:
            step_info = {
                'step': step_name,
                'failed_at': datetime.now().isoformat(),
                'error': error_message,
                'data': step_data or {}
            }
            
            self.steps_failed.append(step_info)
            logger.error(f"Deployment step failed: {step_name} - {error_message}")
            
            return UnifiedResponseHandler.error_response(
                step_info,
                f"Step '{step_name}' failed: {error_message}"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Failed to record step failure: {str(e)}")
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Получение статуса развертывания"""
        try:
            deployment_time = datetime.now() - self.deployment_start
            
            status = {
                'deployment_start': self.deployment_start.isoformat(),
                'deployment_time_seconds': deployment_time.total_seconds(),
                'steps_completed': len(self.steps_completed),
                'steps_failed': len(self.steps_failed),
                'success_rate': (len(self.steps_completed) / max(len(self.steps_completed) + len(self.steps_failed), 1)) * 100,
                'completed_steps': self.steps_completed,
                'failed_steps': self.steps_failed,
                'status': 'completed' if len(self.steps_failed) == 0 else 'failed'
            }
            
            return UnifiedResponseHandler.success_response(
                status,
                f"Deployment status: {status['status']}, Success rate: {status['success_rate']:.1f}%"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Failed to get deployment status: {str(e)}")


# Глобальные экземпляры мониторов
migration_monitor = MigrationMonitor()
deployment_monitor = DeploymentMonitor()

