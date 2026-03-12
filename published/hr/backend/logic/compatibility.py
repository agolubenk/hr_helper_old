"""Файл для обеспечения обратной совместимости при миграции"""

# Импорты старых сервисов с предупреждениями
import warnings

# Попытка импорта старых сервисов
try:
    from apps.finance.services import CurrencyRateService as OldCurrencyRateService
    HAS_OLD_SERVICE = True
except ImportError:
    OldCurrencyRateService = None
    HAS_OLD_SERVICE = False

# Импорт новых сервисов
from logic.base.currency_service import currency_service as new_currency_service

def get_currency_service():
    """Получить сервис валют (новый или старый)"""
    warnings.warn(
        "get_currency_service is deprecated. Use logic.base.currency_service directly",
        DeprecationWarning,
        stacklevel=2
    )
    return new_currency_service

# Алиасы для совместимости
if HAS_OLD_SERVICE:
    CurrencyRateService = OldCurrencyRateService  # Пока оставляем старый
else:
    CurrencyRateService = None  # Старый сервис недоступен

