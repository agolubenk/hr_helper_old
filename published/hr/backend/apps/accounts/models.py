from __future__ import annotations
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta


class SystemChoice(models.TextChoices):
    PROD = "prod", _("Прод")
    SANDBOX = "sandbox", _("Песочница")


class User(AbstractUser):
    """
    Минимально расширяем AbstractUser, чтобы не плодить профиль.
    Роли управляются через стандартные Group.
    Поля, о которых просили: Gemini API, Huntflow prod/sandbox (url+api), telegram, выбор системы.
    Для интервьюеров и наблюдателей используем группы + дополнительные поля.
    """
    # Общие доп.поля
    telegram_username = models.CharField(_("Никнейм Telegram"), max_length=64, blank=True)
    linkedin_url = models.URLField(
        _("LinkedIn профиль"),
        max_length=500,
        blank=True,
        help_text="Ссылка на профиль LinkedIn (например: https://www.linkedin.com/in/username/)"
    )
    profile_photo = models.ImageField(_("Фото профиля"), upload_to='profile_photos/', blank=True, null=True)

    # Интеграции
    gemini_api_key = models.CharField(_("API ключ Gemini"), max_length=256, blank=True)
    clickup_api_key = models.CharField(_("API ключ ClickUp"), max_length=256, blank=True)
    notion_integration_token = models.CharField(_("Integration токен Notion"), max_length=256, blank=True)

    huntflow_prod_url = models.URLField(_("Huntflow прод: ссылка"), blank=True)

    huntflow_sandbox_url = models.URLField(_("Huntflow песочница: ссылка"), blank=True)
    huntflow_sandbox_api_key = models.CharField(_("Huntflow песочница: API ключ"), max_length=256, blank=True)

    active_system = models.CharField(
        _("Активная система"),
        max_length=16,
        choices=SystemChoice.choices,
        default=SystemChoice.SANDBOX,
    )

    # Поля для ролей
    # email для интервьюера используем стандартное поле `email`

    # Настройки рабочего времени для интервью
    interview_start_time = models.TimeField(
        _("Начало рабочего времени для интервью"), 
        default="09:00",
        help_text="Время начала рабочего дня для планирования интервью"
    )
    interview_end_time = models.TimeField(
        _("Конец рабочего времени для интервью"), 
        default="18:00",
        help_text="Время окончания рабочего дня для планирования интервью"
    )
    meeting_interval_minutes = models.PositiveIntegerField(
        _("Время между встречами (минуты)"),
        default=15,
        help_text="Время между встречами в минутах (кратно 5, от 0 до 60)"
    )

    # Новые поля для токенной системы Huntflow
    huntflow_access_token = models.CharField(_("Access token для Huntflow API"), max_length=1000, blank=True, help_text="Access token для Huntflow API")
    huntflow_refresh_token = models.CharField(_("Refresh token для Huntflow API"), max_length=1000, blank=True, help_text="Refresh token для Huntflow API")
    huntflow_token_expires_at = models.DateTimeField(_("Время истечения access token"), null=True, blank=True, help_text="Время истечения access token")
    huntflow_refresh_expires_at = models.DateTimeField(_("Время истечения refresh token"), null=True, blank=True, help_text="Время истечения refresh token")

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
    
    def clean(self):
        super().clean()
        # Валидация времени между встречами
        if self.meeting_interval_minutes is not None:
            if self.meeting_interval_minutes < 0 or self.meeting_interval_minutes > 60:
                raise ValidationError({
                    'meeting_interval_minutes': 'Время между встречами должно быть от 0 до 60 минут'
                })
            if self.meeting_interval_minutes % 5 != 0:
                raise ValidationError({
                    'meeting_interval_minutes': 'Время между встречами должно быть кратно 5 минутам'
                })


    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.groups.filter(name="Администраторы").exists()

    @property
    def is_recruiter(self) -> bool:
        return self.groups.filter(name="Рекрутеры").exists()

    @property
    def is_interviewer(self) -> bool:
        return self.groups.filter(name="Интервьюеры").exists()

    @property
    def is_observer(self) -> bool:
        return self.groups.filter(name="Наблюдатели").exists()

    @property
    def is_huntflow_token_valid(self):
        """Проверяет валидность access token"""
        if not self.huntflow_access_token or not self.huntflow_token_expires_at:
            return False
        return timezone.now() < self.huntflow_token_expires_at
    
    @property
    def is_huntflow_refresh_valid(self):
        """Проверяет валидность refresh token"""
        if not self.huntflow_refresh_token or not self.huntflow_refresh_expires_at:
            return False
        return timezone.now() < self.huntflow_refresh_expires_at
    
    def set_huntflow_tokens(self, access_token, refresh_token, expires_in=604800, refresh_expires_in=1209600):
        """
        Устанавливает токены Huntflow
        
        Args:
            access_token: Access token
            refresh_token: Refresh token
            expires_in: Время жизни access token в секундах (по умолчанию 7 дней)
            refresh_expires_in: Время жизни refresh token в секундах (по умолчанию 14 дней)
        """
        self.huntflow_access_token = access_token
        self.huntflow_refresh_token = refresh_token
        self.huntflow_token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        self.huntflow_refresh_expires_at = timezone.now() + timedelta(seconds=refresh_expires_in)
        self.save(update_fields=[
            'huntflow_access_token', 
            'huntflow_refresh_token', 
            'huntflow_token_expires_at', 
            'huntflow_refresh_expires_at'
        ])
    
    def get_profile_photo_url(self):
        """Получить URL фото профиля (локальное или из Google OAuth)"""
        if self.profile_photo:
            return self.profile_photo.url
        
        # Проверяем Google OAuth фото
        try:
            if hasattr(self, 'google_oauth_account') and self.google_oauth_account.picture_url:
                return self.google_oauth_account.picture_url
        except:
            pass
        
        return None
    
    @staticmethod
    def get_meeting_interval_choices():
        """Получить список доступных значений для времени между встречами"""
        return [(i, f"{i} минут") for i in range(0, 61, 5)]
    
    def get_meeting_interval_display(self):
        """Получить отображаемое значение времени между встречами"""
        return f"{self.meeting_interval_minutes} минут"


