from django.urls import path
from . import views

app_name = 'gemini'

urlpatterns = [
    # Главная страница Gemini
    path('', views.gemini_dashboard, name='dashboard'),
    
    # Чат
    path('chat/', views.chat_session, name='new_chat'),
    path('chat/<int:session_id>/', views.chat_session, name='chat_session'),
    
    # Настройки
    path('settings/', views.settings, name='settings'),
    
    # AJAX endpoints
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/test-api-key/', views.test_api_key, name='test_api_key'),
    
    # Управление сессиями
    path('session/<int:session_id>/delete/', views.delete_session, name='delete_session'),
    path('session/<int:session_id>/update-title/', views.update_session_title, name='update_session_title'),
]




