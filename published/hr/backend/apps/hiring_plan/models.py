from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, Q, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


class PositionType(models.Model):
    """Тип позиции в плане (текущая, замена, плановая)"""
    
    TYPE_CHOICES = [
        ('current', 'Текущая работа'),
        ('replacement', 'Замена сотрудника'),
        ('planned', 'Плановая позиция'),
        ('urgent', 'Срочная позиция'),
        ('potential', 'Потенциальная позиция'),
    ]
    
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        unique=True,
        verbose_name='Тип позиции',
        help_text='Тип позиции в плане найма'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
        help_text='Название типа позиции'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Описание типа позиции'
    )
    priority_boost = models.IntegerField(
        default=0,
        verbose_name='Бонус приоритета',
        help_text='Добавляет приоритет к позиции'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Активен ли тип позиции'
    )
    
    class Meta:
        verbose_name = 'Тип позиции'
        verbose_name_plural = 'Типы позиций'
        ordering = ['priority_boost', 'name']
    
    def __str__(self):
        return self.name


class PlanPeriodType(models.Model):
    """Тип периода плана (месячный, квартальный, годовой)"""
    
    PERIOD_CHOICES = [
        ('monthly', 'Месячный план'),
        ('quarterly', 'Квартальный план'),
        ('yearly', 'Годовой план'),
        ('custom', 'Кастомный период'),
    ]
    
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        unique=True,
        verbose_name='Тип периода',
        help_text='Тип периода плана'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
        help_text='Название типа периода'
    )
    days = models.IntegerField(
        verbose_name='Количество дней',
        help_text='Количество дней в периоде'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Активен ли тип периода'
    )
    
    class Meta:
        verbose_name = 'Тип периода'
        verbose_name_plural = 'Типы периодов'
        ordering = ['days']
    
    def __str__(self):
        return self.name


