from django.urls import path
from . import views
from . import views_tour

app_name = 'wiki'

urlpatterns = [
    path('', views.wiki_list, name='list'),
    path('page/<slug:slug>/', views.wiki_page_detail, name='page_detail'),
    path('page/<slug:slug>/edit/', views.wiki_page_edit, name='page_edit'),
    path('page/<slug:slug>/delete/', views.wiki_page_delete, name='page_delete'),
    path('create/', views.wiki_page_edit, name='page_create'),
    path('tags/create/', views.wiki_tag_create_api, name='tag_create_api'),
    # Статические страницы-примеры для тура
    path('tour/company-settings/', views_tour.tour_company_settings_example, name='tour_company_settings'),
    path('tour/user-profile/', views_tour.tour_user_profile_example, name='tour_user_profile'),
    path('tour/vacancies/', views_tour.tour_vacancies_example, name='tour_vacancies'),
    path('tour/finance/', views_tour.tour_finance_example, name='tour_finance'),
    path('tour/google-oauth/', views_tour.tour_google_oauth_example, name='tour_google_oauth'),
    path('tour/interviewers/', views_tour.tour_interviewers_example, name='tour_interviewers'),
]

