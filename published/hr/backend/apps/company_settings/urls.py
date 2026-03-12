from django.urls import path
from . import views

app_name = 'company_settings'

urlpatterns = [
    path('', views.company_settings_overview, name='overview'),
    path('basic/', views.company_settings_basic, name='basic'),
    path('grades/', views.company_settings_grades, name='grades'),
    path('templates/', views.company_settings_templates, name='templates'),
    path('vacancy-prompt/', views.company_settings_vacancy_prompt, name='vacancy_prompt'),
    path('vacancy-prompt/api/', views.vacancy_prompt_api, name='vacancy_prompt_api'),
    # API endpoints
    path('api/', views.company_settings_api, name='company_settings_api'),
    path('rejection-templates/api/', views.rejection_templates_api, name='rejection_templates_api'),
    path('active-grades/api/', views.active_grades_api, name='active_grades_api'),
    path('rejection-templates/create/', views.rejection_template_create_api, name='rejection_template_create_api'),
    path('rejection-templates/<int:template_id>/update/', views.rejection_template_update_api, name='rejection_template_update_api'),
    path('rejection-templates/<int:template_id>/delete/', views.rejection_template_delete_api, name='rejection_template_delete_api'),
    path('rejection-templates/<int:template_id>/get/', views.rejection_template_get_api, name='rejection_template_get_api'),
]

