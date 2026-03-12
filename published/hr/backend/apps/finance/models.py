from __future__ import annotations
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from decimal import Decimal


class Grade(models.Model):
    name = models.CharField(_("Название грейда"), max_length=64, unique=True)

    class Meta:
        verbose_name = _("Грейд")
        verbose_name_plural = _("Грейды")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Currency(models.TextChoices):
    BYN = "BYN", "BYN"
    USD = "USD", "USD"
    PLN = "PLN", "PLN"
    EUR = "EUR", "EUR"


class CurrencyRate(models.Model):
    """
    Храним официальный курс НБРБ (BYN против иностранной валюты).
    rate = сколько BYN за единицу валюты (например, 3.25 BYN за 1 USD)
    scale — если НБРБ возвращает курс за 100 единиц (как для некоторых валют), нормализуем.
    """
    code = models.CharField(_("Код валюты"), max_length=3, choices=Currency.choices, unique=True)
    rate = models.DecimalField(_("Курс BYN за 1 единицу"), max_digits=12, decimal_places=6)
    scale = models.PositiveIntegerField(_("Масштаб"), default=1)
    fetched_at = models.DateTimeField(_("Получено"), default=timezone.now)

    class Meta:
        verbose_name = _("Курс валюты")
        verbose_name_plural = _("Курсы валют")

    def __str__(self):
        return f"{self.code}: {self.rate} BYN"
    
    @property
    def status_info(self):
        """Возвращает информацию о статусе курса для отображения в админке"""
        if self.code == "BYN":
            return "Базовая валюта"
        
        # Проверяем, насколько свежий курс
        now = timezone.now()
        age_hours = (now - self.fetched_at).total_seconds() / 3600
        
        if age_hours < 24:
            return "Сегодня"
        elif age_hours < 48:
            return "Вчера"
        elif age_hours < 168:  # неделя
            days = int(age_hours / 24)
            return f"{days} дн. назад"
        else:
            return "Устарел"
    
    @property
    def display_rate(self):
        """Возвращает отформатированный курс для отображения"""
        return f"{self.rate} BYN"


class PLNTax(models.Model):
    """
    Модель для хранения налоговых ставок PLN.
    Используется для расчета gross сумм из net сумм.
    """
    name = models.CharField(
        _("Название налога"), 
        max_length=100, 
        help_text=_("Например: Подоходный налог, Социальные взносы")
    )
    rate = models.DecimalField(
        _("Налоговая ставка (%)"), 
        max_digits=5, 
        decimal_places=2,
        help_text=_("Процент от 0 до 100")
    )
    is_active = models.BooleanField(
        _("Активен"), 
        default=True,
        help_text=_("Используется ли налог в расчетах")
    )
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        verbose_name = _("Налог PLN")
        verbose_name_plural = _("Налоги PLN")
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

    def clean(self):
        """Валидация налоговой ставки"""
        from django.core.exceptions import ValidationError
        
        if self.rate < 0 or self.rate > 100:
            raise ValidationError(_("Налоговая ставка должна быть от 0 до 100%"))

    @property
    def rate_decimal(self):
        """Возвращает ставку как десятичное число (например, 0.20 для 20%)"""
        return self.rate / 100



