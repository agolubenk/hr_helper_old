from rest_framework import serializers
from .models import HuntflowCache, HuntflowLog
from apps.accounts.models import User


class HuntflowCacheSerializer(serializers.ModelSerializer):
    """
    Сериализатор для кэша Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - cache_key: ключ кэша
    - data: данные кэша
    - expires_at: время истечения кэша
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowCache модель из apps.huntflow.models
    
    ОБРАБОТКА:
    - Сериализация полей кэша
    - Вычисляемые поля: is_expired, age_minutes
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями кэша и статусом
    
    СВЯЗИ:
    - Использует: HuntflowCache модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Huntflow API viewsets
    """
    is_expired = serializers.ReadOnlyField()
    age_minutes = serializers.ReadOnlyField()
    
    class Meta:
        model = HuntflowCache
        fields = [
            'id', 'cache_key', 'data', 'created_at', 'updated_at',
            'expires_at', 'is_expired', 'age_minutes'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_expired', 'age_minutes']


class HuntflowLogSerializer(serializers.ModelSerializer):
    """
    Сериализатор для логов Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - log_type: тип лога
    - endpoint: эндпоинт API
    - method: HTTP метод
    - status_code: код статуса ответа
    - request_data, response_data: данные запроса и ответа
    - error_message: сообщение об ошибке
    - user: пользователь, выполнивший запрос
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowLog модель из apps.huntflow.models
    - User модель из apps.accounts.models
    
    ОБРАБОТКА:
    - Сериализация полей лога
    - Вычисляемые поля: user_username, is_success, is_error
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями лога и статусом
    
    СВЯЗИ:
    - Использует: HuntflowLog модель, User модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Huntflow API viewsets
    """
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_success = serializers.ReadOnlyField()
    is_error = serializers.ReadOnlyField()
    
    class Meta:
        model = HuntflowLog
        fields = [
            'id', 'log_type', 'endpoint', 'method', 'status_code',
            'request_data', 'response_data', 'error_message',
            'user', 'user_username', 'created_at', 'is_success', 'is_error'
        ]
        read_only_fields = ['id', 'created_at', 'is_success', 'is_error']


class HuntflowLogCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания логов Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - log_type: тип лога
    - endpoint: эндпоинт API
    - method: HTTP метод
    - status_code: код статуса ответа
    - request_data, response_data: данные запроса и ответа
    - error_message: сообщение об ошибке
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowLog модель из apps.huntflow.models
    
    ОБРАБОТКА:
    - Создание нового лога Huntflow
    - Валидация данных лога
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными созданного лога
    
    СВЯЗИ:
    - Использует: HuntflowLog модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Huntflow API viewsets
    """
    
    class Meta:
        model = HuntflowLog
        fields = [
            'log_type', 'endpoint', 'method', 'status_code',
            'request_data', 'response_data', 'error_message'
        ]


class HuntflowStatsSerializer(serializers.Serializer):
    """
    Сериализатор для статистики Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - total_logs: общее количество логов
    - success_logs: количество успешных логов
    - error_logs: количество ошибочных логов
    - logs_by_type: логи по типам
    - logs_by_user: логи по пользователям
    - recent_logs: последние логи
    - cache_stats: статистика кэша
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowLog модель из apps.huntflow.models
    - HuntflowCache модель из apps.huntflow.models
    
    ОБРАБОТКА:
    - Агрегация статистики по логам и кэшу
    - Подсчет количества логов по типам и пользователям
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект со статистикой Huntflow
    
    СВЯЗИ:
    - Использует: HuntflowLog модель, HuntflowCache модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Huntflow API viewsets
    """
    total_logs = serializers.IntegerField()
    success_logs = serializers.IntegerField()
    error_logs = serializers.IntegerField()
    logs_by_type = serializers.DictField()
    logs_by_user = serializers.DictField()
    recent_logs = HuntflowLogSerializer(many=True)
    cache_stats = serializers.DictField()


class HuntflowApiRequestSerializer(serializers.Serializer):
    """
    Сериализатор для API запросов Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - endpoint: эндпоинт API
    - method: HTTP метод (GET, POST, PATCH, DELETE)
    - data: данные запроса (опционально)
    - params: параметры запроса (опционально)
    - use_cache: использовать ли кэш
    - cache_timeout: время жизни кэша в секундах
    
    ИСТОЧНИКИ ДАННЫХ:
    - Пользовательский ввод для API запросов
    
    ОБРАБОТКА:
    - Валидация параметров API запроса
    - Настройка кэширования
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с параметрами API запроса
    
    СВЯЗИ:
    - Использует: данные пользователя
    - Передает данные в: DRF API responses
    - Может вызываться из: Huntflow API viewsets
    """
    endpoint = serializers.CharField(max_length=500)
    method = serializers.ChoiceField(choices=['GET', 'POST', 'PATCH', 'DELETE'])
    data = serializers.JSONField(required=False, default=dict)
    params = serializers.JSONField(required=False, default=dict)
    use_cache = serializers.BooleanField(default=True)
    cache_timeout = serializers.IntegerField(default=300, min_value=0)
