from django.contrib import admin
from django.utils.html import format_html
from .models import Interviewer, InterviewRule


@admin.register(Interviewer)
class InterviewerAdmin(admin.ModelAdmin):
    """Админка для модели Interviewer"""
    
    list_display = [
        'get_full_name', 
        'email', 
        'is_active', 
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'first_name',
        'last_name', 
        'middle_name',
        'email'
    ]
    
    list_editable = ['is_active']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('first_name', 'last_name', 'middle_name', 'email')
        }),
        ('Дополнительная информация', {
            'fields': ('calendar_link', 'is_active'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['last_name', 'first_name']
    
    def get_full_name(self, obj):
        """Отображение полного имени в списке"""
        return obj.get_full_name()
    get_full_name.short_description = 'ФИО'
    get_full_name.admin_order_field = 'last_name'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related()


@admin.register(InterviewRule)
class InterviewRuleAdmin(admin.ModelAdmin):
    """Админка для модели InterviewRule"""
    
    list_display = [
        'name',
        'get_grade_range',
        'daily_limit',
        'weekly_limit',
        'is_active_display',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'min_grade',
        'max_grade',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'name',
        'description'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['deactivate_all_rules']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Лимиты привлечения', {
            'fields': ('daily_limit', 'weekly_limit')
        }),
        ('Грейды', {
            'fields': ('min_grade', 'max_grade')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['min_grade__name', 'name']
    
    def get_grade_range(self, obj):
        """Отображение диапазона грейдов в списке"""
        return obj.get_grade_range()
    get_grade_range.short_description = 'Диапазон грейдов'
    get_grade_range.admin_order_field = 'min_grade__name'
    
    def is_active_display(self, obj):
        """Отображение статуса активности с цветовой индикацией"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✅ Активно</span>'
            )
        else:
            return format_html(
                '<span style="color: #6c757d;">❌ Неактивно</span>'
            )
    is_active_display.short_description = 'Статус'
    is_active_display.admin_order_field = 'is_active'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related('min_grade', 'max_grade')
    
    @admin.action(description='Деактивировать все правила')
    def deactivate_all_rules(self, request, queryset):
        """Деактивировать все правила"""
        count = InterviewRule.objects.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Деактивировано {count} правил.', level='SUCCESS')
