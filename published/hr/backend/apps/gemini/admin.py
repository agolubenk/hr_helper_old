from django.contrib import admin
from django.utils.html import format_html
from .models import ChatSession, ChatMessage


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'message_count', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Количество сообщений'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('messages')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'content_preview', 'tokens_used', 'response_time', 'timestamp']
    list_filter = ['role', 'timestamp', 'session__user']
    search_fields = ['content', 'session__title', 'session__user__username']
    readonly_fields = ['timestamp']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Содержание'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session__user')