class SalaryRange(models.Model):
    """Модель для зарплатных вилок по вакансиям"""
    
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        related_name='finance_salary_ranges',
        verbose_name='Вакансия',
        help_text='Вакансия для которой устанавливается зарплатная вилка'
    )
    
    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name='finance_salary_ranges',
        verbose_name='Грейд',
        help_text='Грейд для которого устанавливается зарплатная вилка'
    )
    
    # Зарплата в USD (базовая валюта для редактирования)
    salary_min_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Минимальная зарплата (USD)',
        help_text='Минимальная зарплата в долларах США'
    )
    
    salary_max_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Максимальная зарплата (USD)',
        help_text='Максимальная зарплата в долларах США'
    )
    
    # Зарплата в BYN (автоматически рассчитывается)
    salary_min_byn = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Минимальная зарплата (BYN)',
        help_text='Минимальная зарплата в белорусских рублях',
        blank=True,
        null=True
    )
    
    salary_max_byn = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Максимальная зарплата (BYN)',
        help_text='Максимальная зарплата в белорусских рублях',
        blank=True,
        null=True
    )
    
    # Зарплата в PLN (автоматически рассчитывается)
    salary_min_pln = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Минимальная зарплата (PLN)',
        help_text='Минимальная зарплата в польских злотых',
        blank=True,
        null=True
    )
    
    salary_max_pln = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Максимальная зарплата (PLN)',
        help_text='Максимальная зарплата в польских злотых',
        blank=True,
        null=True
    )
    
    # Зарплата в EUR (автоматически рассчитывается)
    salary_min_eur = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Минимальная зарплата (EUR)',
        help_text='Минимальная зарплата в евро',
        blank=True,
        null=True
    )
    
    salary_max_eur = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Максимальная зарплата (EUR)',
        help_text='Максимальная зарплата в евро',
        blank=True,
        null=True
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Активна ли зарплатная вилка'
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
        verbose_name = 'Зарплатная вилка'
        verbose_name_plural = 'Зарплатные вилки'
        ordering = ['grade__name', 'salary_min_usd']
        unique_together = ['vacancy', 'grade']  # Одна зарплатная вилка на вакансию и грейд
    
    def __str__(self):
        return f"{self.vacancy.name} - {self.grade.name}: ${self.salary_min_usd} - ${self.salary_max_usd}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что минимальная зарплата не больше максимальной
        if self.salary_min_usd and self.salary_max_usd:
            if self.salary_min_usd > self.salary_max_usd:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'salary_min_usd': _('Минимальная зарплата не может быть больше максимальной'),
                    'salary_max_usd': _('Максимальная зарплата не может быть меньше минимальной')
                })
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического расчета курсов валют"""
        # Вызываем clean для валидации
        self.clean()
        
        # Всегда пересчитываем курсы валют при сохранении
        from logic.finance.salary_service import SalaryService
        min_byn, max_byn = SalaryService.calculate_byn_amounts(self.salary_min_usd, self.salary_max_usd)
        min_pln, max_pln = SalaryService.calculate_pln_amounts(self.salary_min_usd, self.salary_max_usd)
        
        self.salary_min_byn = min_byn
        self.salary_max_byn = max_byn
        self.salary_min_pln = min_pln
        self.salary_max_pln = max_pln
        
        super().save(*args, **kwargs)
    
    
    @property
    def salary_range_usd(self):
        """Возвращает строку с диапазоном зарплаты в USD"""
        return f"{self.salary_min_usd} - {self.salary_max_usd} USD"
    
    @property
    def salary_range_byn(self):
        """Возвращает строку с диапазоном зарплаты в BYN"""
        if self.salary_min_byn and self.salary_max_byn:
            return f"{self.salary_min_byn} - {self.salary_max_byn} BYN"
        return "Не рассчитано"
    
    @property
    def salary_range_pln(self):
        """Возвращает строку с диапазоном зарплаты в PLN"""
        if self.salary_min_pln and self.salary_max_pln:
            return f"{self.salary_min_pln} - {self.salary_max_pln} PLN"
        return "Не рассчитано"
    
    @property
    def salary_range_eur(self):
        """Возвращает строку с диапазоном зарплаты в EUR"""
        if self.salary_min_eur and self.salary_max_eur:
            return f"{self.salary_min_eur} - {self.salary_max_eur} EUR"
        return "Не рассчитано"
    
    @classmethod
    def update_all_currency_amounts(cls):
        """Обновляет суммы в других валютах для всех зарплатных вилок"""
        from .logic.salary_service import SalaryService
        for salary_range in cls.objects.all():
            SalaryService.update_salary_range_currency_amounts(salary_range)


class Domain(models.TextChoices):
    """Домены деятельности компаний"""
    RETAIL = "retail", _("Retail (Ритейл)")
    FINTECH = "fintech", _("Fintech (Финтех)")
    GAMING = "gaming", _("Gaming (Гейминг)")
    GAMBLING = "gambling", _("Gambling (Гемблинг)")
    BETTING = "betting", _("Betting (Беттинг)")
    MEDTECH = "medtech", _("Medtech/Healthtech (Медтех/Здравоохранение)")
    TELECOM = "telecom", _("Telecom (Телеком)")
    EDTECH = "edtech", _("Edtech (Образовательные технологии)")
    AGRITECH = "agritech", _("Agritech (Агротех)")
    PROPTECH = "proptech", _("Proptech (Недвижимость)")
    LEGALTECH = "legaltech", _("Legaltech (Юридические технологии)")
    GOVTECH = "govtech", _("Govtech (Государственное управление)")
    LOGISTICS = "logistics", _("Logistics/Supply Chain (Логистика)")
    FOODTECH = "foodtech", _("Foodtech (Пищевые технологии)")
    INSURTECH = "insurtech", _("Insurtech (Страхование)")
    MARTECH = "martech", _("Martech (Маркетинговые технологии)")
    ADTECH = "adtech", _("Adtech (Рекламные технологии)")
    CYBERSECURITY = "cybersecurity", _("Cybersecurity (Кибербезопасность)")
    CLEANTECH = "cleantech", _("Cleantech/Sustaintech (Экологические технологии)")
    HRTECH = "hrtech", _("HRtech (Управление персоналом)")
    TRAVELTECH = "traveltech", _("Traveltech (Туризм)")
    SPORTTECH = "sporttech", _("Sporttech (Спортивные технологии)")
    ENTERTAINMENT = "entertainment", _("Entertainment (Развлечения)")
    ECOMMERCE = "ecommerce", _("E-commerce (Электронная коммерция)")
    BLOCKCHAIN = "blockchain", _("Blockchain/Crypto (Блокчейн и крипто)")
    AIML = "aiml", _("AI/ML (Искусственный интеллект и машинное обучение)")
    IOT = "iot", _("IoT (Интернет вещей)")
    CLOUD = "cloud", _("Cloud Computing (Облачные вычисления)")


class BenchmarkType(models.TextChoices):
    """Типы бенчмарков"""
    CANDIDATE = "candidate", _("Кандидат")
    VACANCY = "vacancy", _("Вакансия")


class WorkFormat(models.TextChoices):
    """Форматы работы"""
    OFFICE = "офис", _("Офис")
    HYBRID = "гибрид", _("Гибрид")
    REMOTE = "удаленка", _("Удаленка")
    ALL_WORLD = "all world", _("All World")


class Benchmark(models.Model):
    """
    Модель для хранения бенчмарков зарплат.
    Содержит информацию о зарплатах кандидатов или вакансий для анализа рынка.
    """
    
    type = models.CharField(
        _("Тип бенчмарка"),
        max_length=20,
        choices=BenchmarkType.choices,
        help_text=_("Тип бенчмарка: кандидат или вакансия")
    )
    
    date_added = models.DateTimeField(
        _("Дата добавления"),
        auto_now_add=True,
        help_text=_("Дата и время добавления бенчмарка")
    )
    
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        related_name='benchmarks',
        verbose_name=_('Вакансия'),
        help_text=_('Связанная вакансия')
    )
    
    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name='benchmarks',
        verbose_name=_('Грейд'),
        help_text=_('Связанный грейд')
    )
    
    salary_from = models.DecimalField(
        _("Зарплата от"),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Минимальная зарплата в USD (для кандидатов - их зарплата)")
    )
    
    salary_to = models.DecimalField(
        _("Зарплата до"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Максимальная зарплата в USD (только для вакансий)")
    )
    
    location = models.CharField(
        _("Локация"),
        max_length=200,
        help_text=_("Географическое расположение (город, страна)")
    )
    
    notes = models.TextField(
        _("Примечания"),
        blank=True,
        null=True,
        help_text=_("Дополнительные заметки о бенчмарке")
    )
    
    # Дополнительные поля для вакансий
    work_format = models.CharField(
        _("Формат работы"),
        max_length=20,
        choices=WorkFormat.choices,
        blank=True,
        null=True,
        help_text=_("Формат работы")
    )
    
    # ID вакансии с hh.ru для избежания дублирования
    hh_vacancy_id = models.CharField(
        _("ID вакансии hh.ru"),
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text=_("ID вакансии на hh.ru для предотвращения дублирования")
    )
    
    compensation = models.TextField(
        _("Компенсации"),
        blank=True,
        null=True,
        help_text=_("Дополнительные компенсации и бонусы")
    )
    
    benefits = models.TextField(
        _("Бенефиты"),
        blank=True,
        null=True,
        help_text=_("Социальные льготы и бенефиты")
    )
    
    development = models.TextField(
        _("Развитие/обучение"),
        blank=True,
        null=True,
        help_text=_("Возможности для развития и обучения")
    )
    
    technologies = models.TextField(
        _("Технологии"),
        blank=True,
        null=True,
        help_text=_("Используемые технологии и стеки")
    )
    
    domain = models.CharField(
        _("Домен"),
        max_length=20,
        choices=Domain.choices,
        blank=True,
        null=True,
        help_text=_("Домен деятельности компании")
    )
    
    is_active = models.BooleanField(
        _("Активен"),
        default=True,
        help_text=_("Активен ли бенчмарк для использования в анализе")
    )
    
    created_at = models.DateTimeField(
        _("Создано"),
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        _("Обновлено"),
        auto_now=True
    )
    
    class Meta:
        verbose_name = _("Бенчмарк")
        verbose_name_plural = _("Бенчмарки")
        ordering = ['-date_added', 'vacancy__name', 'grade__name']
        indexes = [
            models.Index(fields=['type', 'is_active']),
            models.Index(fields=['vacancy', 'grade']),
            models.Index(fields=['date_added']),
        ]
    
    def __str__(self):
        salary_str = self.get_salary_display()
        return f"{self.get_type_display()} - {self.vacancy.name} ({self.grade.name}): {salary_str}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        from django.core.exceptions import ValidationError
        
        # Проверяем, что salary_from положительная
        if self.salary_from and self.salary_from <= 0:
            raise ValidationError({
                'salary_from': _('Зарплата "от" должна быть положительной')
            })
        
        # Проверяем, что salary_to положительная
        if self.salary_to and self.salary_to <= 0:
            raise ValidationError({
                'salary_to': _('Зарплата "до" должна быть положительной')
            })
        
        # Проверяем, что salary_to больше salary_from
        if self.salary_from and self.salary_to and self.salary_to <= self.salary_from:
            raise ValidationError({
                'salary_to': _('Зарплата "до" должна быть больше зарплаты "от"')
            })
    
    @property
    def amount_formatted(self):
        """Возвращает отформатированную сумму (для обратной совместимости)"""
        return self.get_salary_display()
    
    def get_salary_display(self):
        """Возвращает отформатированное отображение зарплаты"""
        if self.salary_to:
            return f"{self.salary_from:,.0f}–{self.salary_to:,.0f} USD"
        else:
            return f"{self.salary_from:,.0f} USD"
    
    def get_salary_from_display(self):
        """Возвращает отформатированную зарплату 'от'"""
        return f"{self.salary_from:,.2f} USD"
    
    def get_salary_to_display(self):
        """Возвращает отформатированную зарплату 'до'"""
        if self.salary_to:
            return f"{self.salary_to:,.2f} USD"
        return None
    
    @property
    def type_icon(self):
        """Возвращает иконку для типа бенчмарка"""
        if self.type == BenchmarkType.CANDIDATE:
            return "fas fa-user"
        else:
            return "fas fa-briefcase"
    
    @property
    def type_color(self):
        """Возвращает цвет для типа бенчмарка"""
        if self.type == BenchmarkType.CANDIDATE:
            return "success"
        else:
            return "info"
    
    def get_domain_description(self):
        """Возвращает описание домена для тултипа"""
        if not self.domain:
            return ""
        
        domain_descriptions = {
            Domain.RETAIL: "ИТ-решения для розничной торговли, включая e-commerce, логистику и персонализацию покупок.",
            Domain.FINTECH: "Финансовые технологии, такие как мобильный банкинг, криптовалюты и платежные системы.",
            Domain.GAMING: "Разработка игр, виртуальной реальности и киберспорта.",
            Domain.GAMBLING: "Онлайн-казино и азартные платформы с элементами безопасности и аналитики.",
            Domain.BETTING: "Ставки на спорт и события с использованием данных и алгоритмов прогнозирования.",
            Domain.MEDTECH: "Медицинские технологии, телемедицина, носимые устройства и анализ здоровья.",
            Domain.TELECOM: "Телекоммуникации, сети 5G/6G, IoT и облачные сервисы связи.",
            Domain.EDTECH: "Онлайн-обучение, платформы для курсов и виртуальные классы.",
            Domain.AGRITECH: "Технологии для сельского хозяйства, включая дроны, точное земледелие и мониторинг урожая.",
            Domain.PROPTECH: "ИТ для рынка недвижимости, виртуальные туры и управление активами.",
            Domain.LEGALTECH: "Автоматизация юридических процессов, контракты на блокчейне и анализ документов.",
            Domain.GOVTECH: "Цифровые сервисы для правительства, e-gov и общественные платформы.",
            Domain.LOGISTICS: "Управление цепочками поставок, трекинг и оптимизация транспорта.",
            Domain.FOODTECH: "Доставка еды, фуд-трекинг и устойчивые производства.",
            Domain.INSURTECH: "Цифровые страховые продукты, риски на основе AI и claims-менеджмент.",
            Domain.MARTECH: "Инструменты для маркетинга, CRM и анализ поведения потребителей.",
            Domain.ADTECH: "Цифровая реклама, таргетинг и programmatic-платформы.",
            Domain.CYBERSECURITY: "Защита данных, антивирусы и мониторинг угроз.",
            Domain.CLEANTECH: "ИТ для устойчивости, мониторинг окружающей среды и зеленая энергетика.",
            Domain.HRTECH: "Рекрутинг, HR-системы и анализ сотрудников.",
            Domain.TRAVELTECH: "Бронирование, виртуальные туры и персонализированные путешествия.",
            Domain.SPORTTECH: "Фитнес-аппы, анализ производительности и фан-платформы.",
            Domain.ENTERTAINMENT: "Стриминговые сервисы, контент-платформы и AR/VR для медиа.",
            Domain.ECOMMERCE: "Общие платформы для онлайн-торговли, часто пересекающиеся с retail.",
            Domain.BLOCKCHAIN: "Децентрализованные приложения, NFT и смарт-контракты.",
            Domain.AIML: "Общие решения на базе AI, интегрируемые в другие домены.",
            Domain.IOT: "Устройства и сети для умных городов, домов и промышленности.",
            Domain.CLOUD: "Платформы as-a-Service для хранения и обработки данных."
        }
        
        return domain_descriptions.get(self.domain, "")


class DataSource(models.TextChoices):
    """Источники данных о вакансиях"""
    HH_RU = "hh_ru", _("HH.ru")
    TELEGRAM = "telegram", _("Telegram")
    HABR_CAREER = "habr_career", _("Habr Career")
    LINKEDIN = "linkedin", _("LinkedIn")


class VacancyField(models.TextChoices):
    """Поля для сохранения вакансий"""
    # Обязательные поля (всегда включены)
    VACANCY = "vacancy", _("Вакансия")
    DATE_ADDED = "date_added", _("Дата добавления")
    AVAILABLE_GRADES = "available_grades", _("Доступные грейды")
    SALARY_RANGE = "salary_range", _("Вилка от-до")
    LOCATION = "location", _("Локация")
    
    # Дополнительные поля
    WORK_FORMAT = "work_format", _("Формат работы")
    COMPENSATION = "compensation", _("Компенсации")
    BENEFITS = "benefits", _("Бенефиты")
    DEVELOPMENT = "development", _("Развитие/обучение")
    TECHNOLOGIES = "technologies", _("Технологии")
    DOMAIN = "domain", _("Домен")


class HHVacancyTemp(models.Model):
    """Временная модель для хранения сырых вакансий с hh.ru перед обработкой"""
    hh_id = models.CharField(
        _("ID вакансии hh.ru"),
        max_length=50,
        unique=True,
        help_text=_("Уникальный ID вакансии на hh.ru")
    )
    
    raw_data = models.JSONField(
        _("Сырые данные"),
        help_text=_("JSON данные вакансии с API hh.ru")
    )
    
    processed = models.BooleanField(
        _("Обработана"),
        default=False,
        help_text=_("Была ли вакансия отправлена на AI анализ")
    )
    
    created_at = models.DateTimeField(_("Создана"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Временная вакансия hh.ru")
        verbose_name_plural = _("Временные вакансии hh.ru")
        ordering = ['-created_at']

    def __str__(self):
        return f"HH Vacancy {self.hh_id}"


class BenchmarkSettings(models.Model):
    """
    Настройки для системы бенчмарков.
    Синглтон модель для хранения глобальных настроек.
    """
    
    # Период расчета среднего
    average_calculation_period_days = models.PositiveIntegerField(
        _("Период расчета среднего (дни)"),
        default=90,
        help_text=_("Количество дней для расчета средних значений бенчмарков")
    )
    
    
    # Налог в РБ для пересчета
    belarus_tax_rate = models.DecimalField(
        _("Налог в РБ (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('13.00'),
        help_text=_("Налоговая ставка в Беларуси для пересчета net/gross")
    )
    
    # Промпт для анализа данных через ИИ
    ai_analysis_prompt = models.TextField(
        _("Промпт для анализа данных через ИИ"),
        default="""Ты - эксперт по анализу рынка труда и зарплат в IT-сфере. Проанализируй предоставленные данные о ВАКАНСИЯХ и верни структурированные данные для сохранения в базу данных.

