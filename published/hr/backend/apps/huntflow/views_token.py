from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
import json
from .token_service import HuntflowTokenService

@method_decorator([login_required, csrf_exempt], name='dispatch')
class HuntflowTokenAPIView(View):
    """API View для управления токенами Huntflow"""
    
    def post(self, request):
        """Устанавливает токены Huntflow для пользователя"""
        try:
            data = json.loads(request.body)
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            
            if not access_token or not refresh_token:
                return JsonResponse({
                    'success': False,
                    'error': 'Необходимо указать access_token и refresh_token'
                })
            
            # Устанавливаем токены
            request.user.set_huntflow_tokens(
                access_token=access_token,
                refresh_token=refresh_token
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Токены успешно сохранены'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def get(self, request):
        """Получает статус токенов"""
        token_service = HuntflowTokenService(request.user)
        status = token_service.validate_token_setup()
        
        return JsonResponse({
            'success': True,
            'status': status
        })

@login_required
@csrf_exempt
def refresh_huntflow_token_view(request):
    """Обновляет access token"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})
    
    token_service = HuntflowTokenService(request.user)
    
    if token_service.refresh_access_token():
        return JsonResponse({
            'success': True,
            'message': 'Токен успешно обновлен'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Не удалось обновить токен'
        })

@login_required
def test_huntflow_connection_view(request):
    """Тестирует подключение к Huntflow с текущими токенами"""
    try:
        from .services import HuntflowService
        service = HuntflowService(request.user)
        
        # Пробуем получить информацию о пользователе
        result = service._make_request('GET', '/me')
        
        if result:
            return JsonResponse({
                'success': True,
                'message': 'Подключение успешно',
                'user_info': {
                    'name': result.get('name'),
                    'email': result.get('email')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Не удалось подключиться к API'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
