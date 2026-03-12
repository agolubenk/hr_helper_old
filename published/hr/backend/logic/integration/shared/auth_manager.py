"""Централизованное управление аутентификацией для интеграций"""
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.api_client import BaseAPIClient
import time
from typing import Dict, Any, Optional

class AuthManager(BaseAPIClient):
    """
    Централизованный менеджер аутентификации для всех интеграций
    
    ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
    ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
    ОБРАБОТКА: Управление аутентификацией для всех типов интеграций
    ВЫХОДЯЩИЕ ДАННЫЕ: Токены доступа и результаты аутентификации
    СВЯЗИ: BaseAPIClient, внешние API интеграций
    ФОРМАТ: Словари с токенами и статусом аутентификации
    """
    
    def __init__(self, api_key="", base_url="", timeout=30):
        """
        Инициализация менеджера аутентификации
        
        ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
        ИСТОЧНИКИ ДАННЫЕ: Переданные параметры конфигурации
        ОБРАБОТКА: Настройка кэшей токенов и базовой конфигурации
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный менеджер аутентификации
        СВЯЗИ: BaseAPIClient
        ФОРМАТ: Экземпляр класса AuthManager
        """
        super().__init__(api_key, base_url, timeout)
        self._token_cache = {}
        self._refresh_tokens = {}
    
    def authenticate(self, integration_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Аутентификация в интеграции
        
        ВХОДЯЩИЕ ДАННЫЕ: integration_type (строка), credentials (словарь)
        ИСТОЧНИКИ ДАННЫЕ: Параметры аутентификации для конкретной интеграции
        ОБРАБОТКА: Выбор метода аутентификации по типу интеграции
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат аутентификации с токенами
        СВЯЗИ: Методы аутентификации для разных интеграций
        ФОРМАТ: Словарь с токенами и статусом аутентификации
        """
        try:
            if integration_type == "huntflow":
                return self._authenticate_huntflow(credentials)
            elif integration_type == "clickup":
                return self._authenticate_clickup(credentials)
            elif integration_type == "notion":
                return self._authenticate_notion(credentials)
            elif integration_type == "google":
                return self._authenticate_google(credentials)
            else:
                return UnifiedResponseHandler.error_response(f"Неподдерживаемый тип интеграции: {integration_type}")
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _authenticate_huntflow(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Аутентификация в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: credentials (словарь с api_key)
        ИСТОЧНИКИ ДАННЫЕ: Huntflow API
        ОБРАБОТКА: Проверка API ключа через запрос к /accounts
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат аутентификации
        СВЯЗИ: Huntflow API, UnifiedResponseHandler
        ФОРМАТ: Словарь с сообщением и данными
        """
        try:
            api_key = credentials.get('api_key')
            if not api_key:
                return UnifiedResponseHandler.error_response("API ключ Huntflow не указан")
            
            # Устанавливаем API ключ
            self.api_key = api_key
            self.base_url = "https://dev-100000.api.huntflow.ru"
            
            # Тестируем подключение
            response = self.get("accounts")
            
            if response.get('success'):
                token_data = {
                    'access_token': api_key,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'integration_type': 'huntflow'
                }
                
                # Кешируем токен
                self._token_cache['huntflow'] = {
                    'token': token_data,
                    'expires_at': time.time() + 3600
                }
                
                return UnifiedResponseHandler.success_response(
                    token_data,
                    "Успешная аутентификация в Huntflow"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка аутентификации в Huntflow: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _authenticate_clickup(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Аутентификация в ClickUp
        
        ВХОДЯЩИЕ ДАННЫЕ: credentials (словарь с api_key)
        ИСТОЧНИКИ ДАННЫЕ: ClickUp API
        ОБРАБОТКА: Проверка API ключа через запрос к /user
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат аутентификации
        СВЯЗИ: ClickUp API, UnifiedResponseHandler
        ФОРМАТ: Словарь с сообщением и данными
        """
        try:
            api_token = credentials.get('api_token')
            if not api_token:
                return UnifiedResponseHandler.error_response("API токен ClickUp не указан")
            
            # Устанавливаем токен
            self.api_key = api_token
            self.base_url = "https://api.clickup.com/api/v2"
            
            # Тестируем подключение
            response = self.get("user")
            
            if response.get('success'):
                token_data = {
                    'access_token': api_token,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'integration_type': 'clickup'
                }
                
                # Кешируем токен
                self._token_cache['clickup'] = {
                    'token': token_data,
                    'expires_at': time.time() + 3600
                }
                
                return UnifiedResponseHandler.success_response(
                    token_data,
                    "Успешная аутентификация в ClickUp"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка аутентификации в ClickUp: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _authenticate_notion(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Аутентификация в Notion
        
        ВХОДЯЩИЕ ДАННЫЕ: credentials (словарь с integration_token)
        ИСТОЧНИКИ ДАННЫЕ: Notion API
        ОБРАБОТКА: Проверка интеграционного токена через запрос к /users/me
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат аутентификации
        СВЯЗИ: Notion API, UnifiedResponseHandler
        ФОРМАТ: Словарь с сообщением и данными
        """
        try:
            api_token = credentials.get('api_token')
            if not api_token:
                return UnifiedResponseHandler.error_response("API токен Notion не указан")
            
            # Устанавливаем токен
            self.api_key = api_token
            self.base_url = "https://api.notion.com/v1"
            
            # Тестируем подключение
            response = self.get("users/me")
            
            if response.get('success'):
                token_data = {
                    'access_token': api_token,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'integration_type': 'notion'
                }
                
                # Кешируем токен
                self._token_cache['notion'] = {
                    'token': token_data,
                    'expires_at': time.time() + 3600
                }
                
                return UnifiedResponseHandler.success_response(
                    token_data,
                    "Успешная аутентификация в Notion"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка аутентификации в Notion: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _authenticate_google(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Аутентификация в Google
        
        ВХОДЯЩИЕ ДАННЫЕ: credentials (словарь с access_token, refresh_token)
        ИСТОЧНИКИ ДАННЫЕ: Google API
        ОБРАБОТКА: Проверка токенов доступа Google
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат аутентификации
        СВЯЗИ: Google API, UnifiedResponseHandler
        ФОРМАТ: Словарь с сообщением и данными
        """
        try:
            access_token = credentials.get('access_token')
            refresh_token = credentials.get('refresh_token')
            
            if not access_token:
                return UnifiedResponseHandler.error_response("Access токен Google не указан")
            
            # Устанавливаем токен
            self.api_key = access_token
            self.base_url = "https://www.googleapis.com"
            
            if refresh_token:
                self._refresh_tokens['google'] = refresh_token
            
            # Тестируем подключение
            response = self.get("oauth2/v2/userinfo")
            
            if response.get('success'):
                token_data = {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'integration_type': 'google'
                }
                
                # Кешируем токен
                self._token_cache['google'] = {
                    'token': token_data,
                    'expires_at': time.time() + 3600
                }
                
                return UnifiedResponseHandler.success_response(
                    token_data,
                    "Успешная аутентификация в Google"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка аутентификации в Google: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def refresh_token(self, integration_type: str) -> Dict[str, Any]:
        """
        Обновление токена доступа
        
        ВХОДЯЩИЕ ДАННЫЕ: integration_type (строка)
        ИСТОЧНИКИ ДАННЫЕ: Кэш токенов, внешние API
        ОБРАБОТКА: Обновление истекшего токена доступа
        ВЫХОДЯЩИЕ ДАННЫЕ: Новый токен доступа
        СВЯЗИ: Кэш токенов, UnifiedResponseHandler
        ФОРМАТ: Словарь с новым токеном
        """
        try:
            if integration_type not in self._refresh_tokens:
                return UnifiedResponseHandler.error_response(f"Refresh токен для {integration_type} не найден")
            
            refresh_token = self._refresh_tokens[integration_type]
            
            if integration_type == "google":
                return self._refresh_google_token(refresh_token)
            else:
                return UnifiedResponseHandler.error_response(f"Обновление токена для {integration_type} не поддерживается")
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _refresh_google_token(self, refresh_token: str) -> Dict[str, Any]:
        """Обновление Google токена"""
        try:
            # Здесь должна быть логика обновления Google токена
            # Пока возвращаем ошибку, так как нужны дополнительные параметры
            return UnifiedResponseHandler.error_response("Обновление Google токена требует дополнительной реализации")
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_cached_token(self, integration_type: str) -> Optional[Dict[str, Any]]:
        """Получение кешированного токена"""
        try:
            if integration_type not in self._token_cache:
                return None
            
            token_info = self._token_cache[integration_type]
            
            # Проверяем не истек ли токен
            if time.time() > token_info['expires_at']:
                # Пытаемся обновить токен
                refresh_result = self.refresh_token(integration_type)
                if refresh_result.get('success'):
                    return refresh_result.get('data')
                else:
                    # Удаляем истекший токен из кеша
                    del self._token_cache[integration_type]
                    return None
            
            return token_info['token']
            
        except Exception as e:
            return None
    
    def invalidate_token(self, integration_type: str) -> Dict[str, Any]:
        """
        Инвалидация токена
        
        ВХОДЯЩИЕ ДАННЫЕ: integration_type (строка)
        ИСТОЧНИКИ ДАННЫЕ: Кэш токенов
        ОБРАБОТКА: Удаление токена из кэша
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат инвалидации
        СВЯЗИ: Кэш токенов, UnifiedResponseHandler
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            if integration_type in self._token_cache:
                del self._token_cache[integration_type]
            
            if integration_type in self._refresh_tokens:
                del self._refresh_tokens[integration_type]
            
            return UnifiedResponseHandler.success_response(
                None,
                f"Токен для {integration_type} инвалидирован"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def test_connection(self, integration_type: str) -> Dict[str, Any]:
        """
        Тестирование соединения с интеграцией
        
        ВХОДЯЩИЕ ДАННЫЕ: integration_type (строка)
        ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
        ОБРАБОТКА: Проверка доступности API интеграции
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат тестирования соединения
        СВЯЗИ: Внешние API, UnifiedResponseHandler
        ФОРМАТ: Словарь с результатом тестирования
        """
        try:
            token = self.get_cached_token(integration_type)
            
            if not token:
                return UnifiedResponseHandler.error_response(f"Токен для {integration_type} не найден или истек")
            
            # Восстанавливаем настройки для тестирования
            self.api_key = token['access_token']
            
            if integration_type == "huntflow":
                self.base_url = "https://dev-100000.api.huntflow.ru"
                response = self.get("accounts")
            elif integration_type == "clickup":
                self.base_url = "https://api.clickup.com/api/v2"
                response = self.get("user")
            elif integration_type == "notion":
                self.base_url = "https://api.notion.com/v1"
                response = self.get("users/me")
            elif integration_type == "google":
                self.base_url = "https://www.googleapis.com"
                response = self.get("oauth2/v2/userinfo")
            else:
                return UnifiedResponseHandler.error_response(f"Неподдерживаемый тип интеграции: {integration_type}")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response.get('data'),
                    f"Подключение к {integration_type} работает"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка подключения к {integration_type}: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
