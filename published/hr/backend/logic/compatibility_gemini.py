"""Совместимость для Gemini приложения"""
import warnings


def get_gemini_views():
    """Получить views для Gemini приложения"""
    warnings.warn(
        "Использование apps.gemini.views устарело. "
        "Используйте logic.ai_analysis.gemini_management вместо этого.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from logic.ai_analysis.gemini_management import (
        gemini_dashboard, chat_session, settings, send_message,
        delete_session, test_api_key, update_session_title
    )
    
    return {
        'gemini_dashboard': gemini_dashboard,
        'chat_session': chat_session,
        'settings': settings,
        'send_message': send_message,
        'delete_session': delete_session,
        'test_api_key': test_api_key,
        'update_session_title': update_session_title,
    }