class PlanKPIOKRBlock(models.Model):
    """Блок KPI/OKR для применения к позициям группово (massively)"""
    
    name = models.CharField(
        max_length=255,
        verbose_name='Название блока',
        help_text='Например: "Backend найм Q4" или "Замены срочные"'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Описание блока KPI/OKR'
    )
    
    # Какие позиции попадают в блок
    position_types = models.ManyToManyField(
        PositionType,
        blank=True,
        verbose_name='Типы позиций',
        help_text='Типы позиций (если пусто - все)'
    )
    grades = models.ManyToManyField(
        'finance.Grade',
        blank=True,
        verbose_name='Грейды',
        help_text='Грейды (если пусто - все)'
    )
    
    # Статус
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Активен ли блок'
    )
    is_template = models.BooleanField(
        default=False,
        verbose_name='Шаблон',
        help_text='Шаблон для переиспользования'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Блок KPI/OKR для плана'
        verbose_name_plural = 'Блоки KPI/OKR'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_applicable_positions(self):
        """Получить позиции, к которым применяется блок"""
        queryset = HiringPlanPosition.objects.all()
        
        if self.position_types.exists():
            queryset = queryset.filter(position_type__in=self.position_types.all())
        
        if self.grades.exists():
            queryset = queryset.filter(grades__in=self.grades.all()).distinct()
        
        return queryset
    
    def apply_to_plan(self, hiring_plan):
        """Применить блок KPI/OKR к конкретному плану"""
        # Копируем все KPI/OKR этого блока
        kpi_okr_list = PositionKPIOKR.objects.filter(plan_kpi_okr_block=self)
        
        for kpi_okr in kpi_okr_list:
            # Создаем копии для каждой применимой позиции
            applicable_positions = self.get_applicable_positions().filter(
                hiring_plan=hiring_plan
            )
            
            for position in applicable_positions:
                PositionKPIOKR.objects.create(
                    vacancy=position.vacancy,
                    grade=position.grades.first() if position.grades.exists() else None,
                    hiring_plan=hiring_plan,
                    scope='vacancy_grade',
                    name=kpi_okr.name,
                    metric_type=kpi_okr.metric_type,
                    target_value=kpi_okr.target_value,
                    unit=kpi_okr.unit,
                    period_start=kpi_okr.period_start,
                    period_end=kpi_okr.period_end,
                )




class PositionKPIOKR(models.Model):
    """KPI/OKR связаны с вакансией/грейдом или применяются блоками к планам"""
    
    METRIC_TYPE_CHOICES = [
        ('kpi', 'KPI'),
        ('okr', 'OKR'),
        ('custom', 'Custom'),
    ]
    
    SCOPE_CHOICES = [
        ('vacancy', 'Для конкретной вакансии'),
        ('grade', 'Для конкретного грейда'),
        ('vacancy_grade', 'Для вакансии + грейда'),
        ('plan_block', 'Блок для плана (массово)'),
        ('global', 'Глобальная метрика'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ожидается'),
        ('in_progress', 'В процессе'),
        ('achieved', 'Достигнуто'),
        ('failed', 'Не достигнуто'),
    ]
    
    # Scope - определяет применение
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='vacancy',
        verbose_name='Область применения',
        help_text='Определяет, как применяется метрика'
    )
    
    # Связи (зависят от scope)
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Вакансия',
        help_text='Если scope = vacancy/vacancy_grade'
    )
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Грейд',
        help_text='Если scope = grade/vacancy_grade'
    )
    
    # Блок для применения к плану
    plan_kpi_okr_block = models.ForeignKey(
        PlanKPIOKRBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Блок KPI/OKR',
        help_text='Блок KPI/OKR для группового применения'
    )
    
    # Связь с планом найма (опционально)
    hiring_plan = models.ForeignKey(
        'HiringPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='План найма',
        help_text='План найма для KPI/OKR'
    )
    
    # Основные параметры
    name = models.CharField(
        max_length=255,
        verbose_name='Название',
        help_text='Название KPI/OKR'
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPE_CHOICES,
        verbose_name='Тип метрики',
        help_text='Тип метрики'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Описание метрики'
    )
    
    # Целевые значения
    target_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Целевое значение',
        help_text='Целевое значение метрики'
    )
    unit = models.CharField(
        max_length=50,
        default='%',
        verbose_name='Единица измерения',
        help_text='Единица измерения'
    )
    sla_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='SLA значение',
        help_text='Значение по SLA для сравнения'
    )
    
    # Результаты
    actual_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Фактическое значение',
        help_text='Фактическое значение метрики'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус',
        help_text='Статус достижения метрики'
    )
    
    # Период
    period_start = models.DateField(
        verbose_name='Начало периода',
        help_text='Начало периода для метрики'
    )
    period_end = models.DateField(
        verbose_name='Конец периода',
        help_text='Конец периода для метрики'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'KPI/OKR'
        verbose_name_plural = 'KPI/OKR'
        unique_together = [
            ['vacancy', 'grade', 'metric_type', 'period_start'],
            ['vacancy', 'metric_type', 'period_start'],  # Если без грейда
            ['plan_kpi_okr_block', 'period_start'],  # Для блоков
        ]
        ordering = ['-period_start', 'metric_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_metric_type_display()})"
    
    @property
    def achievement_rate(self):
        """% достижения целевого значения"""
        if not self.actual_value or self.target_value == 0:
            return 0
        return round((self.actual_value / self.target_value) * 100, 2)
    
    @property
    def sla_achievement_rate(self):
        """% достижения SLA (если задано)"""
        if not self.actual_value or not self.sla_value or self.sla_value == 0:
            return None
        return round((self.actual_value / self.sla_value) * 100, 2)


class HiringPlan(models.Model):
    """Простой план найма - только основная информация"""
    
    # Основное
    title = models.CharField(
        max_length=255,
        verbose_name='Название плана',
        help_text='Название плана найма'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Подробное описание плана найма'
    )
    
    # Период (вместо start_date/end_date)
    period_type = models.ForeignKey(
        PlanPeriodType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тип периода',
        help_text='Месячный/Квартальный/Годовой'
    )
    
    # История периодов
    previous_plan = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_plans',
        verbose_name='Предыдущий план',
        help_text='Предыдущий план'
    )
    is_auto_generated = models.BooleanField(
        default=False,
        verbose_name='Автоматически созданный',
        help_text='Автоматически созданный план'
    )
    
    # Автоматические поля (опционально)
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_hiring_plans',
        verbose_name='Владелец',
        help_text='Опционально - подтягивается автоматически'
    )
    
    # Статус УБИРАЕМ! Теперь только для отслеживания завершенных периодов
    # Если нужен статус - добавляем is_completed вместо status
    is_completed = models.BooleanField(
        default=False,
        verbose_name='Завершен',
        help_text='План завершен'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'План найма'
        verbose_name_plural = 'Планы найма'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({'Завершен' if self.is_completed else 'Активен'})"
    
    @property
    def total_positions(self):
        """Общее количество позиций"""
        return self.positions.count()
    
    @property
    def total_headcount_needed(self):
        """Общее количество требуемых специалистов"""
        result = self.positions.aggregate(
            total=Sum('headcount_needed')
        )
        return result['total'] or 0
    
    @property
    def total_headcount_hired(self):
        """Общее количество нанятых"""
        result = self.positions.aggregate(
            total=Sum('headcount_hired')
        )
        return result['total'] or 0
    
    @property
    def completion_rate(self):
        """Процент выполнения плана"""
        needed = self.total_headcount_needed
        if needed == 0:
            return 0
        hired = self.total_headcount_hired
        return round((hired / needed) * 100, 2)
    
    def get_sla_for_vacancy(self, vacancy, grade=None):
        """Получить SLA для вакансии в этом плане"""
        if grade:
            sla = VacancySLA.objects.filter(
                vacancy=vacancy, grade=grade, is_active=True
            ).first()
        else:
            # Для новой модели VacancySLA всегда нужен грейд
            sla = None
        
        return sla
    
    def get_kpi_okr_for_vacancy(self, vacancy, grade=None):
        """Получить KPI/OKR для вакансии"""
        kpi_okr = PositionKPIOKR.objects.filter(
            vacancy=vacancy, hiring_plan=self
        )
        
        if grade:
            kpi_okr = kpi_okr.filter(
                Q(grade=grade) | Q(grade__isnull=True)
            )
        
        return kpi_okr


class HiringPlanPosition(models.Model):
    """Позиция в плане"""
    
    PRIORITY_CHOICES = [
        (1, 'Критический'),
        (2, 'Высокий'),
        (3, 'Средний'),
        (4, 'Низкий'),
    ]
    
    # Основные связи
    hiring_plan = models.ForeignKey(
        HiringPlan,
        on_delete=models.CASCADE,
        related_name='positions',
        verbose_name='План найма',
        help_text='План найма, к которому относится позиция'
    )
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        verbose_name='Вакансия',
        help_text='Вакансия для данной позиции'
    )
    
    # Тип позиции
    position_type = models.ForeignKey(
        PositionType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тип позиции',
        help_text='Тип позиции (текущая/замена/плановая)'
    )
    replacement_reason = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Причина замены',
        help_text='Причина замены сотрудника'
    )
    replaced_employee_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID заменяемого сотрудника',
        help_text='ID заменяемого сотрудника (из системы)'
    )
    
    # Количество
    headcount_needed = models.PositiveIntegerField(
        verbose_name='Требуется специалистов',
        help_text='Количество специалистов, которое нужно нанять'
    )
    headcount_hired = models.PositiveIntegerField(
        default=0,
        verbose_name='Нанято специалистов',
        help_text='Количество уже нанятых специалистов'
    )
    headcount_in_progress = models.PositiveIntegerField(
        default=0,
        verbose_name='В процессе найма',
        help_text='Количество специалистов, найм которых в процессе'
    )
    
    # Приоритет и дедлайны
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        verbose_name='Приоритет',
        help_text='Приоритет позиции в плане'
    )
    urgency_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дедлайн',
        help_text='Критический дедлайн для закрытия позиции'
    )
    
    # Грейды и требования
    grades = models.ManyToManyField(
        'finance.Grade',
        blank=True,
        verbose_name='Грейды',
        help_text='Требуемые грейды специалистов'
    )
    specifics = models.TextField(
        blank=True,
        verbose_name='Специфика позиции',
        help_text='Особые требования и специфика позиции'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Заметки',
        help_text='Дополнительные заметки по позиции'
    )
    project = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Проект',
        help_text='Название проекта, для которого нужна позиция'
    )
    
    # Дата закрытия
    filled_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата закрытия позиции',
        help_text='Дата закрытия позиции'
    )
    
    # Активность
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Активна ли позиция в плане'
    )
    
    # НОВОЕ: связь с блоком KPI/OKR (если применен)
    applied_kpi_okr_blocks = models.ManyToManyField(
        PlanKPIOKRBlock,
        blank=True,
        related_name='positions',
        verbose_name='Примененные блоки KPI/OKR',
        help_text='Блоки KPI/OKR, примененные к позиции'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Позиция в плане найма'
        verbose_name_plural = 'Позиции в планах найма'
        ordering = ['priority', 'urgency_deadline']
    
    def __str__(self):
        return f"{self.vacancy.name} в {self.hiring_plan.title}"
    
    @property
    def fulfillment_rate(self):
        """Процент закрытия позиции"""
        if self.headcount_needed == 0:
            return 0
        return round((self.headcount_hired / self.headcount_needed) * 100, 2)
    
    @property
    def is_fulfilled(self):
        """Позиция полностью закрыта?"""
        return self.headcount_hired >= self.headcount_needed
    
    @property
    def remaining_headcount(self):
        """Сколько еще нужно нанять"""
        return max(0, self.headcount_needed - self.headcount_hired)
    
    @property
    def is_overdue(self):
        """Проверка просрочки дедлайна"""
        if not self.urgency_deadline:
            return False
        return timezone.now().date() > self.urgency_deadline and not self.is_fulfilled
    
    @property
    def time_to_fill(self):
        """Время от открытия до закрытия (в днях)"""
        if not self.is_fulfilled or not self.filled_date:
            return None
        return (self.filled_date - self.created_at.date()).days
    
    def get_applicable_sla(self):
        """Получить применимую SLA"""
        # Для каждого грейда вакансии
        for grade in self.grades.all():
            sla = VacancySLA.objects.filter(
                vacancy=self.vacancy,
                grade=grade,
                is_active=True
            ).first()
            if sla:
                return sla
        
        # Fallback - общая SLA
        return self.hiring_plan.get_sla_for_vacancy(self.vacancy)
    
    def get_applicable_kpi_okr(self):
        """Получить применимые KPI/OKR"""
        kpi_okr_list = []
        
        # Из блоков
        for block in self.applied_kpi_okr_blocks.all():
            block_metrics = PositionKPIOKR.objects.filter(
                plan_kpi_okr_block=block
            )
            kpi_okr_list.extend(block_metrics)
        
        # Напрямую для вакансии
        direct_metrics = PositionKPIOKR.objects.filter(
            vacancy=self.vacancy,
            hiring_plan=self.hiring_plan,
            plan_kpi_okr_block__isnull=True  # Не из блока
        )
        kpi_okr_list.extend(direct_metrics)
        
        return kpi_okr_list
    
    @property
    def sla_status(self):
        """Статус по SLA"""
        sla = self.get_applicable_sla()
        if not sla or not self.filled_date:
            return 'no_sla'
        
        time_to_fill = (self.filled_date - self.created_at.date()).days
        
        if time_to_fill <= sla.target_time_to_fill:
            return 'on_time'
        elif time_to_fill <= sla.warning_time:
            return 'warning'
        elif time_to_fill <= sla.critical_time:
            return 'critical'
        else:
            return 'overdue'
    
    @property
    def sla_compliance(self):
        """% соответствия SLA"""
        sla = self.get_applicable_sla()
        if not sla or not self.time_to_fill:
            return None
        
        return round((sla.target_time_to_fill / self.time_to_fill) * 100, 2)
    
    def save(self, *args, **kwargs):
        # Автоматически устанавливаем дату закрытия при полном закрытии
        if self.is_fulfilled and not self.filled_date:
            self.filled_date = timezone.now().date()
        elif not self.is_fulfilled and self.filled_date:
            self.filled_date = None
            
        super().save(*args, **kwargs)
        # Обновляем метрики плана после сохранения позиции
        self.hiring_plan.update_metrics()


class VacancySLA(models.Model):
    """SLA для пары Вакансия + Грейд"""
    
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        verbose_name='Вакансия'
    )
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        verbose_name='Грейд'
    )
    
    # Целевые показатели в днях
    time_to_offer = models.PositiveIntegerField(
        verbose_name='Time-to-Offer (дни)',
        help_text='Целевое время от открытия до предложения кандидату'
    )
    time_to_hire = models.PositiveIntegerField(
        verbose_name='Time-to-Hire (дни)',
        help_text='Целевое время от первого контакта до оффера'
    )
    
    # Метаданные
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'SLA вакансии'
        verbose_name_plural = 'SLA вакансий'
        unique_together = [['vacancy', 'grade']]
        ordering = ['vacancy__name', 'grade__name']
    
    def __str__(self):
        return f"SLA: {self.vacancy.name} - {self.grade.name} ({self.time_to_offer} дней)"


