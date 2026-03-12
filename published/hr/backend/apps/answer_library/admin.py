from django.contrib import admin
from .models import TriggerTopic, AnswerLibrarySession, AnswerLibraryMessage


@admin.register(TriggerTopic)
class TriggerTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'vacancy', 'order', 'is_active', 'updated_at')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'vacancy')
    search_fields = ('title', 'trigger_words')


@admin.register(AnswerLibrarySession)
class AnswerLibrarySessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vacancy', 'title', 'created_at', 'updated_at')
    list_filter = ('user', 'vacancy')


@admin.register(AnswerLibraryMessage)
class AnswerLibraryMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'content_short', 'created_at')
    list_filter = ('role',)

    def content_short(self, obj):
        return (obj.content or '')[:80] + ('...' if len(obj.content or '') > 80 else '')
    content_short.short_description = 'Текст'
