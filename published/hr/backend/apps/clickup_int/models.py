from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import json

User = get_user_model()


class ClickUpSettings(models.Model):
    """Настройки интеграции с ClickUp для пользователя"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='Пользователь',
        related_name='clickup_settings'
    )
    
    # API настройки (используем из профиля пользователя)
    # api_token теперь берется из user.clickup_api_key
    
    # Настройки пути
    team_id = models.CharField(
        max_length=100,
        verbose_name='ID команды',
        help_text='ID команды в ClickUp'
    )
    
    space_id = models.CharField(
        max_length=100,
        verbose_name='ID пространства',
        help_text='ID пространства в ClickUp'
    )
    
    folder_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID папки',
        help_text='ID папки в ClickUp (опционально)'
    )
    
    list_id = models.CharField(
        max_length=100,
        verbose_name='ID списка',
        help_text='ID списка задач в ClickUp'
    )
    
    # Дополнительные настройки
    auto_sync = models.BooleanField(
        default=True,
        verbose_name='Автоматическая синхронизация',
        help_text='Автоматически синхронизировать задачи'
    )
    
    sync_interval = models.PositiveIntegerField(
        default=30,
        verbose_name='Интервал синхронизации (минуты)',
        help_text='Интервал автоматической синхронизации в минутах'
    )
    
    # Фильтрация по тегу huntflow
    HUNTFLOW_FILTER_CHOICES = [
        ('all', 'Все задачи'),
        ('with_huntflow', 'Только с тегом huntflow'),
        ('without_huntflow', 'Только без тега huntflow'),
    ]
    
    huntflow_filter = models.CharField(
        max_length=20,
        choices=HUNTFLOW_FILTER_CHOICES,
        default='all',
        verbose_name='Фильтр по тегу huntflow',
        help_text='Выберите, какие задачи синхронизировать по тегу huntflow'
    )
    
    # Папка для плана найма (вытягивание данных из ClickUp)
    hiring_plan_folder_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID папки для плана найма',
        help_text='Папка в ClickUp, из которой вытягиваются списки и задачи для плана найма'
    )
    hiring_plan_space_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID пространства папки плана найма',
        help_text='Пространство, в котором находится папка плана найма (для UI)'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя синхронизация')
    
    class Meta:
        verbose_name = 'Настройки ClickUp'
        verbose_name_plural = 'Настройки ClickUp'
        db_table = 'clickup_settings'
    
    def __str__(self):
        return f'ClickUp настройки для {self.user.username}'
    
    def clean(self):
        """Валидация настроек"""
        # Проверяем, что пользователь установлен
        if not hasattr(self, 'user') or not self.user:
            return
            
        if not self.user.clickup_api_key:
            raise ValidationError('API токен ClickUp не настроен в профиле пользователя')
        
        if not self.team_id:
            raise ValidationError('ID команды обязателен')
        
        if not self.space_id:
            raise ValidationError('ID пространства обязателен')
        
        if not self.list_id:
            raise ValidationError('ID списка обязателен')
    
    def get_api_token(self):
        """Получает API токен из профиля пользователя"""
        if hasattr(self, 'user') and self.user:
            return self.user.clickup_api_key
        return None
    
    def get_path_description(self):
        """Возвращает описание пути к задачам"""
        path_parts = []
        
        if self.team_id:
            path_parts.append(f"Команда: {self.team_id}")
        
        if self.space_id:
            path_parts.append(f"Пространство: {self.space_id}")
        
        if self.folder_id:
            path_parts.append(f"Папка: {self.folder_id}")
        
        if self.list_id:
            path_parts.append(f"Список: {self.list_id}")
        
        return " → ".join(path_parts)
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Получить или создать настройки для пользователя"""
        settings, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'team_id': '',
                'space_id': '',
                'list_id': '',
            }
        )
        return settings


