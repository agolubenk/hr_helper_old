"""
Сериализаторы для API с использованием сервисного слоя
Объединяет логику из serializers.py с сервисными методами
"""
from rest_framework import serializers
from django.contrib.auth.models import Group
from ..models import User
from .user_service import UserService


class GroupSerializer(serializers.ModelSerializer):
    """Сериализатор для групп пользователей"""
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions']
        depth = 1


class UserSerializer(serializers.ModelSerializer):
    """Основной сериализатор пользователя"""
    groups = GroupSerializer(many=True, read_only=True)
    groups_display = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    is_recruiter = serializers.SerializerMethodField()
    is_interviewer = serializers.SerializerMethodField()
    is_observer = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'groups', 'groups_display',
            'gemini_api_key', 'clickup_api_key', 'notion_integration_token',
            'huntflow_prod_url',
            'huntflow_sandbox_url', 'huntflow_sandbox_api_key',
            'active_system', 'interviewer_calendar_url',
            'is_observer_active', 'is_active', 'is_staff', 'is_superuser',
            'is_admin', 'is_recruiter', 'is_interviewer', 'is_observer',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_admin', 'is_recruiter', 'is_interviewer', 'is_observer']
        extra_kwargs = {
            'password': {'write_only': True},
            'gemini_api_key': {'write_only': True},
            'clickup_api_key': {'write_only': True},
            'notion_integration_token': {'write_only': True},
            'huntflow_sandbox_api_key': {'write_only': True},
        }
    
    def get_groups_display(self, obj):
        return [group.name for group in obj.groups.all()]
    
    def get_is_admin(self, obj):
        return obj.is_admin
    
    def get_is_recruiter(self, obj):
        return obj.is_recruiter
    
    def get_is_interviewer(self, obj):
        return obj.is_interviewer
    
    def get_is_observer(self, obj):
        return obj.is_observer
    
    def create(self, validated_data):
        """Создание пользователя с хешированием пароля"""
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        """Обновление пользователя с хешированием пароля"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания пользователя"""
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'password', 'password_confirm',
            'gemini_api_key', 'clickup_api_key', 'notion_integration_token',
            'huntflow_prod_url',
            'huntflow_sandbox_url', 'huntflow_sandbox_api_key',
            'active_system', 'interviewer_calendar_url',
            'is_observer_active', 'is_active', 'is_staff'
        ]
    
    def validate(self, attrs):
        """Валидация паролей"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs
    
    def create(self, validated_data):
        """Создание пользователя с использованием сервисного слоя"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        validated_data['password'] = password
        
        # Используем сервисный слой для создания пользователя
        return UserService.create_user_with_observer_role(validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля пользователя (без чувствительных данных)"""
    groups_display = serializers.SerializerMethodField()
    is_admin = serializers.ReadOnlyField()
    is_recruiter = serializers.ReadOnlyField()
    is_interviewer = serializers.ReadOnlyField()
    is_observer = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telegram_username', 'groups_display',
            'active_system', 'interviewer_calendar_url',
            'is_observer_active', 'is_active', 'is_staff',
            'is_admin', 'is_recruiter', 'is_interviewer', 'is_observer',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login']
    
    def get_groups_display(self, obj):
        return [group.name for group in obj.groups.all()]


class UserChangePasswordSerializer(serializers.Serializer):
    """Сериализатор для смены пароля"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        """Проверка старого пароля"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный старый пароль")
        return value
    
    def validate(self, attrs):
        """Валидация новых паролей"""
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
    """Сериализатор для настроек пользователя с использованием сервисного слоя"""
    
    class Meta:
        model = User
        fields = [
            'gemini_api_key', 'clickup_api_key', 'notion_integration_token',
            'huntflow_prod_url',
            'huntflow_sandbox_url', 'huntflow_sandbox_api_key',
            'active_system', 'interviewer_calendar_url',
            'is_observer_active'
        ]
    
    def update(self, instance, validated_data):
        """Обновление настроек пользователя с использованием сервисного слоя"""
        return UserService.update_user_api_keys(instance, validated_data)


class UserStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики пользователей"""
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    staff_users = serializers.IntegerField()
    groups_stats = serializers.DictField()
    
    @classmethod
    def get_stats(cls):
        """Получение статистики через сервисный слой"""
        return UserService.get_user_stats()
