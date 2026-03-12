from django.urls import path
from . import views

app_name = 'hiring_plan'

urlpatterns = [
    # Основная страница - список всех заявок
    path('', views.HiringRequestsListView.as_view(), name='hiring_requests_list'),
    
    # Детальный просмотр и редактирование заявки
    path('requests/<int:pk>/', views.HiringRequestDetailView.as_view(), name='hiring_request_detail'),
    path('requests/create/', views.HiringRequestCreateView.as_view(), name='hiring_request_create'),
    path('requests/<int:pk>/edit/', views.HiringRequestUpdateView.as_view(), name='hiring_request_update'),
    
    # SLA управление (оставляем для настройки SLA)
    path('sla/', views.VacancySLAListView.as_view(), name='sla_list'),
    path('sla/create/', views.VacancySLACreateView.as_view(), name='sla_create'),
    path('sla/<int:pk>/edit/', views.VacancySLAUpdateView.as_view(), name='sla_update'),
    path('sla/get-available-grades/', views.get_available_grades, name='get_available_grades'),
    
    # Метрики и KPI
    path('metrics/', views.MetricsDashboardView.as_view(), name='metrics_dashboard'),
    path('metrics/list/', views.MetricsListView.as_view(), name='metrics_list'),
    path('forecasts/', views.ForecastsListView.as_view(), name='forecasts_list'),
    path('capacity/', views.RecruiterCapacityListView.as_view(), name='recruiter_capacity_list'),
    
    # Годовая таблица заявок
    path('yearly/', views.YearlyHiringPlanView.as_view(), name='yearly_hiring_plan'),
    path('yearly/export.xlsx', views.yearly_hiring_plan_export_excel, name='yearly_hiring_plan_export_excel'),

    # Экспорт/импорт заявок и SLA (JSON)
    path('export-json/', views.hiring_requests_export_json, name='hiring_requests_export_json'),
    path('import-json/', views.hiring_requests_import_json, name='hiring_requests_import_json'),
]

