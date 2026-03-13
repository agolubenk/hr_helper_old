from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    HuntflowCache, HuntflowLog,
    LinkedInHuntflowLink, ResumeHuntflowLink, MeetHuntflowLink, GDriveHuntflowLink,
    LinkedInThreadProfile, LevelText,
    HHResponse, HHSyncConfiguration, HHSyncLog, HHFilterStatistics
)


@admin.register(HuntflowCache)
class HuntflowCacheAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "age_display", "status_display", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("cache_key",)
    readonly_fields = ("created_at", "updated_at", "age_display", "status_display")
    
    def age_display(self, obj):
        """Отображает возраст кэша"""
        age = obj.age_minutes
        if age < 60:
            return f"{age} мин"
        elif age < 1440:  # 24 часа
            hours = age // 60
            return f"{hours} ч"
        else:
            days = age // 1440
            return f"{days} дн"
    age_display.short_description = "Возраст"
    
    def status_display(self, obj):
        """Отображает статус кэша с цветовой индикацией"""
        if obj.is_expired:
            return format_html('<span style="color: #dc3545; font-weight: bold;">Истек</span>')
        elif obj.age_minutes < 30:
            return format_html('<span style="color: #28a745; font-weight: bold;">Свежий</span>')
        elif obj.age_minutes < 120:
            return format_html('<span style="color: #ffc107; font-weight: bold;">Устаревает</span>')
        else:
            return format_html('<span style="color: #fd7e14; font-weight: bold;">Устарел</span>')
    status_display.short_description = "Статус"


@admin.register(HuntflowLog)
class HuntflowLogAdmin(admin.ModelAdmin):
    list_display = ("method", "endpoint_short", "status_display", "user", "created_at")
    list_filter = ("log_type", "method", "status_code", "created_at", "user")
    search_fields = ("endpoint", "error_message")
    readonly_fields = ("created_at", "status_display", "request_data_display", "response_data_display")
    date_hierarchy = "created_at"
    
    def endpoint_short(self, obj):
        """Сокращенное отображение эндпоинта"""
        if len(obj.endpoint) > 50:
            return obj.endpoint[:47] + "..."
        return obj.endpoint
    endpoint_short.short_description = "Эндпоинт"
    
    def status_display(self, obj):
        """Отображает статус запроса с цветовой индикацией"""
        if obj.is_success:
            return format_html('<span style="color: #28a745; font-weight: bold;">✅ {}</span>', obj.status_code)
        elif obj.is_error:
            return format_html('<span style="color: #dc3545; font-weight: bold;">❌ {}</span>', obj.status_code or "ERROR")
        else:
            return format_html('<span style="color: #6c757d;">{}</span>', obj.status_code or "N/A")
    status_display.short_description = "Статус"
    
    def request_data_display(self, obj):
        """Отображает данные запроса в читаемом формате"""
        if obj.request_data:
            import json
            return format_html('<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">{}</pre>', 
                             json.dumps(obj.request_data, indent=2, ensure_ascii=False))
        return "Нет данных"
    request_data_display.short_description = "Данные запроса"
    
    def response_data_display(self, obj):
        """Отображает данные ответа в читаемом формате"""
        if obj.response_data:
            import json
            return format_html('<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">{}</pre>', 
                             json.dumps(obj.response_data, indent=2, ensure_ascii=False))
        return "Нет данных"
    response_data_display.short_description = "Данные ответа"
    
    def has_add_permission(self, request):
        """Запрещаем добавление логов через админку"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем изменение логов через админку"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям"""
        return request.user.is_superuser


# ==================== АДМИНКА ДЛЯ СТРАНИЦЫ /extension/ (Chrome-расширение) ====================

