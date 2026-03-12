"""Сериализаторы для Accounts приложения"""
from rest_framework import serializers
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Базовый сериализатор для пользователя
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - username: имя пользователя
    - email: электронная почта
    - first_name, last_name: имя и фамилия
    - full_name: полное имя
    - telegram_username: имя пользователя в Telegram
    - is_active: статус активности
    
    ИСТОЧНИКИ ДАННЫХ:
    - User модель из apps.accounts.models
    - Group модель из django.contrib.auth.models
    
    ОБРАБОТКА:
    - Сериализация полей пользователя
    - Вычисляемые поля: groups (группы пользователя)
    - Автоматическое заполнение системных полей
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями пользователя
    
    СВЯЗИ:
    - Использует: User модель, Group модель
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets
    """
    groups = serializers.StringRelatedField(many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'date_joined', 'last_login', 'is_active',
            'is_staff', 'is_superuser', 'groups'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff', 'is_superuser']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания пользователя
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - username: имя пользователя (обязательно)
    - email: электронная почта (обязательно)
    - password: пароль (обязательно)
    - password_confirm: подтверждение пароля (обязательно)
    - first_name, last_name: имя и фамилия
    - full_name: полное имя
    - telegram_username: имя пользователя в Telegram
    
    ИСТОЧНИКИ ДАННЫХ:
    - User модель из apps.accounts.models
    
    ОБРАБОТКА:
    - Сериализация полей для создания пользователя
    - Валидация пароля
    - Проверка совпадения паролей
    - Создание пользователя с хешированием пароля
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными созданного пользователя
    
    СВЯЗИ:
    - Использует: User модель, validate_password
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (create action)
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'full_name', 'telegram_username'
        ]
    
    def validate(self, attrs):
        """Валидация данных"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs
    
    def create(self, validated_data):
        """Создание пользователя"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Сериализатор для профиля пользователя
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - first_name, last_name: имя и фамилия
    - full_name: полное имя
    - email: электронная почта
    - telegram_username: имя пользователя в Telegram
    
    ИСТОЧНИКИ ДАННЫХ:
    - User модель из apps.accounts.models
    
    ОБРАБОТКА:
    - Сериализация полей профиля пользователя
    - Валидация данных профиля
    - Обновление профиля пользователя
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными профиля пользователя
    
    СВЯЗИ:
    - Использует: User модель
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (profile actions)
    """
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login']


