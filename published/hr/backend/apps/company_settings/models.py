"""
Модели для настроек компании
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MaxLengthValidator
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class CompanySettings(models.Model):
    """Настройки компании - синглтон модель"""
    
    # Название компании
    company_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Название компании',
        help_text='Название вашей компании'
    )
    
    # Главный календарь компании (ID календаря Google Calendar)
    main_calendar_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='ID главного календаря',
        help_text='ID календаря Google Calendar для компании'
    )
    
    # Оргструктура организации (JSON)
    org_structure = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Оргструктура',
        help_text='Организационная структура компании в формате JSON'
    )
    
    # Цветовая тема компании
    THEME_CHOICES = [
        ('light', _('Светлая')),
        ('dark', _('Тёмная')),
        ('auto', _('Автоматическая (по системе)')),
    ]
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='auto',
        verbose_name='Тема оформления',
        help_text='Цветовая тема интерфейса'
    )
    
    # Активные грейды компании
    active_grades = models.ManyToManyField(
        'finance.Grade',
        blank=True,
        verbose_name='Активные грейды компании',
        help_text='Грейды, которые используются в вашей компании',
        related_name='company_settings'
    )
    
    # Адрес офиса компании
    office_address = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Адрес офиса',
        help_text='Полный адрес офиса компании'
    )
    
    # Ссылка на карты
    office_map_link = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='Ссылка на карты',
        help_text='Ссылка на Google Maps, Yandex Maps или другую карту'
    )
    
    # Описание, как пройти
    office_directions = models.TextField(
        blank=True,
        verbose_name='Как пройти',
        help_text='Подробное описание, как добраться до офиса (ориентиры, этаж, вход и т.д.)'
    )
    
    # Инструкции для офисного интервью
    office_interview_instructions = models.TextField(
        blank=True,
        verbose_name='Инструкции для офисного интервью',
        help_text='Инструкции для кандидатов, которые приходят на офисное интервью (что взять с собой, куда обратиться, контакты и т.д.)'
    )
    
    # Игнорировать не принятые встречи (логика использования — отдельно)
    ignore_non_accepted_meetings = models.BooleanField(
        default=False,
        verbose_name='Игнорировать не принятые встречи',
        help_text='Если включено: при расчёте слотов встречи без подтверждения не считаются занятыми. Если выключено: любая встреча, кроме отклонённой, занимает слот.'
    )
    
    # Базовые часы работы компании (если не заданы — используются часы из профиля пользователя)
    work_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('Начало рабочего времени компании'),
        help_text=_('Время начала рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.')
    )
    work_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('Конец рабочего времени компании'),
        help_text=_('Время окончания рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.')
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'Настройки компании'
        verbose_name_plural = 'Настройки компании'
    
    def __str__(self):
        return f"Настройки компании: {self.company_name or 'Без названия'}"
    
    def save(self, *args, **kwargs):
        # Принудительно устанавливаем ID=1 для синглтона
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Получает или создает настройки компании (синглтон)"""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'company_name': '',
                'main_calendar_id': '',
                'org_structure': {},
                'theme': 'auto',
                'office_address': '',
                'office_map_link': '',
                'office_directions': '',
                'office_interview_instructions': '',
                'ignore_non_accepted_meetings': False,
            }
        )
        return settings
    
    def get_active_grades_list(self):
        """Возвращает список активных грейдов компании"""
        return list(self.active_grades.all().values_list('name', flat=True))
    
    def get_active_grades_display(self):
        """Возвращает строку с активными грейдами для отображения"""
        grades = self.active_grades.all()
        if grades:
            return ', '.join([grade.name for grade in grades])
        return 'Не выбрано'
    
    @classmethod
    def get_active_grades(cls):
        """Получает активные грейды компании"""
        settings = cls.get_settings()
        return settings.active_grades.all()
    
    @classmethod
    def is_grade_active(cls, grade):
        """
        Проверяет, является ли грейд активным для компании
        
        Args:
            grade: Объект Grade или название грейда (str)
        
        Returns:
            bool
        """
        settings = cls.get_settings()
        
        if isinstance(grade, str):
            # Если передан строковый идентификатор, ищем по имени
            return settings.active_grades.filter(name=grade).exists()
        else:
            # Если передан объект Grade
            return settings.active_grades.filter(id=grade.id).exists()


