"""
URLs для приложения отчетности
"""
from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    path('', views.report_dashboard, name='dashboard'),
    path('export-events-json/', views.export_calendar_events_json, name='export_calendar_events_json'),
    path('import-events-json/', views.import_calendar_events_json, name='import_calendar_events_json'),
    path('company/', views.company_report, name='company_report'),
    path('company/export/', views.export_company_report_excel, name='export_company_report_excel'),
    path('recruiters/summary/', views.recruiters_summary_report, name='recruiters_summary_report'),
    path('recruiters/summary/export/', views.export_recruiters_summary_excel, name='export_recruiters_summary_excel'),
    path('recruiter/', views.recruiter_report, name='recruiter_list'),
    path('recruiter/<int:recruiter_id>/', views.recruiter_report, name='recruiter_report'),
    path('recruiter/<int:recruiter_id>/export/', views.export_recruiter_report_excel, name='export_recruiter_report_excel'),
    path('vacancy/', views.vacancy_report, name='vacancy_list'),
    path('vacancy/<int:vacancy_id>/', views.vacancy_report, name='vacancy_report'),
    path('vacancy/<int:vacancy_id>/export/', views.export_vacancy_report_excel, name='export_vacancy_report_excel'),
    path('interviewer/', views.interviewer_report, name='interviewer_list'),
    path('interviewer/<int:interviewer_id>/', views.interviewer_report, name='interviewer_report'),
    path('interviewer/<int:interviewer_id>/export/', views.export_interviewer_report_excel, name='export_interviewer_report_excel'),
    path('interviewers/list/export/', views.export_interviewers_list_excel, name='export_interviewers_list_excel'),
    path('api/data/', views.api_report_data, name='api_report_data'),
    path('api/sync/', views.sync_calendar_events, name='api_sync_events'),
]

