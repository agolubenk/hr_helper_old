"""Переходные импорты для Vacancies приложения"""
import warnings

# Импортируем новые модули
from logic.candidate.vacancy_management import (
    vacancy_list, vacancy_detail, vacancy_create, 
    vacancy_update, vacancy_delete, vacancy_duplicate
)
from logic.candidate.vacancy_api import VacancyViewSet
from logic.integration.vacancy_services import VacancyIntegrationService

# Предупреждение о переходе
warnings.warn(
    "Old vacancies views are deprecated. Use logic.candidate.vacancy_management",
    DeprecationWarning,
    stacklevel=2
)

def get_vacancy_views():
    """Получить views для вакансий (новые или старые)"""
    return {
        'vacancy_list': vacancy_list,
        'vacancy_detail': vacancy_detail,
        'vacancy_create': vacancy_create,
        'vacancy_update': vacancy_update,
        'vacancy_delete': vacancy_delete,
        'vacancy_duplicate': vacancy_duplicate
    }

def get_vacancy_api():
    """Получить API для вакансий"""
    return {
        'VacancyViewSet': VacancyViewSet
    }

def get_vacancy_services():
    """Получить сервисы для вакансий"""
    return {
        'VacancyIntegrationService': VacancyIntegrationService
    }

