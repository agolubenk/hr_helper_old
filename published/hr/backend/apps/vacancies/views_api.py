import json
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Min, Max
from decimal import Decimal
from apps.finance.models import (
    Grade, CurrencyRate, PLNTax, SalaryRange, Benchmark, BenchmarkSettings, Domain
)
from apps.finance.serializers import (
    GradeSerializer, CurrencyRateSerializer, PLNTaxSerializer,
    SalaryRangeSerializer, BenchmarkSerializer, BenchmarkSettingsSerializer,
    SalaryCalculationSerializer, TaxCalculationSerializer
)

# Импорты из logic
from logic.base.api_views import BaseAPIViewSet, FinanceAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler


class GradeViewSet(FinanceAPIViewSet):
    """
    ViewSet для управления грейдами
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Grade.objects: активные грейды компании из CompanySettings
    - GradeSerializer: сериализатор для грейдов
    
    ОБРАБОТКА:
    - Наследование от FinanceAPIViewSet
    - Управление грейдами (создание, чтение, обновление, удаление)
    - Поиск и сортировка по названию
    - Использует только активные грейды компании
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными грейдов
    
    СВЯЗИ:
    - Использует: FinanceAPIViewSet, GradeSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    def get_queryset(self):
        from apps.company_settings.utils import get_active_grades_queryset
        return get_active_grades_queryset().order_by('name')
    
    queryset = Grade.objects.all()  # Fallback, но get_queryset() переопределен
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """
        Статистика по грейдам
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫХ:
        - Grade.objects: все грейды из базы данных
        - Vacancy.objects: вакансии связанные с грейдами
        - SalaryRange.objects: зарплатные вилки
        - Benchmark.objects: бенчмарки
        
        ОБРАБОТКА:
        - Подсчет общего количества грейдов
        - Подсчет количества вакансий, зарплатных вилок и бенчмарков для каждого грейда
        - Формирование статистики
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response со статистикой по грейдам
        
        СВЯЗИ:
        - Использует: Grade, Vacancy, SalaryRange, Benchmark модели
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        from apps.company_settings.utils import get_active_grades_queryset
        active_grades = get_active_grades_queryset()
        total_grades = active_grades.count()
        
        # Статистика по вакансиям - только для активных грейдов
        grades_with_vacancies = active_grades.annotate(
            vacancies_count=Count('vacancies', distinct=True),
            salary_ranges_count=Count('finance_salary_ranges', distinct=True),
            benchmarks_count=Count('benchmarks', distinct=True)
        )
        
        return Response({
            'total_grades': total_grades,
            'grades_stats': [
                {
                    'id': grade.id,
                    'name': grade.name,
                    'vacancies_count': grade.vacancies_count,
                    'salary_ranges_count': grade.salary_ranges_count,
                    'benchmarks_count': grade.benchmarks_count
                }
                for grade in grades_with_vacancies
            ]
        })