class RejectionTemplate(models.Model):
    """Шаблоны стандартных ответов для отказа специалистам"""
    
    REJECTION_TYPE_CHOICES = [
        ('office_format', _('Офисный формат')),
        ('finance', _('Финансы')),
        ('finance_more', _('Финансы - больше')),
        ('finance_less', _('Финансы - меньше')),
        ('grade', _('Грейд')),
        ('general', _('Общий отказ')),
    ]
    
    rejection_type = models.CharField(
        max_length=20,
        choices=REJECTION_TYPE_CHOICES,
        verbose_name='Тип отказа',
        help_text='Тип причины отказа'
    )
    
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Грейд',
        help_text='Грейд (заполняется только для типа "Грейд")',
        related_name='rejection_templates'
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name='Название шаблона',
        help_text='Краткое название шаблона для идентификации'
    )
    
    message = models.TextField(
        verbose_name='Текст ответа',
        help_text='Текст стандартного ответа для отказа',
        validators=[MaxLengthValidator(5000)]
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Используется ли этот шаблон'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'Шаблон отказа'
        verbose_name_plural = 'Шаблоны отказов'
        ordering = ['rejection_type', 'grade__name', 'title']
    
    def __str__(self):
        if self.rejection_type == 'grade' and self.grade:
            return f"{self.get_rejection_type_display()} - {self.grade.name}: {self.title}"
        return f"{self.get_rejection_type_display()}: {self.title}"
    
    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        
        # Для типа "grade" обязательно должно быть указано поле grade
        if self.rejection_type == 'grade' and not self.grade:
            raise ValidationError({
                'grade': _('Для типа отказа "Грейд" обязательно укажите грейд')
            })
        
        # Для других типов grade должен быть пустым
        if self.rejection_type != 'grade' and self.grade:
            raise ValidationError({
                'grade': _('Поле "Грейд" заполняется только для типа отказа "Грейд"')
            })
    
    @classmethod
    def get_template(cls, rejection_type, grade=None):
        """
        Получает шаблон отказа по типу и грейду
        
        Args:
            rejection_type: Тип отказа ('office_format', 'finance', 'grade', 'general')
            grade: Объект Grade (обязательно для типа 'grade')
        
        Returns:
            RejectionTemplate или None
        """
        queryset = cls.objects.filter(is_active=True, rejection_type=rejection_type)
        
        if rejection_type == 'grade':
            if not grade:
                return None
            queryset = queryset.filter(grade=grade)
        else:
            queryset = queryset.filter(grade__isnull=True)
        
        return queryset.first()
    
    @classmethod
    def get_templates_by_type(cls, rejection_type):
        """
        Получает все активные шаблоны указанного типа
        
        Args:
            rejection_type: Тип отказа
        
        Returns:
            QuerySet шаблонов
        """
        queryset = cls.objects.filter(is_active=True, rejection_type=rejection_type)
        
        if rejection_type != 'grade':
            queryset = queryset.filter(grade__isnull=True)
        
        return queryset.order_by('title')


class VacancyPrompt(models.Model):
    """Единый промпт для анализа вакансий - синглтон модель"""
    
    prompt = models.TextField(
        verbose_name='Текст промпта',
        help_text='Промпт для анализа вакансий с помощью AI',
        default='Проанализируй вакансию и предоставь детальную информацию о требованиях, зарплате и условиях работы.'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Используется ли этот промпт для анализа вакансий'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'Промпт для вакансий'
        verbose_name_plural = 'Промпты для вакансий'
    
    def __str__(self):
        status = 'Активен' if self.is_active else 'Неактивен'
        return f"Промпт для вакансий ({status})"
    
    def save(self, *args, **kwargs):
        # Извлекаем updated_by из kwargs перед сохранением
        updated_by = kwargs.pop('updated_by', None)
        
        # Проверяем, были ли изменения (только если объект уже существует)
        if self.pk:
            try:
                old_obj = VacancyPrompt.objects.get(pk=self.pk)
                prompt_changed = old_obj.prompt != self.prompt
                status_changed = old_obj.is_active != self.is_active
                has_changes = prompt_changed or status_changed
            except VacancyPrompt.DoesNotExist:
                has_changes = True
        else:
            has_changes = True
        
        # Принудительно устанавливаем ID=1 для синглтона
        self.pk = 1
        super().save(*args, **kwargs)
        
        # Создаем запись в истории только при наличии изменений
        if has_changes and self.prompt and updated_by:  # Только если промпт не пустой и есть пользователь
            VacancyPromptHistory.objects.create(
                prompt=self,
                prompt_text=self.prompt,
                is_active=self.is_active,
                updated_by=updated_by
            )
    
    @classmethod
    def get_prompt(cls):
        """Получает или создает промпт для вакансий (синглтон)"""
        prompt, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'prompt': 'Проанализируй вакансию и предоставь детальную информацию о требованиях, зарплате и условиях работы.',
                'is_active': True
            }
        )
        return prompt


class VacancyPromptHistory(models.Model):
    """История изменений промпта для вакансий"""
    
    prompt = models.ForeignKey(
        VacancyPrompt,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Промпт',
        null=True,
        blank=True
    )
    
    prompt_text = models.TextField(
        verbose_name='Текст промпта',
        help_text='Текст промпта на момент сохранения'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Был ли промпт активен на момент сохранения'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Обновил',
        help_text='Пользователь, который внес изменения'
    )
    
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'История промпта'
        verbose_name_plural = 'История промптов'
        ordering = ['-updated_at']
    
    def __str__(self):
        user_name = self.updated_by.get_full_name() or self.updated_by.username if self.updated_by else 'Неизвестно'
        return f"История от {self.updated_at.strftime('%d.%m.%Y %H:%M')} ({user_name})"