@admin.register(LinkedInHuntflowLink)
class LinkedInHuntflowLinkAdmin(admin.ModelAdmin):
    list_display = ("linkedin_url_short", "account_id", "applicant_id", "vacancy_id", "created_by", "updated_by", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at", "created_by", "updated_by")
    search_fields = ("linkedin_url", "target_url", "created_by__username", "updated_by__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    raw_id_fields = ("created_by", "updated_by")

    def linkedin_url_short(self, obj):
        return obj.linkedin_url[:60] + "…" if len(obj.linkedin_url) > 60 else obj.linkedin_url
    linkedin_url_short.short_description = "LinkedIn URL"


@admin.register(ResumeHuntflowLink)
class ResumeHuntflowLinkAdmin(admin.ModelAdmin):
    list_display = ("resume_id", "resume_url_short", "vacancy_name", "huntflow_url_short", "created_by", "updated_by", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at", "created_by", "updated_by")
    search_fields = ("resume_id", "resume_url", "huntflow_url", "vacancy_name", "created_by__username", "updated_by__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "updated_at"
    raw_id_fields = ("created_by", "updated_by")

    def resume_url_short(self, obj):
        url = obj.resume_url or f"/resume/{obj.resume_id}"
        return url[:50] + "…" if len(url) > 50 else url
    resume_url_short.short_description = "Страница резюме"

    def huntflow_url_short(self, obj):
        return obj.huntflow_url[:50] + "…" if len(obj.huntflow_url) > 50 else obj.huntflow_url
    huntflow_url_short.short_description = "Huntflow"


@admin.register(MeetHuntflowLink)
class MeetHuntflowLinkAdmin(admin.ModelAdmin):
    list_display = ("meet_code", "candidate_name", "vacancy_title", "applicant_id", "created_by", "updated_by", "updated_at")
    list_filter = ("updated_at", "created_by", "updated_by")
    search_fields = ("meet_code", "candidate_name", "vacancy_title", "created_by__username", "updated_by__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "updated_at"
    raw_id_fields = ("created_by", "updated_by")


@admin.register(GDriveHuntflowLink)
class GDriveHuntflowLinkAdmin(admin.ModelAdmin):
    list_display = ("gdrive_file_id_short", "candidate_name", "vacancy_name", "applicant_id", "created_by", "updated_by", "updated_at")
    list_filter = ("updated_at", "created_by", "updated_by")
    search_fields = ("gdrive_file_id", "candidate_name", "vacancy_name", "huntflow_url", "created_by__username", "updated_by__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "updated_at"
    raw_id_fields = ("created_by", "updated_by")

    def gdrive_file_id_short(self, obj):
        fid = obj.gdrive_file_id or ""
        return fid[:20] + "…" if len(fid) > 20 else fid
    gdrive_file_id_short.short_description = "File ID"


@admin.register(LinkedInThreadProfile)
class LinkedInThreadProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "thread_id", "profile_url_short", "created_at", "last_accessed_at")
    list_filter = ("created_at", "last_accessed_at", "user")
    search_fields = ("user__username", "thread_id", "profile_url")
    readonly_fields = ("created_at", "last_accessed_at")
    date_hierarchy = "last_accessed_at"
    raw_id_fields = ("user",)

    def profile_url_short(self, obj):
        return obj.profile_url[:50] + "…" if len(obj.profile_url) > 50 else obj.profile_url
    profile_url_short.short_description = "Профиль LinkedIn"


@admin.register(LevelText)
class LevelTextAdmin(admin.ModelAdmin):
    list_display = ("vacancy_name", "level", "text_preview", "created_by", "updated_by", "updated_at")
    list_filter = ("vacancy_name", "updated_at", "created_by", "updated_by")
    search_fields = ("vacancy_name", "level", "text", "created_by__username", "updated_by__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "updated_at"
    raw_id_fields = ("created_by", "updated_by")

    def text_preview(self, obj):
        if not obj.text:
            return "—"
        return (obj.text[:60] + "…") if len(obj.text) > 60 else obj.text
    text_preview.short_description = "Текст"


# ==================== АДМИНКА ДЛЯ HH.RU МОДЕЛЕЙ ====================

@admin.register(HHResponse)
class HHResponseAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "import_status", "hh_vacancy_id", "imported_at")
    list_filter = ("import_status", "response_state", "imported_at", "hh_vacancy_id")
    search_fields = ("first_name", "last_name", "email", "hh_response_id", "hh_vacancy_id")
    readonly_fields = ("imported_at", "processed_at", "hh_created_at", "hh_updated_at")
    date_hierarchy = "imported_at"
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("hh_response_id", "hh_vacancy_id", "first_name", "last_name", "middle_name")
        }),
        ("Контакты", {
            "fields": ("email", "phone", "location", "location_id")
        }),
        ("Дополнительно", {
            "fields": ("birth_date", "gender", "experience_json", "skills_json", "resume_text")
        }),
        ("Статусы", {
            "fields": ("response_state", "import_status", "filter_score", "filter_reasons")
        }),
        ("Связи", {
            "fields": ("account_id", "vacancy_id", "applicant_id", "imported_by")
        }),
        ("Временные метки", {
            "fields": ("hh_created_at", "hh_updated_at", "imported_at", "processed_at")
        }),
        ("Ссылки", {
            "fields": ("hh_resume_url", "hh_applicant_url")
        }),
        ("Данные", {
            "fields": ("raw_data",),
            "classes": ("collapse",)
        }),
    )


@admin.register(HHSyncConfiguration)
class HHSyncConfigurationAdmin(admin.ModelAdmin):
    list_display = ("user", "account_id", "vacancy_id", "hh_vacancy_id", "enabled", "sync_frequency", "last_sync")
    list_filter = ("enabled", "sync_frequency", "created_at", "last_sync")
    search_fields = ("user__username", "hh_vacancy_id", "account_id", "vacancy_id")
    readonly_fields = ("created_at", "last_sync", "next_scheduled_sync", "statistics_display")
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("user", "account_id", "vacancy_id", "hh_vacancy_id")
        }),
        ("Настройки синхронизации", {
            "fields": ("enabled", "sync_frequency", "filters")
        }),
        ("Статистика", {
            "fields": (
                "total_responses_found", "total_responses_imported",
                "total_responses_filtered", "total_responses_errors",
                "statistics_display"
            )
        }),
        ("Автоматизация", {
            "fields": ("auto_add_to_project", "project_id")
        }),
        ("Временные метки", {
            "fields": ("created_at", "last_sync", "next_scheduled_sync")
        }),
    )
    
    def statistics_display(self, obj):
        """Отображает статистику синхронизации"""
        return format_html(
            """
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                <strong>Найдено:</strong> {}<br>
                <strong>Импортировано:</strong> {}<br>
                <strong>Отфильтровано:</strong> {}<br>
                <strong>Ошибок:</strong> {}
            </div>
            """,
            obj.total_responses_found,
            obj.total_responses_imported,
            obj.total_responses_filtered,
            obj.total_responses_errors
        )
    statistics_display.short_description = "Статистика"


