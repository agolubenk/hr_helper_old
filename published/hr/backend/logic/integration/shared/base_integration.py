"""Базовый класс для всех интеграций"""
from abc import ABC, abstractmethod
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.api_client import BaseAPIClient

class BaseIntegration(BaseAPIClient, ABC):
    """
    Базовый класс для всех интеграций с внешними системами
    
    ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
    ИСТОЧНИКИ ДАННЫЕ: Базовый API клиент
    ОБРАБОТКА: Абстрактный базовый класс для всех интеграций
    ВЫХОДЯЩИЕ ДАННЫЕ: Базовый функционал интеграций
    СВЯЗИ: BaseAPIClient, UnifiedResponseHandler
    ФОРМАТ: Абстрактный класс с общими методами
    """
    
    def __init__(self, api_key="", base_url="", timeout=30):
        """
        Инициализация базовой интеграции
        
        ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
        ИСТОЧНИКИ ДАННЫЕ: Переданные параметры конфигурации
        ОБРАБОТКА: Настройка базовых параметров интеграции
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированная базовая интеграция
        СВЯЗИ: BaseAPIClient
        ФОРМАТ: Экземпляр класса BaseIntegration
        """
        super().__init__(api_key, base_url, timeout)
        self.integration_type = ""
        self.is_authenticated = False
    
    @abstractmethod
    def authenticate(self, credentials):
        """Аутентификация в интеграции - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def test_connection(self):
        """Тест подключения - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def sync_data(self, sync_type="full"):
        """Синхронизация данных - должен быть реализован в наследниках"""
        pass
    
    def get_integration_info(self):
        """
        Получение информации об интеграции
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Внутренние параметры интеграции
        ОБРАБОТКА: Сбор информации о текущем состоянии интеграции
        ВЫХОДЯЩИЕ ДАННЫЕ: Информация об интеграции
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с информацией об интеграции
        """
        try:
            info = {
                'integration_type': self.integration_type,
                'base_url': self.base_url,
                'is_authenticated': self.is_authenticated,
                'timeout': self.timeout,
                'status': 'active' if self.is_authenticated else 'inactive'
            }
            
            return UnifiedResponseHandler.success_response(
                info,
                "Информация об интеграции получена"
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_sync_status(self):
        """
        Получение статуса синхронизации
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Внутренние параметры синхронизации
        ОБРАБОТКА: Сбор информации о статусе синхронизации
        ВЫХОДЯЩИЕ ДАННЫЕ: Статус синхронизации
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь со статусом синхронизации
        """
        try:
            # Базовая реализация - в наследниках может быть переопределена
            status = {
                'last_sync': None,
                'sync_in_progress': False,
                'total_records': 0,
                'synced_records': 0,
                'failed_records': 0,
                'errors': []
            }
            
            return UnifiedResponseHandler.success_response(
                status,
                "Статус синхронизации получен"
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def validate_credentials(self, credentials):
        """
        Валидация учетных данных
        
        ВХОДЯЩИЕ ДАННЫЕ: credentials (словарь)
        ИСТОЧНИКИ ДАННЫЕ: Переданные учетные данные
        ОБРАБОТКА: Проверка валидности учетных данных
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат валидации
        СВЯЗИ: Метод _get_required_credentials_fields
        ФОРМАТ: Кортеж (bool, строка с сообщением)
        """
        try:
            if not isinstance(credentials, dict):
                return False, "Учетные данные должны быть словарем"
            
            # Базовая валидация - в наследниках может быть расширена
            required_fields = self._get_required_credentials_fields()
            
            for field in required_fields:
                if field not in credentials or not credentials[field]:
                    return False, f"Обязательное поле '{field}' не указано или пустое"
            
            return True, "Учетные данные валидны"
            
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"
    
    def _get_required_credentials_fields(self):
        """Получение обязательных полей для учетных данных - должен быть переопределен в наследниках"""
        return []
    
    def handle_api_error(self, response, operation="operation"):
        """
        Обработка ошибок API
        
        ВХОДЯЩИЕ ДАННЫЕ: response (ответ API), operation (строка)
        ИСТОЧНИКИ ДАННЫЕ: Ответ от внешнего API
        ОБРАБОТКА: Анализ и форматирование ошибок API
        ВЫХОДЯЩИЕ ДАННЫЕ: Стандартизированная ошибка
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с ошибкой
        """
        try:
            error_message = f"Ошибка при выполнении {operation}"
            
            if response:
                if isinstance(response, dict):
                    if 'error' in response:
                        error_message += f": {response['error']}"
                    elif 'message' in response:
                        error_message += f": {response['message']}"
                    elif 'detail' in response:
                        error_message += f": {response['detail']}"
                elif isinstance(response, str):
                    error_message += f": {response}"
            
            return UnifiedResponseHandler.error_response(error_message)
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(f"Ошибка обработки ошибки API: {str(e)}")
    
    def log_operation(self, operation, status, details=None):
        """
        Логирование операций интеграции
        
        ВХОДЯЩИЕ ДАННЫЕ: operation (строка), status (строка), details (словарь)
        ИСТОЧНИКИ ДАННЫЕ: Параметры операции интеграции
        ОБРАБОТКА: Создание записи лога операции
        ВЫХОДЯЩИЕ ДАННЫЕ: Запись лога
        СВЯЗИ: Метод _get_current_timestamp
        ФОРМАТ: Словарь с информацией о логе
        """
        try:
            log_entry = {
                'timestamp': self._get_current_timestamp(),
                'integration_type': self.integration_type,
                'operation': operation,
                'status': status,
                'details': details or {}
            }
            
            # Здесь можно добавить логику сохранения в базу данных или файл
            print(f"[INTEGRATION LOG] {log_entry}")
            
            return log_entry
            
        except Exception as e:
            print(f"[INTEGRATION LOG ERROR] {str(e)}")
            return None
    
    def _get_current_timestamp(self):
        """Получение текущего времени"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_rate_limit_info(self):
        """
        Получение информации о лимитах запросов
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Внутренние параметры лимитов
        ОБРАБОТКА: Сбор информации о лимитах запросов
        ВЫХОДЯЩИЕ ДАННЫЕ: Информация о лимитах
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с информацией о лимитах
        """
        try:
            # Базовая реализация - в наследниках может быть переопределена
            rate_limit_info = {
                'requests_per_minute': 60,
                'requests_per_hour': 1000,
                'requests_per_day': 10000,
                'current_usage': 0,
                'reset_time': None
            }
            
            return UnifiedResponseHandler.success_response(
                rate_limit_info,
                "Информация о лимитах запросов получена"
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def check_rate_limit(self):
        """
        Проверка лимитов запросов
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Внутренние параметры лимитов
        ОБРАБОТКА: Проверка текущих лимитов запросов
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат проверки лимитов
        СВЯЗИ: Нет
        ФОРМАТ: Кортеж (bool, строка с сообщением)
        """
        try:
            # Базовая реализация - всегда разрешаем запрос
            # В наследниках может быть реализована более сложная логика
            return True, "Лимиты не превышены"
        except Exception as e:
            return False, f"Ошибка проверки лимитов: {str(e)}"
    
    def retry_request(self, request_func, max_retries=3, delay=1):
        """
        Повторные попытки выполнения запроса
        
        ВХОДЯЩИЕ ДАННЫЕ: request_func (функция), max_retries (число), delay (число)
        ИСТОЧНИКИ ДАННЫЕ: Функция запроса и параметры повтора
        ОБРАБОТКА: Выполнение запроса с повторными попытками
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат запроса
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с результатом запроса
        """
        try:
            for attempt in range(max_retries):
                try:
                    result = request_func()
                    if result.get('success'):
                        return result
                    
                    # Если это ошибка лимитов, ждем и повторяем
                    if 'rate limit' in str(result.get('error', '')).lower():
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(delay * (attempt + 1))
                            continue
                    
                    return result
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    
                    import time
                    time.sleep(delay * (attempt + 1))
            
            return UnifiedResponseHandler.error_response("Превышено максимальное количество попыток")
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
