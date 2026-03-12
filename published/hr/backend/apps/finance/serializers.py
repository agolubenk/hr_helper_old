from rest_framework import serializers
from decimal import Decimal
from .models import Grade, CurrencyRate, PLNTax, SalaryRange, Benchmark, BenchmarkSettings, Domain


class GradeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для грейдов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название грейда (обязательно)
    
    ИСТОЧНИКИ ДАННЫХ:
    - Grade модель из apps.finance.models
    
    ОБРАБОТКА:
    - Сериализация полей id и name
    - id автоматически генерируется, только для чтения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями id и name
    
    СВЯЗИ:
    - Использует: Grade модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Finance API viewsets
    """
    
    class Meta:
        model = Grade
        fields = ['id', 'name']
        read_only_fields = ['id']




class CurrencyRateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для курсов валют
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - code: код валюты (USD, PLN и т.д.)
    - rate: курс валюты
    - scale: масштаб валюты
    
    ИСТОЧНИКИ ДАННЫХ:
    - CurrencyRate модель из apps.finance.models
    
    ОБРАБОТКА:
    - Сериализация полей курса валют
    - Вычисляемые поля: status_info, display_rate
    - fetched_at автоматически устанавливается
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями курса валют и статусом
    
    СВЯЗИ:
    - Использует: CurrencyRate модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Finance API viewsets
    """
    status_info = serializers.ReadOnlyField()
    display_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = CurrencyRate
        fields = ['id', 'code', 'rate', 'scale', 'fetched_at', 'status_info', 'display_rate']
        read_only_fields = ['id', 'fetched_at', 'status_info', 'display_rate']


class PLNTaxSerializer(serializers.ModelSerializer):
    """Сериализатор для налогов PLN"""
    rate_decimal = serializers.ReadOnlyField()
    
    class Meta:
        model = PLNTax
        fields = ['id', 'name', 'rate', 'rate_decimal', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'rate_decimal']


class SalaryRangeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - vacancy: ID вакансии
    - grade: ID грейда
    - salary_min_usd, salary_max_usd: зарплатные вилки в USD
    - is_active: активность вилки
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange модель из apps.finance.models
    - Связанные модели: Grade, Vacancy
    
    ОБРАБОТКА:
    - Сериализация зарплатных вилок в разных валютах
    - Вычисляемые поля: grade_name, vacancy_name, salary_range_*
    - Валидация: min_salary <= max_salary
    - Автоматический расчет BYN и PLN на основе курсов
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с зарплатными вилками во всех валютах
    
    СВЯЗИ:
    - Использует: SalaryRange, Grade, Vacancy модели
    - Передает данные в: DRF API responses
    - Может вызываться из: Finance API viewsets
    """
    grade_name = serializers.CharField(source='grade.name', read_only=True)
    vacancy_name = serializers.CharField(source='vacancy.name', read_only=True)
    salary_range_usd = serializers.ReadOnlyField()
    salary_range_byn = serializers.ReadOnlyField()
    salary_range_pln = serializers.ReadOnlyField()
    salary_range_eur = serializers.ReadOnlyField()
    
    class Meta:
        model = SalaryRange
        fields = [
            'id', 'vacancy', 'vacancy_name', 'grade', 'grade_name',
            'salary_min_usd', 'salary_max_usd', 'salary_min_byn', 'salary_max_byn',
            'salary_min_pln', 'salary_max_pln', 'salary_min_eur', 'salary_max_eur', 'is_active',
            'salary_range_usd', 'salary_range_byn', 'salary_range_pln', 'salary_range_eur',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'salary_min_byn', 'salary_max_byn', 'salary_min_pln', 'salary_max_pln', 'salary_min_eur', 'salary_max_eur', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Валидация зарплатной вилки"""
        if attrs.get('salary_min_usd') and attrs.get('salary_max_usd'):
            if attrs['salary_min_usd'] > attrs['salary_max_usd']:
                raise serializers.ValidationError("Минимальная зарплата не может быть больше максимальной")
        return attrs


