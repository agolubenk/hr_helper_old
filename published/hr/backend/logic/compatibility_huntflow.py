"""Совместимость для Huntflow приложения"""
import warnings
from apps.huntflow.views import * as old_huntflow_views
from logic.integration.huntflow.huntflow_service import * as new_huntflow_views

def get_huntflow_views():
    """
    Получить views для Huntflow (новые или старые)
    
    ВХОДЯЩИЕ ДАННЫЕ: Нет
    ИСТОЧНИКИ ДАННЫЕ: new_huntflow_views модуль
    ОБРАБОТКА: Возврат новых views с предупреждением об устаревании
    ВЫХОДЯЩИЕ ДАННЫЕ: Новые views для Huntflow
    СВЯЗИ: new_huntflow_views
    ФОРМАТ: Модуль views
    """
    warnings.warn(
        "Old huntflow views are deprecated. Use logic.integration.huntflow.huntflow_service",
        DeprecationWarning,
        stacklevel=2
    )
    return new_huntflow_views

# Экспорт основных функций для совместимости
huntflow_dashboard = new_huntflow_views.huntflow_dashboard
vacancies_list = new_huntflow_views.vacancies_list
candidates_list = new_huntflow_views.candidates_list
huntflow_settings = new_huntflow_views.huntflow_settings
huntflow_sync = new_huntflow_views.huntflow_sync
huntflow_test_connection = new_huntflow_views.huntflow_test_connection
huntflow_clear_cache = new_huntflow_views.huntflow_clear_cache
get_correct_account_id = new_huntflow_views.get_correct_account_id
