"""Сериализаторы для Accounts приложения"""
from rest_framework import serializers
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Базовый сериализатор для пользователя
    """
    groups = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'linkedin_url', 'date_joined', 'last_login', 'is_active',
            'is_staff', 'is_superuser', 'groups'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff', 'is_superuser']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания пользователя
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
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Сериализатор для профиля пользователя
    """
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'linkedin_url', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login']


class UserChangePasswordSerializer(serializers.Serializer):
    """
    Сериализатор для смены пароля
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный старый пароль")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Новые пароли не совпадают")
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для настроек пользователя (страница /accounts/api-keys/).
    Включает выбор предпочтительной AI-модели.
    """
    available_ai_models = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'gemini_api_key', 'clickup_api_key', 'notion_integration_token',
            'huntflow_sandbox_api_key',
            'huntflow_sandbox_url', 'huntflow_prod_url', 'active_system',
            'is_observer_active', 'interviewer_calendar_url',
            'preferred_ai_model',
            'available_ai_models',
        ]

    def get_available_ai_models(self, obj):
        """Возвращает список доступных моделей для select на фронте."""
        from logic.ai_analysis.gemini_services import GeminiService
        return GeminiService.AVAILABLE_MODELS

    def validate_gemini_api_key(self, value):
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ Gemini слишком короткий")
        return value

    def validate_clickup_api_key(self, value):
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ ClickUp слишком короткий")
        return value

    def validate_notion_integration_token(self, value):
        if value:
            if len(value) < 20:
                raise serializers.ValidationError("Integration Token слишком короткий")
            if not (value.startswith('secret_') or value.startswith('ntn_')):
                raise serializers.ValidationError("Integration Token должен начинаться с 'secret_' или 'ntn_'")
        return value

    def validate_huntflow_sandbox_api_key(self, value):
        if value and len(value) < 10:
            raise serializers.ValidationError("API ключ Huntflow Sandbox слишком короткий")
        return value

    def validate_active_system(self, value):
        if value not in ['sandbox', 'production']:
            raise serializers.ValidationError("Активная система должна быть 'sandbox' или 'production'")
        return value

    def validate_preferred_ai_model(self, value):
        from logic.ai_analysis.gemini_services import GeminiService
        valid_values = [m['value'] for m in GeminiService.AVAILABLE_MODELS]
        if value and value not in valid_values:
            raise serializers.ValidationError(
                f"Недопустимая модель. Доступные: {', '.join(valid_values)}"
            )
        return value


class GroupSerializer(serializers.ModelSerializer):
    """
    Сериализатор для групп пользователей
    """
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'user_count']

    def get_user_count(self, obj):
        return obj.user_set.count()


class UserStatsSerializer(serializers.Serializer):
    """
    Сериализатор для статистики пользователей
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
    Сериализатор для тестирования API ключей.
    Поддерживает передачу модели для Gemini.
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
    model = serializers.CharField(
        max_length=64,
        required=False,
        default='gemini-2.0-flash',
        help_text="Модель Gemini для тестирования (только для integration_type=gemini)"
    )
