"""Совместимость для ClickUp Integration приложения"""
import warnings
from apps.clickup_int.views import * as old_clickup_views
from logic.integration.clickup.clickup_service import * as new_clickup_views

def get_clickup_views():
    """Получить views для ClickUp (новые или старые)"""
    warnings.warn(
        "Old clickup views are deprecated. Use logic.integration.clickup.clickup_service",
        DeprecationWarning,
        stacklevel=2
    )
    return new_clickup_views

# Экспорт основных функций для совместимости
dashboard = new_clickup_views.dashboard
settings = new_clickup_views.settings
tasks_list = new_clickup_views.tasks_list
task_detail = new_clickup_views.task_detail
test_connection = new_clickup_views.test_connection
sync_tasks = new_clickup_views.sync_tasks
sync_logs = new_clickup_views.sync_logs
bulk_import = new_clickup_views.bulk_import
bulk_import_status = new_clickup_views.bulk_import_status
