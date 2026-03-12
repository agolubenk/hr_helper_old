"""
Утилиты для работы с настройками компании
"""
from apps.finance.models import Grade


def get_active_grades_queryset():
    """
    Получает queryset активных грейдов компании.
    Если активные грейды не выбраны - возвращает все грейды.
    
    Returns:
        QuerySet: queryset грейдов для использования в формах, views, serializers
    """
    from .models import CompanySettings
    
    settings = CompanySettings.get_settings()
    active_grades = settings.active_grades.all()
    
    # Если активные грейды не выбраны - возвращаем все грейды
    if not active_grades.exists():
        return Grade.objects.all()
    
    # Возвращаем только активные грейды
    return active_grades


def get_all_grades_queryset():
    """
    Получает queryset всех грейдов (для админки и полного выбора).
    Используется когда нужно показать все грейды, включая неактивные.
    
    Returns:
        QuerySet: queryset всех грейдов
    """
    return Grade.objects.all()
