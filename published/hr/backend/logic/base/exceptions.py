"""Кастомные исключения для системы logic"""

class LogicBaseException(Exception):
    """
    Базовое исключение для всех logic компонентов
    
    ВХОДЯЩИЕ ДАННЫЕ: message (строка сообщения об ошибке)
    ИСТОЧНИКИ ДАННЫЕ: Python Exception класс
    ОБРАБОТКА: Базовое исключение для всех logic модулей
    ВЫХОДЯЩИЕ ДАННЫЕ: Exception объект
    СВЯЗИ: Python Exception
    ФОРМАТ: Exception класс
    """
    pass

class APIClientException(LogicBaseException):
    """
    Исключения API клиента
    
    ВХОДЯЩИЕ ДАННЫЕ: message (строка сообщения об ошибке)
    ИСТОЧНИКИ ДАННЫЕ: LogicBaseException
    ОБРАБОТКА: Исключения при работе с внешними API
    ВЫХОДЯЩИЕ ДАННЫЕ: Exception объект
    СВЯЗИ: LogicBaseException
    ФОРМАТ: Exception класс
    """
    pass

class ValidationException(LogicBaseException):
    """
    Исключения валидации
    
    ВХОДЯЩИЕ ДАННЫЕ: message (строка сообщения об ошибке)
    ИСТОЧНИКИ ДАННЫЕ: LogicBaseException
    ОБРАБОТКА: Исключения при валидации данных
    ВЫХОДЯЩИЕ ДАННЫЕ: Exception объект
    СВЯЗИ: LogicBaseException
    ФОРМАТ: Exception класс
    """
    pass

class SyncException(LogicBaseException):
    """
    Исключения синхронизации
    
    ВХОДЯЩИЕ ДАННЫЕ: message (строка сообщения об ошибке)
    ИСТОЧНИКИ ДАННЫЕ: LogicBaseException
    ОБРАБОТКА: Исключения при синхронизации данных
    ВЫХОДЯЩИЕ ДАННЫЕ: Exception объект
    СВЯЗИ: LogicBaseException
    ФОРМАТ: Exception класс
    """
    pass

class AnalysisException(LogicBaseException):
    """
    Исключения AI анализа
    
    ВХОДЯЩИЕ ДАННЫЕ: message (строка сообщения об ошибке)
    ИСТОЧНИКИ ДАННЫЕ: LogicBaseException
    ОБРАБОТКА: Исключения при AI анализе данных
    ВЫХОДЯЩИЕ ДАННЫЕ: Exception объект
    СВЯЗИ: LogicBaseException
    ФОРМАТ: Exception класс
    """
    pass
