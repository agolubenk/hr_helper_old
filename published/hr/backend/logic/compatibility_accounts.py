"""Совместимость для Accounts приложения"""
import warnings


def get_accounts_views():
    """Получить views для Accounts приложения"""
    warnings.warn(
        "Использование apps.accounts.views устарело. "
        "Используйте logic.utilities.user_management вместо этого.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from logic.utilities.user_management import (
        unified_template_view, unified_api_view,
        login_api_handler, logout_api_handler,
        test_gemini_api_handler, test_huntflow_api_handler,
        test_clickup_api_handler, test_notion_api_handler,
        profile_template_handler, profile_edit_template_handler,
        integrations_template_handler,
        api_keys_template_handler, google_oauth_redirect,
        google_oauth_callback, unified_login, unified_logout,
        google_oauth_demo, google_oauth_test, oauth_debug
    )
    
    return {
        'unified_template_view': unified_template_view,
        'unified_api_view': unified_api_view,
        'login_api_handler': login_api_handler,
        'logout_api_handler': logout_api_handler,
        'test_gemini_api_handler': test_gemini_api_handler,
        'test_huntflow_api_handler': test_huntflow_api_handler,
        'test_clickup_api_handler': test_clickup_api_handler,
        'test_notion_api_handler': test_notion_api_handler,
        'profile_template_handler': profile_template_handler,
        'profile_edit_template_handler': profile_edit_template_handler,
        'integrations_template_handler': integrations_template_handler,
        'api_keys_template_handler': api_keys_template_handler,
        'google_oauth_redirect': google_oauth_redirect,
        'google_oauth_callback': google_oauth_callback,
        'unified_login': unified_login,
        'unified_logout': unified_logout,
        'google_oauth_demo': google_oauth_demo,
        'google_oauth_test': google_oauth_test,
        'oauth_debug': oauth_debug,
    }
