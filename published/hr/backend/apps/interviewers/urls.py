from django.urls import path
from . import views

app_name = 'interviewers'

urlpatterns = [
    # Дашборд
    path('', views.interviewer_dashboard, name='dashboard'),
    
    # CRUD операции
    path('list/', views.interviewer_list, name='interviewer_list'),
    path('list/export-json/', views.export_interviewers_json, name='export_interviewers_json'),
    path('list/import-json/', views.import_interviewers_json, name='import_interviewers_json'),
    path('create/', views.interviewer_create, name='interviewer_create'),
    path('<int:pk>/', views.interviewer_detail, name='interviewer_detail'),
    path('<int:pk>/edit/', views.interviewer_edit, name='interviewer_edit'),
    path('<int:pk>/delete/', views.interviewer_delete, name='interviewer_delete'),
    
    # AJAX операции
    path('<int:pk>/toggle-active/', views.interviewer_toggle_active, name='interviewer_toggle_active'),
    
    # Правила привлечения интервьюеров
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/create/', views.rule_create, name='rule_create'),
    path('rules/<int:pk>/', views.rule_detail, name='rule_detail'),
    path('rules/<int:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<int:pk>/delete/', views.rule_delete, name='rule_delete'),
    path('rules/<int:pk>/toggle-active/', views.rule_toggle_active, name='rule_toggle_active'),
    
    # Автозаполнение календарей
    path('auto-fill-calendar/', views.auto_fill_calendar, name='auto_fill_calendar'),
    path('auto-fill-all-calendars/', views.auto_fill_all_calendars, name='auto_fill_all_calendars'),
]
