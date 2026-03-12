"""Адаптеры для плавной миграции существующих сервисов"""

import warnings
from typing import Any, Dict

class DeprecatedServiceAdapter:
    """
    Адаптер для старых сервисов с предупреждениями
    
    ВХОДЯЩИЕ ДАННЫЕ: old_service_class, new_service_class (классы сервисов)
    ИСТОЧНИКИ ДАННЫХ: Переданные классы сервисов
    ОБРАБОТКА: Создание адаптера для плавной миграции с предупреждениями
    ВЫХОДЯЩИЕ ДАННЫЕ: Экземпляр адаптера
    СВЯЗИ: warnings модуль
    ФОРМАТ: Экземпляр класса DeprecatedServiceAdapter
    """
    
    def __init__(self, old_service_class, new_service_class):
        """
        Инициализация адаптера
        
        ВХОДЯЩИЕ ДАННЫЕ: old_service_class (старый класс), new_service_class (новый класс)
        ИСТОЧНИКИ ДАННЫХ: Переданные классы сервисов
        ОБРАБОТКА: Сохранение ссылок на старый и новый классы
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный адаптер
        СВЯЗИ: Нет
        ФОРМАТ: Экземпляр класса
        """
        self.old_service_class = old_service_class
        self.new_service_class = new_service_class
    
    def __call__(self, *args, **kwargs):
        """
        Вызов старого сервиса с предупреждением
        
        ВХОДЯЩИЕ ДАННЫЕ: *args, **kwargs (аргументы для создания сервиса)
        ИСТОЧНИКИ ДАННЫХ: self.old_service_class
        ОБРАБОТКА: Вывод предупреждения о deprecation, создание экземпляра старого сервиса
        ВЫХОДЯЩИЕ ДАННЫЕ: Экземпляр старого сервиса
        СВЯЗИ: warnings.warn()
        ФОРМАТ: Экземпляр старого сервиса
        """
        warnings.warn(
            f"{self.old_service_class.__name__} is deprecated. "
            f"Use {self.new_service_class.__name__} instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.old_service_class(*args, **kwargs)