class BenchmarkSerializer(serializers.ModelSerializer):
    """Сериализатор для бенчмарков"""
    vacancy_name = serializers.CharField(source='vacancy.name', read_only=True)
    grade_name = serializers.CharField(source='grade.name', read_only=True)
    domain_display = serializers.CharField(source='get_domain_display', read_only=True)
    domain_description = serializers.SerializerMethodField()
    salary_display = serializers.SerializerMethodField()
    type_icon = serializers.ReadOnlyField()
    type_color = serializers.ReadOnlyField()
    
    class Meta:
        model = Benchmark
        fields = [
            'id', 'type', 'vacancy', 'vacancy_name', 'grade', 'grade_name',
            'salary_from', 'salary_to', 'salary_display', 'location',
            'work_format', 'compensation', 'benefits', 'development',
                'technologies', 'domain', 'domain_display', 'domain_description', 'hh_vacancy_id', 'notes', 'is_active',
            'type_icon', 'type_color', 'date_added', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'date_added', 'created_at', 'updated_at', 'salary_display', 'type_icon', 'type_color', 'domain_display', 'domain_description']
    
    def get_salary_display(self, obj):
        """Возвращает отформатированное отображение зарплаты"""
        return obj.get_salary_display()
    
    def get_domain_description(self, obj):
        """Возвращает описание домена для тултипа"""
        return obj.get_domain_description()
    
    def validate(self, attrs):
        """Валидация бенчмарка"""
        salary_from = attrs.get('salary_from')
        salary_to = attrs.get('salary_to')
        
        if salary_from and salary_from <= 0:
            raise serializers.ValidationError("Зарплата 'от' должна быть положительной")
        
        if salary_to and salary_to <= 0:
            raise serializers.ValidationError("Зарплата 'до' должна быть положительной")
        
        if salary_from and salary_to and salary_to <= salary_from:
            raise serializers.ValidationError("Зарплата 'до' должна быть больше зарплаты 'от'")
        
        return attrs


class BenchmarkSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек бенчмарков"""
    data_sources_display = serializers.ReadOnlyField()
    vacancy_fields_display = serializers.ReadOnlyField()
    
    class Meta:
        model = BenchmarkSettings
        fields = [
            'id', 'average_calculation_period_days', 'belarus_tax_rate',
            'ai_analysis_prompt', 'data_sources', 'data_sources_display',
            'max_daily_tasks', 'vacancy_fields', 'vacancy_fields_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'data_sources_display', 'vacancy_fields_display']
    
    def validate_belarus_tax_rate(self, value):
        """Валидация налоговой ставки"""
        if value < 0 or value > 50:
            raise serializers.ValidationError("Налоговая ставка должна быть от 0 до 50%")
        return value
    
    def validate_average_calculation_period_days(self, value):
        """Валидация периода расчета"""
        if value < 1 or value > 365:
            raise serializers.ValidationError("Период расчета должен быть от 1 до 365 дней")
        return value
    
    def validate_max_daily_tasks(self, value):
        """Валидация максимального количества задач"""
        if value < 1 or value > 10000:
            raise serializers.ValidationError("Максимальное количество задач должно быть от 1 до 10000")
        return value


class SalaryCalculationSerializer(serializers.Serializer):
    """Сериализатор для расчета зарплат"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    from_currency = serializers.ChoiceField(choices=['USD', 'BYN', 'PLN'])
    to_currency = serializers.ChoiceField(choices=['USD', 'BYN', 'PLN'])
    include_taxes = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Валидация валют"""
        if attrs['from_currency'] == attrs['to_currency']:
            raise serializers.ValidationError("Валюты должны отличаться")
        return attrs


class TaxCalculationSerializer(serializers.Serializer):
    """Сериализатор для расчета налогов PLN"""
    gross_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    def validate_gross_amount(self, value):
        """Валидация суммы"""
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной")
        return value
