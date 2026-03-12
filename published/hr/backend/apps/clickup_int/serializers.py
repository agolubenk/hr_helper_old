from rest_framework import serializers
from .models import ClickUpSettings, ClickUpTask, ClickUpSyncLog, ClickUpBulkImport
from apps.accounts.models import User


class ClickUpSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек ClickUp"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    path_description = serializers.SerializerMethodField()
    
    class Meta:
        model = ClickUpSettings
        fields = [
            'id', 'user', 'user_username', 'team_id', 'space_id', 'folder_id',
            'list_id', 'auto_sync', 'sync_interval', 'path_description',
            'created_at', 'updated_at', 'last_sync_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'path_description']
    
    def get_path_description(self, obj):
        """Возвращает описание пути к задачам"""
        return obj.get_path_description()


class ClickUpTaskSerializer(serializers.ModelSerializer):
    """Сериализатор для задач ClickUp"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    assignees_display = serializers.SerializerMethodField()
    tags_display = serializers.SerializerMethodField()
    attachments_display = serializers.SerializerMethodField()
    custom_fields_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ClickUpTask
        fields = [
            'id', 'task_id', 'name', 'description', 'status', 'priority',
            'date_created', 'date_updated', 'due_date', 'url',
            'assignees', 'assignees_display', 'tags', 'tags_display',
            'attachments', 'attachments_display', 'custom_fields',
            'custom_fields_display', 'user', 'user_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'assignees_display', 'tags_display', 'attachments_display', 'custom_fields_display']
    
    def get_assignees_display(self, obj):
        """Возвращает список исполнителей для отображения"""
        return obj.get_assignees_display()
    
    def get_tags_display(self, obj):
        """Возвращает список тегов для отображения"""
        return obj.get_tags_display()
    
    def get_attachments_display(self, obj):
        """Возвращает список вложений для отображения"""
        return obj.get_attachments_display()
    
    def get_custom_fields_display(self, obj):
        """Возвращает дополнительные поля для отображения"""
        return obj.get_custom_fields_display()


class ClickUpSyncLogSerializer(serializers.ModelSerializer):
    """Сериализатор для логов синхронизации ClickUp"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = ClickUpSyncLog
        fields = [
            'id', 'user', 'user_username', 'status', 'tasks_processed',
            'tasks_created', 'tasks_updated', 'error_message',
            'sync_duration', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ClickUpBulkImportSerializer(serializers.ModelSerializer):
    """Сериализатор для массового импорта ClickUp"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = ClickUpBulkImport
        fields = [
            'id', 'user', 'user_username', 'status', 'total_tasks',
            'processed_tasks', 'successful_tasks', 'failed_tasks',
            'failed_task_ids', 'error_message', 'celery_task_id',
            'progress_percentage', 'success_rate', 'created_at',
            'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'progress_percentage', 'success_rate']


class ClickUpBulkImportCreateSerializer(serializers.Serializer):
    """Сериализатор для создания массового импорта ClickUp"""
    sync_settings = serializers.BooleanField(default=True, help_text="Синхронизировать настройки перед импортом")
    delay_between_tasks = serializers.IntegerField(default=8, min_value=1, max_value=60, help_text="Задержка между задачами в секундах")
    max_tasks = serializers.IntegerField(default=100, min_value=1, max_value=1000, help_text="Максимальное количество задач для импорта")
    
    def validate(self, attrs):
        """Валидация параметров импорта"""
        if attrs['delay_between_tasks'] < 1:
            raise serializers.ValidationError("Задержка между задачами должна быть не менее 1 секунды")
        
        if attrs['max_tasks'] < 1:
            raise serializers.ValidationError("Максимальное количество задач должно быть не менее 1")
        
        return attrs


class ClickUpStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики ClickUp"""
    total_tasks = serializers.IntegerField()
    tasks_by_status = serializers.DictField()
    tasks_by_user = serializers.DictField()
    recent_sync_logs = ClickUpSyncLogSerializer(many=True)
    active_bulk_imports = ClickUpBulkImportSerializer(many=True)
    sync_settings_count = serializers.IntegerField()


class ClickUpApiRequestSerializer(serializers.Serializer):
    """Сериализатор для API запросов ClickUp"""
    endpoint = serializers.CharField(max_length=500)
    method = serializers.ChoiceField(choices=['GET', 'POST', 'PUT', 'DELETE'])
    data = serializers.JSONField(required=False, default=dict)
    params = serializers.JSONField(required=False, default=dict)
    use_cache = serializers.BooleanField(default=True)
    cache_timeout = serializers.IntegerField(default=300, min_value=0)
