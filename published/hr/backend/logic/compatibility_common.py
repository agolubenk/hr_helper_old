"""Переходные импорты для Common приложения"""
import warnings

# Импортируем новые модули
from logic.utilities.common_api import common_dashboard, system_settings, api_status
from logic.utilities.context_helpers import ContextHelper, DataHelper, SearchHelper, PermissionHelper
from logic.utilities.template_helpers import TemplateHelper, FormHelper, ValidationHelper, DataFormatHelper, ResponseHelper

# Предупреждение о переходе
warnings.warn(
    "Old common views are deprecated. Use logic.utilities.common_api",
    DeprecationWarning,
    stacklevel=2
)

def get_common_views():
    """Получить views для Common (новые или старые)"""
    return {
        'common_dashboard': common_dashboard,
        'system_settings': system_settings,
        'api_status': api_status
    }

def get_context_helpers():
    """Получить помощники контекста"""
    return {
        'ContextHelper': ContextHelper,
        'DataHelper': DataHelper,
        'SearchHelper': SearchHelper,
        'PermissionHelper': PermissionHelper
    }

def get_template_helpers():
    """Получить помощники шаблонов"""
    return {
        'TemplateHelper': TemplateHelper,
        'FormHelper': FormHelper,
        'ValidationHelper': ValidationHelper,
        'DataFormatHelper': DataFormatHelper,
        'ResponseHelper': ResponseHelper
    }
