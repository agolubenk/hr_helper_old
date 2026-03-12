from django.contrib import admin
from django.utils.html import format_html
from .models import Vacancy, ScorecardUpdateHistory
from apps.finance.models import SalaryRange


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'external_id',
        'recruiter',
        'get_interviewers_count_display',
        'is_active_display',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'recruiter',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'name',
        'external_id',
        'technologies',
        'recruiter__first_name',
        'recruiter__last_name',
        'recruiter__email'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Блок 1: Основная информация', {
            'fields': ('name', 'external_id', 'recruiter', 'additional_recruiters', 'technologies', 'is_active')
        }),
        ('Блок 2: Этапы для перевода кандидатов', {
            'fields': (
                'screening_duration', 'invite_title', 'invite_text', 'hr_screening_stage',
                'tech_interview_duration', 'tech_invite_title', 'tech_invite_text', 'tech_screening_stage',
                'tech_interview_stage'
            ),
            'classes': ('collapse',)
        }),
        ('Блок 3: Scorecard', {
            'fields': ('scorecard_title', 'scorecard_link'),
            'classes': ('collapse',)
        }),
        ('Блок 4: Ссылки на вакансии по странам', {
            'fields': ('vacancy_link_belarus', 'vacancy_link_poland'),
            'classes': ('collapse',)
        }),
        ('Блок 5: Вопросы для интервью', {
            'fields': ('questions_belarus', 'questions_poland'),
            'classes': ('collapse',)
        }),
        ('Блок 6: Промпт для анализа после скрининга', {
            'fields': ('use_common_prompt', 'candidate_update_prompt',),
            'classes': ('collapse',)
        }),
        ('Блок 7: Интервьюеры (только связанные с вакансией)', {
            'fields': ('interviewers',),
            'classes': ('collapse',)
        }),
        ('Блок 8: Обязательные участники тех. интервью', {
            'fields': ('mandatory_tech_interviewers',),
            'classes': ('collapse',)
        }),
        ('Блок 9: Зарплатные вилки', {
            'fields': ('available_grades',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['interviewers', 'mandatory_tech_interviewers', 'additional_recruiters']
    
    ordering = ['-created_at']
    
    def get_interviewers_count_display(self, obj):
        """Отображение количества интервьюеров"""
        count = obj.get_interviewers_count()
        if count > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{} интервьюеров</span>',
                count
            )
        else:
            return format_html(
                '<span style="color: #6c757d;">Нет интервьюеров</span>'
            )
    get_interviewers_count_display.short_description = 'Интервьюеры'
    get_interviewers_count_display.admin_order_field = 'interviewers__count'
    
    def is_active_display(self, obj):
        """Отображение статуса активности"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✅ Активна</span>'
            )
        else:
            return format_html(
                '<span style="color: #6c757d;">❌ Неактивна</span>'
            )
    is_active_display.short_description = 'Статус'
    is_active_display.admin_order_field = 'is_active'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related('recruiter').prefetch_related('interviewers', 'additional_recruiters')
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Ограничиваем выбор интервьюеров только активными"""
        if db_field.name == "interviewers":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_active=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    
    actions = ['update_activity_status']
    
    def update_activity_status(self, request, queryset):
        """Обновляет статус активности выбранных вакансий"""
        updated_count = 0
        for vacancy in queryset:
            if vacancy.update_activity_status():
                updated_count += 1
        
        if updated_count > 0:
            self.message_user(
                request,
                f'Статус активности обновлен для {updated_count} вакансий.',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                'Статус активности не изменился ни для одной вакансии.',
                level='INFO'
            )
    update_activity_status.short_description = 'Обновить статус активности на основе заявок'


# SalaryRangeAdmin удален - используется finance.SalaryRangeAdmin


@admin.register(ScorecardUpdateHistory)
class ScorecardUpdateHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'vacancy',
        'user',
        'action_type_display',
        'success_rate_display',
        'updated_count',
        'total_found',
        'date_range_display',
        'has_errors_display',
        'created_at'
    ]
    
    list_filter = [
        'action_type',
        'vacancy',
        'user',
        'created_at',
        'updated_count',
        'total_found'
    ]
    
    search_fields = [
        'vacancy__name',
        'user__first_name',
        'user__last_name',
        'user__email'
    ]
    
    readonly_fields = [
        'vacancy',
        'user',
        'action_type',
        'updated_count',
        'total_found',
        'date_range_from',
        'date_range_to',
        'errors',
        'updated_interviews',
        'created_at',
        'success_rate_display',
        'has_errors_display'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('vacancy', 'user', 'action_type', 'created_at')
        }),
        ('Результаты операции', {
            'fields': ('updated_count', 'total_found', 'success_rate_display', 'has_errors_display')
        }),
        ('Период обновления', {
            'fields': ('date_range_from', 'date_range_to')
        }),
        ('Детали операции', {
            'fields': ('updated_interviews',),
            'classes': ('collapse',)
        }),
        ('Ошибки', {
            'fields': ('errors',),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    
    def action_type_display(self, obj):
        """Отображение типа операции"""
        if obj.action_type == 'bulk_update':
            return format_html(
                '<span style="color: #007bff; font-weight: bold;">🔄 Массовое обновление</span>'
            )
        else:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✏️ Обновление одного</span>'
            )
    action_type_display.short_description = 'Тип операции'
    action_type_display.admin_order_field = 'action_type'
    
    def success_rate_display(self, obj):
        """Отображение процента успешности"""
        rate = obj.success_rate
        if rate >= 90:
            color = '#28a745'  # Зеленый
            icon = '✅'
        elif rate >= 70:
            color = '#ffc107'  # Желтый
            icon = '⚠️'
        else:
            color = '#dc3545'  # Красный
            icon = '❌'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}%</span>',
            color, icon, rate
        )
    success_rate_display.short_description = 'Успешность'
    
    def date_range_display(self, obj):
        """Отображение периода"""
        return f"{obj.date_range_from.strftime('%d.%m.%Y')} - {obj.date_range_to.strftime('%d.%m.%Y')}"
    date_range_display.short_description = 'Период'
    date_range_display.admin_order_field = 'date_range_from'
    
    def has_errors_display(self, obj):
        """Отображение наличия ошибок"""
        if obj.has_errors:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">❌ {} ошибок</span>',
                len(obj.errors)
            )
        else:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✅ Без ошибок</span>'
            )
    has_errors_display.short_description = 'Ошибки'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related('vacancy', 'user')
    
    def has_add_permission(self, request):
        """Запрещаем добавление новых записей через админку"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем редактирование записей через админку"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям"""
        return request.user.is_superuser