class ClickUpTask(models.Model):
    """Кэшированные задачи из ClickUp"""
    
    # Основные поля задачи
    task_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='ID задачи',
        help_text='Уникальный ID задачи в ClickUp'
    )
    
    name = models.CharField(
        max_length=500,
        verbose_name='Название задачи'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Описание задачи'
    )
    
    status = models.CharField(
        max_length=100,
        verbose_name='Статус задачи'
    )
    
    priority = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Приоритет'
    )
    
    # Даты
    date_created = models.DateTimeField(null=True, blank=True, verbose_name='Дата создания')
    date_updated = models.DateTimeField(null=True, blank=True, verbose_name='Дата обновления')
    due_date = models.DateTimeField(null=True, blank=True, verbose_name='Срок выполнения')
    
    # Ссылки и файлы
    url = models.URLField(verbose_name='Ссылка на задачу')
    attachments = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Вложения',
        help_text='Список вложений в формате JSON'
    )
    
    # Дополнительные данные
    assignees = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Исполнители',
        help_text='Список исполнителей в формате JSON'
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Теги',
        help_text='Список тегов в формате JSON'
    )
    
    # Дополнительные поля (custom fields)
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные поля',
        help_text='Дополнительные поля задачи в формате JSON'
    )
    
    # Метаданные
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='clickup_tasks'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано в системе')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено в системе')
    
    class Meta:
        verbose_name = 'Задача ClickUp'
        verbose_name_plural = 'Задачи ClickUp'
        db_table = 'clickup_tasks'
        ordering = ['-date_updated']
    
    def __str__(self):
        return f'{self.name} ({self.task_id})'
    
    def get_assignees_display(self):
        """Возвращает список исполнителей для отображения"""
        if not self.assignees:
            return []
        
        try:
            if isinstance(self.assignees, str):
                assignees = json.loads(self.assignees)
            else:
                assignees = self.assignees
            
            return [assignee.get('username', assignee.get('email', 'Неизвестно')) for assignee in assignees]
        except (json.JSONDecodeError, TypeError):
            return []
    
    def get_tags_display(self):
        """Возвращает список тегов для отображения"""
        if not self.tags:
            return []
        
        try:
            if isinstance(self.tags, str):
                tags = json.loads(self.tags)
            else:
                tags = self.tags
            
            return [tag.get('name', str(tag)) for tag in tags]
        except (json.JSONDecodeError, TypeError):
            return []
    
    def get_attachments_display(self):
        """Возвращает список вложений для отображения"""
        if not self.attachments:
            return []
        
        try:
            if isinstance(self.attachments, str):
                attachments = json.loads(self.attachments)
            else:
                attachments = self.attachments
            
            return [
                {
                    'name': att.get('title', att.get('name', 'Файл')),
                    'url': att.get('url', ''),
                    'size': att.get('size', 0),
                    'type': att.get('type', 'unknown')
                }
                for att in attachments
            ]
        except (json.JSONDecodeError, TypeError):
            return []
    
    def get_custom_fields_display(self):
        """Возвращает дополнительные поля для отображения (только с заполненными значениями)"""
        if not self.custom_fields:
            return []
        
        try:
            if isinstance(self.custom_fields, str):
                custom_fields = json.loads(self.custom_fields)
            else:
                custom_fields = self.custom_fields
            
            # Преобразуем в список для удобного отображения
            fields_list = []
            for field_id, field_data in custom_fields.items():
                if isinstance(field_data, dict):
                    field_name = field_data.get('name', f'Поле {field_id}')
                    field_value = field_data.get('value', '')
                    field_type = field_data.get('type', 'text')
                    
                    # Пропускаем поля без значений
                    if not field_value:
                        continue
                    
                    # Проверяем, что это строка, и она не пустая
                    if isinstance(field_value, str) and field_value.strip() == '':
                        continue
                    
                    # Если это список, проверяем, что он не пустой
                    if isinstance(field_value, list) and len(field_value) == 0:
                        continue
                    
                    fields_list.append({
                        'id': field_id,
                        'name': field_name,
                        'value': field_value,
                        'type': field_type
                    })
                else:
                    # Если данные в простом формате
                    field_value = str(field_data)
                    if field_value and field_value.strip() != '':
                        fields_list.append({
                            'id': field_id,
                            'name': f'Поле {field_id}',
                            'value': field_value,
                            'type': 'text'
                        })
            
            return fields_list
        except (json.JSONDecodeError, TypeError):
            return []