class CurrencyRateViewSet(FinanceAPIViewSet):
    """
    ViewSet для управления курсами валют
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - CurrencyRate.objects: курсы валют из базы данных
    - CurrencyRateSerializer: сериализатор для курсов валют
    
    ОБРАБОТКА:
    - Наследование от FinanceAPIViewSet
    - Управление курсами валют (создание, чтение, обновление, удаление)
    - Поиск по коду валюты
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными курсов валют
    
    СВЯЗИ:
    - Использует: FinanceAPIViewSet, CurrencyRateSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    queryset = CurrencyRate.objects.all()
    serializer_class = CurrencyRateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['code']
    ordering_fields = ['code', 'fetched_at']
    ordering = ['-fetched_at']
    
    @action(detail=False, methods=['post'], url_path='update-rates')
    def update_rates(self, request):
        """Обновление курсов валют"""
        try:
            # ПЕРЕХОДНЫЙ ВАРИАНТ - ОСТАВЛЯЕМ ОБА ИМПОРТА
            from .logic.currency_service import CurrencyService  # Старый (deprecated)
            from logic.base.currency_service import currency_service  # Новый
            
            # Временно используем старый метод, но с предупреждением
            import warnings
            warnings.warn(
                "CurrencyService.update_currency_rates() is deprecated. "
                "Use logic.base.currency_service instead.",
                DeprecationWarning,
                stacklevel=2
            )
            CurrencyService.update_currency_rates()
            return Response(
                UnifiedResponseHandler.success_response(
                    message="Курсы валют успешно обновлены"
                )
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        """Получение последних курсов валют"""
        rates = CurrencyRate.objects.all().order_by('-fetched_at')
        serializer = CurrencyRateSerializer(rates, many=True)
        return Response(serializer.data)


class PLNTaxViewSet(FinanceAPIViewSet):
    """ViewSet для управления налогами PLN"""
    queryset = PLNTax.objects.all()
    serializer_class = PLNTaxSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'rate', 'created_at']
    ordering = ['name']
    
    @action(detail=False, methods=['post'], url_path='calculate-gross')
    def calculate_gross(self, request):
        """Расчет gross суммы из net суммы"""
        serializer = TaxCalculationSerializer(data=request.data)
        if serializer.is_valid():
            net_amount = serializer.validated_data['gross_amount']
            # gross_amount = TaxService.calculate_gross_from_net(net_amount, "PLN")  # УДАЛЕНО - логика перенесена
            
            return Response({
                'net_amount': float(net_amount),
                'gross_amount': float(net_amount),  # Временно возвращаем net_amount
                'breakdown': {}  # УДАЛЕНО - логика перенесена
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='calculate-net')
    def calculate_net(self, request):
        """Расчет net суммы из gross суммы"""
        serializer = TaxCalculationSerializer(data=request.data)
        if serializer.is_valid():
            gross_amount = serializer.validated_data['gross_amount']
            # net_amount = TaxService.calculate_net_from_gross(gross_amount, "PLN")  # УДАЛЕНО - логика перенесена
            
            return Response({
                'gross_amount': float(gross_amount),
                'net_amount': float(gross_amount),  # Временно возвращаем gross_amount
                'breakdown': {}  # УДАЛЕНО - логика перенесена
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SalaryRangeViewSet(FinanceAPIViewSet):
    """
    ViewSet для управления зарплатными вилками
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange.objects: зарплатные вилки из базы данных
    - SalaryRangeSerializer: сериализатор для зарплатных вилок
    - Vacancy.objects, Grade.objects: связанные модели
    
    ОБРАБОТКА:
    - Наследование от FinanceAPIViewSet
    - Управление зарплатными вилками (создание, чтение, обновление, удаление)
    - Фильтрация по вакансии, грейду, активности
    - Поиск и сортировка
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными зарплатных вилок
    
    СВЯЗИ:
    - Использует: FinanceAPIViewSet, SalaryRangeSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    queryset = SalaryRange.objects.all()
    serializer_class = SalaryRangeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['vacancy', 'grade', 'is_active']
    search_fields = ['vacancy__name', 'grade__name']
    ordering_fields = ['salary_min_usd', 'salary_max_usd', 'created_at']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['post'], url_path='update-currency-amounts')
    def update_currency_amounts(self, request):
        """Обновление сумм в других валютах"""
        try:
            SalaryRange.update_all_currency_amounts()
            return Response({'message': 'Суммы в валютах успешно обновлены'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по зарплатным вилкам"""
        total_ranges = SalaryRange.objects.count()
        active_ranges = SalaryRange.objects.filter(is_active=True).count()
        
        # Статистика по грейдам
        grade_stats = SalaryRange.objects.values('grade__name').annotate(
            count=Count('id'),
            avg_min=Avg('salary_min_usd'),
            avg_max=Avg('salary_max_usd')
        )
        
        return Response({
            'total_ranges': total_ranges,
            'active_ranges': active_ranges,
            'grade_stats': list(grade_stats)
        })

    @action(detail=False, methods=['get'], url_path='export-json')
    def export_json(self, request):
        """Экспорт всех зарплатных вилок в JSON."""
        from .export_import import export_salary_ranges_json
        data = export_salary_ranges_json()
        return Response(data)

    @action(detail=False, methods=['post'], url_path='import-json')
    def import_json(self, request):
        """Импорт зарплатных вилок из JSON (тело запроса или файл)."""
        from .export_import import import_salary_ranges_json

        if request.FILES.get('file'):
            try:
                raw = request.FILES['file'].read().decode('utf-8')
                data = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                return Response({'error': f'Неверный JSON: {e}'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            data = request.data if isinstance(request.data, dict) else None
            if not data:
                return Response(
                    {'error': 'Отправьте JSON в теле запроса или загрузите файл (ключ "file")'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        created, updated, errors = import_salary_ranges_json(data)
        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
        }, status=status.HTTP_200_OK)


class BenchmarkViewSet(FinanceAPIViewSet):
    """
    ViewSet для управления бенчмарками
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    - BenchmarkSerializer: сериализатор для бенчмарков
    - Vacancy.objects, Grade.objects: связанные модели
    
    ОБРАБОТКА:
    - Наследование от FinanceAPIViewSet
    - Управление бенчмарками (создание, чтение, обновление, удаление)
    - Фильтрация по вакансии, грейду, статусу
    - Поиск и сортировка
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными бенчмарков
    
    СВЯЗИ:
    - Использует: FinanceAPIViewSet, BenchmarkSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    queryset = Benchmark.objects.all()
    serializer_class = BenchmarkSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['type', 'vacancy', 'grade', 'domain', 'is_active']
    search_fields = ['vacancy__name', 'grade__name', 'location', 'domain']
    ordering_fields = ['salary_from', 'salary_to', 'date_added', 'created_at']
    ordering = ['-date_added']
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по бенчмаркам"""
        total_benchmarks = Benchmark.objects.count()
        active_benchmarks = Benchmark.objects.filter(is_active=True).count()
        
        # Статистика по типам
        type_stats = Benchmark.objects.values('type').annotate(
            count=Count('id'),
            avg_salary_from=Avg('salary_from'),
            avg_salary_to=Avg('salary_to')
        )
        
        # Статистика по грейдам
        grade_stats = Benchmark.objects.values('grade__name').annotate(
            count=Count('id'),
            avg_salary_from=Avg('salary_from'),
            avg_salary_to=Avg('salary_to')
        )
        
        return Response({
            'total_benchmarks': total_benchmarks,
            'active_benchmarks': active_benchmarks,
            'type_stats': list(type_stats),
            'grade_stats': list(grade_stats)
        })


class BenchmarkSettingsViewSet(FinanceAPIViewSet):
    """ViewSet для настроек бенчмарков"""
    queryset = BenchmarkSettings.objects.all()
    serializer_class = BenchmarkSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Получение единственного объекта настроек"""
        return BenchmarkSettings.load()
    
    def list(self, request, *args, **kwargs):
        """Переопределяем list для возврата единственного объекта"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Создание настроек (обновление существующих)"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SalaryCalculationViewSet(viewsets.ViewSet):
    """ViewSet для расчета зарплат"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='convert')
    def convert(self, request):
        """Конвертация суммы между валютами"""
        serializer = SalaryCalculationSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            from_currency = serializer.validated_data['from_currency']
            to_currency = serializer.validated_data['to_currency']
            include_taxes = serializer.validated_data['include_taxes']
            
            try:
                # Получаем курсы валют
                from_rate = CurrencyRate.objects.get(code=from_currency)
                to_rate = CurrencyRate.objects.get(code=to_currency)
                
                # Конвертируем через BYN
                byn_amount = amount * from_rate.rate
                converted_amount = byn_amount / to_rate.rate
                
                result = {
                    'original_amount': float(amount),
                    'original_currency': from_currency,
                    'converted_amount': float(converted_amount),
                    'converted_currency': to_currency,
                    'byn_amount': float(byn_amount)
                }
                
                # Если нужно включить налоги для PLN
                if include_taxes and to_currency == 'PLN':
                    active_taxes = PLNTax.objects.filter(is_active=True)
                    if active_taxes.exists():
                        total_tax_rate = sum(tax.rate_decimal for tax in active_taxes)
                        gross_amount = converted_amount / (1 - total_tax_rate)
                        result['gross_amount'] = float(gross_amount)
                        result['tax_breakdown'] = {}  # УДАЛЕНО - логика перенесена
                
                return Response(result)
                
            except CurrencyRate.DoesNotExist:
                return Response({'error': 'Курс валют не найден'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Реэкспорт для config.api_urls (роут vacancies/vacancies)
from logic.candidate.vacancy_api import VacancyViewSet
