# Управление Chrome-расширением — отдельный пункт меню (вне раздела Huntflow)
# URL: /extension/
from django.urls import path
from . import views

app_name = 'extension'

urlpatterns = [
    path('', views.chrome_extension_management, name='management'),
    path('link/<int:link_id>/', views.chrome_extension_link_ajax, name='link_ajax'),
    path('resume-link/<int:link_id>/', views.chrome_extension_resume_link_delete_ajax, name='resume_link_delete'),
    path('thread/<int:thread_id>/', views.chrome_extension_thread_ajax, name='thread_ajax'),
    path('clear-cache/', views.chrome_extension_clear_cache_ajax, name='clear_cache'),
    path('level/<str:vacancy_name>/<str:level>/text/', views.chrome_extension_level_text_ajax, name='level_text'),
]
