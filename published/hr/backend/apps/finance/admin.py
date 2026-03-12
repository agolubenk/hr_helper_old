from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from .models import Grade, CurrencyRate, PLNTax, SalaryRange, Benchmark, BenchmarkSettings, DataSource, VacancyField, Domain, HHVacancyTemp


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("code", "display_rate", "scale", "fetched_at", "status_display", "last_update_info")
    readonly_fields = ("fetched_at", "last_update_info", "status_display")
    list_filter = ("code", "fetched_at")
    search_fields = ("code",)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-rates/', self.update_rates, name='finance_currencyrate_update_rates'),
        ]
        return custom_urls + urls
    
    def update_rates(self, request):
        """Обновляет курсы валют из НБРБ"""
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Захватываем вывод команды
            out = StringIO()
            call_command('update_nbrb_rates', stdout=out, stderr=out)
            
            # Показываем результат
            output = out.getvalue()
            if "🎉 Обновление курсов завершено успешно!" in output:
                messages.success(request, "Курсы валют успешно обновлены из НБРБ!")
            else:
                messages.warning(request, f"Курсы обновлены с предупреждениями: {output}")
                
        except Exception as e:
            messages.error(request, f"Ошибка при обновлении курсов: {e}")
        
        return HttpResponseRedirect("../")
    
    def status_display(self, obj):
        """Отображает статус курса с цветовой индикацией"""
        status = obj.status_info
        
        if status == "Базовая валюта":
            color = "#28a745"  # зеленый
        elif status == "Сегодня":
            color = "#17a2b8"  # синий
        elif status == "Вчера":
            color = "#ffc107"  # желтый
        elif "дн. назад" in status:
            color = "#fd7e14"  # оранжевый
        else:
            color = "#dc3545"  # красный
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    status_display.short_description = "Статус"
    
    def display_rate(self, obj):
        """Отображает курс с форматированием"""
        return obj.display_rate
    display_rate.short_description = "Курс"
    
    def last_update_info(self, obj):
        """Показывает информацию о последнем обновлении с кнопкой обновления"""
        if obj.fetched_at:
            return format_html(
                '<div style="display: flex; align-items: center; gap: 10px;">'
                '<span>{}</span>'
                '<a href="update-rates/" class="button" style="background: #79aec8; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">'
                '🔄 Обновить курсы'
                '</a>'
                '</div>',
                obj.fetched_at.strftime("%d.%m.%Y %H:%M:%S")
            )
        return "Не обновлялось"
    
    last_update_info.short_description = "Последнее обновление"
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем кнопку обновления в список"""
        extra_context = extra_context or {}
        extra_context['show_update_button'] = True
        return super().changelist_view(request, extra_context)


@admin.register(PLNTax)
class PLNTaxAdmin(admin.ModelAdmin):
    list_display = ("name", "rate_display", "is_active", "total_tax_rate_display", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at", "total_tax_rate_display")
    fieldsets = (
        (None, {
            'fields': ('name', 'rate', 'is_active')
        }),
        ('Информация', {
            'fields': ('created_at', 'updated_at', 'total_tax_rate_display'),
            'classes': ('collapse',)
        }),
    )
    
    def rate_display(self, obj):
        """Отображает ставку с символом %"""
        return f"{obj.rate}%"
    rate_display.short_description = "Ставка"
    
    def total_tax_rate_display(self, obj):
        """Показывает общую налоговую ставку всех активных налогов"""
        active_taxes = PLNTax.objects.filter(is_active=True)
        total_rate = sum(tax.rate for tax in active_taxes)
        if total_rate > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{}%</span>',
                total_rate
            )
        return "0%"
    total_tax_rate_display.short_description = "Общая ставка"
    
    def save_model(self, request, obj, form, change):
        """Валидация при сохранении"""
        try:
            obj.clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            messages.error(request, f"Ошибка валидации: {e}")
            return
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем информацию о расчетах в контекст"""
        extra_context = extra_context or {}
        
        # Пример расчета для демонстрации
        from decimal import Decimal
        example_gross = Decimal('10000.00')
        breakdown = PLNTax.get_tax_breakdown(example_gross)
        
        extra_context['example_calculation'] = {
            'gross_amount': example_gross,
            'breakdown': breakdown
        }
        
        return super().changelist_view(request, extra_context)


