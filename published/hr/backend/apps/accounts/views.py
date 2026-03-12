"""Views для Accounts приложения - использует новые модули"""
from logic.utilities.user_management import (
    unified_template_view, unified_api_view,
    login_api_handler, logout_api_handler,
    test_gemini_api_handler, test_huntflow_api_handler,
    test_clickup_api_handler, test_notion_api_handler,
    profile_template_handler, profile_edit_template_handler,
    integrations_template_handler,
    api_keys_template_handler, quick_buttons_template_handler,
    google_oauth_redirect,
    google_oauth_callback, unified_login, unified_logout,
    google_oauth_demo, google_oauth_test, oauth_debug
)


def components_template_handler(request):
    """
    Обработчик для страницы демонстрации компонентов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос
    
    ИСТОЧНИКИ ДАННЫХ:
    - ProfileEditForm: форма редактирования профиля
    - Демонстрационные данные пользователя и интеграций
    
    ОБРАБОТКА:
    - Создание экземпляров форм для демонстрации
    - Подготовка демонстрационных данных пользователя
    - Подготовка демонстрационных данных интеграций
    - Создание контекста для шаблона
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с формами и демонстрационными данными
    - render: HTML страница 'accounts/components_demo.html'
    
    СВЯЗИ:
    - Использует: ProfileEditForm
    - Передает данные в: accounts/components_demo.html
    - Может вызываться из: accounts/ URL patterns
    """
    from apps.accounts.forms import ProfileEditForm
    
    # Создаем экземпляры форм для демонстрации
    profile_form = ProfileEditForm()
    
    # Демонстрационные данные
    demo_user = {
        'username': 'demo_user',
        'full_name': 'Иван Иванов',
        'email': 'ivan.ivanov@example.com',
        'telegram_username': '@ivan_ivanov',
        'active_system': 'sandbox',
        'is_observer_active': True,
        'interviewer_calendar_url': 'https://calendar.google.com/calendar/embed?src=example@gmail.com',
    }
    
    # Демонстрационные интеграции
    demo_integrations = {
        'huntflow': {
            'name': 'Huntflow',
            'enabled': True,
            'sandbox_configured': True,
            'prod_configured': False,
            'active_system': 'sandbox',
        },
        'gemini': {
            'name': 'Gemini AI',
            'enabled': True,
            'configured': True,
        },
        'clickup': {
            'name': 'ClickUp',
            'enabled': True,
            'configured': True,
        },
        'telegram': {
            'name': 'Telegram',
            'enabled': True,
            'configured': True,
        }
    }
    
    # Демонстрационные социальные аккаунты
    demo_social_accounts = [
        {
            'provider': 'google',
            'uid': '123456789',
            'extra_data': {'name': 'Иван Иванов', 'email': 'ivan.ivanov@gmail.com'},
            'date_joined': '2024-01-15',
        }
    ]
    
    # Демонстрационная статистика Google
    demo_google_stats = {
        'calendar_events': 15,
        'drive_files': 8,
        'sheets': 3,
    }
    
    context = {
        'profile_form': profile_form,
        'demo_user': demo_user,
        'demo_integrations': demo_integrations,
        'demo_social_accounts': demo_social_accounts,
        'demo_google_stats': demo_google_stats,
    }
    
    return unified_template_view(request, 'temp/components.html', context)