class UserChangePasswordSerializer(serializers.Serializer):
    """
    Сериализатор для смены пароля
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - old_password: старый пароль (обязательно)
    - new_password: новый пароль (обязательно)
    - new_password_confirm: подтверждение нового пароля (обязательно)
    
    ИСТОЧНИКИ ДАННЫХ:
    - request.data: данные для смены пароля
    
    ОБРАБОТКА:
    - Валидация старого пароля
    - Валидация нового пароля
    - Проверка совпадения нового пароля и подтверждения
    - Смена пароля пользователя
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с результатом смены пароля
    
    СВЯЗИ:
    - Использует: validate_password, authenticate
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (change password action)
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        """Валидация старого пароля"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный старый пароль")
        return value
    
    def validate(self, attrs):
        """Валидация данных"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Новые пароли не совпадают")
        return attrs
    
    def save(self):
        """Сохранение нового пароля"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для настроек пользователя
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - gemini_api_key: API ключ для Gemini
    - huntflow_prod_url: URL продакшн Huntflow
    - huntflow_sandbox_url: URL сэндбокс Huntflow
    - clickup_api_key: API ключ для ClickUp
    - notion_api_key: API ключ для Notion
    - telegram_bot_token: токен Telegram бота
    
    ИСТОЧНИКИ ДАННЫХ:
    - User модель из apps.accounts.models
    
    ОБРАБОТКА:
    - Сериализация настроек пользователя
    - Валидация API ключей
    - Обновление настроек пользователя
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с настройками пользователя
    
    СВЯЗИ:
    - Использует: User модель
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (settings actions)
    """
    
    class Meta:
        model = User
        fields = [
            'gemini_api_key', 'clickup_api_key', 'notion_integration_token',
            'huntflow_sandbox_api_key',
            'huntflow_sandbox_url', 'huntflow_prod_url', 'active_system',
            'is_observer_active', 'interviewer_calendar_url'
        ]
    
    def validate_gemini_api_key(self, value):
        """Валидация API ключа Gemini"""
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ Gemini слишком короткий")
        return value
    
    def validate_clickup_api_key(self, value):
        """Валидация API ключа ClickUp"""
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ ClickUp слишком короткий")
        return value
    
    def validate_notion_integration_token(self, value):
        """Валидация Integration Token Notion"""
        if value:
            if len(value) < 20:
                raise serializers.ValidationError("Integration Token слишком короткий")
            if not value.startswith('secret_'):
                raise serializers.ValidationError("Integration Token должен начинаться с 'secret_'")
        return value
    
    def validate_huntflow_sandbox_api_key(self, value):
        """Валидация API ключа Huntflow Sandbox"""
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ Huntflow Sandbox слишком короткий")
        return value
    
    # huntflow_prod_api_key больше не используется, для PROD используются токены
    
    def validate_active_system(self, value):
        """Валидация активной системы"""
        if value not in ['sandbox', 'production']:
            raise serializers.ValidationError("Активная система должна быть 'sandbox' или 'production'")
        return value


class GroupSerializer(serializers.ModelSerializer):
    """
    Сериализатор для групп пользователей
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название группы
    - permissions: разрешения группы
    
    ИСТОЧНИКИ ДАННЫХ:
    - Group модель из django.contrib.auth.models
    
    ОБРАБОТКА:
    - Сериализация полей группы
    - Включение разрешений группы
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями группы
    
    СВЯЗИ:
    - Использует: Group модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Group API viewsets
    """
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'user_count']
    
    def get_user_count(self, obj):
        """Получить количество пользователей в группе"""
        return obj.user_set.count()


class UserStatsSerializer(serializers.Serializer):
    """
    Сериализатор для статистики пользователей
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - total_users: общее количество пользователей
    - active_users: количество активных пользователей
    - users_by_group: статистика по группам
    - recent_users: последние пользователи
    
    ИСТОЧНИКИ ДАННЫЕ:
    - User.objects: агрегированные данные пользователей
    - Group.objects: данные групп
    
    ОБРАБОТКА:
    - Сериализация статистических данных
    - Агрегация данных по различным критериям
    - Формирование структурированной статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект со статистикой пользователей
    
    СВЯЗИ:
    - Использует: User.objects, Group.objects
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (stats action)
    """
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    staff_users = serializers.IntegerField()
    superusers = serializers.IntegerField()
    group_stats = serializers.DictField()
    integrations_stats = serializers.DictField()


class IntegrationStatusSerializer(serializers.Serializer):
    """
    Сериализатор для статуса интеграций
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - integration_name: название интеграции
    - is_configured: статус настройки
    - is_active: статус активности
    - last_sync: последняя синхронизация
    - error_message: сообщение об ошибке
    
    ИСТОЧНИКИ ДАННЫЕ:
    - User модель: настройки пользователя
    - Внешние API: статус интеграций
    
    ОБРАБОТКА:
    - Сериализация статуса интеграций
    - Проверка настройки интеграций
    - Формирование статуса активности
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект со статусом интеграций
    
    СВЯЗИ:
    - Использует: User модель, внешние API
    - Передает данные в: DRF API responses
    - Может вызываться из: User API viewsets (integration status action)
    """
    name = serializers.CharField()
    enabled = serializers.BooleanField()
    configured = serializers.BooleanField()
    connected = serializers.BooleanField(required=False)
    token_valid = serializers.BooleanField(required=False)
    api_key = serializers.CharField(required=False, allow_null=True)
    token = serializers.CharField(required=False, allow_null=True)
    username = serializers.CharField(required=False, allow_null=True)
    active_system = serializers.CharField(required=False, allow_null=True)
    sandbox_configured = serializers.BooleanField(required=False)
    prod_configured = serializers.BooleanField(required=False)


class ApiKeyTestSerializer(serializers.Serializer):
    """
    Сериализатор для тестирования API ключей
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - integration_type: тип интеграции (gemini, huntflow, clickup, notion, telegram)
    - api_key: API ключ для тестирования
    - environment: окружение (sandbox, production)
    
    ИСТОЧНИКИ ДАННЫЕ:
    - request.data: данные для тестирования API ключа
    
    ОБРАБОТКА:
    - Сериализация данных для тестирования API ключа
    - Валидация типа интеграции
    - Проверка окружения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными для тестирования API ключа
    
    СВЯЗИ:
    - Использует: request.data
    - Передает данные в: API тестирование
    - Может вызываться из: User API viewsets (test integration action)
    """
    integration_type = serializers.ChoiceField(choices=[
        ('gemini', 'Gemini AI'),
        ('huntflow', 'Huntflow'),
        ('clickup', 'ClickUp'),
        ('notion', 'Notion'),
    ])
    api_key = serializers.CharField(max_length=500)
    api_url = serializers.URLField(required=False, allow_blank=True)
    system = serializers.ChoiceField(
        choices=[('sandbox', 'Sandbox'), ('production', 'Production')],
        required=False,
        default='sandbox'
    )