class RecruiterAssignment(models.Model):
    """История назначения рекрутеров на заявки"""
    
    hiring_request = models.ForeignKey(
        'HiringRequest',
        on_delete=models.CASCADE,
        related_name='recruiter_assignments',
        verbose_name='Заявка'
    )
    recruiter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Рекрутер'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Назначен'
    )
    unassigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Снят с заявки'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно',
        help_text='Активно ли назначение'
    )
    
    class Meta:
        verbose_name = 'Назначение рекрутера'
        verbose_name_plural = 'Назначения рекрутеров'
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.hiring_request} - {self.recruiter} ({self.assigned_at.strftime('%d.%m.%Y')})"
    
    @property
    def duration_days(self):
        """Количество дней работы рекрутера над заявкой"""
        if self.unassigned_at:
            return (self.unassigned_at - self.assigned_at).days
        else:
            from django.utils import timezone
            return (timezone.now() - self.assigned_at).days


class HiringRequest(models.Model):
    """Заявка на найм одного специалиста"""
    
    # === ОСНОВНАЯ ИНФОРМАЦИЯ ===
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        verbose_name='Вакансия'
    )
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.PROTECT,
        verbose_name='Грейд'
    )
    project = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Проект'
    )
    
    # === ПРИОРИТЕТ ===
    PRIORITY_CHOICES = [
        (1, 'Критический'),
        (2, 'Высокий'),
        (3, 'Средний'),
        (4, 'Низкий'),
    ]
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        verbose_name='Приоритет'
    )
    
    # === СТАТУС ===
    STATUS_CHOICES = [
        ('planned', 'Планируется'),
        ('in_progress', 'В процессе'),
        ('cancelled', 'Отменена'),
        ('closed', 'Закрыта'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned',
        verbose_name='Статус'
    )
    
    # === ПРИЧИНА ОТКРЫТИЯ ===
    REASON_CHOICES = [
        ('planned', 'Плановая'),
        ('new_position', 'Новая'),
        ('replacement', 'Замена'),
    ]
    opening_reason = models.CharField(
        max_length=30,
        choices=REASON_CHOICES,
        default='new_position',
        verbose_name='Причина открытия'
    )
    
    # === ДАТЫ ===
    opening_date = models.DateField(
        verbose_name='Дата открытия вакансии',
        help_text='Может быть в будущем или прошлом'
    )
    closed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата закрытия'
    )
    hire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата выхода специалиста',
        help_text='Дата, когда специалист вышел на работу (для расчета time2hire)'
    )
    
    # === SLA (автоматически подтягивается) ===
    sla = models.ForeignKey(
        VacancySLA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='SLA',
        help_text='Автоматически определяется по Вакансия+Грейд'
    )
    
    # === КАНДИДАТ (если закрыта) ===
    candidate_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID кандидата',
        help_text='ID найденного кандидата (из внешней системы)'
    )
    candidate_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Имя кандидата',
        help_text='Имя найденного кандидата'
    )
    
    # === РЕКРУТЕР ===
    recruiter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Рекрутер',
        help_text='Ответственный рекрутер за данную заявку'
    )
    
    # === ЗАМЕТКИ ===
    notes = models.TextField(blank=True, verbose_name='Заметки')
    
    # === СВЯЗЬ С CLICKUP (ПЛАН НАЙМА) ===
    clickup_task_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID задачи в ClickUp',
        help_text='ID задачи в ClickUp для связи заявки с планом найма (например, из папки плана найма)'
    )
    
    # === МЕТАДАННЫЕ ===
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_requests',
        verbose_name='Создано пользователем'
    )
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_requests',
        verbose_name='Закрыто пользователем',
        help_text='Рекрутер, который закрыл вакансию'
    )
    
    class Meta:
        verbose_name = 'Заявка на найм'
        verbose_name_plural = 'Заявки на найм'
        ordering = ['-opening_date', 'priority']
        indexes = [
            models.Index(fields=['status', 'opening_date']),
            models.Index(fields=['vacancy', 'grade']),
            models.Index(fields=['opening_date']),
        ]
    
    def __str__(self):
        return f"{self.vacancy.name} ({self.grade.name}) - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        from datetime import timedelta
        
        # Автоматически определяем SLA
        if not self.sla:
            self.sla = VacancySLA.objects.filter(
                vacancy=self.vacancy,
                grade=self.grade,
                is_active=True
            ).first()
        
        # Автоматически определяем статус на основе дат и данных кандидата
        today = timezone.now().date()
        
        if self.closed_date:
            # Если есть дата закрытия - проверяем наличие данных кандидата
            if self.candidate_name or self.candidate_id:
                # Если есть данные кандидата - статус "закрыта"
                self.status = 'closed'
            else:
                # Если нет данных кандидата - статус "отменена"
                self.status = 'cancelled'
        elif self.opening_date and self.opening_date > today:
            # Если дата открытия в будущем - статус "планируется"
            self.status = 'planned'
        elif self.opening_date:
            # Если дата открытия в прошлом или сегодня - статус "в процессе"
            # Наличие candidate_id или candidate_name не влияет на статус
            # Статус "отменена" должен устанавливаться вручную
            self.status = 'in_progress'
        else:
            # Если дата открытия не указана - статус "планируется" по умолчанию
            self.status = 'planned'
        
        super().save(*args, **kwargs)
    
    def _update_status(self):
        """
        Обновляет статус заявки на основе текущих данных
        """
        today = timezone.now().date()
        
        if self.closed_date:
            # Если есть дата закрытия - проверяем наличие данных кандидата
            if self.candidate_name or self.candidate_id:
                # Если есть данные кандидата - статус "закрыта"
                self.status = 'closed'
            else:
                # Если нет данных кандидата - статус "отменена"
                self.status = 'cancelled'
        elif self.opening_date and self.opening_date > today:
            # Если дата открытия в будущем - статус "планируется"
            self.status = 'planned'
        elif self.opening_date:
            # Если дата открытия в прошлом или сегодня - статус "в процессе"
            self.status = 'in_progress'
        else:
            # Если дата открытия не указана - статус "планируется" по умолчанию
            self.status = 'planned'
    
    def sync_recruiter_with_vacancy(self):
        """
        Синхронизирует рекрутера заявки с рекрутером вакансии
        """
        if self.vacancy and self.recruiter:
            try:
                # Обновляем рекрутера в вакансии
                self.vacancy.recruiter = self.recruiter
                self.vacancy.save(update_fields=['recruiter'])
                print(f"✅ Рекрутер {self.recruiter.username} синхронизирован с вакансией {self.vacancy.name}")
            except Exception as e:
                print(f"❌ Ошибка синхронизации рекрутера: {e}")
                # Если рекрутер не может быть назначен (например, не в группе Рекрутер),
                # оставляем вакансию без изменений
        elif self.vacancy and not self.recruiter:
            try:
                # Если рекрутер не назначен, очищаем рекрутера в вакансии
                self.vacancy.recruiter = None
                self.vacancy.save(update_fields=['recruiter'])
                print(f"ℹ️ Рекрутер очищен в вакансии {self.vacancy.name}")
            except Exception as e:
                print(f"❌ Ошибка очистки рекрутера: {e}")
    
    @property
    def deadline(self):
        """Автоматически рассчитываемый дедлайн на основе SLA"""
        if self.sla and self.opening_date:
            from datetime import timedelta
            return self.opening_date + timedelta(days=self.sla.time_to_offer)
        return None
    
    @property
    def days_in_progress(self):
        """Количество дней в работе"""
        if self.status == 'closed' and self.closed_date:
            return (self.closed_date - self.opening_date).days
        else:
            return (timezone.now().date() - self.opening_date).days
    
    @property
    def time2hire(self):
        """Количество дней от получения заявки до выхода специалиста"""
        if self.hire_date:
            return (self.hire_date - self.opening_date).days
        return None
    
    @property
    def is_overdue(self):
        """Проверка просрочки"""
        if self.status == 'closed':
            return False
        if self.deadline:
            return timezone.now().date() > self.deadline
        return False
    
    @property
    def sla_compliance(self):
        """Соответствие SLA (%)"""
        if not self.sla or not self.closed_date:
            return None
        
        actual_days = (self.closed_date - self.opening_date).days
        target_days = self.sla.time_to_offer
        
        if actual_days <= target_days:
            return 100
        else:
            return round((target_days / actual_days) * 100, 2)
    
    @property
    def sla_status_display(self):
        """Текстовый статус по SLA"""
        if not self.sla:
            return 'Нет SLA'
        
        if self.status == 'closed' and self.closed_date:
            compliance = self.sla_compliance
            if compliance >= 100:
                return 'В срок'
            elif compliance >= 80:
                return 'Просрочено'
            else:
                return 'Просрочено'
        else:
            days_left = (self.deadline - timezone.now().date()).days
            if days_left >= 7:
                return 'Нормально'
            elif days_left >= 0:
                return 'Риск просрочки'
            else:
                return 'Просрочено'
    
    @property
    def closed_date_color_class(self):
        """CSS класс для цветового кодирования даты закрытия"""
        if self.status == 'closed':
            # Проверяем, была ли заявка закрыта в срок по SLA
            if self.sla_compliance and self.sla_compliance >= 100:
                return 'text-success'  # Зеленый для закрытых в срок
            else:
                return 'text-danger'  # Красный для просроченных
        elif self.status == 'cancelled':
            return 'text-dark'  # Черный для отмененных
        else:
            return 'text-muted'  # Серый для остальных
    
    @property
    def deadline_color_class(self):
        """CSS класс для цветового кодирования дедлайна"""
        if self.status == 'planned':
            return 'text-muted'  # Серый для будущих
        elif self.is_overdue:
            return 'text-danger'  # Красный для просроченных
        elif self.status == 'in_progress':
            if self.deadline:
                days_to_deadline = (self.deadline - timezone.now().date()).days
                if days_to_deadline <= 7:
                    return 'text-warning'  # Желтый для тех, что скоро подойдут к дедлайну
                else:
                    return 'text-primary'  # Синий для тех, что в процессе и срок не наступил
            else:
                return 'text-primary'  # Синий для тех, что в процессе без дедлайна
        else:
            return 'text-muted'  # По умолчанию серый
    
    def assign_recruiter(self, recruiter, user=None):
        """Назначить рекрутера на заявку"""
        from django.utils import timezone
        
        # Деактивируем предыдущие назначения
        self.recruiter_assignments.filter(is_active=True).update(
            is_active=False,
            unassigned_at=timezone.now()
        )
        
        # Создаем новое назначение
        assignment = RecruiterAssignment.objects.create(
            hiring_request=self,
            recruiter=recruiter
        )
        
        # Обновляем текущего рекрутера
        self.recruiter = recruiter
        self.save()
        
        return assignment
    
    def unassign_recruiter(self, user=None):
        """Снять рекрутера с заявки"""
        from django.utils import timezone
        
        # Деактивируем текущее назначение
        self.recruiter_assignments.filter(is_active=True).update(
            is_active=False,
            unassigned_at=timezone.now()
        )
        
        # Убираем рекрутера
        self.recruiter = None
        self.save()
    
    @property
    def current_recruiter_assignment(self):
        """Текущее активное назначение рекрутера"""
        return self.recruiter_assignments.filter(is_active=True).first()
    
    @property
    def recruiter_work_days(self):
        """Количество дней работы текущего рекрутера над заявкой"""
        assignment = self.current_recruiter_assignment
        if assignment:
            return assignment.duration_days
        return 0
    
    @property
    def total_recruiter_work_days(self):
        """Общее количество дней работы всех рекрутеров над заявкой"""
        return sum(
            assignment.duration_days 
            for assignment in self.recruiter_assignments.all()
        )
    
    def fetch_candidate_data_from_huntflow(self, user=None):
        """
        Автоматически получает данные кандидата из Huntflow по candidate_id:
        - Имя и фамилию (candidate_name)
        - Дату перевода в статус "Offer accepted" (closed_date)
        - Дату выхода на работу (hire_date)
        """
        if not self.candidate_id:
            return False
        
        try:
            from apps.huntflow.services import HuntflowService
            from datetime import datetime
            
            # Получаем аккаунт Huntflow для пользователя
            if not user:
                return False
            
            # Создаем сервис Huntflow
            huntflow_service = HuntflowService(user)
            
            # Получаем список аккаунтов и берем первый
            accounts = huntflow_service.get_accounts()
            if not accounts or 'items' not in accounts or not accounts['items']:
                print("❌ Не удалось получить аккаунты Huntflow")
                return False
            
            account_id = accounts['items'][0]['id']
            print(f"🔍 Используем account_id: {account_id}")
            
            # Получаем информацию о кандидате
            candidate_data = huntflow_service.get_applicant(
                account_id=account_id,
                applicant_id=int(self.candidate_id)
            )
            
            if not candidate_data:
                print("❌ Не удалось получить данные кандидата из Huntflow")
                # Если имя уже есть, считаем это частичным успехом
                if self.candidate_name:
                    print("ℹ️ Кандидат не найден в Huntflow, но имя уже заполнено")
                    return True
                return False
            
            print(f"✅ Получены данные кандидата: {candidate_data}")
            
            # Получаем логи кандидата для поиска дат (только статусы)
            try:
                logs_data = huntflow_service.get_applicant_logs(
                    account_id=account_id,
                    applicant_id=int(self.candidate_id)
                )
                print(f"🔍 Получены логи кандидата: {logs_data}")
                if logs_data and 'items' in logs_data:
                    print(f"📋 Количество логов: {len(logs_data['items'])}")
                    # Выводим первые несколько логов для отладки
                    for i, log in enumerate(logs_data['items'][:3]):
                        print(f"📝 Лог {i+1}: {log}")
                else:
                    print("⚠️ Логи не найдены или пусты")
            except Exception as e:
                print(f"⚠️ Не удалось получить логи кандидата: {e}")
                logs_data = None
            
            updated_fields = []
            
            # 1. Получаем имя кандидата
            if not self.candidate_name:
                first_name = candidate_data.get('first_name', '').strip()
                last_name = candidate_data.get('last_name', '').strip()
                
                if first_name and last_name:
                    full_name = f"{first_name} {last_name}"
                    self.candidate_name = full_name
                    updated_fields.append('candidate_name')
                    print(f"✅ Сохранено полное имя: {full_name}")
                elif first_name:
                    self.candidate_name = first_name
                    updated_fields.append('candidate_name')
                    print(f"✅ Сохранено имя: {first_name}")
                elif last_name:
                    self.candidate_name = last_name
                    updated_fields.append('candidate_name')
                    print(f"✅ Сохранена фамилия: {last_name}")
            
            # 2. Получаем дату перевода в статус "Offer accepted" (closed_date)
            if not self.closed_date and logs_data and 'items' in logs_data:
                offer_accepted_date = self._find_offer_accepted_date(logs_data['items'])
                if offer_accepted_date:
                    self.closed_date = offer_accepted_date
                    updated_fields.append('closed_date')
                    print(f"✅ Сохранена дата закрытия (Offer accepted): {offer_accepted_date}")
            
            # 3. Получаем дату выхода на работу (hire_date)
            if not self.hire_date and logs_data and 'items' in logs_data:
                hire_date = self._find_hire_date(logs_data['items'])
                if hire_date:
                    self.hire_date = hire_date
                    updated_fields.append('hire_date')
                    print(f"✅ Сохранена дата выхода: {hire_date}")
            
            # Сохраняем изменения
            if updated_fields:
                # Используем полное сохранение для вызова сигналов и пересчета статуса
                self.save()
                print(f"✅ Обновлены поля: {', '.join(updated_fields)}")
                
                # Принудительно пересчитываем статус после получения данных кандидата
                old_status = self.status
                self._update_status()
                if old_status != self.status:
                    self.save(update_fields=['status'])
                    print(f"🔄 Статус заявки изменен с '{old_status}' на '{self.status}'")
                else:
                    print(f"🔄 Статус заявки пересчитан: '{self.status}'")
                
                return True
            else:
                print("ℹ️ Нет новых данных для обновления")
                return True
            
        except Exception as e:
            print(f"❌ Ошибка при получении данных кандидата из Huntflow: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _find_offer_accepted_date(self, logs):
        """
        Ищет дату перевода в статус 186507 (Offer accepted) в логах кандидата
        Согласно Huntflow API: ищем в логах с type=STATUS
        """
        from datetime import datetime
        
        print(f"🔍 Поиск даты принятия оффера в {len(logs)} логах")
        
        # Сортируем логи по дате создания (от старых к новым)
        sorted_logs = sorted(logs, key=lambda x: x.get('created', ''), reverse=False)
        
        for i, log in enumerate(sorted_logs):
            print(f"📝 Проверяем лог {i+1}: type={log.get('type')}, status={log.get('status')}")
            
            # Проверяем тип лога и статус (согласно Huntflow API)
            if log.get('type') == 'STATUS' and log.get('status'):
                status_id = log.get('status')
                
                print(f"🔍 Статус ID: {status_id}")
                
                # Ищем статус принятия оффера (186507)
                if status_id == 186507:
                    created_at = log.get('created')
                    print(f"🎯 Найден подходящий статус! Дата: {created_at}")
                    
                    if created_at:
                        try:
                            # Парсим дату из ISO формата
                            if 'T' in created_at:
                                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            else:
                                date_obj = datetime.fromisoformat(created_at)
                            
                            print(f"✅ Найдена дата принятия оффера (статус {status_id}): {date_obj.date()}")
                            return date_obj.date()
                        except ValueError as e:
                            print(f"❌ Ошибка парсинга даты {created_at}: {e}")
                            continue
        
        print("ℹ️ Дата принятия оффера (статус 186507) не найдена в логах")
        return None
    
    def _find_hire_date(self, logs):
        """
        Ищет дату выхода на работу в логах кандидата
        Согласно Huntflow API: ищем поле employment_date в логах со статусом "Hired"
        """
        from datetime import datetime
        import re
        
        print(f"🔍 Поиск даты выхода в {len(logs)} логах")
        
        # Сортируем логи по дате создания (от старых к новым)
        sorted_logs = sorted(logs, key=lambda x: x.get('created', ''), reverse=False)
        
        # Ищем в логах со статусом "Hired" поле employment_date
        for i, log in enumerate(sorted_logs):
            print(f"📝 Проверяем лог {i+1}: type={log.get('type')}, status={log.get('status')}")
            
            if log.get('type') == 'STATUS' and log.get('status'):
                status_id = log.get('status')
                employment_date = log.get('employment_date')
                
                print(f"🔍 Статус ID: {status_id}, employment_date: {employment_date}")
                
                # Ищем статус "Hired" (принят на работу) с полем employment_date
                if employment_date:
                    print(f"🎯 Найдена дата выхода! employment_date: {employment_date}")
                    
                    try:
                        # Парсим дату из ISO формата
                        if 'T' in employment_date:
                            date_obj = datetime.fromisoformat(employment_date.replace('Z', '+00:00'))
                        else:
                            date_obj = datetime.fromisoformat(employment_date)
                        
                        print(f"✅ Найдена дата выхода (employment_date): {date_obj.date()}")
                        return date_obj.date()
                    except ValueError as e:
                        print(f"❌ Ошибка парсинга даты {employment_date}: {e}")
                        continue
        
        # Если не найдено по статусам, ищем в комментариях и полях
        date_patterns = [
            r'выход.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'start.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'hire.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'приступил.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'начал.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'дата выхода.*?(\d{1,2}[./]\d{1,2}[./]\d{4})',
        ]
        
        for log in logs:
            # Проверяем комментарии
            comment = log.get('comment', '')
            if comment:
                for pattern in date_patterns:
                    match = re.search(pattern, comment.lower())
                    if match:
                        date_str = match.group(1)
                        try:
                            # Пробуем разные форматы даты
                            for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    print(f"✅ Найдена дата выхода в комментарии: {date_obj.date()}")
                                    return date_obj.date()
                                except ValueError:
                                    continue
                        except ValueError:
                            continue
            
            # Проверяем дополнительные поля
            if 'fields' in log:
                for field in log['fields']:
                    field_name = field.get('name', '').lower()
                    field_value = field.get('value', '')
                    
                    if any(keyword in field_name for keyword in ['выход', 'start', 'hire', 'дата выхода', 'дата начала работы']):
                        if field_value and re.match(r'\d{1,2}[./]\d{1,2}[./]\d{4}', field_value):
                            try:
                                for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                                    try:
                                        date_obj = datetime.strptime(field_value, fmt)
                                        print(f"✅ Найдена дата выхода в поле {field_name}: {date_obj.date()}")
                                        return date_obj.date()
                                    except ValueError:
                                        continue
                            except ValueError:
                                continue
        
        print("ℹ️ Дата выхода на работу не найдена в логах")
        return None


class RecruitmentMetrics(models.Model):
    """Агрегированные метрики найма за период"""
    
    # Период
    PERIOD_TYPE_CHOICES = [
        ('weekly', 'Неделя'),
        ('monthly', 'Месяц'),
        ('quarterly', 'Квартал'),
        ('yearly', 'Год'),
        ('custom', 'Произвольный'),
    ]
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPE_CHOICES,
        verbose_name='Тип периода'
    )
    period_start = models.DateField(verbose_name='Начало периода')
    period_end = models.DateField(verbose_name='Конец периода')
    
    # Опциональная группировка
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Вакансия (если метрика для конкретной)'
    )
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Грейд (если метрика для конкретного)'
    )
    project = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Проект'
    )
    
    # === ВРЕМЕННЫЕ МЕТРИКИ ===
    avg_time_to_offer = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Средний Time-to-Offer (дни)',
        help_text='Среднее время от открытия до предложения кандидату'
    )
    median_time_to_offer = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Медианный Time-to-Offer (дни)'
    )
    avg_time_to_hire = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Средний Time-to-Hire (дни)',
        help_text='Среднее время от первого контакта до оффера'
    )
    
    # === HIRING VELOCITY ===
    hires_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество найма за период'
    )
    hiring_velocity_weekly = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Скорость найма (hires/week)',
        help_text='Количество закрытий в неделю'
    )
    
    # === DAYS BEHIND SCHEDULE ===
    avg_days_behind_schedule = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Среднее отставание от графика (дни)',
        help_text='Среднее количество дней просрочки для закрытых заявок'
    )
    overdue_requests_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество просроченных заявок'
    )
    
    # === SLA COMPLIANCE ===
    sla_compliance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='SLA Compliance (%)',
        help_text='% заявок, закрытых в срок по SLA'
    )
    
    # === ОБЩАЯ СТАТИСТИКА ===
    total_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего заявок за период'
    )
    closed_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='Закрыто заявок'
    )
    active_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='Активные заявки',
        help_text='Все заявки, которые не закрыты (in_progress + planned + cancelled)'
    )
    in_progress_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='В процессе'
    )
    planned_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='Планируемые'
    )
    cancelled_requests = models.PositiveIntegerField(
        default=0,
        verbose_name='Отменено'
    )
    critical_requests_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Критические',
        help_text='Активные заявки, которые просрочены'
    )
    
    # Метаданные
    calculated_at = models.DateTimeField(auto_now=True, verbose_name='Рассчитано')
    
    class Meta:
        verbose_name = 'Метрики найма'
        verbose_name_plural = 'Метрики найма'
        unique_together = [
            ['period_type', 'period_start', 'vacancy', 'grade', 'project']
        ]
        indexes = [
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['vacancy', 'grade']),
        ]
        ordering = ['-period_start']
    
    def __str__(self):
        return f"Метрики: {self.period_type} ({self.period_start} - {self.period_end})"


