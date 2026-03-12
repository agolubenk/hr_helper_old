from django.contrib import admin
from .models import HHruOAuthConfig, HHruOAuthAccount, HHruApiLog, HHruVacancyLink, HHruResumeHuntflowCheck


@admin.register(HHruOAuthConfig)
class HHruOAuthConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'is_default', 'created_at')
    list_filter = ('is_active', 'is_default')


@admin.register(HHruOAuthAccount)
class HHruOAuthAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'hh_user_id', 'email', 'is_token_valid', 'created_at')
    list_filter = ('user',)
    search_fields = ('user__email', 'hh_user_id', 'email')


@admin.register(HHruApiLog)
class HHruApiLogAdmin(admin.ModelAdmin):
    list_display = ('account', 'method', 'endpoint', 'status_code', 'log_type', 'created_at')
    list_filter = ('log_type', 'method')


@admin.register(HHruVacancyLink)
class HHruVacancyLinkAdmin(admin.ModelAdmin):
    list_display = ('account', 'hh_vacancy_id', 'huntflow_id', 'updated_at')
    list_filter = ('account',)
    search_fields = ('hh_vacancy_id', 'huntflow_id')


@admin.register(HHruResumeHuntflowCheck)
class HHruResumeHuntflowCheckAdmin(admin.ModelAdmin):
    list_display = ('resume_id', 'status', 'checked_at')
    list_filter = ('status',)
    search_fields = ('resume_id',)
