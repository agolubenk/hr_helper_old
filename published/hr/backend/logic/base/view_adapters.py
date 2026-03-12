"""Адаптеры для views с сохранением совместимости"""
from functools import wraps
from django.http import JsonResponse
from logic.base.response_handler import UnifiedResponseHandler

def legacy_view_adapter(new_view_func):
    """
    Адаптер для обеспечения совместимости старых views
    
    ВХОДЯЩИЕ ДАННЫЕ: new_view_func (функция view)
    ИСТОЧНИКИ ДАННЫЕ: Django views
    ОБРАБОТКА: Обертка view функции с обработкой ошибок
    ВЫХОДЯЩИЕ ДАННЫЕ: Обернутая view функция
    СВЯЗИ: functools.wraps, UnifiedResponseHandler
    ФОРМАТ: Декоратор функции
    """
    @wraps(new_view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return new_view_func(request, *args, **kwargs)
        except Exception as e:
            # Логируем ошибку
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in {new_view_func.__name__}: {e}")
            
            # Возвращаем унифицированный ответ об ошибке
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(
                    "Internal server error",
                    error_code="INTERNAL_ERROR"
                ),
                status_code=500
            )
    return wrapper

def deprecated_view_wrapper(old_view_name, new_view_name):
    """
    Обертка для deprecated views с предупреждением
    
    ВХОДЯЩИЕ ДАННЫЕ: old_view_name (строка), new_view_name (строка)
    ИСТОЧНИКИ ДАННЫЕ: Deprecated views
    ОБРАБОТКА: Создание декоратора с предупреждением о deprecation
    ВЫХОДЯЩИЕ ДАННЫЕ: Декоратор функции
    СВЯЗИ: warnings.warn
    ФОРМАТ: Декоратор функции
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            import warnings
            warnings.warn(
                f"{old_view_name} is deprecated. Use {new_view_name} instead.",
                DeprecationWarning,
                stacklevel=2
            )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

def finance_view_adapter(view_func):
    """
    Специальный адаптер для Finance views
    
    ВХОДЯЩИЕ ДАННЫЕ: view_func (функция Finance view)
    ИСТОЧНИКИ ДАННЫЕ: Finance views
    ОБРАБОТКА: Обертка Finance view с логированием и обработкой ошибок
    ВЫХОДЯЩИЕ ДАННЫЕ: Обернутая Finance view функция
    СВЯЗИ: logging, UnifiedResponseHandler
    ФОРМАТ: Декоратор функции
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            # Добавляем логирование для Finance views
            import logging
            logger = logging.getLogger('apps.finance')
            logger.info(f"Finance view called: {view_func.__name__}")
            
            return view_func(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Finance view error in {view_func.__name__}: {e}")
            
            # Возвращаем унифицированный ответ об ошибке
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(
                    f"Finance view error: {str(e)}",
                    error_code="FINANCE_VIEW_ERROR"
                ),
                status_code=500
            )
    return wrapper
