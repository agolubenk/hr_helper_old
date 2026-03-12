"""Совместимость для Google OAuth приложения"""
import warnings


def get_google_oauth_views():
    """Получить views для Google OAuth приложения"""
    warnings.warn(
        "Использование apps.google_oauth.views устарело. "
        "Используйте logic.integration.oauth.oauth_management вместо этого.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from logic.integration.oauth.oauth_management import (
        google_oauth_start, google_oauth_callback, google_oauth_dashboard,
        google_oauth_disconnect, google_sync_data, google_ai_analysis,
        google_settings, determine_action_type_from_text
    )
    
    return {
        'google_oauth_start': google_oauth_start,
        'google_oauth_callback': google_oauth_callback,
        'google_oauth_dashboard': google_oauth_dashboard,
        'google_oauth_disconnect': google_oauth_disconnect,
        'google_sync_data': google_sync_data,
        'google_ai_analysis': google_ai_analysis,
        'google_settings': google_settings,
        'determine_action_type_from_text': determine_action_type_from_text,
    }