@admin.register(SalaryRange)
class SalaryRangeAdmin(admin.ModelAdmin):
    list_display = ("vacancy", "grade", "salary_range_usd", "salary_range_byn", "salary_range_pln", "salary_range_eur", "is_active", "created_at")
    list_filter = ("is_active", "grade", "vacancy", "created_at")
    search_fields = ("vacancy__name", "grade__name")
    readonly_fields = ("created_at", "updated_at", "salary_range_usd", "salary_range_byn", "salary_range_pln", "salary_range_eur")
    fieldsets = (
        (None, {
            'fields': ('vacancy', 'grade', 'is_active')
        }),
        ('Зарплата в USD', {
            'fields': ('salary_min_usd', 'salary_max_usd')
        }),
        ('Зарплата в BYN (автоматически)', {
            'fields': ('salary_min_byn', 'salary_max_byn'),
            'classes': ('collapse',)
        }),
        ('Зарплата в PLN (автоматически)', {
            'fields': ('salary_min_pln', 'salary_max_pln'),
            'classes': ('collapse',)
        }),
        ('Зарплата в EUR (автоматически)', {
            'fields': ('salary_min_eur', 'salary_max_eur'),
            'classes': ('collapse',)
        }),
        ('Информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def salary_range_usd(self, obj):
        """Отображает диапазон зарплаты в USD"""
        return obj.salary_range_usd
    salary_range_usd.short_description = "Зарплата (USD)"
    
    def salary_range_byn(self, obj):
        """Отображает диапазон зарплаты в BYN"""
        return obj.salary_range_byn
    salary_range_byn.short_description = "Зарплата (BYN)"
    
    def salary_range_pln(self, obj):
        """Отображает диапазон зарплаты в PLN"""
        return obj.salary_range_pln
    salary_range_pln.short_description = "Зарплата (PLN)"
    
    def salary_range_eur(self, obj):
        """Отображает диапазон зарплаты в EUR"""
        return obj.salary_range_eur
    salary_range_eur.short_description = "Зарплата (EUR)"
    
    def save_model(self, request, obj, form, change):
        """Валидация при сохранении"""
        try:
            obj.clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            messages.error(request, f"Ошибка валидации: {e}")
            return
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем кнопку обновления курсов валют"""
        extra_context = extra_context or {}
        extra_context['show_update_currency_button'] = True
        return super().changelist_view(request, extra_context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-currency-amounts/', self.update_currency_amounts, name='finance_salaryrange_update_currency'),
        ]
        return custom_urls + urls
    
    def update_currency_amounts(self, request):
        """Обновляет курсы валют для всех зарплатных вилок"""
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Захватываем вывод команды
            out = StringIO()
            call_command('update_salary_currency_amounts', stdout=out, stderr=out)
            
            # Показываем результат
            output = out.getvalue()
            if "успешно обновлены" in output.lower():
                messages.success(request, "Курсы валют для всех зарплатных вилок успешно обновлены!")
            else:
                messages.warning(request, f"Обновление завершено с предупреждениями: {output}")
                
        except Exception as e:
            messages.error(request, f"Ошибка при обновлении курсов: {e}")
        
        return HttpResponseRedirect("../")


@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ("type_display", "vacancy", "grade", "salary_display", "location", "work_format", "domain", "hh_vacancy_id", "is_active", "date_added")
    list_filter = ("type", "is_active", "grade", "vacancy", "work_format", "domain", "date_added")
    search_fields = ("vacancy__name", "grade__name", "location", "notes", "work_format", "technologies", "domain", "hh_vacancy_id")
    readonly_fields = ("created_at", "updated_at", "date_added")
    fieldsets = (
        (None, {
            'fields': ('type', 'vacancy', 'grade', 'salary_from', 'salary_to', 'location', 'is_active')
        }),
        ('Дополнительная информация', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Дополнительные поля вакансии', {
            'fields': ('work_format', 'compensation', 'benefits', 'development', 'technologies', 'domain', 'hh_vacancy_id'),
            'classes': ('collapse',),
            'description': 'Дополнительные поля, которые отображаются в зависимости от настроек бенчмарков'
        }),
        ('Системная информация', {
            'fields': ('date_added', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def type_display(self, obj):
        """Отображает тип с иконкой и цветом"""
        if obj.type == 'candidate':
            color = '#28a745'  # Зеленый
            icon = 'fas fa-user'
        else:
            color = '#007bff'  # Синий
            icon = 'fas fa-briefcase'
        
        return format_html(
            '<span style="color: {};"><i class="{}"></i> {}</span>',
            color, icon, obj.get_type_display()
        )
    type_display.short_description = "Тип"
    
    def salary_display(self, obj):
        """Отображает отформатированную зарплату"""
        return obj.get_salary_display()
    salary_display.short_description = "Зарплата"
    
    def save_model(self, request, obj, form, change):
        """Валидация при сохранении"""
        try:
            obj.clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            messages.error(request, f"Ошибка валидации: {e}")
            return
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику в контекст"""
        extra_context = extra_context or {}
        
        # Статистика по типам
        candidate_count = Benchmark.objects.filter(type='candidate', is_active=True).count()
        vacancy_count = Benchmark.objects.filter(type='vacancy', is_active=True).count()
        total_count = Benchmark.objects.filter(is_active=True).count()
        
        extra_context['benchmark_stats'] = {
            'candidate_count': candidate_count,
            'vacancy_count': vacancy_count,
            'total_count': total_count
        }
        
        return super().changelist_view(request, extra_context)


@admin.register(HHVacancyTemp)
class HHVacancyTempAdmin(admin.ModelAdmin):
    list_display = ("hh_id", "processed", "created_at", "company_name", "vacancy_title")
    list_filter = ("processed", "created_at")
    search_fields = ("hh_id", "raw_data")
    readonly_fields = ("hh_id", "raw_data", "created_at")
    fieldsets = (
        (None, {
            'fields': ('hh_id', 'processed')
        }),
        ('Данные вакансии', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
        ('Информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def company_name(self, obj):
        """Извлекает название компании из raw_data"""
        try:
            return obj.raw_data.get('employer', {}).get('name', 'Не указано')
        except:
            return 'Не указано'
    company_name.short_description = "Компания"
    
    def vacancy_title(self, obj):
        """Извлекает название вакансии из raw_data"""
        try:
            return obj.raw_data.get('name', 'Не указано')[:50]
        except:
            return 'Не указано'
    vacancy_title.short_description = "Вакансия"


@admin.register(BenchmarkSettings)
class BenchmarkSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "average_calculation_period_days",
        "belarus_tax_rate",
        "max_daily_tasks",
        "data_sources_display",
        "vacancy_fields_display",
        "hh_channel_active",
        "max_daily_hh_tasks",
        "updated_at",
    )
    fieldsets = (
        (None, {
            'fields': (
                'average_calculation_period_days',
                'belarus_tax_rate',
                'max_daily_tasks',
                'ai_analysis_prompt'
            )
        }),
        ('Источники данных', {
            'fields': ('data_sources',),
            'description': 'Выберите источники, из которых будут собираться данные о вакансиях.',
        }),
        ('Поля для сохранения вакансий', {
            'fields': ('vacancy_fields',),
            'description': 'Выберите дополнительные поля, которые будут сохраняться для вакансий.',
        }),
                ('Настройки hh.ru', {
                    'fields': ('hh_channel_active', 'max_daily_hh_tasks', 'hh_ai_prompt'),
                    'description': 'Настройки для интеграции с hh.ru',
                }),
    )
    
    # Переопределяем методы для синглтон модели
    def has_add_permission(self, request):
        return not BenchmarkSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    def changelist_view(self, request, extra_context=None):
        # Перенаправляем на страницу редактирования единственной записи
        obj = self.model.load()
        return HttpResponseRedirect(f'./{obj.pk}/change/')
    
    def get_form(self, request, obj=None, **kwargs):
        from django.forms import CheckboxSelectMultiple, MultipleChoiceField
        
        form = super().get_form(request, obj, **kwargs)
        
        # Заменяем JSONField на MultipleChoiceField для источников данных
        form.base_fields['data_sources'] = MultipleChoiceField(
            choices=DataSource.choices,
            widget=CheckboxSelectMultiple(),
            required=False,
            help_text="Выберите источники данных о вакансиях"
        )
        
        # Заменяем JSONField на MultipleChoiceField для полей вакансий
        form.base_fields['vacancy_fields'] = MultipleChoiceField(
            choices=VacancyField.choices,
            widget=CheckboxSelectMultiple(),
            required=False,
            help_text="Выберите поля для сохранения вакансий"
        )
        
        # Инициализируем значения из объекта
        if obj:
            form.base_fields['data_sources'].initial = obj.data_sources or []
            form.base_fields['vacancy_fields'].initial = obj.vacancy_fields or []
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Валидация при сохранении"""
        try:
            # Обрабатываем данные из MultipleChoiceField
            if 'data_sources' in form.cleaned_data:
                obj.data_sources = form.cleaned_data['data_sources']
            
            if 'vacancy_fields' in form.cleaned_data:
                # Добавляем обязательные поля
                required_fields = ['vacancy', 'date_added', 'available_grades', 'salary_range', 'location']
                all_fields = list(set(form.cleaned_data['vacancy_fields'] + required_fields))
                obj.vacancy_fields = all_fields
            
            obj.clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            messages.error(request, f"Ошибка валидации: {e}")
            return
