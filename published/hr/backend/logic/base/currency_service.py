"""Унифицированный сервис для работы с валютами"""
from logic.base.api_client import BaseAPIClient, APIResponse
from typing import Dict, Any, Optional

class UnifiedCurrencyService(BaseAPIClient):
    """
    Унифицированный сервис валют для всех приложений
    
    ВХОДЯЩИЕ ДАННЫЕ: НБРБ API параметры
    ИСТОЧНИКИ ДАННЫЕ: НБРБ API (api.nbrb.by)
    ОБРАБОТКА: Получение и обновление курсов валют через НБРБ API
    ВЫХОДЯЩИЕ ДАННЫЕ: Курсы валют в формате APIResponse
    СВЯЗИ: BaseAPIClient, НБРБ API
    ФОРМАТ: APIResponse объекты с данными о курсах валют
    """
    
    def __init__(self):
        """
        Инициализация унифицированного сервиса валют
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (для НБРБ API не нужен API ключ)
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API конфигурация
        ОБРАБОТКА: Настройка подключения к НБРБ API
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный сервис валют
        СВЯЗИ: BaseAPIClient
        ФОРМАТ: Экземпляр UnifiedCurrencyService
        """
        # Для НБРБ API не нужен API ключ
        super().__init__("", "https://api.nbrb.by", timeout=15)
    
    def _setup_auth(self):
        """
        Настройка аутентификации для НБРБ API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API конфигурация
        ОБРАБОТКА: НБРБ API не требует аутентификации
        ВЫХОДЯЩИЕ ДАННЫЕ: Нет
        СВЯЗИ: Нет
        ФОРМАТ: Нет
        """
        # НБРБ API не требует аутентификации
        pass
    
    def get_currency_rate(self, currency_code: str) -> APIResponse:
        """
        Получить курс валюты
        
        ВХОДЯЩИЕ ДАННЫЕ: currency_code (строка кода валюты)
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API
        ОБРАБОТКА: Запрос курса валюты через НБРБ API
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с курсом валюты
        СВЯЗИ: self.get()
        ФОРМАТ: APIResponse объект
        """
        endpoint = f"exrates/rates/{currency_code}?parammode=2"
        return self.get(endpoint)
    
    def get_all_rates(self) -> Dict[str, Any]:
        """
        Получить все курсы валют
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API для USD, PLN и EUR
        ОБРАБОТКА: Получение курсов для всех поддерживаемых валют
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с курсами валют
        СВЯЗИ: self.get_currency_rate()
        ФОРМАТ: Dict[str, Any] с курсами валют
        """
        rates = {}
        for currency in ['USD', 'PLN', 'EUR']:
            response = self.get_currency_rate(currency)
            if response.success:
                rates[currency] = response.data
        return rates
    
    def test_connection(self) -> APIResponse:
        """
        Тест подключения к НБРБ API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API
        ОБРАБОТКА: Тестовый запрос курса USD для проверки подключения
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом теста
        СВЯЗИ: self.get()
        ФОРМАТ: APIResponse объект
        """
        return self.get("exrates/rates/USD?parammode=2")
    
    def update_currency_rates_in_db(self) -> Dict[str, Any]:
        """
        Обновляет курсы валют в базе данных
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: НБРБ API, Django модель CurrencyRate
        ОБРАБОТКА: Получение курсов валют и сохранение в базу данных
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатами обновления
        СВЯЗИ: self.get_all_rates(), CurrencyRate модель
        ФОРМАТ: Dict[str, Any] с результатами обновления
        """
        from django.utils import timezone
        from apps.finance.models import CurrencyRate
        from decimal import Decimal
        
        rates_data = self.get_all_rates()
        updated_count = 0
        results = {}
        
        for currency, data in rates_data.items():
            try:
                # Создаем или обновляем запись
                currency_rate, created = CurrencyRate.objects.get_or_create(
                    code=currency,
                    defaults={
                        'rate': Decimal(str(data['Cur_OfficialRate'])),
                        'scale': data.get('Cur_Scale', 1),
                        'fetched_at': timezone.now()
                    }
                )
                
                if not created:
                    currency_rate.rate = Decimal(str(data['Cur_OfficialRate']))
                    currency_rate.scale = data.get('Cur_Scale', 1)
                    currency_rate.fetched_at = timezone.now()
                    currency_rate.save()
                
                updated_count += 1
                results[currency] = {
                    'success': True,
                    'rate': currency_rate.rate,
                    'created': created
                }
                
            except Exception as e:
                results[currency] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'updated_count': updated_count,
            'results': results
        }

# Создаем глобальный экземпляр
currency_service = UnifiedCurrencyService()
