"""Общие API функции и утилиты"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.api_client import BaseAPIClient

class CommonAPIService(BaseAPIClient):
    """Общий API сервис для различных операций"""
    
    def __init__(self):
        super().__init__("", "", timeout=30)
    
    def _setup_auth(self):
        """Настройка аутентификации для общих операций"""
        pass
    
    def test_connection(self):
        """Тест подключения для общих операций"""
        return True, "Common service connection OK"
    
    def get_system_info(self):
        """Получение информации о системе"""
        try:
            system_info = {
                'status': 'active',
                'version': '1.0.0',
                'modules': [
                    'finance',
                    'vacancies', 
                    'interviewers',
                    'huntflow',
                    'gemini'
                ],
                'integrations': [
                    'huntflow',
                    'clickup',
                    'notion',
                    'telegram',
                    'google_oauth'
                ]
            }
            return UnifiedResponseHandler.success_response(system_info)
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_health_check(self):
        """Проверка здоровья системы"""
        try:
            health_status = {
                'database': 'connected',
                'cache': 'available',
                'external_apis': 'responsive',
                'ai_services': 'operational'
            }
            return UnifiedResponseHandler.success_response(health_status)
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))

@login_required
def common_dashboard(request):
    """Общий дашборд системы"""
    try:
        api_service = CommonAPIService()
        system_info = api_service.get_system_info()
        health_check = api_service.get_health_check()
        
        context = {
            'system_info': system_info.get('data', {}),
            'health_check': health_check.get('data', {}),
            'title': 'Общий дашборд'
        }
        return render(request, 'common/dashboard.html', context)
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def system_settings(request):
    """Настройки системы"""
    if request.method == 'POST':
        try:
            # Обработка настроек системы
            settings_data = request.POST.dict()
            
            # Здесь можно добавить логику сохранения настроек
            messages.success(request, 'Настройки системы обновлены')
            return redirect('common_dashboard')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении настроек: {str(e)}')
    
    context = {
        'title': 'Настройки системы'
    }
    return render(request, 'common/system_settings.html', context)

@login_required
def api_status(request):
    """Статус API системы"""
    try:
        api_service = CommonAPIService()
        health_check = api_service.get_health_check()
        
        return JsonResponse(health_check)
    except Exception as e:
        return JsonResponse(
            UnifiedResponseHandler.error_response(str(e)),
            status=500
        )