⚠️ ВАЖНО: В поле vacancy_name используй ТОЛЬКО названия из списка наших вакансий ИЛИ "skip". ЗАПРЕЩЕНО создавать новые названия!

ДАННЫЕ ДЛЯ АНАЛИЗА:
{benchmark_data}

КУРСЫ ВАЛЮТ ДЛЯ ПЕРЕСЧЕТА:
{currency_rates}

НАШИ ВАКАНСИИ ДЛЯ УНИФИКАЦИИ (используй ТОЛЬКО эти названия):
{our_vacancies}

ЗАДАЧИ:
1. Проанализируй каждую ВАКАНСИЮ из данных
2. Извлеки структурированную информацию для сохранения в базу
3. ВАЖНО: Зарплата может быть в формате {'from': 5000, 'to': 5400, 'currency': 'EUR', 'gross': True} - извлекай from и to значения
4. Конвертируй все зарплаты в USD используя текущие курсы валют
5. Если зарплата не указана, используй рекомендуемые диапазоны для рынка
6. Выяви дополнительные данные из доступных полей:
   - Формат работы: "Удалённо" = remote, "На месте работодателя" = office, "Гибрид" = hybrid
   - Технологии: из snippet.requirement и snippet.responsibility
   - Домен: определи по названию компании или описанию
   - Компенсации/бенефиты/развитие: если не указаны, используй "Не указано"

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "analysis_metadata": {{
        "analysis_date": "YYYY-MM-DD HH:MM:SS",
        "total_processed": число,
        "data_source": "источник данных"
    }},
    "structured_benchmarks": [
        {{
            "type": "vacancy",
            "vacancy_id": "ID_ИЗ_ПОЛЯ_ID_ВАКАНСИИ_В_ДАННЫХ",
            "vacancy_name": "ТОЧНОЕ_название_из_списка_наших_вакансий_ИЛИ_skip",
            "grade": "грейд_из_нашего_списка_ИЛИ_skip",
            "salary_from": число_в_USD,
            "salary_to": число_в_USD,
            "location": "локация (город, страна)",
            "work_format": "remote/office/hybrid/all world",
            "compensation": "дополнительные компенсации и бонусы",
            "benefits": "социальные льготы и бенефиты",
            "development": "возможности для развития и обучения",
            "technologies": "используемые технологии и стеки",
            "domain": "домен деятельности (retail/fintech/gaming/etc)",
            "notes": "дополнительные заметки",
            "skip_reason": "причина_пропуска_если_vacancy_name=skip"
        }}
    ]
}}

