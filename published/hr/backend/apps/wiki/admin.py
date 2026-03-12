from django.contrib import admin
from django.utils.html import format_html
from .models import WikiPage, WikiPageHistory, WikiTag


@admin.register(WikiTag)
class WikiTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'pages_count', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Цвет'
    
    def pages_count(self, obj):
        return obj.pages.count()
    pages_count.short_description = 'Страниц'


@admin.register(WikiPage)
class WikiPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'related_app_display', 'tags_display', 'order', 'is_published', 'author', 'updated_at']
    list_filter = ['category', 'related_app', 'tags', 'is_published', 'created_at', 'updated_at']
    search_fields = ['title', 'slug', 'content', 'description']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'author', 'last_edited_by']
    filter_horizontal = ['tags']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'description', 'category', 'related_app', 'order', 'is_published')
        }),
        ('Теги и связи', {
            'fields': ('tags',)
        }),
        ('Содержание', {
            'fields': ('content',)
        }),
        ('Метаданные', {
            'fields': ('author', 'last_edited_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def related_app_display(self, obj):
        if obj.related_app:
            return obj.get_related_app_display()
        return '—'
    related_app_display.short_description = 'Приложение'
    
    def tags_display(self, obj):
        tags = obj.tags.all()
        if tags:
            return format_html(
                ' '.join([
                    f'<span style="background-color: {tag.color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px;">#{tag.name}</span>'
                    for tag in tags[:5]
                ]) + (' ...' if tags.count() > 5 else '')
            )
        return '—'
    tags_display.short_description = 'Теги'
    
    def save_model(self, request, obj, form, change):
        """Сохраняет автора и редактора при создании/обновлении"""
        if not change:  # Создание новой страницы
            obj.author = request.user
        obj.last_edited_by = request.user
        
        # Сохраняем историю изменений
        if change:
            old_obj = WikiPage.objects.get(pk=obj.pk)
            if old_obj.content != obj.content or old_obj.title != obj.title:
                WikiPageHistory.objects.create(
                    page=obj,
                    title=old_obj.title,
                    content=old_obj.content,
                    edited_by=request.user,
                    change_note=f'Обновлено через админ-панель'
                )
        
        super().save_model(request, obj, form, change)


@admin.register(WikiPageHistory)
class WikiPageHistoryAdmin(admin.ModelAdmin):
    list_display = ['page', 'title', 'edited_by', 'created_at', 'change_note']
    list_filter = ['created_at', 'edited_by']
    search_fields = ['page__title', 'title', 'content', 'change_note']
    readonly_fields = ['page', 'title', 'content', 'edited_by', 'created_at', 'change_note']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