class QuickButtonType(models.TextChoices):
    """Типы быстрых кнопок"""
    LINK = "link", _("Ссылка")
    TEXT = "text", _("Текст")
    DATETIME = "datetime", _("Дата и время")


class QuickButton(models.Model):
    """Модель для быстрых кнопок пользователя"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quick_buttons',
        verbose_name=_("Пользователь")
    )
    name = models.CharField(
        _("Название"),
        max_length=100,
        help_text="Название быстрой кнопки"
    )
    icon = models.CharField(
        _("Иконка"),
        max_length=50,
        default="fas fa-circle",
        help_text="Класс иконки Font Awesome (например: fas fa-link, fas fa-calendar)"
    )
    button_type = models.CharField(
        _("Тип"),
        max_length=20,
        choices=QuickButtonType.choices,
        default=QuickButtonType.LINK,
        help_text="Тип быстрой кнопки"
    )
    value = models.TextField(
        _("Значение"),
        help_text="Значение в зависимости от типа: URL для ссылки, текст для текста, дата/время для datetime"
    )
    order = models.PositiveIntegerField(
        _("Порядок"),
        default=0,
        help_text="Порядок отображения (меньше = выше)"
    )
    color = models.CharField(
        _("Цвет фона"),
        max_length=7,
        default="#007bff",
        help_text="Цвет фона кнопки в формате HEX (например: #007bff)"
    )
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        verbose_name = _("Быстрая кнопка")
        verbose_name_plural = _("Быстрые кнопки")
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['user', 'order']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_button_type_display()})"

    def clean(self):
        """Валидация данных"""
        super().clean()
        if self.button_type == QuickButtonType.LINK:
            # Проверяем, что значение похоже на URL
            if not (self.value.startswith('http://') or self.value.startswith('https://') or 
                    self.value.startswith('/') or self.value.startswith('mailto:') or
                    self.value.startswith('tel:')):
                raise ValidationError({
                    'value': 'Для типа "Ссылка" значение должно быть URL (начинаться с http://, https://, /, mailto: или tel:)'
                })
        elif self.button_type == QuickButtonType.DATETIME:
            # Проверяем, что значение можно распарсить как дату/время
            from datetime import datetime
            try:
                # Пробуем разные форматы
                datetime.strptime(self.value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    datetime.strptime(self.value, '%Y-%m-%d')
                except ValueError:
                    try:
                        datetime.strptime(self.value, '%d.%m.%Y %H:%M')
                    except ValueError:
                        raise ValidationError({
                            'value': 'Для типа "Дата и время" значение должно быть в формате YYYY-MM-DD HH:MM:SS, YYYY-MM-DD или DD.MM.YYYY HH:MM'
                        })


class UserReminderPhrase(models.Model):
    """
    Зашифрованная фраза-напоминание пользователя.
    Хранится в зашифрованном виде, доступна только владельцу.
    Не отображается в админке в явном виде.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='reminder_phrase',
        verbose_name=_("Пользователь")
    )
    encrypted_value = models.TextField(
        _("Зашифрованное значение"),
        blank=True,
        default="",
        help_text="Фраза хранится в зашифрованном виде"
    )

    class Meta:
        verbose_name = _("Фраза-напоминание")
        verbose_name_plural = _("Фразы-напоминания")

    def __str__(self):
        return f"Фраза-напоминание пользователя {self.user.username}"