class DemandForecast(models.Model):
    """Прогноз потребности в персонале"""
    
    # Период прогноза
    FORECAST_PERIOD_CHOICES = [
        ('next_month', 'Следующий месяц'),
        ('next_quarter', 'Следующий квартал'),
        ('next_year', 'Следующий год'),
    ]
    forecast_period = models.CharField(
        max_length=20,
        choices=FORECAST_PERIOD_CHOICES,
        verbose_name='Период прогноза'
    )
    forecast_start = models.DateField(verbose_name='Начало прогнозного периода')
    forecast_end = models.DateField(verbose_name='Конец прогнозного периода')
    
    # Для чего прогноз
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        verbose_name='Вакансия'
    )
    grade = models.ForeignKey(
        'finance.Grade',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Грейд'
    )
    project = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Проект'
    )
    
    # === ПРОГНОЗ ===
    forecasted_demand = models.PositiveIntegerField(
        verbose_name='Прогнозируемая потребность',
        help_text='Ожидаемое количество заявок'
    )
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Уровень уверенности (%)',
        help_text='Уверенность в прогнозе (0-100%)'
    )
    
    # Факторы прогноза
    based_on_history = models.BooleanField(
        default=True,
        verbose_name='На основе истории',
        help_text='Прогноз основан на исторических данных'
    )
    seasonality_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name='Фактор сезонности',
        help_text='Коэффициент сезонности (1.0 = нормально)'
    )
    growth_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name='Фактор роста',
        help_text='Коэффициент роста команды'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создано пользователем'
    )
    notes = models.TextField(blank=True, verbose_name='Заметки')
    
    class Meta:
        verbose_name = 'Прогноз потребности'
        verbose_name_plural = 'Прогнозы потребности'
        ordering = ['-forecast_start']
    
    def __str__(self):
        return f"Прогноз: {self.vacancy.name} - {self.forecasted_demand} чел."


