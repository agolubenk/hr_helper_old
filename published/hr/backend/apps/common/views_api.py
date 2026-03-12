from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
import redis
from django.conf import settings

# Импорты новых модулей
from logic.utilities.common_api import api_status
from logic.base.response_handler import UnifiedResponseHandler


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Проверка здоровья API
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос
    
    ИСТОЧНИКИ ДАННЫХ:
    - Django database connection
    - Redis connection
    - Django cache
    
    ОБРАБОТКА:
    - Проверка подключения к базе данных
    - Проверка подключения к Redis
    - Проверка работы кэша
    - Формирование статуса здоровья системы
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Response с данными о состоянии системы
    
    СВЯЗИ:
    - Использует: Django database, Redis, cache
    - Передает: DRF Response
    - Может вызываться из: DRF API endpoints
    """
    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'services': {}
    }
    
    # Проверка базы данных
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Проверка Redis
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        redis_client.ping()
        health_status['services']['redis'] = 'healthy'
    except Exception as e:
        health_status['services']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Проверка кэша
    try:
        cache.set('health_check', 'ok', 30)
        cache_result = cache.get('health_check')
        if cache_result == 'ok':
            health_status['services']['cache'] = 'healthy'
        else:
            health_status['services']['cache'] = 'unhealthy'
    except Exception as e:
        health_status['services']['cache'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Определение HTTP статуса
    http_status = 200 if health_status['status'] == 'healthy' else 503
    
    return Response(health_status, status=http_status)
