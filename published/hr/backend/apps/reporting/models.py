"""
Модели для приложения отчетности
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ReportCache(models.Model):
    """Кэш для хранения предвычисленных отчетов"""
    
    PERIOD_CHOICES = [
        ('daily', 'Ежедневная'),
        ('weekly', 'Понедельная'),
        ('monthly', 'Помесячная'),
        ('quarterly', 'Поквартальная'),
        ('yearly', 'Годовая'),
    ]
    
    REPORT_TYPE_CHOICES = [
        ('company', 'По компании'),
        ('recruiter', 'По рекрутеру'),
        ('vacancy', 'По вакансии'),
        ('interviewer', 'По интервьюеру'),
    ]
    
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        verbose_name='Тип отчета'
    )
    
    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        verbose_name='Период'
    )
    
    # Фильтры
    start_date = models.DateField(
        verbose_name='Дата начала'
    )
    
    end_date = models.DateField(
        verbose_name='Дата окончания'
    )
    
    # Опциональные фильтры
    recruiter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='report_caches',
        verbose_name='Рекрутер'
    )
    
    vacancy_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='ID вакансии'
    )
    
    interviewer_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID интервьюера'
    )
    
    # Данные отчета (JSON)
    data = models.JSONField(
        default=dict,
        verbose_name='Данные отчета'
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
        verbose_name = 'Кэш отчета'
        verbose_name_plural = 'Кэш отчетов'
        unique_together = [
            ['report_type', 'period', 'start_date', 'end_date', 'recruiter', 'vacancy_id', 'interviewer_id']
        ]
        indexes = [
            models.Index(fields=['report_type', 'period', 'start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.get_period_display()} ({self.start_date} - {self.end_date})"


class CalendarEvent(models.Model):
    """Модель для хранения событий календаря рекрутеров"""
    
    EVENT_TYPE_CHOICES = [
        ('screening', 'Скрининг'),
        ('interview', 'Интервью'),
        ('unknown', 'Не определено'),
    ]
    
    # Связь с рекрутером
    recruiter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calendar_events',
        verbose_name='Рекрутер',
        limit_choices_to={'groups__name': 'Рекрутер'},
        null=True,
        blank=True
    )
    
    # ID события в Google Calendar
    event_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='ID события',
        help_text='Уникальный идентификатор события в Google Calendar'
    )
    
    # Основная информация о событии
    title = models.CharField(
        max_length=500,
        verbose_name='Название события'
    )
    
    # Тип события (скрининг или интервью)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='unknown',
        verbose_name='Тип события',
        help_text='Определяется автоматически на основе названия события'
    )
    
    # Связь с вакансией
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_events',
        verbose_name='Вакансия',
        help_text='Определяется автоматически на основе соответствия названия события с заголовками инвайтов'
    )
    
    start_time = models.DateTimeField(
        verbose_name='Время начала'
    )
    
    end_time = models.DateTimeField(
        verbose_name='Время окончания'
    )
    
    duration_minutes = models.PositiveIntegerField(
        verbose_name='Продолжительность (минуты)',
        help_text='Вычисляется автоматически из start_time и end_time'
    )
    
    # Участники события (JSON массив с email и именами)
    attendees = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Участники',
        help_text='Список участников события в формате [{"email": "...", "name": "..."}]'
    )
    
    # Дополнительная информация
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание'
    )
    
    location = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Местоположение'
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания записи'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления записи'
    )
    
    # Время последнего обновления из Google Calendar
    google_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время обновления в Google Calendar'
    )
    
    class Meta:
        verbose_name = 'Событие календаря'
        verbose_name_plural = 'События календаря'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['recruiter', 'start_time']),
            models.Index(fields=['start_time', 'end_time']),
            models.Index(fields=['event_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['vacancy']),
            models.Index(fields=['recruiter', 'event_type', 'start_time']),
            models.Index(fields=['vacancy', 'event_type', 'start_time']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recruiter.username} ({self.start_time})"
    
    def determine_event_type(self):
        """
        Определяет тип события на основе названия
        Возвращает 'screening', 'interview' или 'unknown'
        """
        if not self.title:
            return 'unknown'
        
        title_lower = self.title.lower()
        
        # Ключевые слова для скрининга (русские и английские варианты)
        screening_keywords = [
            'screening', 'screen', 'скрининг', 'скрин', 'скриннинг'
        ]
        
        # Ключевые слова для интервью (русские и английские варианты)
        interview_keywords = [
            'interview', 'интервью'
        ]
        
        # Проверяем наличие ключевых слов для интервью (приоритет выше)
        for keyword in interview_keywords:
            if keyword in title_lower:
                return 'interview'
        
        # Проверяем наличие ключевых слов для скрининга
        for keyword in screening_keywords:
            if keyword in title_lower:
                return 'screening'
        
        return 'unknown'
    
    def determine_vacancy(self):
        """
        Определяет вакансию на основе соответствия названия события
        с заголовками инвайтов (invite_title или tech_invite_title)
        
        Returns:
            Vacancy или None
        """
        if not self.title:
            return None
        
        try:
            from apps.vacancies.models import Vacancy
            
            title_lower = self.title.lower().strip()
            event_type = self.determine_event_type()
            
            # Получаем активные вакансии
            vacancies = Vacancy.objects.filter(is_active=True)
            
            # Для скринингов ищем по invite_title
            if event_type == 'screening':
                for vacancy in vacancies:
                    if vacancy.invite_title:
                        invite_title_lower = vacancy.invite_title.lower().strip()
                        # Проверяем, содержит ли название события хотя бы часть заголовка инвайта
                        if invite_title_lower and (
                            invite_title_lower in title_lower or 
                            title_lower in invite_title_lower or
                            self._titles_match(title_lower, invite_title_lower)
                        ):
                            return vacancy
            
            # Для интервью ищем по tech_invite_title
            elif event_type == 'interview':
                for vacancy in vacancies:
                    if vacancy.tech_invite_title:
                        tech_invite_title_lower = vacancy.tech_invite_title.lower().strip()
                        # Проверяем соответствие
                        if tech_invite_title_lower and (
                            tech_invite_title_lower in title_lower or 
                            title_lower in tech_invite_title_lower or
                            self._titles_match(title_lower, tech_invite_title_lower)
                        ):
                            return vacancy
            
            # Если тип не определен, пробуем оба варианта
            else:
                # Сначала пробуем tech_invite_title (для интервью)
                for vacancy in vacancies:
                    if vacancy.tech_invite_title:
                        tech_invite_title_lower = vacancy.tech_invite_title.lower().strip()
                        if tech_invite_title_lower and (
                            tech_invite_title_lower in title_lower or 
                            title_lower in tech_invite_title_lower or
                            self._titles_match(title_lower, tech_invite_title_lower)
                        ):
                            return vacancy
                
                # Затем пробуем invite_title (для скринингов)
                for vacancy in vacancies:
                    if vacancy.invite_title:
                        invite_title_lower = vacancy.invite_title.lower().strip()
                        if invite_title_lower and (
                            invite_title_lower in title_lower or 
                            title_lower in invite_title_lower or
                            self._titles_match(title_lower, invite_title_lower)
                        ):
                            return vacancy
            
            return None
            
        except Exception as e:
            # В случае ошибки возвращаем None
            print(f"Ошибка при определении вакансии: {e}")
            return None
    
    def _titles_match(self, title1, title2):
        """
        Проверяет, совпадают ли названия хотя бы частично
        Использует нормализацию (убирает лишние пробелы, приводит к нижнему регистру)
        """
        # Нормализуем строки
        normalized1 = ' '.join(title1.split())
        normalized2 = ' '.join(title2.split())
        
        # Проверяем, содержит ли одно название другое или наоборот
        if len(normalized1) > 0 and len(normalized2) > 0:
            # Если одно из названий содержит хотя бы 3 слова из другого
            words1 = set(normalized1.split())
            words2 = set(normalized2.split())
            
            # Ищем общие слова (минимум 2 слова для совпадения)
            common_words = words1.intersection(words2)
            if len(common_words) >= 2:
                return True
            
            # Также проверяем частичное вхождение (если одно название содержит другое)
            if normalized1 in normalized2 or normalized2 in normalized1:
                return True
        
        return False
    
    def save(self, *args, **kwargs):
        """Автоматически вычисляем продолжительность и определяем тип события и вакансию при сохранении"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = int(delta.total_seconds() / 60)
        
        # Автоматически определяем тип события на основе названия
        # Всегда переопределяем, чтобы при изменении названия тип тоже обновлялся
        self.event_type = self.determine_event_type()
        
        # Автоматически определяем вакансию на основе названия
        # Всегда переопределяем, чтобы при изменении названия вакансия тоже обновлялась
        self.vacancy = self.determine_vacancy()
        
        super().save(*args, **kwargs)
    
    def is_current_week(self):
        """Проверяет, относится ли событие к текущей неделе"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        return week_start <= self.start_time < week_end