class RecruiterCapacity(models.Model):
    """Планирование мощностей команды рекрутеров"""
    
    # Рекрутер
    recruiter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='capacity_plans',
        verbose_name='Рекрутер'
    )
    
    # Период
    period_start = models.DateField(verbose_name='Начало периода')
    period_end = models.DateField(verbose_name='Конец периода')
    
    # === ТЕКУЩАЯ ЗАГРУЗКА ===
    active_requests_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Активных заявок',
        help_text='Текущее количество заявок в работе'
    )
    planned_requests_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Запланировано заявок',
        help_text='Заявки, которые скоро начнутся'
    )
    
    # === МОЩНОСТЬ ===
    max_capacity = models.PositiveIntegerField(
        default=10,
        verbose_name='Максимальная мощность',
        help_text='Максимальное количество заявок одновременно'
    )
    available_capacity = models.PositiveIntegerField(
        default=0,
        verbose_name='Доступная мощность',
        help_text='Свободные слоты для новых заявок'
    )
    capacity_utilization = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Загрузка (%)',
        help_text='Процент использования мощности'
    )
    
    # === ПРОИЗВОДИТЕЛЬНОСТЬ ===
    avg_time_per_request = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Среднее время на заявку (дни)'
    )
    closed_requests_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Закрыто заявок за период'
    )
    success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Успешность закрытия (%)'
    )
    
    # Статус
    is_overloaded = models.BooleanField(
        default=False,
        verbose_name='Перегружен',
        help_text='Загрузка > 90%'
    )
    
    # Метаданные
    calculated_at = models.DateTimeField(auto_now=True, verbose_name='Рассчитано')
    
    class Meta:
        verbose_name = 'Мощность рекрутера'
        verbose_name_plural = 'Мощности рекрутеров'
        unique_together = [['recruiter', 'period_start']]
        ordering = ['-period_start', 'recruiter']
    
    def __str__(self):
        return f"{self.recruiter.get_full_name()} - {self.capacity_utilization}%"
    
    def calculate_capacity(self):
        """Автоматический расчет мощности"""
        self.available_capacity = self.max_capacity - self.active_requests_count
        if self.max_capacity > 0:
            self.capacity_utilization = round(
                (self.active_requests_count / self.max_capacity) * 100, 2
            )
        self.is_overloaded = self.capacity_utilization > 90
        self.save()


