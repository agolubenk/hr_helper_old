"""
Документация по проблемным импортам (линтер):
- django.urls — маршрутизация URL для Google OAuth

Влияние: подключение путей (login/callback/drive/calendar/chat) не будет работать
при отсутствии модуля, что делает весь набор URL недоступным.
"""
from django.urls import path
from . import views
from . import views_simple
from . import views_new

app_name = 'google_oauth'

urlpatterns = [
    # Основные страницы
    path('', views.dashboard, name='dashboard'),
    
    # OAuth
    path('oauth/start/', views.google_oauth_start, name='oauth_start'),
    path('oauth/callback/', views.google_oauth_callback, name='oauth_callback'),
    path('disconnect/', views.disconnect_google, name='disconnect'),
    
    # Календарь
    path('calendar/', views.calendar_events, name='calendar_events'),
    
    # Синхронизация
    path('sync/calendar/', views.sync_calendar, name='sync_calendar'),
    path('sync/drive/', views.sync_drive, name='sync_drive'),
    
    # Тестирование
    path('test/oauth/', views.test_oauth, name='test_oauth'),
    path('test/oauth-url/', views.test_oauth_url, name='test_oauth_url'),
    path('test/check-integration/', views.check_integration, name='check_integration'),
    
    # API endpoints
    path('api/event/<str:event_id>/', views.get_event_details, name='get_event_details'),
    path('api/meetings-count/', views.get_meetings_count, name='get_meetings_count'),
    path('api/slots-settings/', views.api_slots_settings, name='api_slots_settings'),
    path('api/calendar-events/', views.api_calendar_events, name='api_calendar_events'),
    path('api/interviewers-autocomplete/', views.api_interviewers_autocomplete, name='api_interviewers_autocomplete'),
    path('api/interview-slots/', views.api_interview_slots, name='api_interview_slots'),
    path('api/third-week-slots/', views.api_third_week_slots, name='api_third_week_slots'),
    path('api/weekly-reports/', views.api_weekly_reports, name='api_weekly_reports'),
    path('debug/cache/', views.debug_cache, name='debug_cache'),
    
    # Инвайты
    path('invites/', views.invite_dashboard, name='invite_dashboard'),
    path('invites/list/', views.invite_list, name='invite_list'),
    path('invites/create/', views.invite_create, name='invite_create'),
    path('invites/create/combined/', views.invite_create_combined, name='invite_create_combined'),
    path('invites/<int:pk>/', views.invite_detail, name='invite_detail'),
    path('invites/<int:pk>/edit/', views.invite_update, name='invite_update'),
    path('invites/<int:pk>/delete/', views.invite_delete, name='invite_delete'),
    path('invites/<int:pk>/regenerate-scorecard/', views.invite_regenerate_scorecard, name='invite_regenerate_scorecard'),
    path('invites/<int:pk>/invitation-text/', views.get_invitation_text, name='get_invitation_text'),
    path('invites/<int:pk>/parser-time-analysis/', views.get_parser_time_analysis, name='get_parser_time_analysis'),
    
    # Настройки структуры папок
    path('invites/settings/', views.scorecard_path_settings, name='scorecard_path_settings'),
    path('api/scorecard-path-settings/', views.api_scorecard_path_settings, name='api_scorecard_path_settings'),
    
    # HR-скрининги
    path('hr-screening/', views.hr_screening_list, name='hr_screening_list'),
    path('hr-screening/create/', views.hr_screening_create, name='hr_screening_create'),
    path('hr-screening/<int:pk>/', views.hr_screening_detail, name='hr_screening_detail'),
    path('hr-screening/<int:pk>/delete/', views.hr_screening_delete, name='hr_screening_delete'),
    path('hr-screening/<int:pk>/retry-analysis/', views.hr_screening_retry_analysis, name='hr_screening_retry_analysis'),
    path('reject-candidate/<int:hr_screening_id>/', views.reject_candidate, name='reject_candidate'),
    
    # Объединенный рабочий процесс
    path('combined-workflow/', views.combined_workflow, name='combined_workflow'),
    
    # Чат-интерфейс
    path('chat/', views.chat_workflow, name='chat_workflow'),
    path('chat/<int:session_id>/', views.chat_workflow, name='chat_workflow_session'),
    path('chat/<int:session_id>/ajax/', views.chat_ajax_handler, name='chat_ajax_handler'),
    path('chat/<int:session_id>/update-title/', views.update_chat_title, name='update_chat_title'),
    
    # Новый чат-интерфейс
    path('chat-new/', views_new.chat_workflow_new, name='chat_workflow_new'),
    path('chat-new/<int:vacancy_id>/', views_new.chat_workflow_new, name='chat_workflow_new_vacancy'),
    path('chat-new/<int:session_id>/ajax/', views_new.chat_ajax_handler_new, name='chat_ajax_handler_new'),
    
    # AJAX API для отправки сообщений
    path('api/send-message/', views.send_chat_message, name='send_chat_message'),
    
    # AJAX API для чат-воркфлоу
    # path('api/chat/vacancy/<int:vacancy_id>/', views.api_chat_vacancy_data, name='api_chat_vacancy_data'),
    # path('api/chat/sessions/', views.api_chat_sessions, name='api_chat_sessions'),
    
    # G-данные и автоматизация
    path('gdata-automation/', views.gdata_automation, name='gdata_automation'),
    
    # Старые маршруты для совместимости
    path('start/', views.google_oauth_start, name='oauth_start_old'),
    path('callback/', views_simple.google_oauth_callback_simple, name='oauth_callback_old'),
    path('calendar-view/', views.calendar_view, name='calendar_view'),
    path('sheets/', views.sheets_view, name='sheets'),
    path('sync/sheets/', views.sync_sheets, name='sync_sheets'),
    path('sync/all/', views.sync_all, name='sync_all'),
]
