from django.db import models
from django.core.validators import EmailValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Interviewer(models.Model):
    """Модель интервьюера"""
    
    first_name = models.CharField(
        max_length=100,
        verbose_name='Имя',
        help_text='Имя интервьюера'
    )
    
    last_name = models.CharField(
        max_length=100,
        verbose_name='Фамилия',
        help_text='Фамилия интервьюера'
    )
    
    middle_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Отчество',
        help_text='Отчество интервьюера (необязательно)'
    )
    
    email = models.EmailField(
        unique=True,
        verbose_name='Email',
        help_text='Email адрес интервьюера',
        validators=[EmailValidator()]
    )
    
    calendar_link = models.URLField(
        verbose_name='Ссылка на календарь',
        help_text='Публичная ссылка на календарь интервьюера',
        blank=True
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Активен ли интервьюер для проведения интервью'
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
        verbose_name = 'Интервьюер'
        verbose_name_plural = 'Интервьюеры'
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Получить полное имя интервьюера"""
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"
    
    def get_short_name(self):
        """Получить краткое имя интервьюера"""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name[0]}."
        return self.first_name
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что email уникален
        if Interviewer.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError({'email': 'Интервьюер с таким email уже существует'})
    
    def save(self, *args, **kwargs):
        """Переопределяем save для вызова clean"""
        self.clean()
        super().save(*args, **kwargs)


class InterviewRule(models.Model):
    """Модель правил привлечения интервьюеров"""
    
    name = models.CharField(
        max_length=200,
        verbose_name='Название правила',
        help_text='Краткое описание правила привлечения'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Подробное описание правила'
    )
    
    # Лимиты привлечения
    daily_limit = models.PositiveIntegerField(
        default=5,
        verbose_name='Лимит в день',
        help_text='Максимальное количество интервью в день для одного интервьюера',
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    
    weekly_limit = models.PositiveIntegerField(
        default=20,
        verbose_name='Лимит в неделю',
        help_text='Максимальное количество интервью в неделю для одного интервьюера',
        validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    
    # Грейды (связь с моделью Grade из finance)
    min_grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        related_name='interview_rules_min',
        verbose_name='Минимальный грейд',
        help_text='Минимальный грейд для привлечения интервьюера'
    )
    
    max_grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        related_name='interview_rules_max',
        verbose_name='Максимальный грейд',
        help_text='Максимальный грейд для привлечения интервьюера'
    )
    
    # Статус и метаданные
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно',
        help_text='Активно ли правило для применения'
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
        verbose_name = 'Правило привлечения интервьюеров'
        verbose_name_plural = 'Правила привлечения интервьюеров'
        ordering = ['min_grade__name', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.min_grade.name}-{self.max_grade.name}"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматической деактивации других правил"""
        # Если активируем это правило, деактивируем все остальные
        if self.is_active:
            InterviewRule.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)
    
    def get_grade_range(self):
        """Получить диапазон грейдов в читаемом виде"""
        return f"{self.min_grade.name} - {self.max_grade.name}"
    
    def is_grade_in_range(self, grade):
        """Проверить, входит ли грейд в диапазон правила"""
        # Получаем активные грейды компании для проверки диапазона
        from apps.company_settings.utils import get_active_grades_queryset
        grades = get_active_grades_queryset().order_by('name')
        grade_names = [g.name for g in grades]
        
        try:
            min_index = grade_names.index(self.min_grade.name)
            max_index = grade_names.index(self.max_grade.name)
            grade_index = grade_names.index(grade.name)
            
            return min_index <= grade_index <= max_index
        except (ValueError, AttributeError):
            return False
    
    @classmethod
    def get_active_rule(cls):
        """Получить активное правило"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def activate_rule(cls, rule_id):
        """Активировать правило и деактивировать все остальные"""
        # Деактивируем все правила
        cls.objects.filter(is_active=True).update(is_active=False)
        
        # Активируем выбранное правило
        rule = cls.objects.get(pk=rule_id)
        rule.is_active = True
        rule.save()
        
        return rule