class PlanMetrics(models.Model):
    """Метрики плана найма"""
    
    hiring_plan = models.OneToOneField(
        HiringPlan,
        on_delete=models.CASCADE,
        related_name='metrics',
        verbose_name='План найма',
        help_text='План найма, для которого рассчитываются метрики'
    )
    
    # Простые счетчики
    total_positions = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего позиций',
        help_text='Общее количество позиций в плане'
    )
    total_headcount_needed = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего требуется',
        help_text='Общее количество требуемых специалистов'
    )
    total_headcount_hired = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего нанято',
        help_text='Общее количество нанятых специалистов'
    )
    
    # Прогресс (в процентах)
    completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Процент выполнения',
        help_text='Процент выполнения плана найма'
    )
    
    # Дата последнего обновления
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Последнее обновление',
        help_text='Дата последнего обновления метрик'
    )
    
    class Meta:
        verbose_name = 'Метрики плана найма'
        verbose_name_plural = 'Метрики планов найма'
    
    def __str__(self):
        return f"Метрики для {self.hiring_plan.title}"


def create_requests_for_position(position):
    """Создает заявки для позиции на основе headcount_needed и грейдов"""
    # Удаляем существующие заявки для этой позиции
    HiringRequest.objects.filter(
        vacancy=position.vacancy,
        grade__in=position.grades.all()
    ).delete()
    
    grades = position.grades.all()
    if not grades.exists():
        return
    
    count = position.headcount_needed
    for grade in grades:
        for n in range(1, count + 1):
            # Рассчитываем даты
            opening_date = position.created_at.date()
            deadline = position.urgency_deadline or (opening_date + timedelta(days=30))
            
            HiringRequest.objects.create(
                vacancy=position.vacancy,
                grade=grade,
                project=position.project,
                priority=position.priority,
                opening_reason='new_position',  # По умолчанию новая позиция
                opening_date=opening_date,
                deadline=deadline,
                status='planned',
            )


