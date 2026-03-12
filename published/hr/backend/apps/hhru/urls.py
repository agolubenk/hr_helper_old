from django.urls import path
from . import views

app_name = 'hhru'

urlpatterns = [
    # Корень: OAuth callback (GET ?code=...) или редирект на дашборд
    path('', views.root_view, name='oauth_callback'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('oauth/authorize/', views.oauth_authorize, name='oauth_authorize'),

    # Конфигурации OAuth
    path('configurations/', views.configurations_list, name='configurations_list'),
    path('configurations/create/', views.configuration_create, name='configuration_create'),
    path('configurations/<int:pk>/edit/', views.configuration_edit, name='configuration_edit'),
    path('configurations/<int:pk>/delete/', views.configuration_delete, name='configuration_delete'),

    # Аккаунты
    path('accounts/', views.accounts_list, name='accounts_list'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),

    # Логи
    path('logs/', views.logs_list, name='logs_list'),

    # ID работодателя (ручная настройка)
    path('employer-id/', views.employer_id_set, name='employer_id_set'),

    # Вакансии HH.ru (активные и архивные) + связь с локальными по huntflow_id
    path('vacancies/active/', views.vacancies_active, name='vacancies_active'),
    path('vacancies/archived/', views.vacancies_archived, name='vacancies_archived'),
    path('vacancies/<str:hh_vacancy_id>/responses/', views.vacancy_responses, name='vacancy_responses'),
    path('ajax/vacancy-link/', views.vacancy_link_save_ajax, name='vacancy_link_save_ajax'),
    path('ajax/change-negotiation-status/', views.change_negotiation_status_ajax, name='change_negotiation_status_ajax'),
    path('ajax/check-huntflow/', views.check_huntflow_ajax, name='check_huntflow_ajax'),
    path('ajax/update-huntflow-link/', views.update_huntflow_link_ajax, name='update_huntflow_link_ajax'),

    # AJAX
    path('ajax/test-connection/', views.test_connection_ajax, name='test_connection_ajax'),
    path('ajax/refresh-token/', views.refresh_token_ajax, name='refresh_token_ajax'),
]