class ClickUpSyncLog(models.Model):
    """Лог синхронизации с ClickUp"""
    
    SYNC_STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('partial', 'Частично'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='clickup_sync_logs'
    )
    
    status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        verbose_name='Статус синхронизации'
    )
    
    tasks_processed = models.PositiveIntegerField(
        default=0,
        verbose_name='Обработано задач'
    )
    
    tasks_created = models.PositiveIntegerField(
        default=0,
        verbose_name='Создано задач'
    )
    
    tasks_updated = models.PositiveIntegerField(
        default=0,
        verbose_name='Обновлено задач'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    
    sync_duration = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Длительность синхронизации (секунды)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время синхронизации')
    
    class Meta:
        verbose_name = 'Лог синхронизации ClickUp'
        verbose_name_plural = 'Логи синхронизации ClickUp'
        db_table = 'clickup_sync_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Синхронизация {self.user.username} - {self.get_status_display()} ({self.created_at})'


class ClickUpBulkImport(models.Model):
    """Модель для отслеживания массового импорта задач ClickUp"""
    
    STATUS_CHOICES = [
        ('running', 'Выполняется'),
        ('completed', 'Завершен'),
        ('failed', 'Ошибка'),
        ('cancelled', 'Отменен'),
        ('stopped', 'Остановлен'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='clickup_bulk_imports'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='running',
        verbose_name='Статус'
    )
    
    total_tasks = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего задач'
    )
    
    processed_tasks = models.PositiveIntegerField(
        default=0,
        verbose_name='Обработано задач'
    )
    
    successful_tasks = models.PositiveIntegerField(
        default=0,
        verbose_name='Успешно импортировано'
    )
    
    failed_tasks = models.PositiveIntegerField(
        default=0,
        verbose_name='Неудачных импортов'
    )
    
    failed_task_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name='ID неудачных задач',
        help_text='Список ID задач, которые не удалось импортировать'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='ID задачи Celery'
    )
    
    # Поле для выбранной вакансии в Huntflow
    huntflow_vacancy_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID вакансии в Huntflow',
        help_text='ID вакансии в Huntflow, к которой будут привязаны импортированные кандидаты'
    )
    
    # Опция передачи комментариев
    include_comments = models.BooleanField(
        default=True,
        verbose_name='Передавать комментарии в Huntflow',
        help_text='Если отмечено, комментарии из ClickUp будут переданы в Huntflow'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершено')
    
    class Meta:
        verbose_name = 'Массовый импорт ClickUp'
        verbose_name_plural = 'Массовые импорты ClickUp'
        db_table = 'clickup_bulk_imports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Массовый импорт {self.user.username} - {self.get_status_display()}'
    
    @property
    def progress_percentage(self):
        """Возвращает процент выполнения"""
        if self.total_tasks == 0:
            return 0
        return round((self.processed_tasks / self.total_tasks) * 100, 1)
    
    @property
    def success_rate(self):
        """Возвращает процент успешных импортов"""
        if self.processed_tasks == 0:
            return 0
        return round((self.successful_tasks / self.processed_tasks) * 100, 1)


class ClickUpHiringRequest(models.Model):
    """
    Заявка плана найма (hiring/transfer), вытянутая из папки ClickUp.
    Хранится отдельно от ClickUpTask (выгрузка в Huntflow). Один источник — папка плана найма.
    """
    REQUEST_TYPE_CHOICES = [
        ('hiring', 'Найм'),
        ('transfer', 'Перевод'),
        ('group', 'Группа'),
        ('unknown', 'Не определено'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='clickup_hiring_requests'
    )
    clickup_task_id = models.CharField(
        max_length=100,
        verbose_name='ID задачи ClickUp',
        db_index=True
    )
    name = models.CharField(max_length=500, verbose_name='Название', blank=True)
    clickup_status = models.CharField(max_length=100, verbose_name='Статус в ClickUp', blank=True)
    date_created = models.DateTimeField(null=True, blank=True, verbose_name='Дата создания в ClickUp')
    date_updated = models.DateTimeField(null=True, blank=True, verbose_name='Дата обновления в ClickUp')
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата начала')
    due_date = models.DateTimeField(null=True, blank=True, verbose_name='Срок')
    list_id = models.CharField(max_length=100, verbose_name='ID списка (спринт)', blank=True, db_index=True)
    list_name = models.CharField(max_length=255, verbose_name='Название списка (спринт)', blank=True)
    folder_id = models.CharField(max_length=100, verbose_name='ID папки', blank=True, db_index=True)
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        default='unknown',
        verbose_name='Тип заявки'
    )
    normalized_status = models.CharField(
        max_length=100,
        verbose_name='Нормализованный статус',
        blank=True,
        help_text='Маппинг статуса ClickUp в единый статус системы'
    )
    recruiter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_clickup_hiring_requests',
        verbose_name='Рекрутер'
    )
    department = models.CharField(max_length=255, verbose_name='Отдел/группа', blank=True)
    assignees = models.JSONField(default=list, blank=True, verbose_name='Ответственные (JSON)')
    creator = models.JSONField(default=dict, blank=True, verbose_name='Создатель (JSON)')
    custom_fields = models.JSONField(default=dict, blank=True, verbose_name='Кастомные поля ClickUp')
    raw_task = models.JSONField(default=dict, blank=True, verbose_name='Слепок задачи (для отладки)')
    synced_at = models.DateTimeField(auto_now=True, verbose_name='Время последней синхронизации')

    class Meta:
        verbose_name = 'Заявка плана найма (ClickUp)'
        verbose_name_plural = 'Заявки плана найма (ClickUp)'
        db_table = 'clickup_hiring_requests'
        ordering = ['-date_updated', '-synced_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'clickup_task_id'],
                name='unique_user_clickup_task_hiring'
            )
        ]

    def __str__(self):
        return f'{self.name or self.clickup_task_id} ({self.get_request_type_display()})'
