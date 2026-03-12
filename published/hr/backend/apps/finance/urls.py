from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('update-rates/', views.update_currency_rates, name='update_currency_rates'),
    path('grades/add/', views.add_grade, name='add_grade'),
    path('grades/<int:grade_id>/delete/', views.delete_grade, name='delete_grade'),
    
    # PLN Taxes URLs
    path('pln-taxes/', views.pln_taxes_dashboard, name='pln_taxes_dashboard'),
    path('pln-taxes/add/', views.add_pln_tax, name='add_pln_tax'),
    path('pln-taxes/<int:tax_id>/update/', views.update_pln_tax, name='update_pln_tax'),
    path('pln-taxes/<int:tax_id>/delete/', views.delete_pln_tax, name='delete_pln_tax'),
    path('pln-taxes/calculate/', views.calculate_pln_taxes, name='calculate_pln_taxes'),
    
    # Salary Ranges URLs
    path('salary-ranges/', views.salary_ranges_list, name='salary_ranges_list'),
    path('salary-ranges/create/', views.salary_range_create, name='salary_range_create'),
    path('salary-ranges/<int:pk>/', views.salary_range_detail, name='salary_range_detail'),
    path('salary-ranges/<int:pk>/edit/', views.salary_range_edit, name='salary_range_edit'),
    path('salary-ranges/<int:pk>/update/', views.salary_range_update, name='salary_range_update'),
    path('salary-ranges/<int:pk>/delete/', views.salary_range_delete, name='salary_range_delete'),
    path('salary-ranges/update-currency/', views.update_salary_currency_amounts, name='update_salary_currency_amounts'),
    
    # Benchmark URLs
    path('benchmarks/', views.benchmarks_dashboard, name='benchmarks_dashboard'),
    path('benchmarks/list/', views.benchmarks_list, name='benchmarks_list'),
    path('benchmarks/create/', views.benchmark_create, name='benchmark_create'),
    path('benchmarks/<int:pk>/', views.benchmark_detail, name='benchmark_detail'),
    path('benchmarks/<int:pk>/edit/', views.benchmark_edit, name='benchmark_edit'),
    path('benchmarks/<int:pk>/update/', views.benchmark_update, name='benchmark_update'),
    path('benchmarks/<int:pk>/delete/', views.benchmark_delete, name='benchmark_delete'),
    path('benchmarks/settings/', views.benchmark_settings, name='benchmark_settings'),
    
    # HH.ru Analysis URLs
    path('hh-analysis/', views.hh_analysis_dashboard, name='hh_analysis_dashboard'),
    path('hh-analysis/start/', views.start_hh_analysis, name='start_hh_analysis'),
    path('hh-analysis/batch/', views.start_batch_hh_analysis, name='start_batch_hh_analysis'),
    
    # AI Analysis URLs
    path('ai-analysis/', views.ai_analysis_dashboard, name='ai_analysis_dashboard'),
    path('ai-analysis/run/', views.run_ai_analysis, name='run_ai_analysis'),
    path('ai-analysis/update-prompt/', views.update_ai_prompt, name='update_ai_prompt'),
    
    # Task Status URL
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    
    # Настройки hh.ru
    path('benchmarks/settings/', views.benchmarks_settings, name='benchmarks_settings'),
    path('api/hh/start-collection/', views.start_hh_collection_manual, name='start_hh_collection'),
]
