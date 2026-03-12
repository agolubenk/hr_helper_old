"""
Compatibility модуль для финансовых сервисов
Обеспечивает плавную миграцию с старых импортов на новые
"""
import warnings
from logic.finance.tax_service import TaxService as NewTaxService
from logic.finance.salary_service import SalaryService as NewSalaryService


def get_tax_service():
    """
    Возвращает TaxService из logic/finance/
    
    ВХОДЯЩИЕ ДАННЫЕ: Нет
    ИСТОЧНИКИ ДАННЫХ: logic.finance.tax_service.TaxService
    ОБРАБОТКА: Возвращает новый TaxService с предупреждением о deprecation
    ВЫХОДЯЩИЕ ДАННЫЕ: Класс TaxService
    СВЯЗИ: warnings.warn()
    ФОРМАТ: Класс TaxService
    """
    warnings.warn(
        "apps.finance.logic.tax_service.TaxService is deprecated. "
        "Use logic.finance.tax_service.TaxService instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return NewTaxService


def get_salary_service():
    """
    Возвращает SalaryService из logic/finance/
    
    ВХОДЯЩИЕ ДАННЫЕ: Нет
    ИСТОЧНИКИ ДАННЫХ: logic.finance.salary_service.SalaryService
    ОБРАБОТКА: Возвращает новый SalaryService с предупреждением о deprecation
    ВЫХОДЯЩИЕ ДАННЫЕ: Класс SalaryService
    СВЯЗИ: warnings.warn()
    ФОРМАТ: Класс SalaryService
    """
    warnings.warn(
        "apps.finance.logic.salary_service.SalaryService is deprecated. "
        "Use logic.finance.salary_service.SalaryService instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return NewSalaryService


# Для обратной совместимости
TaxService = get_tax_service()
SalaryService = get_salary_service()
