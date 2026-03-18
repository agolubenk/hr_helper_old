"""
Документация по проблемным импортам (линтер):
- django.db, django.contrib.auth, django.core.exceptions, django.utils
- apps.huntflow.utils (вспомогательные функции для интеграции)

Влияние: модели вакансий, валидация и интеграции с Huntflow (получение статусов,
связанная логика активностей) зависят от этих импортов. При их недоступности сохранение
моделей, расчёт активности и отображение связанных данных могут не работать.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.finance.models import Grade, Currency

User = get_user_model()


class Vacancy(models.Model):
    """Модель для локальных данных по вакансиям"""
    
    name = models.CharField(
        max_length=200, 
        verbose_name='Название вакансии',
        help_text='Название вакансии'
    )
    
    external_id = models.CharField(
        max_length=100,
        verbose_name='ID для связи',
        help_text='Внешний идентификатор для связи с внешними системами',
        unique=True
    )
    
    recruiter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vacancies',
        verbose_name='Ответственный рекрутер',
        help_text='Рекрутер, ответственный за вакансию',
        limit_choices_to={'groups__name': 'Рекрутер'}  # Ограничиваем выбор только рекрутерами
    )
    
    additional_recruiters = models.ManyToManyField(
        User,
        related_name='vacancies_extra_recruiters',
        verbose_name='Дополнительные рекрутеры',
        help_text='Дополнительные рекрутеры по вакансии (опционально)',
        limit_choices_to={'groups__name': 'Рекрутер'},
        blank=True
    )
    
    invite_title = models.CharField(
        max_length=200,
        verbose_name='Заголовок инвайтов',
        help_text='Заголовок для приглашений кандидатов'
    )
    
    invite_text = models.TextField(
        verbose_name='Сопровождающий текст для инвайтов',
        help_text='Текст сопроводительного письма для приглашений'
    )
    
    scorecard_title = models.CharField(
        max_length=200,
        verbose_name='Заголовок Scorecard',
        help_text='Заголовок для Scorecard'
    )
    
    scorecard_link = models.URLField(
        verbose_name='Ссылка на Scorecard',
        help_text='Ссылка на Scorecard для оценки кандидатов',
        blank=True
    )
    
    questions_belarus = models.TextField(
        verbose_name='Вопросы Беларусь',
        help_text='Вопросы для интервью в Беларуси',
        blank=True
    )
    
    questions_poland = models.TextField(
        verbose_name='Вопросы Польша',
        help_text='Вопросы для интервью в Польше',
        blank=True
    )
    
    # Ссылки на вакансии в разных странах
    vacancy_link_belarus = models.URLField(
        verbose_name='Ссылка на вакансию (Беларусь)',
        help_text='Ссылка на вакансию в Беларуси (например, rabota.by, jobs.tut.by)',
        blank=True
    )
    
    vacancy_link_poland = models.URLField(
        verbose_name='Ссылка на вакансию (Польша)',
        help_text='Ссылка на вакансию в Польше (например, pracuj.pl, nofluffjobs.com)',
        blank=True
    )
    
    candidate_update_prompt = models.TextField(
        verbose_name='Промпт для обновления кандидата',
        help_text='Промпт для обновления информации о кандидате',
        blank=True
    )
    
    use_common_prompt = models.BooleanField(
        default=False,
        verbose_name='Использовать общий промпт',
        help_text='Если включено, используется единый промпт из настроек компании. Если выключено, используется индивидуальный промпт.'
    )
    
    # Этапы для перевода кандидатов
    hr_screening_stage = models.CharField(
        max_length=100,
        verbose_name='Этап после HR-скрининга',
        help_text='Этап в Huntflow, на который переводить кандидата после HR-скрининга',
        blank=True
    )
    
    tech_screening_stage = models.CharField(
        max_length=100,
        verbose_name='Этап после Tech-скрининга',
        help_text='Этап в Huntflow, на который переводить кандидата после Tech-скрининга',
        blank=True
    )
    
    tech_interview_stage = models.CharField(
        max_length=100,
        verbose_name='Этап после Tech-интервью',
        help_text='Этап в Huntflow, на который переводить кандидата после Tech-интервью',
        blank=True
    )
    
    screening_duration = models.PositiveIntegerField(
        verbose_name='Длительность скринингов (минуты)',
        help_text='Длительность скринингов в минутах',
        default=45
    )
    
    available_grades = models.ManyToManyField(
        Grade,
        related_name='available_vacancies',
        verbose_name='Доступные грейды',
        help_text='Грейды, доступные для данной вакансии',
        blank=True
    )
    
    interviewers = models.ManyToManyField(
        'interviewers.Interviewer',
        related_name='vacancies',
        verbose_name='Интервьюеры',
        help_text='Интервьюеры, привязанные к вакансии',
        blank=True
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Активна ли вакансия'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    technologies = models.TextField(
        verbose_name='Технологии',
        help_text='Список технологий через запятую (например: Python, Django, PostgreSQL, Redis)',
        blank=True
    )
    
    tech_interview_duration = models.PositiveIntegerField(
        verbose_name='Длительность тех. интервью (минуты)',
        help_text='Продолжительность технического интервью в минутах',
        blank=True,
        null=True
    )
    
    mandatory_tech_interviewers = models.ManyToManyField(
        'interviewers.Interviewer',
        verbose_name='Обязательные участники тех. интервью',
        help_text='Интервьюеры, которые обязательно должны участвовать в техническом интервью',
        blank=True,
        related_name='mandatory_tech_interviews'
    )
    
    tech_invite_title = models.CharField(
        max_length=200,
        verbose_name='Заголовок инвайтов на тех. интервью',
        help_text='Заголовок для приглашений на технические интервью',
        blank=True
    )
    
    tech_invite_text = models.TextField(
        verbose_name='Сопровождающий текст для инвайтов на тех. интервью',
        help_text='Текст сопроводительного письма для приглашений на технические интервью',
        blank=True
    )
    
    # Статус активности вакансии
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Автоматически определяется на основе активных заявок на найм'
    )

    review_period_months = models.PositiveIntegerField(
        verbose_name='Срок пересмотра (месяцы)',
        help_text='Срок пересмотра вакансии в месяцах (число)',
        null=True,
        blank=True
    )

    # ID для связи с вакансией в Huntflow / HH.ru (не уникален: у нескольких локальных вакансий может быть один huntflow_id)
    huntflow_id = models.CharField(
        max_length=100,
        verbose_name='Huntflow ID',
        help_text='Идентификатор для связи с вакансией в Huntflow или HH.ru (может совпадать у нескольких вакансий)',
        blank=True,
        null=True,
        db_index=True,
    )

    class Meta:
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.external_id})"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что рекрутер действительно в группе "Рекрутер"
        if self.recruiter and not self.recruiter.groups.filter(name='Рекрутер').exists():
            raise ValidationError({
                'recruiter': 'Выбранный пользователь не является рекрутером'
            })
        for rec in (self.additional_recruiters.all() if self.pk else []):
            if not rec.groups.filter(name='Рекрутер').exists():
                raise ValidationError({
                    'additional_recruiters': 'Все дополнительные рекрутеры должны быть в группе «Рекрутер»'
                })
            if self.recruiter and rec.pk == self.recruiter_id:
                raise ValidationError({
                    'additional_recruiters': 'Дополнительные рекрутеры не должны включать основного рекрутера'
                })
    
    def update_activity_status(self):
        """Обновляет статус активности вакансии на основе заявок на найм"""
        from apps.hiring_plan.models import HiringRequest
        from django.utils import timezone
        
        # Проверяем наличие активных заявок
        today = timezone.now().date()
        
        # Активные заявки: планируется, в процессе
        active_requests = HiringRequest.objects.filter(
            vacancy=self,
            status__in=['planned', 'in_progress']
        ).exists()
        
        # Заявки в будущем (дата открытия в будущем)
        future_requests = HiringRequest.objects.filter(
            vacancy=self,
            opening_date__gt=today
        ).exists()
        
        # Вакансия активна, если есть активные заявки или заявки в будущем
        new_status = active_requests or future_requests
        
        # Обновляем статус только если он изменился
        if self.is_active != new_status:
            self.is_active = new_status
            self.save(update_fields=['is_active'])
            return True  # Статус изменился
        
        return False  # Статус не изменился
    
    @classmethod
    def update_all_activity_statuses(cls):
        """Обновляет статус активности для всех вакансий"""
        updated_count = 0
        for vacancy in cls.objects.all():
            if vacancy.update_activity_status():
                updated_count += 1
        return updated_count
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def get_interviewers_count(self):
        """Получить количество привязанных интервьюеров"""
        return self.interviewers.count()
    
    def get_interviewers_list(self):
        """Получить список привязанных интервьюеров"""
        return self.interviewers.all()
    
    def has_interviewers(self):
        """Проверить, есть ли привязанные интервьюеры"""
        return self.interviewers.exists()
    
    def get_vacancy_links(self):
        """Получить все ссылки на вакансии по странам"""
        links = {}
        if self.vacancy_link_belarus:
            links['Беларусь'] = self.vacancy_link_belarus
        if self.vacancy_link_poland:
            links['Польша'] = self.vacancy_link_poland
        return links
    
    def has_vacancy_links(self):
        """Проверить, есть ли ссылки на вакансии"""
        return any([
            self.vacancy_link_belarus,
            self.vacancy_link_poland
        ])
    
    def get_vacancy_links_count(self):
        """Получить количество ссылок на вакансии"""
        return len(self.get_vacancy_links())
    
    def get_vacancy_link_by_country(self, country):
        """Получить ссылку на вакансию для конкретной страны"""
        country_mapping = {
            'belarus': self.vacancy_link_belarus,
            'poland': self.vacancy_link_poland
        }
        return country_mapping.get(country.lower())
    
    def get_stage_by_type(self, stage_type):
        """Получить этап по типу"""
        stage_mapping = {
            'hr_screening': self.hr_screening_stage,
            'tech_screening': self.tech_screening_stage,
            'tech_interview': self.tech_interview_stage
        }
        return stage_mapping.get(stage_type)
    
    def has_stages_configured(self):
        """Проверить, настроены ли этапы"""
        return any([
            self.hr_screening_stage,
            self.tech_screening_stage,
            self.tech_interview_stage
        ])
    
    def get_configured_stages(self):
        """Получить список настроенных этапов"""
        stages = {}
        if self.hr_screening_stage:
            stages['hr_screening'] = self.hr_screening_stage
        if self.tech_screening_stage:
            stages['tech_screening'] = self.tech_screening_stage
        if self.tech_interview_stage:
            stages['tech_interview'] = self.tech_interview_stage
        return stages
    
    def get_stage_name(self, stage_id, user=None):
        """
        Получить название этапа по ID из Huntflow
        
        Args:
            stage_id: ID этапа в Huntflow
            user: Пользователь для получения API ключей Huntflow
            
        Returns:
            Название этапа или ID если не найдено
        """
        if not stage_id or not user:
            return stage_id or "Не указан"
        
        try:
            from apps.huntflow.services import HuntflowService
            from apps.huntflow.utils import get_correct_account_id
            
            # Получаем правильный account_id
            account_id = get_correct_account_id(user, None)
            if not account_id:
                return stage_id
            
            # Получаем сервис Huntflow
            huntflow_service = HuntflowService(user)
            
            # Получаем статусы
            statuses = huntflow_service.get_vacancy_statuses(account_id)
            if not statuses or 'items' not in statuses:
                return stage_id
            
            # Ищем статус по ID
            for status in statuses['items']:
                if str(status['id']) == str(stage_id):
                    return status.get('name', stage_id)
            
            return stage_id
            
        except Exception as e:
            # В случае ошибки возвращаем ID
            print(f"Ошибка при получении названия этапа {stage_id}: {e}")
            return stage_id



# SalaryRange модель удалена - используется apps.finance.models.SalaryRange
# Полная документация для восстановления: VACANCIES_SALARY_MODEL_BACKUP.md


class ScorecardUpdateHistory(models.Model):
    """История обновлений скоркардов"""
    
    ACTION_TYPES = [
        ('bulk_update', 'Массовое обновление'),
        ('single_update', 'Обновление одного скоркарда'),
    ]
    
    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name='scorecard_updates',
        verbose_name='Вакансия'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        default='bulk_update',
        verbose_name='Тип операции'
    )
    
    updated_count = models.PositiveIntegerField(
        verbose_name='Количество обновленных скоркардов'
    )
    
    total_found = models.PositiveIntegerField(
        verbose_name='Всего найдено скоркардов'
    )
    
    date_range_from = models.DateField(
        verbose_name='Период с'
    )
    
    date_range_to = models.DateField(
        verbose_name='Период по'
    )
    
    errors = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Ошибки'
    )
    
    updated_interviews = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Обновленные интервью'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    class Meta:
        verbose_name = 'История обновления скоркардов'
        verbose_name_plural = 'История обновлений скоркардов'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Обновление скоркардов для {self.vacancy.name} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    @property
    def success_rate(self):
        """Процент успешных обновлений"""
        if self.total_found == 0:
            return 0
        return round((self.updated_count / self.total_found) * 100, 1)
    
    @property
    def has_errors(self):
        """Есть ли ошибки при обновлении"""
        return len(self.errors) > 0
