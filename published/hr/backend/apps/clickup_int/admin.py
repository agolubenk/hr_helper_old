from django.contrib import admin
from django.utils.html import format_html
from .models import ClickUpSettings, ClickUpTask, ClickUpSyncLog, ClickUpBulkImport, ClickUpHiringRequest


@admin.register(ClickUpSettings)
class ClickUpSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'team_id', 'space_id', 'list_id', 'auto_sync', 'huntflow_filter', 'last_sync_at', 'created_at']
    list_filter = ['auto_sync', 'huntflow_filter', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'team_id', 'space_id', 'list_id']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('API настройки', {
            'fields': (),
            'description': 'API токен настраивается в профиле пользователя'
        }),
        ('Путь к задачам', {
            'fields': ('team_id', 'space_id', 'folder_id', 'list_id'),
            'description': 'Укажите путь к списку задач в ClickUp'
        }),
        ('Настройки синхронизации', {
            'fields': ('auto_sync', 'sync_interval', 'huntflow_filter'),
            'description': 'Настройки автоматической синхронизации'
        }),
        ('План найма', {
            'fields': ('hiring_plan_folder_id', 'hiring_plan_space_id'),
            'description': 'Папка ClickUp для вытягивания заявок плана найма (Shared with me и т.п.)'
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at', 'last_sync_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ClickUpTask)
class ClickUpTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_id', 'status', 'priority', 'user', 'date_updated', 'due_date', 'clickup_link', 'tags_display']
    list_filter = ['status', 'priority', 'user', 'date_created', 'date_updated']
    search_fields = ['name', 'description', 'task_id', 'user__username']
    readonly_fields = ['task_id', 'date_created', 'date_updated', 'created_at', 'updated_at', 'clickup_link', 'tags_display', 'assignees_display']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('task_id', 'name', 'description', 'url')
        }),
        ('Статус и приоритет', {
            'fields': ('status', 'priority')
        }),
        ('Даты', {
            'fields': ('date_created', 'date_updated', 'due_date')
        }),
        ('Участники и теги', {
            'fields': ('assignees_display', 'tags_display'),
            'classes': ('collapse',)
        }),
        ('Вложения', {
            'fields': ('attachments',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('user', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def clickup_link(self, obj):
        """Отображает ссылку на задачу в ClickUp"""
        if obj.url:
            return format_html('<a href="{}" target="_blank" class="button">Открыть в ClickUp</a>', obj.url)
        return '-'
    clickup_link.short_description = 'Ссылка'
    clickup_link.admin_order_field = 'url'
    
    def tags_display(self, obj):
        """Отображает теги задачи"""
        if obj.tags:
            tags_html = []
            for tag in obj.tags:
                # Обрабатываем разные форматы тегов
                if isinstance(tag, dict):
                    tag_name = tag.get('name', str(tag))
                else:
                    tag_name = str(tag)
                tags_html.append(f'<span class="badge bg-secondary">{tag_name}</span>')
            return format_html(' '.join(tags_html))
        return '-'
    tags_display.short_description = 'Теги'
    tags_display.allow_tags = True
    
    def assignees_display(self, obj):
        """Отображает исполнителей задачи"""
        if obj.assignees:
            assignees_html = []
            for assignee in obj.assignees:
                assignees_html.append(f'<span class="badge bg-primary">{assignee}</span>')
            return format_html(' '.join(assignees_html))
        return '-'
    assignees_display.short_description = 'Исполнители'
    assignees_display.allow_tags = True


@admin.register(ClickUpSyncLog)
class ClickUpSyncLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'tasks_processed', 'tasks_created', 'tasks_updated', 'sync_duration', 'created_at']
    list_filter = ['status', 'created_at', 'user']
    search_fields = ['user__username', 'error_message']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'status', 'created_at')
        }),
        ('Статистика', {
            'fields': ('tasks_processed', 'tasks_created', 'tasks_updated', 'sync_duration')
        }),
        ('Ошибки', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ClickUpBulkImport)
class ClickUpBulkImportAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'progress_display', 'success_rate_display', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at', 'completed_at', 'user']
    search_fields = ['user__username', 'error_message', 'celery_task_id']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'progress_display', 'success_rate_display', 'failed_task_ids_display']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'status', 'celery_task_id')
        }),
        ('Прогресс', {
            'fields': ('total_tasks', 'processed_tasks', 'successful_tasks', 'failed_tasks', 'progress_display', 'success_rate_display')
        }),
        ('Ошибки', {
            'fields': ('error_message', 'failed_task_ids_display'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def progress_display(self, obj):
        """Отображает прогресс в процентах"""
        if obj.total_tasks == 0:
            return '0%'
        percentage = (obj.processed_tasks / obj.total_tasks) * 100
        color = 'green' if percentage == 100 else 'orange' if percentage > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}% ({}/{})</span>',
            color, round(percentage, 1), obj.processed_tasks, obj.total_tasks
        )
    progress_display.short_description = 'Прогресс'
    progress_display.admin_order_field = 'processed_tasks'
    
    def success_rate_display(self, obj):
        """Отображает процент успешных задач"""
        if obj.processed_tasks == 0:
            return '-'
        rate = (obj.successful_tasks / obj.processed_tasks) * 100
        color = 'green' if rate >= 80 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{}% ({}/{})</span>',
            color, round(rate, 1), obj.successful_tasks, obj.processed_tasks
        )
    success_rate_display.short_description = 'Успешность'
    success_rate_display.admin_order_field = 'successful_tasks'
    
    def failed_task_ids_display(self, obj):
        """Отображает список неудачных задач"""
        if not obj.failed_task_ids:
            return '-'
        
        # Показываем первые 10 ID
        display_ids = obj.failed_task_ids[:10]
        ids_html = []
        for task_id in display_ids:
            ids_html.append(f'<span class="badge bg-danger">{task_id}</span>')
        
        result = ' '.join(ids_html)
        if len(obj.failed_task_ids) > 10:
            result += f' <span class="badge bg-secondary">+{len(obj.failed_task_ids) - 10} еще</span>'
        
        return format_html(result)
    failed_task_ids_display.short_description = 'Неудачные задачи'
    failed_task_ids_display.allow_tags = True


@admin.register(ClickUpHiringRequest)
class ClickUpHiringRequestAdmin(admin.ModelAdmin):
    list_display = ['name', 'clickup_task_id', 'user', 'request_type', 'clickup_status', 'list_name', 'recruiter', 'department', 'date_updated', 'synced_at']
    list_filter = ['request_type', 'user', 'synced_at']
    search_fields = ['name', 'clickup_task_id', 'list_name', 'department', 'user__username']
    readonly_fields = ['clickup_task_id', 'synced_at', 'raw_task', 'custom_fields', 'assignees', 'creator']
    fieldsets = (
        ('Основное', {
            'fields': ('user', 'clickup_task_id', 'name', 'request_type', 'clickup_status', 'normalized_status')
        }),
        ('Даты и список', {
            'fields': ('date_created', 'date_updated', 'start_date', 'due_date', 'list_id', 'list_name', 'folder_id')
        }),
        ('Рекрутер и отдел', {
            'fields': ('recruiter', 'department')
        }),
        ('Данные из ClickUp', {
            'fields': ('assignees', 'creator', 'custom_fields', 'raw_task', 'synced_at'),
            'classes': ('collapse',)
        }),
    )
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'recruiter')