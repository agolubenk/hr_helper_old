from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views
from . import test_views

app_name = 'accounts'

urlpatterns = [
    # Основные маршруты профиля
    path('', login_required(views.unified_template_view), {'template_name': 'profile/profile.html', 'handler_func': views.profile_template_handler}, name='profile'),
    path('edit/', login_required(views.unified_template_view), {'template_name': 'profile/profile_edit.html', 'handler_func': views.profile_edit_template_handler}, name='profile_edit'),
    
    # Интеграции
    path('integrations/', login_required(views.unified_template_view), {'template_name': 'profile/integrations.html', 'handler_func': views.integrations_template_handler}, name='integrations'),
    path('api-keys/', login_required(views.unified_template_view), {'template_name': 'profile/api_keys.html', 'handler_func': views.api_keys_template_handler}, name='api_keys'),
    path('quick-buttons/', login_required(views.unified_template_view), {'template_name': 'profile/quick_buttons.html', 'handler_func': views.quick_buttons_template_handler}, name='quick_buttons'),
    path('components/', login_required(views.unified_template_view), {'template_name': 'account/test_google_oauth.html', 'handler_func': views.components_template_handler}, name='components'),
    
    # Аутентификация
    path('login/', views.unified_login, name='account_login'),
    path('logout/', views.unified_logout, name='account_logout'),
    
    # Google OAuth
    path('google-oauth/', views.google_oauth_redirect, name='google_oauth_redirect'),
    path('google-oauth-callback/', views.google_oauth_callback, name='google_oauth_callback'),
    
    # API тестирование
    path('test-gemini/', views.unified_api_view, {'handler_func': views.test_gemini_api_handler}, name='test_gemini_api'),
    path('test-huntflow/', views.unified_api_view, {'handler_func': views.test_huntflow_api_handler}, name='test_huntflow_api'),
    path('test-clickup/', views.unified_api_view, {'handler_func': views.test_clickup_api_handler}, name='test_clickup_api'),
    path('test-notion/', views.unified_api_view, {'handler_func': views.test_notion_api_handler}, name='test_notion_api'),
    
    # Тестирование прав доступа
    path('test-permissions/', test_views.test_permission_info, name='test_permission_info'),
    path('test-permissions/without/', test_views.test_view_without_permission, name='test_view_without_permission'),
    path('test-permissions/with/', test_views.test_view_with_permission, name='test_view_with_permission'),
    path('test-permissions/huntflow/', test_views.test_view_with_huntflow_permission, name='test_view_with_huntflow_permission'),
    path('test-permissions/admin/', test_views.test_admin_required, name='test_admin_required'),
    path('test-permissions/recruiter/', test_views.test_recruiter_required, name='test_recruiter_required'),
    path('test-permissions/interviewer/', test_views.test_interviewer_required, name='test_interviewer_required'),
    path('test-permissions/observer/', test_views.test_observer_required, name='test_observer_required'),
]