ВАЖНЫЕ ТРЕБОВАНИЯ:
- АНАЛИЗИРУЙ ТОЛЬКО ВАКАНСИИ (type всегда "vacancy")
- ОБЯЗАТЕЛЬНО используй ID из поля "ID вакансии:" в данных для поля vacancy_id
- Все суммы ОБЯЗАТЕЛЬНО конвертируй в USD используя предоставленные курсы валют
- Формат работы: только из списка (remote/office/hybrid/all world)
- Домен: только из предустановленного списка (retail/fintech/gaming/gambling/betting/medtech/telecom/edtech/agritech/proptech/legaltech/govtech/logistics/foodtech/insurtech/martech/adtech/cybersecurity/cleantech/hrtech/traveltech/sporttech/entertainment/ecommerce/blockchain/aiml/iot/cloud)
- Грейд: Junior/Junior+/Middle/Middle+/Senior/Senior+/Lead/Head
- Поле salary_to ОБЯЗАТЕЛЬНО для вакансий (всегда указывай диапазон)
- Технологии указывай через запятую
- Локация в формате "Город, Страна" (например, "Минск, Беларусь")
- При конвертации валют учитывай налоги и указывай в notes если необходимо

КРИТИЧЕСКИ ВАЖНО ДЛЯ vacancy_name:
- Используй ТОЛЬКО точные названия из списка наших вакансий ИЛИ "skip"
- ЗАПРЕЩЕНО создавать новые названия!
- Список наших вакансий находится выше в разделе "НАШИ ВАКАНСИИ ДЛЯ УНИФИКАЦИИ"

