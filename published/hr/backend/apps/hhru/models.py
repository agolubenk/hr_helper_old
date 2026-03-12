"""Модели для интеграции HeadHunter.ru (OAuth, аккаунты, логи)."""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class HHruOAuthConfig(models.Model):
    """Конфигурация OAuth-приложения на dev.hh.ru (client_id, client_secret, redirect_uri)."""
    name = models.CharField('Название', max_length=255)
    client_id = models.CharField('Client ID', max_length=512)
    client_secret = models.CharField('Client Secret', max_length=512)
    redirect_uri = models.URLField('Redirect URI', max_length=1024)
    is_active = models.BooleanField('Активна', default=True)
    is_default = models.BooleanField('По умолчанию', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Конфигурация OAuth HH.ru'
        verbose_name_plural = 'Конфигурации OAuth HH.ru'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            HHruOAuthConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class HHruOAuthAccount(models.Model):
    """Подключённый аккаунт пользователя HH.ru (токены и данные профиля)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hhru_oauth_accounts',
        verbose_name='Пользователь',
    )
    config = models.ForeignKey(
        HHruOAuthConfig,
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='Конфигурация OAuth',
        null=True,
        blank=True,
    )
    access_token = models.TextField('Access Token')
    refresh_token = models.TextField('Refresh Token', blank=True, null=True)
    token_expires_at = models.DateTimeField('Токен истекает', null=True, blank=True)

    hh_user_id = models.CharField('HH User ID', max_length=64, blank=True)
    first_name = models.CharField('Имя', max_length=255, blank=True)
    last_name = models.CharField('Фамилия', max_length=255, blank=True)
    middle_name = models.CharField('Отчество', max_length=255, blank=True, null=True)
    email = models.EmailField('Email', blank=True)
    is_employer = models.BooleanField('Работодатель', default=False)
    is_admin = models.BooleanField('Администратор', default=False)
    employer_id = models.CharField('ID работодателя на HH.ru', max_length=64, blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Аккаунт HH.ru'
        verbose_name_plural = 'Аккаунты HH.ru'
        ordering = ['-created_at']
        unique_together = [['user', 'hh_user_id']]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email or self.hh_user_id})"

    @property
    def is_token_valid(self):
        if not self.token_expires_at:
            return False
        return timezone.now() < self.token_expires_at

    @property
    def needs_refresh(self):
        if not self.token_expires_at or not self.refresh_token:
            return True
        return timezone.now() > (self.token_expires_at - timedelta(minutes=5))


class HHruApiLog(models.Model):
    """Лог запроса к API HH.ru."""
    class LogType(models.TextChoices):
        GET = 'GET', 'GET'
        POST = 'POST', 'POST'
        PUT = 'PUT', 'PUT'
        PATCH = 'PATCH', 'PATCH'
        DELETE = 'DELETE', 'DELETE'
        ERROR = 'ERROR', 'Ошибка'

    account = models.ForeignKey(
        HHruOAuthAccount,
        on_delete=models.CASCADE,
        related_name='api_logs',
        null=True,
        blank=True,
    )
    method = models.CharField(max_length=10, default='GET')
    endpoint = models.CharField(max_length=1024)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    log_type = models.CharField(max_length=10, choices=LogType.choices, default=LogType.GET)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Лог API HH.ru'
        verbose_name_plural = 'Логи API HH.ru'
        ordering = ['-created_at']


class HHruResumeHuntflowCheck(models.Model):
    """
    Результат проверки: есть ли резюме HH.ru в Huntflow.
    Если связи (ResumeHuntflowLink) нет и статус not_found — показываем «Нужно добавить».
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Проверка'
        FOUND = 'found', 'Найден в Huntflow'
        NOT_FOUND = 'not_found', 'Нужно добавить'

    resume_id = models.CharField('ID резюме HH.ru', max_length=100, unique=True, db_index=True)
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.PENDING)
    huntflow_url = models.URLField('Ссылка Huntflow', max_length=800, blank=True)
    checked_at = models.DateTimeField('Проверено', null=True, blank=True)

    class Meta:
        verbose_name = 'Проверка HH резюме → Huntflow'
        verbose_name_plural = 'Проверки HH резюме → Huntflow'
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.resume_id}: {self.get_status_display()}"


class HHruVacancyLink(models.Model):
    """Связь вакансии HH.ru с huntflow_id (по которому подтягиваются локальные вакансии)."""
    account = models.ForeignKey(
        HHruOAuthAccount,
        on_delete=models.CASCADE,
        related_name='vacancy_links',
        verbose_name='Аккаунт HH.ru',
    )
    hh_vacancy_id = models.CharField('ID вакансии на HH.ru', max_length=64, db_index=True)
    huntflow_id = models.CharField('Huntflow ID', max_length=100, blank=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Связь вакансии HH.ru'
        verbose_name_plural = 'Связи вакансий HH.ru'
        unique_together = [['account', 'hh_vacancy_id']]
        ordering = ['-updated_at']

    def __str__(self):
        return f"HH {self.hh_vacancy_id} → huntflow_id={self.huntflow_id}"
