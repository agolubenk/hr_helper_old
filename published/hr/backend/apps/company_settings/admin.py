from django.contrib import admin
from django.utils.html import format_html
from .models import CompanySettings, RejectionTemplate, VacancyPrompt, VacancyPromptHistory


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'theme', 'active_grades_display', 'main_calendar_id', 'updated_at']
    list_filter = ['theme', 'active_grades', 'created_at', 'updated_at']
    search_fields = ['company_name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['active_grades']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('company_name', 'theme')
        }),
        ('Активные грейды компании', {
            'fields': ('active_grades',),
            'description': 'Выберите грейды, которые используются в вашей компании. Эти грейды будут использоваться в связке с внешними ресурсами и системами.'
        }),
        ('Интеграции', {
            'fields': ('main_calendar_id', 'ignore_non_accepted_meetings', 'work_start_time', 'work_end_time')
        }),
        ('Оргструктура', {
            'fields': ('org_structure',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def active_grades_display(self, obj):
        """Отображает активные грейды компании"""
        grades = obj.active_grades.all()
        if grades:
            grade_names = ', '.join([grade.name for grade in grades[:5]])
            if grades.count() > 5:
                grade_names += f' (+{grades.count() - 5} еще)'
            return format_html('<span style="color: #17a2b8;">{}</span>', grade_names)
        return format_html('<span style="color: #6c757d;">Не выбрано</span>')
    active_grades_display.short_description = 'Активные грейды'
    
    def has_add_permission(self, request):
        # Разрешаем создание только если нет записей
        return CompanySettings.objects.count() == 0
    
    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление синглтона
        return False


@admin.register(RejectionTemplate)
class RejectionTemplateAdmin(admin.ModelAdmin):
    list_display = ['rejection_type_display', 'grade_display', 'title', 'is_active', 'updated_at']
    list_filter = ['rejection_type', 'is_active', 'grade', 'created_at', 'updated_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('rejection_type', 'grade', 'title', 'message', 'is_active')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def rejection_type_display(self, obj):
        """Отображает тип отказа с цветовой индикацией"""
        colors = {
            'office_format': '#ffc107',  # желтый
            'finance': '#dc3545',  # красный
            'finance_more': '#c82333',  # темно-красный
            'finance_less': '#bd2130',  # очень темно-красный
            'grade': '#17a2b8',  # синий
            'general': '#6c757d',  # серый
        }
        color = colors.get(obj.rejection_type, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_rejection_type_display()
        )
    rejection_type_display.short_description = 'Тип отказа'
    
    def grade_display(self, obj):
        """Отображает грейд или прочерк"""
        if obj.grade:
            return format_html('<span style="color: #17a2b8;">{}</span>', obj.grade.name)
        return '—'
    grade_display.short_description = 'Грейд'
    
    class Media:
        js = ('admin/js/rejection_template_admin.js',)
    
    def get_form(self, request, obj=None, **kwargs):
        """Динамически управляем полем grade"""
        form = super().get_form(request, obj, **kwargs)
        
        # Добавляем класс для JavaScript идентификации
        if 'grade' in form.base_fields:
            form.base_fields['grade'].widget.attrs['class'] = 'grade-field'
        
        if 'rejection_type' in form.base_fields:
            form.base_fields['rejection_type'].widget.attrs['class'] = 'rejection-type-field'
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Валидация перед сохранением"""
        obj.clean()
        super().save_model(request, obj, form, change)


@admin.register(VacancyPrompt)
class VacancyPromptAdmin(admin.ModelAdmin):
    list_display = ['is_active', 'prompt_preview', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Промпт', {
            'fields': ('prompt', 'is_active')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def prompt_preview(self, obj):
        """Превью промпта"""
        if obj.prompt:
            preview = obj.prompt[:100] + '...' if len(obj.prompt) > 100 else obj.prompt
            return format_html('<span style="font-family: monospace;">{}</span>', preview)
        return '—'
    prompt_preview.short_description = 'Промпт'
    
    def has_add_permission(self, request):
        # Разрешаем создание только если нет записей
        return VacancyPrompt.objects.count() == 0
    
    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление синглтона
        return False
    
    def save_model(self, request, obj, form, change):
        """Сохраняем с указанием пользователя для истории"""
        obj.save(updated_by=request.user)


@admin.register(VacancyPromptHistory)
class VacancyPromptHistoryAdmin(admin.ModelAdmin):
    list_display = ['updated_at', 'updated_by', 'is_active', 'prompt_preview']
    list_filter = ['is_active', 'updated_at', 'updated_by']
    readonly_fields = ['prompt', 'prompt_text', 'is_active', 'updated_by', 'updated_at']
    search_fields = ['prompt_text']
    
    fieldsets = (
        ('Информация', {
            'fields': ('prompt', 'prompt_text', 'is_active', 'updated_by', 'updated_at')
        }),
    )
    
    def prompt_preview(self, obj):
        """Превью промпта"""
        if obj.prompt_text:
            preview = obj.prompt_text[:100] + '...' if len(obj.prompt_text) > 100 else obj.prompt_text
            return format_html('<span style="font-family: monospace;">{}</span>', preview)
        return '—'
    prompt_preview.short_description = 'Промпт'
    
    def has_add_permission(self, request):
        # Запрещаем создание вручную - только через VacancyPrompt
        return False
    
    def has_change_permission(self, request, obj=None):
        # Запрещаем редактирование истории
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Разрешаем удаление только суперпользователям
        return request.user.is_superuser