НАШИ ГРЕЙДЫ (используй ТОЛЬКО эти названия):
{our_grades}

- Если внешняя вакансия НЕ соответствует нашим, используй "skip"
- Сопоставляй по смыслу и технологиям:
  * Java/Backend разработчики → "Backend Engineer (Java)" (если Java в стеке)
  * React/Frontend разработчики → "Frontend Engineer (React)" (если React в стеке)
  * QA/тестировщики → "QA Engineer"
  * DevOps/SRE/инфраструктура → "DevOps Engineer"
  * Менеджеры проектов → "Project Manager"
  * Системные администраторы → "System Administrator"
  * UI/UX дизайнеры → "UX/UI Designer"
  * Поддержка/сервис → "Support Engineer (Service Manager/Sport Analyst)"
- ВСЕ ОСТАЛЬНОЕ → "skip"

ВАЖНО: Если vacancy_name = "skip", то:
- salary_from и salary_to должны быть null
- skip_reason должен содержать причину пропуска
- Примеры причин:
  * "Не соответствует стек технологий (Node.js вместо Java)"
  * "Не IT вакансия"
  * "Нет подходящей вакансии в нашем списке"
  * "Технологии не соответствуют требованиям"

ПРАВИЛА ОБРАБОТКИ ЗАРПЛАТЫ:
- Если зарплата указана как {'from': 5000, 'to': 5400, 'currency': 'EUR', 'gross': True}, используй from=5000, to=5400
- Если зарплата указана как {'from': 3000, 'currency': 'USD', 'gross': False}, используй from=3000, to=3000 (или рассчитай диапазон)
- Если зарплата None или пустая, рассчитай рекомендуемый диапазон для данной позиции и грейда

