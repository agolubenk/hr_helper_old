from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests
import time
from dataclasses import dataclass

@dataclass
class APIResponse:
    """
    Стандартный ответ API
    
    ВХОДЯЩИЕ ДАННЫЕ: success (bool), data (Any), error (str), status_code (int), headers (Dict)
    ИСТОЧНИКИ ДАННЫХ: HTTP ответы от внешних API
    ОБРАБОТКА: Стандартизация ответов API для унифицированной обработки
    ВЫХОДЯЩИЕ ДАННЫЕ: Структурированный ответ API
    СВЯЗИ: Нет
    ФОРМАТ: dataclass с полями success, data, error, status_code, headers
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    headers: Optional[Dict] = None

class BaseAPIClient(ABC):
    """
    Базовый клиент для работы с внешними API
    
    ВХОДЯЩИЕ ДАННЫЕ: API ключи, URL, параметры конфигурации
    ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP запросы
    ОБРАБОТКА: Унифицированная работа с внешними API, обработка ошибок, повторные попытки
    ВЫХОДЯЩИЕ ДАННЫЕ: Стандартизированные ответы API
    СВЯЗИ: requests библиотека, внешние API
    ФОРМАТ: APIResponse объекты
    """
    
    def __init__(self, api_key: str, base_url: str, **kwargs):
        """
        Инициализация базового API клиента
        
        ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), **kwargs (параметры)
        ИСТОЧНИКИ ДАННЫХ: Переданные параметры конфигурации
        ОБРАБОТКА: Настройка сессии, параметров таймаута и повторных попыток
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный API клиент
        СВЯЗИ: requests.Session
        ФОРМАТ: Экземпляр класса BaseAPIClient
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = kwargs.get('timeout', 30)
        self.max_retries = kwargs.get('max_retries', 3)
        self.retry_delay = kwargs.get('retry_delay', 1)
        
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """
        Настройка сессии
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (использует self.session)
        ИСТОЧНИКИ ДАННЫХ: requests.Session
        ОБРАБОТКА: Настройка заголовков HTTP сессии
        ВЫХОДЯЩИЕ ДАННЫЕ: Настроенная HTTP сессия
        СВЯЗИ: self._setup_auth()
        ФОРМАТ: requests.Session
        """
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'HR-Helper/2.0'
        })
        self._setup_auth()
    
    @abstractmethod
    def _setup_auth(self):
        """
        Настройка аутентификации
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (абстрактный метод)
        ИСТОЧНИКИ ДАННЫХ: Нет (абстрактный метод)
        ОБРАБОТКА: Абстрактный метод для настройки аутентификации в наследниках
        ВЫХОДЯЩИЕ ДАННЫЕ: Нет (абстрактный метод)
        СВЯЗИ: Нет (абстрактный метод)
        ФОРМАТ: Нет (абстрактный метод)
        """
        pass
    
    def make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """
        Выполнение запроса с повторными попытками
        
        ВХОДЯЩИЕ ДАННЫЕ: method (строка), endpoint (строка), data (словарь), params (словарь), **kwargs
        ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP запросы
        ОБРАБОТКА: Отправка HTTP запроса, обработка ошибок, повторные попытки при необходимости
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом запроса
        СВЯЗИ: requests библиотека, внешние API
        ФОРМАТ: APIResponse объект
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code in [200, 201, 204]:
                    try:
                        json_data = response.json() if response.text else {}
                    except:
                        json_data = response.text
                    
                    return APIResponse(
                        success=True,
                        data=json_data,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )
                
                elif response.status_code in [429, 503, 502, 504]:
                    # Повторяемые ошибки
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                
                return APIResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return APIResponse(success=False, error="Request timeout")
            
            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return APIResponse(success=False, error="Connection error")
        
        return APIResponse(success=False, error="Max retries exceeded")
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> APIResponse:
        """
        Выполнение GET запроса
        
        ВХОДЯЩИЕ ДАННЫЕ: endpoint (строка), params (словарь)
        ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP GET запросы
        ОБРАБОТКА: Вызов make_request с методом GET
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом GET запроса
        СВЯЗИ: self.make_request()
        ФОРМАТ: APIResponse объект
        """
        return self.make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> APIResponse:
        """
        Выполнение POST запроса
        
        ВХОДЯЩИЕ ДАННЫЕ: endpoint (строка), data (словарь)
        ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP POST запросы
        ОБРАБОТКА: Вызов make_request с методом POST
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом POST запроса
        СВЯЗИ: self.make_request()
        ФОРМАТ: APIResponse объект
        """
        return self.make_request('POST', endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> APIResponse:
        """
        Выполнение PUT запроса
        
        ВХОДЯЩИЕ ДАННЫЕ: endpoint (строка), data (словарь)
        ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP PUT запросы
        ОБРАБОТКА: Вызов make_request с методом PUT
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом PUT запроса
        СВЯЗИ: self.make_request()
        ФОРМАТ: APIResponse объект
        """
        return self.make_request('PUT', endpoint, data=data)
    
    def delete(self, endpoint: str) -> APIResponse:
        """
        Выполнение DELETE запроса
        
        ВХОДЯЩИЕ ДАННЫЕ: endpoint (строка)
        ИСТОЧНИКИ ДАННЫХ: Внешние API через HTTP DELETE запросы
        ОБРАБОТКА: Вызов make_request с методом DELETE
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом DELETE запроса
        СВЯЗИ: self.make_request()
        ФОРМАТ: APIResponse объект
        """
        return self.make_request('DELETE', endpoint)
    
    @abstractmethod
    def test_connection(self) -> APIResponse:
        """
        Тестирование подключения к API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (абстрактный метод)
        ИСТОЧНИКИ ДАННЫХ: Нет (абстрактный метод)
        ОБРАБОТКА: Абстрактный метод для тестирования подключения в наследниках
        ВЫХОДЯЩИЕ ДАННЫЕ: Нет (абстрактный метод)
        СВЯЗИ: Нет (абстрактный метод)
        ФОРМАТ: Нет (абстрактный метод)
        """
        pass
