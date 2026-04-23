from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django import forms
from .models import User, QuickButton, UserReminderPhrase


class UserAdminForm(forms.ModelForm):
    """Кастомная форма для User в админке"""
    class Meta:
        model = User
        fields = '__all__'
        widgets = {
            'huntflow_access_token': forms.TextInput(attrs={'placeholder': 'Введите access token'}),
            'huntflow_refresh_token': forms.TextInput(attrs={'placeholder': 'Введите refresh token'}),
            'gemini_api_key': forms.TextInput(attrs={'placeholder': 'Введите API ключ Gemini'}),
            'clickup_api_key': forms.TextInput(attrs={'placeholder': 'Введите API ключ ClickUp'}),
            'meeting_interval_minutes': forms.NumberInput(attrs={
                'min': '0', 
                'max': '60', 
                'step': '5',
                'placeholder': 'Кратно 5, от 0 до 60'
            }),
        }


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    fieldsets = BaseUserAdmin.fieldsets + (
        (_("Интеграции"), {
            "fields": (
                "gemini_api_key",
                "preferred_ai_model",
                "clickup_api_key",
                "telegram_username",
            )
        }),
        (_("Huntflow Песочница"), {
            "fields": (
                "huntflow_sandbox_url",
                "huntflow_sandbox_api_key",
            )
        }),
        (_("Huntflow Продакшн"), {
            "fields": (
                "huntflow_prod_url",
            )
        }),
        (_("Настройки интервью"), {
            "fields": (
                "interview_start_time",
                "interview_end_time",
                "meeting_interval_minutes",
            )
        }),
        (_("Huntflow Настройки"), {
            "fields": (
                "active_system",
                "huntflow_access_token", 
                "huntflow_refresh_token",
                "huntflow_token_expires_at",
                "huntflow_refresh_expires_at"
            ),
            "classes": ("collapse",)
        }),
    )
    list_display = ("username", "first_name", "last_name", "email", "active_system", "get_clickup_status", "get_huntflow_token_status", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "active_system", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email", "telegram_username")
    readonly_fields = ('huntflow_token_expires_at', 'huntflow_refresh_expires_at', 'huntflow_token_status')
    
    def get_clickup_status(self, obj):
        """Отображение статуса ClickUp API ключа"""
        if obj.clickup_api_key:
            return "✅ Настроен"
        else:
            return "❌ Не настроен"
    get_clickup_status.short_description = "ClickUp API"
    get_clickup_status.admin_order_field = "clickup_api_key"
    
    def get_huntflow_token_status(self, obj):
        """Отображение статуса Huntflow токенов"""
        if not obj.huntflow_access_token:
            return "❌ Не настроены"
        
        status = "✅ Валидный" if obj.is_huntflow_token_valid else "❌ Истек"
        refresh_status = "✅ Валидный" if obj.is_huntflow_refresh_valid else "❌ Истек"
        
        return f"Access: {status}, Refresh: {refresh_status}"
    get_huntflow_token_status.short_description = "Huntflow Токены"
    
    def huntflow_token_status(self, obj):
        """Показывает статус токенов в админке"""
        if not obj.huntflow_access_token:
            return "Токены не настроены"
        
        status = "✅ Валидный" if obj.is_huntflow_token_valid else "❌ Истек"
        refresh_status = "✅ Валидный" if obj.is_huntflow_refresh_valid else "❌ Истек"
        
        return f"Access: {status}, Refresh: {refresh_status}"
    huntflow_token_status.short_description = "Статус токенов"
    
    def has_delete_permission(self, request, obj=None):
        """Проверка прав на удаление пользователя"""
        # Если это суперпользователь, разрешаем удаление
        if request.user.is_superuser:
            return True
        
        # Если это обычный пользователь, запрещаем удаление
        if obj and obj.is_superuser:
            return False
            
        # Проверяем, есть ли связанные авторизованные TelegramUser
        if obj:
            try:
                from apps.telegram.models import TelegramUser
                telegram_user = TelegramUser.objects.get(user=obj)
                if telegram_user.is_authorized:
                    # Если есть авторизованный TelegramUser, разрешаем удаление
                    # но сначала деавторизуем TelegramUser
                    return True
            except:
                pass
        
        return super().has_delete_permission(request, obj)
    
    def delete_model(self, request, obj):
        """Удаление пользователя с предварительной очисткой связанных объектов"""
        # Деавторизуем TelegramUser перед удалением
        try:
            from apps.telegram.models import TelegramUser
            telegram_user = TelegramUser.objects.get(user=obj)
            if telegram_user.is_authorized:
                telegram_user.is_authorized = False
                telegram_user.save()
        except:
            pass
        
        # Удаляем пользователя
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Массовое удаление пользователей с предварительной очисткой"""
        # Деавторизуем всех связанных TelegramUser
        try:
            from apps.telegram.models import TelegramUser
            for user in queryset:
                try:
                    telegram_user = TelegramUser.objects.get(user=user)
                    if telegram_user.is_authorized:
                        telegram_user.is_authorized = False
                        telegram_user.save()
                except:
                    pass
        except:
            pass
        
        # Удаляем пользователей
        super().delete_queryset(request, queryset)


@admin.register(QuickButton)
class QuickButtonAdmin(admin.ModelAdmin):
    """Админка для быстрых кнопок"""
    list_display = ('name', 'user', 'button_type', 'icon', 'order', 'created_at')
    list_filter = ('button_type', 'created_at', 'updated_at')
    search_fields = ('name', 'value', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('order',)
    ordering = ('user', 'order', 'created_at')
    
    fieldsets = (
        (_("Основная информация"), {
            "fields": (
                "user",
                "name",
                "icon",
                "button_type",
            )
        }),
        (_("Значение"), {
            "fields": (
                "value",
            )
        }),
        (_("Настройки отображения"), {
            "fields": (
                "color",
                "order",
            )
        }),
        (_("Системная информация"), {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user')


@admin.register(UserReminderPhrase)
class UserReminderPhraseAdmin(admin.ModelAdmin):
    """Админка для фраз-напоминаний. Текст хранится зашифрованно, в админке показывается только факт наличия."""
    list_display = ('user', 'get_encrypted_display', 'has_value')
    list_filter = ('user',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('encrypted_value_display',)
    ordering = ('user',)
    exclude = ('encrypted_value',)  # Не показываем сырые зашифрованные данные

    fieldsets = (
        (_("Пользователь"), {
            "fields": ("user",),
        }),
        (_("Данные (зашифрованы)"), {
            "fields": ("encrypted_value_display",),
            "description": _("Текст фразы хранится в зашифрованном виде. Расшифровка доступна только владельцу на странице настроек."),
        }),
    )

    def get_encrypted_display(self, obj):
        if not obj.encrypted_value:
            return "—"
        return _("зашифровано (%(len)s символов)") % {"len": len(obj.encrypted_value)}
    get_encrypted_display.short_description = _("Значение")

    def has_value(self, obj):
        return bool(obj.encrypted_value)
    has_value.boolean = True
    has_value.short_description = _("Заполнено")

    def encrypted_value_display(self, obj):
        if not obj.encrypted_value:
            return "—"
        return _("зашифровано (%(len)s символов)") % {"len": len(obj.encrypted_value)}
    encrypted_value_display.short_description = _("Зашифрованное значение")

    def has_add_permission(self, request):
        return False  # Создаётся только через настройки профиля

    def has_change_permission(self, request, obj=None):
        return False  # Редактируется только через настройки профиля