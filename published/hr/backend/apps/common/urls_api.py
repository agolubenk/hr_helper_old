from django.urls import path
from . import views_api

urlpatterns = [
    path('', views_api.health_check, name='api-health-check'),
]
