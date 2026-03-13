from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class HuntflowCache(models.Model):
    """
    Кэш для данных Huntflow API
    """
    cache_key = models.CharField(_("Ключ кэша"), max_length=255, unique=True)
    data = models.JSONField(_("Данные"), default=dict)
    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), default=timezone.now)
    expires_at = models.DateTimeField(_("Истекает"), null=True, blank=True)
    
    class Meta:
        verbose_name = _("Кэш Huntflow")
        verbose_name_plural = _("Кэш Huntflow")
        ordering = ("-updated_at",)
    
    def __str__(self):
        return f"{self.cache_key} ({self.updated_at.strftime('%d.%m.%Y %H:%M')})"
    
    @property
    def is_expired(self):
        """Проверяет, истек ли кэш"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def age_minutes(self):
        """Возвращает возраст кэша в минутах"""
        return int((timezone.now() - self.updated_at).total_seconds() / 60)


class HuntflowLog(models.Model):
    """
    Лог операций с Huntflow API
    """
    LOG_TYPES = [
        ('GET', 'Получение данных'),
        ('POST', 'Создание'),
        ('PATCH', 'Обновление'),
        ('DELETE', 'Удаление'),
        ('ERROR', 'Ошибка'),
    ]
    
    log_type = models.CharField(_("Тип операции"), max_length=10, choices=LOG_TYPES)
    endpoint = models.CharField(_("Эндпоинт"), max_length=500)
    method = models.CharField(_("HTTP метод"), max_length=10)
    status_code = models.IntegerField(_("Код ответа"), null=True, blank=True)
    request_data = models.JSONField(_("Данные запроса"), default=dict, blank=True)
    response_data = models.JSONField(_("Данные ответа"), default=dict, blank=True)
    error_message = models.TextField(_("Сообщение об ошибке"), blank=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, verbose_name=_("Пользователь"))
    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    
    class Meta:
        verbose_name = _("Лог Huntflow")
        verbose_name_plural = _("Логи Huntflow")
        ordering = ("-created_at",)
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code or 'ERROR'} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
    @property
    def is_success(self):
        """Проверяет, был ли запрос успешным"""
        return self.status_code and 200 <= self.status_code < 300
    
    @property
    def is_error(self):
        """Проверяет, была ли ошибка"""
        return self.log_type == 'ERROR' or (self.status_code and self.status_code >= 400)


class LinkedInHuntflowLink(models.Model):
    """
    Связка LinkedIn профиля с кандидатом в Huntflow (общая для всех пользователей).

    Используется расширением Chrome, чтобы определять "сохранён/не сохранён"
    без обращения к поиску в Huntflow.
    Аудит: created_by/updated_by для логирования.
    """

    linkedin_url = models.URLField(_("LinkedIn URL"), max_length=500, unique=True)

    # Можно хранить либо точные идентификаторы, либо просто ссылку на карточку кандидата
    # (например URL на страницу кандидата в нашем веб-интерфейсе).
    target_url = models.URLField(_("Ссылка на кандидата (Huntflow/HRHelper)"), max_length=800, blank=True, null=True)

    account_id = models.IntegerField(_("Huntflow account_id"), blank=True, null=True)
    applicant_id = models.IntegerField(_("Huntflow applicant_id"), blank=True, null=True)
    vacancy_id = models.IntegerField(_("Huntflow vacancy_id"), blank=True, null=True)

    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_linkedin_huntflow_links',
        verbose_name=_("Кто создал"),
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_linkedin_huntflow_links',
        verbose_name=_("Кто обновил"),
    )

    class Meta:
        verbose_name = _("Связка LinkedIn↔Huntflow")
        verbose_name_plural = _("Связки LinkedIn↔Huntflow")
        indexes = [
            models.Index(fields=['linkedin_url']),
            models.Index(fields=['account_id', 'applicant_id']),
        ]

    def __str__(self):
        return f"{self.linkedin_url} -> {self.account_id}/{self.applicant_id}"


def _extract_resume_id_from_url(url):
    """Извлекает resume_id из URL (часть после /resume/). Работает для hh.ru, rabota.by и субдоменов."""
    if not url:
        return None
    import re
    m = re.search(r"/resume/([^/?#]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


class ResumeHuntflowLink(models.Model):
    """
    Связка страницы резюме (hh.ru / rabota.by) с кандидатом в Huntflow (общая для всех).
    Поиск по resume_id (часть после /resume/) — один ID работает для всех доменов и субдоменов.
    Сохраняется из расширения при нажатии «Применить» на странице резюме.
    Аудит: created_by/updated_by для логирования.
    """
    resume_id = models.CharField(
        _("ID резюме (из пути /resume/{id})"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Уникальный ID из URL, напр. 1a6de8370007670893003b77395447734e764e",
    )
    resume_url = models.URLField(
        _("URL страницы резюме (канонический)"),
        max_length=500,
        blank=True,
        help_text="Канонический URL для отображения (hh.ru или rabota.by)",
    )
    huntflow_url = models.URLField(_("Ссылка Huntflow"), max_length=800)
    vacancy_name = models.CharField(_("Название вакансии"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_resume_huntflow_links',
        verbose_name=_("Кто создал"),
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_resume_huntflow_links',
        verbose_name=_("Кто обновил"),
    )

    class Meta:
        verbose_name = _("Связка резюме↔Huntflow")
        verbose_name_plural = _("Связки резюме↔Huntflow")
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=['resume_id']),
        ]

    def save(self, *args, **kwargs):
        if self.resume_url and "?" in self.resume_url:
            self.resume_url = self.resume_url.split("?")[0]
        if not self.resume_id and self.resume_url:
            self.resume_id = _extract_resume_id_from_url(self.resume_url)
        super().save(*args, **kwargs)

    def __str__(self):
        url = self.resume_url or f"/resume/{self.resume_id}"
        return f"{url[:50]}… → Huntflow"


class GDriveHuntflowLink(models.Model):
    """
    Связка файла Google Drive с кандидатом в Huntflow.
    Сохраняется из расширения при создании кандидата из файла Google Drive.
    Используется для показа плавающего окна на странице Google Drive.
    """
    gdrive_file_id = models.CharField(
        _("ID файла Google Drive"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Уникальный ID файла из URL Google Drive",
    )
    gdrive_url = models.URLField(
        _("URL файла Google Drive"),
        max_length=500,
        blank=True,
    )
    huntflow_url = models.URLField(_("Ссылка Huntflow"), max_length=800)
    applicant_id = models.IntegerField(_("ID кандидата в Huntflow"), null=True, blank=True)
    account_id = models.IntegerField(_("ID организации в Huntflow"), null=True, blank=True)
    vacancy_id = models.IntegerField(_("ID вакансии"), null=True, blank=True)
    vacancy_name = models.CharField(_("Название вакансии"), max_length=255, blank=True)
    candidate_name = models.CharField(_("ФИО кандидата"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_gdrive_huntflow_links',
        verbose_name=_("Кто создал"),
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_gdrive_huntflow_links',
        verbose_name=_("Кто обновил"),
    )

    class Meta:
        verbose_name = _("Связка GDrive↔Huntflow")
        verbose_name_plural = _("Связки GDrive↔Huntflow")
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=['gdrive_file_id']),
        ]

    def __str__(self):
        return f"GDrive {self.gdrive_file_id[:20]}… → Huntflow {self.applicant_id}"


class MeetHuntflowLink(models.Model):
    """
    Связка Google Meet встречи с кандидатом в Huntflow (общая для всех).

    Заполняется при создании инвайта (когда в календарном событии появляется
    ссылка на Google Meet). Используется расширением на странице meet.google.com
    для отображения кнопок: копирование грейда, Scorecard, контакт.
    Аудит: created_by/updated_by для логирования.
    """
    # Нормализованный код встречи (например xim-pyga-awt) или полный URL
    meet_code = models.CharField(
        _("Код встречи Google Meet"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_("Часть URL после meet.google.com/, например xim-pyga-awt"),
    )
    meet_url = models.URLField(
        _("Полный URL встречи"),
        max_length=500,
        blank=True,
        help_text=_("Полная ссылка на встречу (https://meet.google.com/...)"),
    )

    account_id = models.IntegerField(_("Huntflow account_id"), blank=True, null=True)
    applicant_id = models.IntegerField(_("Huntflow applicant_id"), blank=True, null=True)
    vacancy_id = models.IntegerField(_("Huntflow vacancy_id"), blank=True, null=True)

    candidate_name = models.CharField(_("Имя кандидата"), max_length=255, blank=True)
    vacancy_title = models.CharField(_("Название вакансии"), max_length=255, blank=True)
    candidate_grade = models.CharField(_("Грейд/уровень"), max_length=100, blank=True)

    scorecard_url = models.URLField(_("Ссылка на Scorecard"), max_length=800, blank=True)
    huntflow_candidate_url = models.URLField(
        _("Ссылка на кандидата в Huntflow"),
        max_length=800,
        blank=True,
    )

    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_meet_huntflow_links',
        verbose_name=_("Кто создал"),
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_meet_huntflow_links',
        verbose_name=_("Кто обновил"),
    )

    class Meta:
        verbose_name = _("Связка Meet↔Huntflow")
        verbose_name_plural = _("Связки Meet↔Huntflow")
        indexes = [
            models.Index(fields=['meet_code']),
        ]

    def __str__(self):
        return f"Meet {self.meet_code} -> {self.candidate_name}"


class LinkedInThreadProfile(models.Model):
    """
    Маппинг LinkedIn thread_id (из /messaging/thread/<id>/) → profile_url.
    
    Используется Chrome-расширением для определения профиля кандидата
    на странице сообщений LinkedIn, где нет прямой ссылки на профиль.
    
    Расширение автоматически сохраняет thread_id при посещении профиля,
    затем использует его на странице /messaging/ для восстановления профиля.
    """
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='linkedin_thread_profiles',
        verbose_name=_("Пользователь"),
    )
    
    thread_id = models.CharField(
        _("LinkedIn Thread ID"),
        max_length=255,
        help_text="ID треда из URL /messaging/thread/<thread_id>/"
    )
    
    profile_url = models.URLField(
        _("LinkedIn Profile URL"),
        max_length=500,
        help_text="Нормализованный URL профиля (https://www.linkedin.com/in/<username>/)"
    )
    
    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    last_accessed_at = models.DateTimeField(_("Последний доступ"), default=timezone.now)
    
    class Meta:
        verbose_name = _("Маппинг LinkedIn Thread→Profile")
        verbose_name_plural = _("Маппинги LinkedIn Thread→Profile")
        unique_together = (('user', 'thread_id'),)
        indexes = [
            models.Index(fields=['user', 'thread_id']),
            models.Index(fields=['user', 'profile_url']),
        ]
    
    def __str__(self):
        return f"{self.thread_id} -> {self.profile_url} ({self.user.username})"


class LevelText(models.Model):
    """
    Тексты для уровней кандидатов из Huntflow (общие для всех пользователей).

    Позволяет сохранять многострочный текст для каждого уровня по вакансии.
    Уровни привязаны к вакансии: вакансия → уровни.
    Аудит: created_by/updated_by для логирования.
    """

    vacancy_name = models.CharField(
        _("Вакансия"),
        max_length=255,
        help_text="Название вакансии из Huntflow (например: Frontend, Backend)",
    )

    level = models.CharField(
        _("Уровень"),
        max_length=100,
        help_text="Название уровня из Huntflow (например: Junior, Middle, Senior)"
    )

    text = models.TextField(
        _("Текст"),
        blank=True,
        help_text="Многострочный текст для этого уровня"
    )

    created_at = models.DateTimeField(_("Создано"), default=timezone.now)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_level_texts',
        verbose_name=_("Кто создал"),
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_level_texts',
        verbose_name=_("Кто обновил"),
    )

    class Meta:
        verbose_name = _("Текст для уровня")
        verbose_name_plural = _("Тексты для уровней")
        unique_together = (('vacancy_name', 'level'),)
        indexes = [
            models.Index(fields=['vacancy_name', 'level']),
        ]

    def __str__(self):
        return f"{self.vacancy_name}: {self.level}"


# ==================== МОДЕЛИ ДЛЯ HH.RU ИНТЕГРАЦИИ ====================

class HHResponse(models.Model):
    """
    Модель для сохранения откликов из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ: ID отклика из HH.ru, данные резюме, статус
    ИСТОЧНИКИ ДАННЫХ: HH.ru API
    ОБРАБОТКА: Сохранение и отслеживание откликов из HH.ru
    ВЫХОДЯЩИЕ ДАННЫЕ: Информация об отклике в базе данных
    СВЯЗИ: User, HuntflowApplicant
    ФОРМАТ: Django модель
    """
    
    RESPONSE_STATE_CHOICES = [
        ('invitation', 'Приглашение'),
        ('applied', 'Отклик'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('ignored', 'Проигнорировано'),
    ]
    
    IMPORT_STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('imported', 'Импортирован'),
        ('filtered', 'Отфильтрован'),
        ('error', 'Ошибка'),
        ('skipped', 'Пропущен'),
    ]
    
    # Основные поля
    hh_response_id = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Уникальный ID отклика на HH.ru"
    )
    hh_vacancy_id = models.CharField(
        max_length=50,
        help_text="ID вакансии на HH.ru"
    )
    
    # Данные кандидата
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Дополнительная информация
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    location = models.CharField(max_length=100, blank=True)
    location_id = models.CharField(max_length=10, blank=True)
    
    # Опыт работы (JSON)
    experience_json = models.JSONField(
        default=list,
        help_text="История опыта работы в формате JSON"
    )
    
    # Навыки (JSON)
    skills_json = models.JSONField(
        default=list,
        help_text="Список навыков в формате JSON"
    )
    
    # Полный текст резюме
    resume_text = models.TextField(blank=True)
    
    # Ссылки
    hh_resume_url = models.URLField(blank=True)
    hh_applicant_url = models.URLField(blank=True)
    
    # Статусы
    response_state = models.CharField(
        max_length=20,
        choices=RESPONSE_STATE_CHOICES,
        default='applied'
    )
    import_status = models.CharField(
        max_length=20,
        choices=IMPORT_STATUS_CHOICES,
        default='pending'
    )
    
    # Данные о фильтрации
    filter_reasons = models.JSONField(
        default=list,
        help_text="Причины отфильтрации кандидата"
    )
    filter_score = models.FloatField(
        default=0.0,
        help_text="Оценка совпадения с фильтрами (0-100)"
    )
    
    # Связь с Huntflow
    account_id = models.IntegerField(null=True, blank=True)
    vacancy_id = models.IntegerField(null=True, blank=True)
    applicant_id = models.IntegerField(null=True, blank=True)
    
    # Пользователь, который импортировал
    imported_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_hh_responses'
    )
    
    # Метаинформация
    raw_data = models.JSONField(
        default=dict,
        help_text="Полные данные из HH.ru API"
    )
    
    # Временные метки
    hh_created_at = models.DateTimeField(
        help_text="Когда был создан отклик на HH.ru"
    )
    hh_updated_at = models.DateTimeField(
        help_text="Когда отклик был обновлен на HH.ru"
    )
    imported_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Когда отклик был импортирован в нашу систему"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Когда отклик был обработан"
    )
    
    class Meta:
        db_table = 'hh_responses'
        ordering = ['-hh_updated_at']
        indexes = [
            models.Index(fields=['account_id', 'vacancy_id']),
            models.Index(fields=['import_status']),
            models.Index(fields=['hh_vacancy_id']),
            models.Index(fields=['email']),
            models.Index(fields=['hh_response_id']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.import_status}"
    
    def calculate_age(self):
        """Рассчитывает возраст кандидата"""
        if self.birth_date:
            today = timezone.now().date()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None
    
    def calculate_experience_years(self):
        """Рассчитывает общий стаж работы в годах"""
        from datetime import datetime, date
        
        experience_list = self.experience_json or []
        total_days = 0
        today = date.today()
        
        for exp in experience_list:
            try:
                start_str = exp.get('start', '')
                end_str = exp.get('end')
                
                if 'T' in start_str:
                    start = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
                else:
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                
                if end_str:
                    if 'T' in end_str:
                        end = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
                    else:
                        end = datetime.strptime(end_str, '%Y-%m-%d').date()
                else:
                    end = today
                
                total_days += (end - start).days
            except (ValueError, TypeError):
                continue
        
        return total_days / 365.25 if total_days > 0 else 0


class HHSyncConfiguration(models.Model):
    """
    Конфигурация синхронизации откликов из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ: user, account_id, vacancy_id, фильтры
    ИСТОЧНИКИ ДАННЫХ: Конфигурация пользователя
    ОБРАБОТКА: Сохранение и управление конфигурациями синхронизации
    ВЫХОДЯЩИЕ ДАННЫЕ: Сохраненные конфигурации в базе данных
    СВЯЗИ: User, HHResponse
    ФОРМАТ: Django модель
    """
    
    SYNC_FREQUENCY_CHOICES = [
        ('hourly', 'Каждый час'),
        ('every_6_hours', 'Каждые 6 часов'),
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('manual', 'Ручная синхронизация'),
    ]
    
    # Идентификация
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='hh_sync_configurations'
    )
    account_id = models.IntegerField()
    vacancy_id = models.IntegerField()
    hh_vacancy_id = models.CharField(max_length=50)
    
    # Фильтры (JSON)
    filters = models.JSONField(
        default=dict,
        help_text="""
        {
            "allowed_locations": ["1", "2"],
            "allowed_genders": ["any"],
            "min_age": 18,
            "max_age": 65,
            "check_existing": true,
            "min_experience_years": 1,
            "max_experience_years": 50
        }
        """
    )
    
    # Настройки синхронизации
    enabled = models.BooleanField(default=True)
    sync_frequency = models.CharField(
        max_length=20,
        choices=SYNC_FREQUENCY_CHOICES,
        default='daily'
    )
    
    # Статистика
    total_responses_found = models.IntegerField(default=0)
    total_responses_imported = models.IntegerField(default=0)
    total_responses_filtered = models.IntegerField(default=0)
    total_responses_errors = models.IntegerField(default=0)
    
    # Дополнительные опции
    auto_add_to_project = models.BooleanField(
        default=False,
        help_text="Автоматически добавлять импортированных кандидатов в проект"
    )
    project_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID проекта для автоматического добавления"
    )
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Дата последней успешной синхронизации"
    )
    next_scheduled_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Дата следующей запланированной синхронизации"
    )
    
    class Meta:
        db_table = 'hh_sync_configurations'
        unique_together = ('user', 'account_id', 'vacancy_id')
        indexes = [
            models.Index(fields=['user', 'enabled']),
            models.Index(fields=['sync_frequency']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Синхронизация вакансии {self.vacancy_id}"
    
    def get_filters(self):
        """Получает фильтры в виде словаря с значениями по умолчанию"""
        default_filters = {
            'allowed_locations': ['1', '2', '3'],
            'allowed_genders': ['male', 'female', 'any'],
            'min_age': 18,
            'max_age': 65,
            'check_existing': True,
            'min_experience_years': 1,
            'max_experience_years': 50
        }
        
        if self.filters:
            default_filters.update(self.filters)
        
        return default_filters
    
    def set_filters(self, filters):
        """Устанавливает фильтры"""
        self.filters = filters
        self.save()
    
    def update_statistics(self, import_result):
        """Обновляет статистику на основе результатов импорта"""
        self.total_responses_found += import_result.get('total_responses', 0)
        self.total_responses_imported += import_result.get('imported', 0)
        self.total_responses_filtered += import_result.get('filtered_out', 0)
        self.total_responses_errors += import_result.get('errors', 0)
        self.last_sync = timezone.now()
        self.save()
    
    def schedule_next_sync(self):
        """Планирует следующую синхронизацию в зависимости от частоты"""
        from datetime import timedelta
        
        frequency_map = {
            'hourly': timedelta(hours=1),
            'every_6_hours': timedelta(hours=6),
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1),
            'manual': None,  # Не планировать автоматически
        }
        
        delta = frequency_map.get(self.sync_frequency)
        if delta:
            self.next_scheduled_sync = timezone.now() + delta
            self.save()


class HHSyncLog(models.Model):
    """
    Логирование синхронизаций из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ: configuration, результаты синхронизации
    ИСТОЧНИКИ ДАННЫЕ: HH.ru API, процесс импорта
    ОБРАБОТКА: Ведение логов синхронизации
    ВЫХОДЯЩИЕ ДАННЫЕ: История синхронизаций в базе данных
    СВЯЗИ: HHSyncConfiguration
    ФОРМАТ: Django модель
    """
    
    STATUS_CHOICES = [
        ('started', 'Начато'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
        ('partial', 'Частичное завершение'),
    ]
    
    configuration = models.ForeignKey(
        HHSyncConfiguration,
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )
    
    # Статус
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='started'
    )
    
    # Результаты
    total_responses = models.IntegerField(default=0)
    imported_count = models.IntegerField(default=0)
    filtered_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Ошибки
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict)
    
    # Статистика
    sync_duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Длительность синхронизации в секундах"
    )
    
    # Метаинформация
    filter_summary = models.JSONField(
        default=dict,
        help_text="Резюме фильтрации (reason: count)"
    )
    
    # Временные метки
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'hh_sync_logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['configuration', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Синхронизация {self.configuration} - {self.get_status_display()}"
    
    def mark_completed(self):
        """Отмечает синхронизацию как завершенную"""
        self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.sync_duration_seconds = int(delta.total_seconds())
        self.save()
    
    def mark_failed(self, error_message, error_details=None):
        """Отмечает синхронизацию как ошибку"""
        self.status = 'failed'
        self.error_message = error_message
        self.error_details = error_details or {}
        self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.sync_duration_seconds = int(delta.total_seconds())
        self.save()


class HHFilterStatistics(models.Model):
    """
    Статистика фильтрации откликов из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ: configuration, результаты фильтрации
    ИСТОЧНИКИ ДАННЫЕ: HH.ru API отклики
    ОБРАБОТКА: Агрегирование статистики фильтрации
    ВЫХОДЯЩИЕ ДАННЫЕ: Аналитика фильтрации в базе данных
    СВЯЗИ: HHSyncConfiguration
    ФОРМАТ: Django модель
    """
    
    configuration = models.OneToOneField(
        HHSyncConfiguration,
        on_delete=models.CASCADE,
        related_name='filter_statistics'
    )
    
    # Счетчики по причинам отклонения
    location_mismatch_count = models.IntegerField(default=0)
    gender_mismatch_count = models.IntegerField(default=0)
    age_mismatch_count = models.IntegerField(default=0)
    experience_mismatch_count = models.IntegerField(default=0)
    already_in_db_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)
    
    # Процентное распределение
    location_mismatch_percent = models.FloatField(default=0)
    gender_mismatch_percent = models.FloatField(default=0)
    age_mismatch_percent = models.FloatField(default=0)
    experience_mismatch_percent = models.FloatField(default=0)
    already_in_db_percent = models.FloatField(default=0)
    other_percent = models.FloatField(default=0)
    
    # Общая статистика
    total_responses = models.IntegerField(default=0)
    accepted_count = models.IntegerField(default=0)
    rejection_rate = models.FloatField(default=0.0)
    
    # Временные метки
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'hh_filter_statistics'
    
    def __str__(self):
        return f"Статистика фильтрации для {self.configuration}"
    
    def update_from_filter_results(self, filter_results):
        """Обновляет статистику на основе результатов фильтрации"""
        
        rejected = filter_results.get('rejected', {})
        
        self.location_mismatch_count = len(rejected.get('location_mismatch', []))
        self.gender_mismatch_count = len(rejected.get('gender_mismatch', []))
        self.age_mismatch_count = len(rejected.get('age_mismatch', []))
        self.experience_mismatch_count = len(rejected.get('experience_mismatch', []))
        self.already_in_db_count = len(rejected.get('already_in_db', []))
        self.other_count = len(rejected.get('other', []))
        
        self.accepted_count = filter_results.get('passed_filter', 0)
        self.total_responses = filter_results.get('total_responses', 0)
        
        if self.total_responses > 0:
            self.location_mismatch_percent = (self.location_mismatch_count / self.total_responses) * 100
            self.gender_mismatch_percent = (self.gender_mismatch_count / self.total_responses) * 100
            self.age_mismatch_percent = (self.age_mismatch_count / self.total_responses) * 100
            self.experience_mismatch_percent = (self.experience_mismatch_count / self.total_responses) * 100
            self.already_in_db_percent = (self.already_in_db_count / self.total_responses) * 100
            self.other_percent = (self.other_count / self.total_responses) * 100
            
            self.rejection_rate = (1 - (self.accepted_count / self.total_responses)) * 100
        
        self.save()
