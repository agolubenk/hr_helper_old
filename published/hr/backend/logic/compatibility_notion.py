"""Совместимость для Notion Integration приложения"""
import warnings
from apps.notion_int.views import * as old_notion_views
from logic.integration.notion.notion_service import * as new_notion_views

def get_notion_views():
    """Получить views для Notion (новые или старые)"""
    warnings.warn(
        "Old notion views are deprecated. Use logic.integration.notion.notion_service",
        DeprecationWarning,
        stacklevel=2
    )
    return new_notion_views

# Экспорт основных функций для совместимости
settings = new_notion_views.settings
dashboard = new_notion_views.dashboard
pages_list = new_notion_views.pages_list
page_detail = new_notion_views.page_detail
test_connection = new_notion_views.test_connection
sync_pages = new_notion_views.sync_pages
sync_logs = new_notion_views.sync_logs
bulk_import_view = new_notion_views.bulk_import_view
bulk_import = new_notion_views.bulk_import
bulk_import_status = new_notion_views.bulk_import_status