ПРАВИЛА КОНВЕРТАЦИИ ВАЛЮТ:
- Если зарплата указана в BYN: умножь на курс BYN к USD
- Если зарплата указана в PLN: умножь на курс PLN к USD  
- Если зарплата указана в EUR: умножь на курс EUR к USD (примерно 1.1)
- Если зарплата указана в других валютах: используй ближайший курс или укажи в notes
- Всегда указывай исходную валюту в notes при конвертации

Отвечай ТОЛЬКО в формате JSON, без дополнительных комментариев.""",
        help_text=_("Промпт для анализа данных о зарплатах через ИИ")
    )
    
    # Источники данных о вакансиях (JSON поле для множественного выбора)
    data_sources = models.JSONField(
        _("Источники данных о вакансиях"),
        default=list,
        help_text=_("Список активных источников данных о вакансиях")
    )
    
    # Максимальное количество задач для обработки в день
    max_daily_tasks = models.PositiveIntegerField(
        _("Максимальное количество задач в день"),
        default=100,  # 1 задача в минуту (60 минут * 1 задача)
        help_text=_("Максимальное количество задач для обработки в день")
    )
    
    # Поля для сохранения вакансий (JSON поле для множественного выбора)
    vacancy_fields = models.JSONField(
        _("Поля для сохранения вакансий"),
        default=list,
        help_text=_("Список полей для сохранения информации о вакансиях")
    )
    
    # Настройки для hh.ru
    hh_channel_active = models.BooleanField(
        _("Канал hh.ru активен"),
        default=True,
        help_text=_("Включить/отключить сбор вакансий с hh.ru")
    )
    
    max_daily_hh_tasks = models.IntegerField(
        _("Максимум задач hh.ru в сутки"),
        default=100,
        help_text=_("Лимит обработки вакансий с hh.ru за день")
    )
    
    hh_ai_prompt = models.TextField(
        _("AI промпт для hh.ru"),
        default="",
        help_text=_("Специальный промпт для анализа вакансий с hh.ru")
    )
    
    # Временные метки
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    
    class Meta:
        verbose_name = _("Настройки бенчмарков")
        verbose_name_plural = _("Настройки бенчмарков")
    
    def __str__(self):
        return "Настройки бенчмарков"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для обеспечения единственности записи"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Запрещаем удаление настроек"""
        pass
    
    @classmethod
    def load(cls):
        """Загружает настройки, создавая их при необходимости"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    @property
    def data_sources_display(self):
        """Возвращает отформатированный список источников данных"""
        if not self.data_sources:
            return "Не выбрано"
        
        source_names = []
        for source in self.data_sources:
            for choice in DataSource.choices:
                if choice[0] == source:
                    source_names.append(str(choice[1]))
                    break
        
        return ", ".join(source_names)
    
    @property
    def vacancy_fields_display(self):
        """Возвращает отформатированный список полей вакансий"""
        if not self.vacancy_fields:
            return "Только обязательные поля"
        
        field_names = []
        for field in self.vacancy_fields:
            for choice in VacancyField.choices:
                if choice[0] == field:
                    field_names.append(str(choice[1]))
                    break
        
        return ", ".join(field_names)
    
    def get_available_data_sources(self):
        """Возвращает список доступных источников данных"""
        return DataSource.choices
    
    def get_available_vacancy_fields(self):
        """Возвращает список доступных полей вакансий"""
        return VacancyField.choices
    
    def get_required_vacancy_fields(self):
        """Возвращает список обязательных полей вакансий"""
        return [
            ('vacancy', 'Вакансия'),
            ('date_added', 'Дата добавления'),
            ('available_grades', 'Доступные грейды'),
            ('salary_range', 'Вилка от-до'),
            ('location', 'Локация'),
        ]
    
    def get_optional_vacancy_fields(self):
        """Возвращает список дополнительных полей вакансий"""
        return [
            ('work_format', 'Формат работы'),
            ('compensation', 'Компенсации'),
            ('benefits', 'Бенефиты'),
            ('development', 'Развитие/обучение'),
            ('technologies', 'Технологии'),
            ('domain', 'Домен'),
        ]
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что налоговая ставка в разумных пределах
        if self.belarus_tax_rate < 0 or self.belarus_tax_rate > 50:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'belarus_tax_rate': _('Налоговая ставка должна быть от 0 до 50%')
            })
        
        # Проверяем, что период расчета в разумных пределах
        if self.average_calculation_period_days < 1 or self.average_calculation_period_days > 365:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'average_calculation_period_days': _('Период расчета должен быть от 1 до 365 дней')
            })
        
        # Проверяем, что максимальное количество задач в разумных пределах
        if self.max_daily_tasks < 1 or self.max_daily_tasks > 10000:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'max_daily_tasks': _('Максимальное количество задач должно быть от 1 до 10000')
            })


# Сигналы для автоматического пересчета зарплатных вилок при обновлении курсов валют
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CurrencyRate)
def recalculate_salary_ranges_on_currency_update(sender, instance, created, **kwargs):
    """
    Автоматически пересчитывает зарплатные вилки при обновлении курсов валют
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - sender: CurrencyRate модель
    - instance: обновленный объект CurrencyRate
    - created: флаг создания нового объекта
    - **kwargs: дополнительные параметры
    
    ИСТОЧНИКИ ДАННЫЕ:
    - CurrencyRate: обновленный курс валюты
    - SalaryRange: все зарплатные вилки в системе
    
    ОБРАБОТКА:
    - Проверяет, что курс был обновлен (не создан)
    - Получает все активные зарплатные вилки
    - Пересчитывает зарплаты в других валютах
    - Сохраняет обновленные вилки
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Обновленные SalaryRange объекты в базе данных
    
    СВЯЗИ:
    - Использует: SalaryRange._calculate_other_currencies()
    - Передает: обновленные зарплатные вилки
    - Может вызываться из: CurrencyRate.save()
    """
    # Пересчитываем только при обновлении существующего курса, не при создании
    if not created:
        try:
            from django.apps import apps
            
            logger.info(f"🔄 Пересчитываем зарплатные вилки после обновления курса {instance.code}")
            
            # Получаем модель SalaryRange из finance приложения
            SalaryRange = apps.get_model('finance', 'SalaryRange')
            
            # Получаем все активные зарплатные вилки
            salary_ranges = SalaryRange.objects.filter(is_active=True)
            updated_count = 0
            
            for salary_range in salary_ranges:
                try:
                    # Пересчитываем зарплаты в других валютах используя SalaryService
                    from logic.finance.salary_service import SalaryService
                    min_byn, max_byn = SalaryService.calculate_byn_amounts(salary_range.salary_min_usd, salary_range.salary_max_usd)
                    min_pln, max_pln = SalaryService.calculate_pln_amounts(salary_range.salary_min_usd, salary_range.salary_max_usd)
                    min_eur, max_eur = SalaryService.calculate_eur_amounts(salary_range.salary_min_usd, salary_range.salary_max_usd)
                    
                    salary_range.salary_min_byn = min_byn
                    salary_range.salary_max_byn = max_byn
                    salary_range.salary_min_pln = min_pln
                    salary_range.salary_max_pln = max_pln
                    salary_range.salary_min_eur = min_eur
                    salary_range.salary_max_eur = max_eur
                    
                    salary_range.save(update_fields=[
                        'salary_min_byn', 'salary_max_byn',
                        'salary_min_pln', 'salary_max_pln', 
                        'salary_min_eur', 'salary_max_eur',
                        'updated_at'
                    ])
                    updated_count += 1
                except Exception as e:
                    logger.error(f"❌ Ошибка при пересчете вилки {salary_range}: {e}")
                    continue
            
            logger.info(f"✅ Пересчитано {updated_count} зарплатных вилок после обновления курса {instance.code}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при пересчете зарплатных вилок: {e}")
