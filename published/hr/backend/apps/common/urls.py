"""
URL маршруты для приложения common
"""
from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    # Политика конфиденциальности (публичная, без входа)
    path('privacy/', views.privacy_policy_view, name='privacy'),
    # Обработчики ошибок
    path('404/', views.custom_404_view, name='404'),
    path('500/', views.custom_500_view, name='500'),
    path('403/', views.custom_403_view, name='403'),
    
    # Тестовые страницы для отладки
    path('test-404/', views.test_404_view, name='test_404'),
    path('test-500/', views.test_500_view, name='test_500'),
    path('test-403/', views.test_403_view, name='test_403'),
    path('debug-image/', views.debug_image_view, name='debug_image'),
]