@receiver(post_save, sender=HiringPlanPosition)
def create_requests_on_position_save(sender, instance, created, **kwargs):
    """Автоматически создает заявки при сохранении позиции"""
    if created or kwargs.get('update_fields') is None:
        # Создаем заявки только при создании или полном обновлении
        create_requests_for_position(instance)


class HuntflowSync(models.Model):
    """Синхронизация данных с HuntFlow"""
    
    ENTITY_TYPE_CHOICES = [
        ('vacancy', 'Вакансия'),
        ('applicant', 'Кандидат'),
        ('status_change', 'Изменение статуса'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
        ('skipped', 'Пропущено'),
    ]
    
    # Идентификаторы HuntFlow
    huntflow_vacancy_id = models.IntegerField(
        verbose_name='ID вакансии в HuntFlow',
        db_index=True
    )
    huntflow_applicant_id = models.IntegerField(
        null=True, blank=True,
        verbose_name='ID кандидата в HuntFlow',
        db_index=True
    )
    huntflow_log_id = models.IntegerField(
        null=True, blank=True,
        verbose_name='ID лога в HuntFlow'
    )
    
    # Тип синхронизируемой сущности
    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_TYPE_CHOICES,
        verbose_name='Тип сущности'
    )
    
    # Связь с HiringRequest
    hiring_request = models.ForeignKey(
        HiringRequest,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='huntflow_syncs',
        verbose_name='Заявка на найм'
    )
    
    # Данные из HuntFlow (JSON)
    huntflow_data = models.JSONField(
        verbose_name='Данные из HuntFlow',
        help_text='Полные данные объекта из HuntFlow API'
    )
    
    # Статус синхронизации
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='pending',
        verbose_name='Статус синхронизации'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    
    # Метаданные
    synced_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Дата синхронизации'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Синхронизация HuntFlow'
        verbose_name_plural = 'Синхронизации HuntFlow'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['huntflow_vacancy_id', 'huntflow_applicant_id']),
            models.Index(fields=['sync_status']),
        ]
    
    def __str__(self):
        return f"HuntFlow Sync: Vacancy #{self.huntflow_vacancy_id} - {self.get_sync_status_display()}"