@admin.register(HHSyncLog)
class HHSyncLogAdmin(admin.ModelAdmin):
    list_display = ("configuration", "status", "total_responses", "imported_count", "filtered_count", "started_at")
    list_filter = ("status", "started_at", "configuration")
    search_fields = ("configuration__hh_vacancy_id", "error_message")
    readonly_fields = ("started_at", "completed_at", "sync_duration_display")
    date_hierarchy = "started_at"
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("configuration", "status")
        }),
        ("Результаты", {
            "fields": ("total_responses", "imported_count", "filtered_count", "error_count")
        }),
        ("Ошибки", {
            "fields": ("error_message", "error_details"),
            "classes": ("collapse",)
        }),
        ("Статистика", {
            "fields": ("filter_summary", "sync_duration_display")
        }),
        ("Временные метки", {
            "fields": ("started_at", "completed_at")
        }),
    )
    
    def sync_duration_display(self, obj):
        """Отображает длительность синхронизации"""
        if obj.sync_duration_seconds:
            if obj.sync_duration_seconds < 60:
                return f"{obj.sync_duration_seconds} сек"
            elif obj.sync_duration_seconds < 3600:
                minutes = obj.sync_duration_seconds // 60
                seconds = obj.sync_duration_seconds % 60
                return f"{minutes} мин {seconds} сек"
            else:
                hours = obj.sync_duration_seconds // 3600
                minutes = (obj.sync_duration_seconds % 3600) // 60
                return f"{hours} ч {minutes} мин"
        return "Не завершено"
    sync_duration_display.short_description = "Длительность"


@admin.register(HHFilterStatistics)
class HHFilterStatisticsAdmin(admin.ModelAdmin):
    list_display = ("configuration", "total_responses", "accepted_count", "rejection_rate", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("configuration__hh_vacancy_id",)
    readonly_fields = ("updated_at", "statistics_display")
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("configuration",)
        }),
        ("Статистика отклонений", {
            "fields": (
                "location_mismatch_count", "gender_mismatch_count",
                "age_mismatch_count", "experience_mismatch_count",
                "already_in_db_count", "other_count"
            )
        }),
        ("Процентное распределение", {
            "fields": (
                "location_mismatch_percent", "gender_mismatch_percent",
                "age_mismatch_percent", "experience_mismatch_percent",
                "already_in_db_percent", "other_percent"
            )
        }),
        ("Общая статистика", {
            "fields": ("total_responses", "accepted_count", "rejection_rate", "statistics_display")
        }),
        ("Временные метки", {
            "fields": ("updated_at",)
        }),
    )
    
    def statistics_display(self, obj):
        """Отображает статистику фильтрации"""
        return format_html(
            """
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                <strong>Всего откликов:</strong> {}<br>
                <strong>Принято:</strong> {}<br>
                <strong>Процент отклонения:</strong> {:.2f}%<br><br>
                <strong>Причины отклонения:</strong><br>
                - Локация: {} ({:.2f}%)<br>
                - Пол: {} ({:.2f}%)<br>
                - Возраст: {} ({:.2f}%)<br>
                - Опыт: {} ({:.2f}%)<br>
                - Уже в БД: {} ({:.2f}%)<br>
                - Другое: {} ({:.2f}%)
            </div>
            """,
            obj.total_responses,
            obj.accepted_count,
            obj.rejection_rate,
            obj.location_mismatch_count, obj.location_mismatch_percent,
            obj.gender_mismatch_count, obj.gender_mismatch_percent,
            obj.age_mismatch_count, obj.age_mismatch_percent,
            obj.experience_mismatch_count, obj.experience_mismatch_percent,
            obj.already_in_db_count, obj.already_in_db_percent,
            obj.other_count, obj.other_percent
        )
    statistics_display.short_description = "Детальная статистика"