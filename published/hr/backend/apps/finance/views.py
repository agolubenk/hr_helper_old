from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import models
from django.db.models import Count, Avg, Min, Max, Case, When
from io import StringIO
import json
from .models import Grade, CurrencyRate, PLNTax, SalaryRange, Benchmark, BenchmarkType, BenchmarkSettings, DataSource, VacancyField, HHVacancyTemp
from apps.vacancies.models import Vacancy
# from logic.finance.tax_service import TaxService  # УДАЛЕНО - логика перенесена в views_modules

# Импорты из новых модулей
from .views_modules.dashboard_views import benchmarks_dashboard, dashboard, pln_taxes_dashboard, hh_analysis_dashboard, ai_analysis_dashboard
from .views_modules.currency_views import update_currency_rates
from .views_modules.grade_views import add_grade, delete_grade
from .views_modules.tax_views import add_pln_tax, update_pln_tax, delete_pln_tax, calculate_pln_taxes
from .views_modules.salary_views import (
    salary_ranges_list, salary_range_detail, salary_range_create, 
    salary_range_update, salary_range_delete, update_salary_currency_amounts
)
from .views_modules.benchmark_views import (
    benchmark_list, benchmark_detail, benchmark_create, 
    benchmark_update, benchmark_delete, benchmark_ai_analysis
)
from .views_modules.analysis_views import (
    finance_dashboard_analysis, salary_trends_analysis, 
    benchmark_comparison_analysis, custom_finance_analysis
)

# Импорты из logic
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.view_adapters import finance_view_adapter, legacy_view_adapter


@login_required
def benchmarks_dashboard(request):
    """
    Отдельный дашборд для бенчмарков с аналитикой и статистикой
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.GET: grade_filter, vacancy_filter, location_filter (списки ID для фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: все бенчмарки из базы данных
    - Grade.objects: грейды для фильтрации
    - Vacancy.objects: вакансии для фильтрации
    
    ОБРАБОТКА:
    - Фильтрация бенчмарков по грейдам, вакансиям, локациям
    - Расчет статистики (средние, минимальные, максимальные зарплаты)
    - Группировка по грейдам и типам
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с отфильтрованными данными и статистикой
    - render: HTML страница 'finance/benchmarks_dashboard.html'
    
    СВЯЗИ:
    - Использует: logic.base.response_handler.UnifiedResponseHandler
    - Передает данные в: finance/benchmarks_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    from decimal import Decimal
    from django.db.models import Count, Avg, Min, Max, Case, When
    from django.db import models
    
    # Получаем фильтры из GET параметров
    grade_filter = request.GET.getlist('grades')
    vacancy_filter = request.GET.getlist('vacancies')
    location_filter = request.GET.getlist('locations')
    
    # Базовый queryset с фильтрами
    base_queryset = Benchmark.objects.filter(is_active=True)
    
    if grade_filter:
        base_queryset = base_queryset.filter(grade_id__in=grade_filter)
    if vacancy_filter:
        base_queryset = base_queryset.filter(vacancy_id__in=vacancy_filter)
    if location_filter:
        base_queryset = base_queryset.filter(location__in=location_filter)
    
    # Основная статистика
    total_benchmarks = base_queryset.count()
    candidate_benchmarks = base_queryset.filter(type='candidate')
    vacancy_benchmarks = base_queryset.filter(type='vacancy')
    
    candidate_count = candidate_benchmarks.count()
    vacancy_count = vacancy_benchmarks.count()
    
    # Статистика по суммам
    if total_benchmarks > 0:
        avg_amount = base_queryset.aggregate(avg=Avg('salary_from'))['avg'] or Decimal('0')
        min_amount = base_queryset.aggregate(min=Min('salary_from'))['min'] or Decimal('0')
        # Для максимальной зарплаты используем salary_to, если есть, иначе salary_from
        from django.db.models import Case, When, Value, IntegerField
        from django.db import models
        max_amount = base_queryset.aggregate(
            max=Max(Case(
                When(salary_to__isnull=False, then='salary_to'),
                default='salary_from',
                output_field=models.DecimalField()
            ))
        )['max'] or Decimal('0')
        
        avg_candidate = candidate_benchmarks.aggregate(avg=Avg('salary_from'))['avg'] or Decimal('0')
        avg_vacancy = vacancy_benchmarks.aggregate(avg=Avg('salary_from'))['avg'] or Decimal('0')
    else:
        avg_amount = min_amount = max_amount = avg_candidate = avg_vacancy = Decimal('0')
    
    # Статистика по вакансиям
    vacancy_stats = base_queryset.values('vacancy__name').annotate(
        count=Count('id'),
        avg_amount=Avg('salary_from')
    ).order_by('-count')[:10]
    
    # Статистика по грейдам
    grade_stats = base_queryset.values('grade__name').annotate(
        count=Count('id'),
        avg_amount=Avg('salary_from')
    ).order_by('-count')[:10]
    
    # Статистика по локациям
    location_stats = base_queryset.values('location').annotate(
        count=Count('id'),
        avg_amount=Avg('salary_from')
    ).order_by('-count')[:10]
    
    # Последние бенчмарки
    recent_benchmarks = base_queryset.select_related('vacancy', 'grade').order_by('-date_added')[:6]
    
    # Топ вакансии по количеству бенчмарков
    top_vacancies = base_queryset.values(
        'vacancy__name', 'vacancy__id'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Топ грейды по количеству бенчмарков
    top_grades = base_queryset.values(
        'grade__name', 'grade__id'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Данные для круговых графиков
    # Распределение по грейдам (для кругового графика)
    grade_distribution = base_queryset.values('grade__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Распределение по вакансиям (для кругового графика)
    vacancy_distribution = base_queryset.values('vacancy__name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]  # Топ 10 вакансий
    
    # Распределение по локациям (для кругового графика)
    location_distribution = base_queryset.values('location').annotate(
        count=Count('id')
    ).order_by('-count')[:10]  # Топ 10 локаций
    
    # Данные для линейного графика медианной зарплаты
    # Группируем по месяцам для последних 12 месяцев
    from django.db.models.functions import TruncMonth
    
    # Получаем данные за последние 12 месяцев
    from datetime import datetime, timedelta
    twelve_months_ago = datetime.now() - timedelta(days=365)
    
    # Средняя зарплата кандидатов по месяцам (используем Avg вместо Median)
    candidate_avg_by_month = base_queryset.filter(
        type='candidate',
        date_added__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('date_added')
    ).values('month').annotate(
        avg_salary=Avg('salary_from')
    ).order_by('month')
    
    # Средняя зарплата вакансий по месяцам (используем Avg вместо Median)
    vacancy_avg_by_month = base_queryset.filter(
        type='vacancy',
        date_added__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('date_added')
    ).values('month').annotate(
        avg_salary=Avg('salary_from')
    ).order_by('month')
    
    # Данные для графика-свечек по вакансиям
    # Группируем по месяцам для каждой вакансии отдельно
    vacancy_candlestick_data = base_queryset.filter(
        type='vacancy',
        date_added__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('date_added')
    ).values('month', 'vacancy__name', 'vacancy__id').annotate(
        min_salary=Min('salary_from'),
        median_min_salary=Avg('salary_from'),  # Используем Avg как приближение к медиане
        median_max_salary=Avg(Case(
            When(salary_to__isnull=False, then='salary_to'),
            default='salary_from',
            output_field=models.DecimalField()
        )),
        max_salary=Max(Case(
            When(salary_to__isnull=False, then='salary_to'),
            default='salary_from',
            output_field=models.DecimalField()
        )),
        count=Count('id')
    ).order_by('month', 'vacancy__name')
    
    # Данные для фильтров - показываем все грейды, которые есть в бенчмарках
    # (бенчмарки связаны с внешними данными и рынком, поэтому используем все грейды)
    available_grades = Benchmark.objects.filter(
        is_active=True
    ).values_list('grade__id', 'grade__name').distinct().order_by('grade__name')
    available_vacancies = Benchmark.objects.filter(is_active=True).values_list('vacancy__id', 'vacancy__name').distinct().order_by('vacancy__name')
    available_locations = Benchmark.objects.filter(is_active=True).values_list('location', flat=True).distinct().order_by('location')
    
    context = {
        'total_benchmarks': total_benchmarks,
        'candidate_count': candidate_count,
        'vacancy_count': vacancy_count,
        'avg_amount': avg_amount,
        'min_amount': min_amount,
        'max_amount': max_amount,
        'avg_candidate': avg_candidate,
        'avg_vacancy': avg_vacancy,
        'vacancy_stats': vacancy_stats,
        'grade_stats': grade_stats,
        'location_stats': location_stats,
        'recent_benchmarks': recent_benchmarks,
        'top_vacancies': top_vacancies,
        'top_grades': top_grades,
        
        # Данные для графиков (сериализованные в JSON)
        'grade_distribution': json.dumps([{'grade__name': item['grade__name'], 'count': item['count']} for item in grade_distribution]),
        'vacancy_distribution': json.dumps([{'vacancy__name': item['vacancy__name'], 'count': item['count']} for item in vacancy_distribution]),
        'location_distribution': json.dumps([{'location': item['location'], 'count': item['count']} for item in location_distribution]),
        'type_comparison_data': [
            {'type': 'Кандидаты', 'count': candidate_count, 'avg_salary': float(avg_candidate) if avg_candidate else 0},
            {'type': 'Вакансии', 'count': vacancy_count, 'avg_salary': float(avg_vacancy) if avg_vacancy else 0}
        ],
        'candidate_avg_by_month': [{'month': item['month'].strftime('%Y-%m-%d') if item['month'] else None, 'avg_salary': float(item['avg_salary']) if item['avg_salary'] else 0} for item in candidate_avg_by_month],
        'vacancy_avg_by_month': [{'month': item['month'].strftime('%Y-%m-%d') if item['month'] else None, 'avg_salary': float(item['avg_salary']) if item['avg_salary'] else 0} for item in vacancy_avg_by_month],
        'vacancy_candlestick_data': [{
            'month': item['month'].strftime('%Y-%m-%d') if item['month'] else None,
            'vacancy__name': item['vacancy__name'],
            'vacancy__id': item['vacancy__id'],
            'min_salary': float(item['min_salary']) if item['min_salary'] else 0,
            'median_min_salary': float(item['median_min_salary']) if item['median_min_salary'] else 0,
            'median_max_salary': float(item['median_max_salary']) if item['median_max_salary'] else 0,
            'max_salary': float(item['max_salary']) if item['max_salary'] else 0,
            'count': item['count']
        } for item in vacancy_candlestick_data],
        
        # Данные для фильтров
        'available_grades': available_grades,
        'available_vacancies': available_vacancies,
        'available_locations': available_locations,
    }
    return render(request, 'finance/benchmarks_dashboard.html', context)


@login_required
def dashboard(request):
    """
    Дашборд с грейдами, курсами валют, зарплатными вилками и налогами PLN
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Grade.objects: все грейды из базы данных
    - CurrencyRate.objects: курсы валют USD, PLN
    - SalaryRange.objects: активные зарплатные вилки
    - PLNTax.objects: налоги PLN
    
    ОБРАБОТКА:
    - Получение всех грейдов, отсортированных по имени
    - Получение курсов валют USD и PLN
    - Получение активных зарплатных вилок с связанными данными
    - Получение налогов PLN
    - Расчет статистики (количество активных вилок)
    - Создание примера расчета налогов (временно статический)
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными для дашборда
    - render: HTML страница 'finance/dashboard.html'
    
    СВЯЗИ:
    - Использует: Grade, CurrencyRate, SalaryRange, PLNTax модели
    - Передает данные в: finance/dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    # Используем только активные грейды компании
    from apps.company_settings.utils import get_active_grades_queryset
    active_grades = get_active_grades_queryset()
    grades = active_grades.order_by('name')
    currency_rates = CurrencyRate.objects.all().order_by('code')
    pln_taxes = PLNTax.objects.filter(is_active=True).order_by('name')
    # Фильтруем вилки только по активным грейдам
    salary_ranges = SalaryRange.objects.select_related('vacancy', 'grade').filter(
        is_active=True,
        grade__in=active_grades
    ).order_by('grade__name', 'vacancy__name')
    
    # Статистика
    active_salary_ranges_count = salary_ranges.count()
    
    # Пример расчета налогов для демонстрации
    from logic.finance.tax_service import TaxService
    from decimal import Decimal
    
    try:
        example_net = Decimal('5000.00')
        example_gross = TaxService.calculate_gross_from_net(example_net, "PLN")
        example_breakdown = TaxService.get_tax_breakdown(example_gross, "PLN")
        
        example_calculation = {
            'net_amount': example_net,
            'gross_amount': example_gross,
            'breakdown': example_breakdown
        }
    except Exception as e:
        # Fallback если есть ошибка
        example_calculation = {
            'net_amount': Decimal('5000.00'),
            'gross_amount': Decimal('5000.00'),
            'breakdown': {
                'gross_amount': Decimal('5000.00'),
                'net_amount': Decimal('5000.00'),
                'total_tax_amount': Decimal('0'),
                'taxes': []
            }
        }
    
    context = {
        'grades': grades,
        'currency_rates': currency_rates,
        'pln_taxes': pln_taxes,
        'salary_ranges': salary_ranges,
        'active_salary_ranges_count': active_salary_ranges_count,
        'example_calculation': example_calculation
    }
    return render(request, 'finance/dashboard.html', context)


@login_required
def update_currency_rates(request):
    """
    Обновляет курсы валют из НБРБ используя UnifiedCurrencyService
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - UnifiedCurrencyService: сервис для работы с валютами
    - NBRB API: API Национального банка Беларуси
    
    ОБРАБОТКА:
    - Вызов метода update_currency_rates_in_db() из UnifiedCurrencyService
    - Обработка результата обновления
    - Установка соответствующих сообщений (success/warning/error)
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/warning/error: сообщения о результате
    - redirect: перенаправление на finance:dashboard
    
    СВЯЗИ:
    - Использует: UnifiedCurrencyService, NBRB API
    - Передает: HTTP redirect
    - Может вызываться из: finance/ URL patterns
    """
    try:
        # Импортируем сервис валют
        from logic.base.currency_service import currency_service
        
        # Используем существующую архитектуру - новый метод
        result = currency_service.update_currency_rates_in_db()
        updated_count = result.get('updated_count', 0)
        
        if updated_count > 0:
            messages.success(request, f'Курсы валют успешно обновлены из НБРБ ({updated_count} валют)')
        else:
            messages.warning(request, 'Не удалось обновить ни одного курса валют')
            
    except Exception as e:
        messages.error(request, f'Ошибка при обновлении курсов: {str(e)}')
    
    return redirect('finance:dashboard')


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_grade(request):
    """
    Добавляет новый грейд
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с полем name
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация имени грейда
    - Проверка существования грейда
    - Создание нового Grade объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: Grade.objects.create()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        grade_name = data.get('name', '').strip()
        
        if not grade_name:
            return JsonResponse({'success': False, 'message': 'Название грейда не может быть пустым'})
        
        # Проверяем, не существует ли уже такой грейд
        if Grade.objects.filter(name=grade_name).exists():
            return JsonResponse({'success': False, 'message': 'Грейд с таким названием уже существует'})
        
        # Создаем новый грейд
        grade = Grade.objects.create(name=grade_name)
        
        return JsonResponse({
            'success': True, 
            'message': 'Грейд успешно добавлен',
            'grade': {
                'id': grade.id,
                'name': grade.name
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при добавлении грейда: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_grade(request, grade_id):
    """
    Удаляет грейд
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - grade_id: ID грейда для удаления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр grade_id
    - Grade.objects, Benchmark.objects для проверки связей
    
    ОБРАБОТКА:
    - Получение грейда по ID
    - Проверка связей с бенчмарками
    - Удаление грейда если нет связей
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: Grade.objects, Benchmark.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        grade = get_object_or_404(Grade, id=grade_id)
        grade_name = grade.name
        
        # Проверяем, не используется ли грейд в других моделях
        # Здесь можно добавить проверки на связанные объекты
        
        grade.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Грейд "{grade_name}" успешно удален'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при удалении грейда: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_pln_tax(request):
    """
    Добавляет новый налог PLN
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с полями name, rate, description
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация полей налога
    - Проверка существования налога
    - Создание нового PLNTax объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: PLNTax.objects.create()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        rate = data.get('rate')
        is_active = data.get('is_active', True)
        
        if not name:
            return JsonResponse({'success': False, 'message': 'Название налога не может быть пустым'})
        
        if rate is None:
            return JsonResponse({'success': False, 'message': 'Налоговая ставка обязательна'})
        
        try:
            rate = float(rate)
            if rate < 0 or rate > 100:
                return JsonResponse({'success': False, 'message': 'Налоговая ставка должна быть от 0 до 100%'})
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Некорректное значение налоговой ставки'})
        
        # Создаем новый налог
        tax = PLNTax.objects.create(
            name=name,
            rate=rate,
            is_active=is_active
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Налог успешно добавлен',
            'tax': {
                'id': tax.id,
                'name': tax.name,
                'rate': float(tax.rate),
                'is_active': tax.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при добавлении налога: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["PUT"])
def update_pln_tax(request, tax_id):
    """
    Обновляет налог PLN
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - tax_id: ID налога для обновления
    - request.body: JSON с полями name, rate, description
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр tax_id
    - JSON данные из request.body
    
    ОБРАБОТКА:
    - Получение налога по ID
    - Парсинг JSON данных
    - Валидация полей
    - Обновление PLNTax объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: PLNTax.objects.get(), PLNTax.save()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        tax = get_object_or_404(PLNTax, id=tax_id)
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        rate = data.get('rate')
        is_active = data.get('is_active')
        
        if name:
            tax.name = name
        
        if rate is not None:
            try:
                rate = float(rate)
                if rate < 0 or rate > 100:
                    return JsonResponse({'success': False, 'message': 'Налоговая ставка должна быть от 0 до 100%'})
                tax.rate = rate
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Некорректное значение налоговой ставки'})
        
        if is_active is not None:
            tax.is_active = is_active
        
        tax.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Налог успешно обновлен',
            'tax': {
                'id': tax.id,
                'name': tax.name,
                'rate': float(tax.rate),
                'is_active': tax.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при обновлении налога: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_pln_tax(request, tax_id):
    """
    Удаляет налог PLN
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - tax_id: ID налога для удаления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр tax_id
    
    ОБРАБОТКА:
    - Получение налога по ID
    - Удаление PLNTax объекта
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: PLNTax.objects.get(), PLNTax.delete()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        tax = get_object_or_404(PLNTax, id=tax_id)
        tax_name = tax.name
        tax.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Налог "{tax_name}" успешно удален'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при удалении налога: {str(e)}'})


@login_required
@require_http_methods(["GET"])
def calculate_pln_taxes(request):
    """
    Рассчитывает налоги PLN для заданной суммы
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.GET: amount (сумма), type (gross/net)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - GET параметры amount и type
    - PLNTax.objects: активные налоги
    
    ОБРАБОТКА:
    - Получение параметров из GET запроса
    - Получение активных налогов
    - Расчет налогов для указанной суммы
    - Формирование результата расчета
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатами расчета налогов
    
    СВЯЗИ:
    - Использует: PLNTax.objects, расчеты налогов
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        amount = request.GET.get('amount')
        calculation_type = request.GET.get('type', 'gross')  # gross или net
        
        if not amount:
            return JsonResponse({'success': False, 'message': 'Сумма обязательна'})
        
        try:
            from decimal import Decimal
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Некорректное значение суммы'})
        
        if calculation_type == 'gross':
            # Рассчитываем net из gross
            from logic.finance.tax_service import TaxService
            breakdown = TaxService.get_tax_breakdown(amount, "PLN")
            result = {
                'gross_amount': float(breakdown['gross_amount']),
                'net_amount': float(breakdown['net_amount']),
                'total_tax_amount': float(breakdown['total_tax_amount']),
                'taxes': breakdown['taxes']
            }
        else:
            # Рассчитываем gross из net
            from logic.finance.tax_service import TaxService
            gross_amount = TaxService.calculate_gross_from_net(amount, "PLN")
            breakdown = TaxService.get_tax_breakdown(gross_amount, "PLN")
            result = {
                'gross_amount': float(breakdown['gross_amount']),
                'net_amount': float(breakdown['net_amount']),
                'total_tax_amount': float(breakdown['total_tax_amount']),
                'taxes': breakdown['taxes']
            }
        
        return JsonResponse({
            'success': True,
            'calculation': result
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при расчете: {str(e)}'})


@login_required
def pln_taxes_dashboard(request):
    """
    Дашборд для управления налогами PLN
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - PLNTax.objects: все налоги PLN
    
    ОБРАБОТКА:
    - Получение всех налогов PLN
    - Создание контекста для дашборда
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными налогов
    - render: HTML страница 'finance/pln_taxes_dashboard.html'
    
    СВЯЗИ:
    - Использует: PLNTax.objects
    - Передает данные в: finance/pln_taxes_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    pln_taxes = PLNTax.objects.all().order_by('name')
    active_taxes = PLNTax.objects.filter(is_active=True)
    inactive_taxes = PLNTax.objects.filter(is_active=False)
    
    # Пример расчета для демонстрации
    from logic.finance.tax_service import TaxService
    from decimal import Decimal
    
    try:
        example_net = Decimal('5000.00')
        example_gross = TaxService.calculate_gross_from_net(example_net, "PLN")
        example_breakdown = TaxService.get_tax_breakdown(example_gross, "PLN")
        
        example_calculation = {
            'net_amount': example_net,
            'gross_amount': example_gross,
            'breakdown': example_breakdown
        }
    except Exception as e:
        # Fallback если есть ошибка
        example_calculation = {
            'net_amount': Decimal('5000.00'),
            'gross_amount': Decimal('5000.00'),
            'breakdown': {
                'gross_amount': Decimal('5000.00'),
                'net_amount': Decimal('5000.00'),
                'total_tax_amount': Decimal('0'),
                'taxes': []
            }
        }
    
    context = {
        'pln_taxes': pln_taxes,
        'active_taxes_count': active_taxes.count(),
        'inactive_taxes_count': inactive_taxes.count(),
        'example_calculation': example_calculation
    }
    
    return render(request, 'finance/pln_taxes_dashboard.html', context)


# Views для зарплатных вилок

@login_required
def salary_ranges_list(request):
    """
    Список зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.GET: search, status_filter (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - SalaryRange.objects: все зарплатные вилки
    - SalaryRangeSearchForm: для валидации параметров поиска
    
    ОБРАБОТКА:
    - Получение параметров поиска из GET запроса
    - Применение фильтров по поиску и статусу
    - Пагинация результатов (10 вилок на страницу)
    - Подсчет статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с отфильтрованными вилками и пагинацией
    - render: HTML страница 'finance/salary_ranges_list.html'
    
    СВЯЗИ:
    - Использует: SalaryRange.objects, SalaryRangeSearchForm
    - Передает данные в: finance/salary_ranges_list.html
    - Может вызываться из: finance/ URL patterns
    """
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Получаем параметры поиска
    search_query = request.GET.get('search', '')
    vacancy_filter = request.GET.get('vacancy', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('is_active', '')
    
    # Базовый queryset
    salary_ranges = SalaryRange.objects.select_related('grade', 'vacancy').all()
    
    # Применяем фильтры
    if search_query:
        salary_ranges = salary_ranges.filter(
            Q(grade__name__icontains=search_query) |
            Q(vacancy__name__icontains=search_query)
        )
    
    if vacancy_filter:
        salary_ranges = salary_ranges.filter(vacancy_id=vacancy_filter)
    
    if grade_filter:
        salary_ranges = salary_ranges.filter(grade_id=grade_filter)
    
    if status_filter == 'true':
        salary_ranges = salary_ranges.filter(is_active=True)
    elif status_filter == 'false':
        salary_ranges = salary_ranges.filter(is_active=False)
    
    # Пагинация
    paginator = Paginator(salary_ranges, 10)  # 10 вилок на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем списки для фильтров
    from apps.vacancies.models import Vacancy
    from apps.company_settings.utils import get_active_grades_queryset
    vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    grades = get_active_grades_queryset().order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'vacancy_filter': vacancy_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'vacancies': vacancies,
        'grades': grades,
        'total_count': salary_ranges.count(),
        'active_count': salary_ranges.filter(is_active=True).count(),
        'inactive_count': salary_ranges.filter(is_active=False).count(),
    }
    
    response = render(request, 'finance/salary_ranges_list.html', context)
    
    # Добавляем заголовки для предотвращения кэширования
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response


@login_required
def salary_range_detail(request, pk):
    """
    Детальная информация о зарплатной вилке
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID зарплатной вилки
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - SalaryRange.objects: конкретная зарплатная вилка по ID
    
    ОБРАБОТКА:
    - Получение зарплатной вилки по ID (404 если не найдена)
    - Создание контекста для детального просмотра
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными зарплатной вилки
    - render: HTML страница 'finance/salary_range_detail.html'
    
    СВЯЗИ:
    - Использует: SalaryRange.objects.get(), get_object_or_404()
    - Передает данные в: finance/salary_range_detail.html
    - Может вызываться из: finance/ URL patterns
    """
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    
    context = {
        'salary_range': salary_range,
    }
    
    return render(request, 'finance/salary_range_detail.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def salary_range_create(request):
    """
    Создание новой зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с данными зарплатной вилки
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - Grade.objects, Vacancy.objects для валидации связей
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация связанных объектов
    - Создание нового SalaryRange объекта
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: SalaryRange.objects.create(), Grade.objects, Vacancy.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        vacancy_id = data.get('vacancy_id')
        grade_id = data.get('grade_id')
        salary_min_usd = data.get('salary_min_usd')
        salary_max_usd = data.get('salary_max_usd')
        is_active = data.get('is_active', True)
        
        # Валидация
        if not all([vacancy_id, grade_id, salary_min_usd, salary_max_usd]):
            return JsonResponse({'success': False, 'message': 'Все поля обязательны'})
        
        # Проверяем, что грейд является активным для компании
        from apps.company_settings.utils import get_active_grades_queryset
        active_grades = get_active_grades_queryset()
        if not active_grades.filter(id=grade_id).exists():
            return JsonResponse({'success': False, 'message': 'Выбранный грейд не является активным для компании'})
        
        try:
            salary_min_usd = float(salary_min_usd)
            salary_max_usd = float(salary_max_usd)
            
            if salary_min_usd > salary_max_usd:
                return JsonResponse({'success': False, 'message': 'Минимальная зарплата не может быть больше максимальной'})
                
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Некорректные значения зарплаты'})
        
        # Проверяем, не существует ли уже такая вилка
        if SalaryRange.objects.filter(vacancy_id=vacancy_id, grade_id=grade_id).exists():
            return JsonResponse({'success': False, 'message': 'Зарплатная вилка для этой вакансии и грейда уже существует'})
        
        # Создаем новую зарплатную вилку
        salary_range = SalaryRange.objects.create(
            vacancy_id=vacancy_id,
            grade_id=grade_id,
            salary_min_usd=salary_min_usd,
            salary_max_usd=salary_max_usd,
            is_active=is_active
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Зарплатная вилка успешно создана',
            'salary_range': {
                'id': salary_range.id,
                'vacancy_name': salary_range.vacancy.name,
                'grade_name': salary_range.grade.name,
                'salary_range_usd': salary_range.salary_range_usd,
                'is_active': salary_range.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при создании зарплатной вилки: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["PUT"])
def salary_range_update(request, pk):
    """
    Обновление зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID зарплатной вилки для обновления
    - request.body: JSON с обновленными данными
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    - JSON данные из request.body
    - Grade.objects, Vacancy.objects для валидации связей
    
    ОБРАБОТКА:
    - Получение зарплатной вилки по ID
    - Парсинг JSON данных
    - Валидация связанных объектов
    - Обновление SalaryRange объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: SalaryRange.objects.get(), Grade.objects, Vacancy.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        salary_range = get_object_or_404(SalaryRange, pk=pk)
        data = json.loads(request.body)
        
        salary_min_usd = data.get('salary_min_usd')
        salary_max_usd = data.get('salary_max_usd')
        grade_id = data.get('grade_id')
        is_active = data.get('is_active')
        
        # Если обновляется грейд, проверяем, что он является активным для компании
        if grade_id is not None and grade_id != salary_range.grade_id:
            from apps.company_settings.utils import get_active_grades_queryset
            active_grades = get_active_grades_queryset()
            if not active_grades.filter(id=grade_id).exists():
                return JsonResponse({'success': False, 'message': 'Выбранный грейд не является активным для компании'})
            salary_range.grade_id = grade_id
        
        if salary_min_usd is not None:
            try:
                salary_min_usd = float(salary_min_usd)
                salary_range.salary_min_usd = salary_min_usd
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Некорректное значение минимальной зарплаты'})
        
        if salary_max_usd is not None:
            try:
                salary_max_usd = float(salary_max_usd)
                salary_range.salary_max_usd = salary_max_usd
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Некорректное значение максимальной зарплаты'})
        
        if is_active is not None:
            salary_range.is_active = is_active
        
        # Валидация
        if salary_range.salary_min_usd and salary_range.salary_max_usd:
            if salary_range.salary_min_usd > salary_range.salary_max_usd:
                return JsonResponse({'success': False, 'message': 'Минимальная зарплата не может быть больше максимальной'})
        
        salary_range.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Зарплатная вилка успешно обновлена',
            'salary_range': {
                'id': salary_range.id,
                'vacancy_name': salary_range.vacancy.name,
                'grade_name': salary_range.grade.name,
                'salary_range_usd': salary_range.salary_range_usd,
                'is_active': salary_range.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при обновлении зарплатной вилки: {str(e)}'})


@login_required
def salary_range_edit(request, pk):
    """
    Страница редактирования зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID зарплатной вилки для редактирования
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    - SalaryRange, Vacancy, Grade модели
    
    ОБРАБОТКА:
    - Получение зарплатной вилки по ID
    - Получение списка вакансий и грейдов
    - Подготовка контекста для шаблона
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - HTML страница с формой редактирования
    
    СВЯЗИ:
    - Использует: SalaryRange, Vacancy, Grade модели
    - Передает: context в salary_range_edit.html
    - Может вызываться из: GET запросы
    """
    try:
        salary_range = get_object_or_404(SalaryRange, pk=pk)
        
        # Получаем списки для выпадающих меню
        from apps.company_settings.utils import get_active_grades_queryset
        vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
        grades = get_active_grades_queryset().order_by('name')
        
        context = {
            'salary_range': salary_range,
            'vacancies': vacancies,
            'grades': grades,
        }
        
        return render(request, 'finance/salary_range_edit.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке зарплатной вилки: {str(e)}')
        return redirect('finance:salary_ranges_list')


@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def salary_range_delete(request, pk):
    """
    Удаление зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID зарплатной вилки для удаления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    
    ОБРАБОТКА:
    - Получение зарплатной вилки по ID
    - Удаление SalaryRange объекта
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: SalaryRange.objects.get(), SalaryRange.delete()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        salary_range = get_object_or_404(SalaryRange, pk=pk)
        salary_range_name = f"{salary_range.vacancy.name} - {salary_range.grade.name}"
        salary_range.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Зарплатная вилка "{salary_range_name}" успешно удалена'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при удалении зарплатной вилки: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_salary_currency_amounts(request):
    """
    Обновляет суммы в других валютах для всех зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - SalaryRange.objects: все зарплатные вилки
    - CurrencyRate.objects: актуальные курсы валют
    
    ОБРАБОТКА:
    - Получение всех зарплатных вилок
    - Получение актуальных курсов валют
    - Пересчет сумм в разных валютах
    - Обновление записей в базе данных
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: SalaryRange.objects, CurrencyRate.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        SalaryRange.update_all_currency_amounts()
        return JsonResponse({
            'success': True, 
            'message': 'Курсы валют для всех зарплатных вилок успешно обновлены'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при обновлении курсов: {str(e)}'})


# Views для бенчмарков

@login_required
def benchmarks_list(request):
    """
    Список бенчмарков
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.GET: search, type_filter, grade_filter, location_filter (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Benchmark.objects: все бенчмарки
    - Grade.objects, Vacancy.objects для фильтрации
    
    ОБРАБОТКА:
    - Получение параметров фильтрации из GET запроса
    - Применение фильтров по поиску, типу, грейду, локации
    - Пагинация результатов (10 бенчмарков на страницу)
    - Подсчет статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с отфильтрованными бенчмарками и пагинацией
    - render: HTML страница 'finance/benchmarks_list.html'
    
    СВЯЗИ:
    - Использует: Benchmark.objects, Grade.objects, Vacancy.objects
    - Передает данные в: finance/benchmarks_list.html
    - Может вызываться из: finance/ URL patterns
    """
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Получаем параметры поиска и фильтрации
    search_query = request.GET.get('search', '')
    type_filter = request.GET.get('type', '')
    vacancy_filter = request.GET.get('vacancy', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('is_active', '')
    
    # Базовый queryset
    benchmarks = Benchmark.objects.select_related('grade', 'vacancy').all()
    
    # Применяем фильтры
    if search_query:
        benchmarks = benchmarks.filter(
            Q(vacancy__name__icontains=search_query) |
            Q(grade__name__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    if type_filter:
        benchmarks = benchmarks.filter(type=type_filter)
    
    if vacancy_filter:
        benchmarks = benchmarks.filter(vacancy_id=vacancy_filter)
    
    if grade_filter:
        benchmarks = benchmarks.filter(grade_id=grade_filter)
    
    if status_filter == 'true':
        benchmarks = benchmarks.filter(is_active=True)
    elif status_filter == 'false':
        benchmarks = benchmarks.filter(is_active=False)
    
    # Пагинация
    paginator = Paginator(benchmarks, 15)  # 15 бенчмарков на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем списки для фильтров
    from apps.vacancies.models import Vacancy
    from apps.company_settings.utils import get_active_grades_queryset
    vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    grades = get_active_grades_queryset().order_by('name')
    
    # Статистика
    candidate_count = Benchmark.objects.filter(type='candidate', is_active=True).count()
    vacancy_count = Benchmark.objects.filter(type='vacancy', is_active=True).count()
    total_count = Benchmark.objects.filter(is_active=True).count()
    
    # Получаем настройки бенчмарков для определения дополнительных полей
    from apps.finance.models import BenchmarkSettings
    settings = BenchmarkSettings.load()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'type_filter': type_filter,
        'vacancy_filter': vacancy_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'vacancies': vacancies,
        'grades': grades,
        'total_count': total_count,
        'candidate_count': candidate_count,
        'vacancy_count': vacancy_count,
        'benchmark_types': BenchmarkType.choices,
        'settings': settings,
        'enabled_fields': settings.vacancy_fields if settings.vacancy_fields else [],
    }
    
    return render(request, 'finance/benchmarks_list.html', context)


@login_required
def benchmark_detail(request, pk):
    """
    Детальная информация о бенчмарке
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Benchmark.objects: конкретный бенчмарк по ID
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID (404 если не найден)
    - Создание контекста для детального просмотра
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными бенчмарка
    - render: HTML страница 'finance/benchmark_detail.html'
    
    СВЯЗИ:
    - Использует: Benchmark.objects.get(), get_object_or_404()
    - Передает данные в: finance/benchmark_detail.html
    - Может вызываться из: finance/ URL patterns
    """
    benchmark = get_object_or_404(Benchmark, pk=pk)
    
    context = {
        'benchmark': benchmark,
    }
    
    return render(request, 'finance/benchmark_detail.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def benchmark_create(request):
    """
    Создание нового бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с данными бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - Grade.objects, Vacancy.objects для валидации связей
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация связанных объектов
    - Создание нового Benchmark объекта
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: Benchmark.objects.create(), Grade.objects, Vacancy.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        type_value = data.get('type')
        vacancy_id = data.get('vacancy_id')
        grade_id = data.get('grade_id')
        salary_from = data.get('salary_from')
        salary_to = data.get('salary_to')
        location = data.get('location', '').strip()
        notes = data.get('notes', '').strip()
        is_active = data.get('is_active', True)
        
        # Валидация
        if not all([type_value, vacancy_id, grade_id, salary_from, location]):
            return JsonResponse({'success': False, 'message': 'Все обязательные поля должны быть заполнены'})
        
        # Проверяем тип
        if type_value not in ['candidate', 'vacancy']:
            return JsonResponse({'success': False, 'message': 'Неверный тип бенчмарка'})
        
        try:
            salary_from = float(salary_from)
            if salary_from <= 0:
                return JsonResponse({'success': False, 'message': 'Зарплата "от" должна быть положительной'})
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Некорректное значение зарплаты "от"'})
        
        # Обработка salary_to (опционально для вакансий)
        if salary_to:
            try:
                salary_to = float(salary_to)
                if salary_to <= 0:
                    return JsonResponse({'success': False, 'message': 'Зарплата "до" должна быть положительной'})
                if salary_to <= salary_from:
                    return JsonResponse({'success': False, 'message': 'Зарплата "до" должна быть больше зарплаты "от"'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Некорректное значение зарплаты "до"'})
        else:
            salary_to = None
        
        # Создаем новый бенчмарк
        benchmark = Benchmark.objects.create(
            type=type_value,
            vacancy_id=vacancy_id,
            grade_id=grade_id,
            salary_from=salary_from,
            salary_to=salary_to,
            location=location,
            notes=notes,
            is_active=is_active,
            # Дополнительные поля
            work_format=data.get('work_format', '').strip() or None,
            compensation=data.get('compensation', '').strip() or None,
            benefits=data.get('benefits', '').strip() or None,
            development=data.get('development', '').strip() or None,
            technologies=data.get('technologies', '').strip() or None,
            domain=data.get('domain', '').strip() or None,
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Бенчмарк успешно создан',
            'benchmark': {
                'id': benchmark.id,
                'type': benchmark.get_type_display(),
                'vacancy_name': benchmark.vacancy.name,
                'grade_name': benchmark.grade.name,
                'salary': benchmark.get_salary_display(),
                'location': benchmark.location,
                'is_active': benchmark.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при создании бенчмарка: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["PUT"])
def benchmark_update(request, pk):
    """
    Обновление бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка для обновления
    - request.body: JSON с обновленными данными
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    - JSON данные из request.body
    - Grade.objects, Vacancy.objects для валидации связей
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Парсинг JSON данных
    - Валидация связанных объектов
    - Обновление Benchmark объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: Benchmark.objects.get(), Grade.objects, Vacancy.objects
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        benchmark = get_object_or_404(Benchmark, pk=pk)
        data = json.loads(request.body)
        
        type_value = data.get('type')
        vacancy_id = data.get('vacancy_id')
        grade_id = data.get('grade_id')
        salary_from = data.get('salary_from')
        salary_to = data.get('salary_to')
        location = data.get('location')
        notes = data.get('notes')
        is_active = data.get('is_active')
        
        if type_value is not None:
            if type_value not in ['candidate', 'vacancy']:
                return JsonResponse({'success': False, 'message': 'Неверный тип бенчмарка'})
            benchmark.type = type_value
        
        if vacancy_id is not None:
            benchmark.vacancy_id = vacancy_id
        
        if grade_id is not None:
            benchmark.grade_id = grade_id
        
        if salary_from is not None:
            try:
                salary_from = float(salary_from)
                if salary_from <= 0:
                    return JsonResponse({'success': False, 'message': 'Зарплата "от" должна быть положительной'})
                benchmark.salary_from = salary_from
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Некорректное значение зарплаты "от"'})
        
        if salary_to is not None:
            if salary_to == '':
                benchmark.salary_to = None
            else:
                try:
                    salary_to = float(salary_to)
                    if salary_to <= 0:
                        return JsonResponse({'success': False, 'message': 'Зарплата "до" должна быть положительной'})
                    if salary_to <= benchmark.salary_from:
                        return JsonResponse({'success': False, 'message': 'Зарплата "до" должна быть больше зарплаты "от"'})
                    benchmark.salary_to = salary_to
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'message': 'Некорректное значение зарплаты "до"'})
        
        if location is not None:
            benchmark.location = location.strip()
        
        if notes is not None:
            benchmark.notes = notes.strip()
        
        if is_active is not None:
            benchmark.is_active = is_active
        
        benchmark.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Бенчмарк успешно обновлен',
            'benchmark': {
                'id': benchmark.id,
                'type': benchmark.get_type_display(),
                'vacancy_name': benchmark.vacancy.name,
                'grade_name': benchmark.grade.name,
                'salary': benchmark.get_salary_display(),
                'location': benchmark.location,
                'is_active': benchmark.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при обновлении бенчмарка: {str(e)}'})


@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def benchmark_delete(request, pk):
    """
    Удаление бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка для удаления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Удаление Benchmark объекта
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: Benchmark.objects.get(), Benchmark.delete()
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        benchmark = get_object_or_404(Benchmark, pk=pk)
        benchmark_name = f"{benchmark.get_type_display()} - {benchmark.vacancy.name} ({benchmark.grade.name})"
        benchmark.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Бенчмарк "{benchmark_name}" успешно удален'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при удалении бенчмарка: {str(e)}'})


@login_required
def benchmark_edit(request, pk):
    """
    Страница редактирования бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка для редактирования
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр pk
    - Benchmark.objects, Grade.objects, Vacancy.objects
    
    ОБРАБОТКА:
    - Обработка GET запроса (отображение формы редактирования)
    - Обработка POST запроса (сохранение изменений)
    - Валидация данных формы
    - Обновление Benchmark объекта
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с формой и связанными объектами
    - render: HTML страница 'finance/benchmark_edit.html'
    - redirect: на детальный просмотр при успешном сохранении
    
    СВЯЗИ:
    - Использует: BenchmarkForm, Grade.objects, Vacancy.objects
    - Передает данные в: finance/benchmark_edit.html
    - Может вызываться из: finance/ URL patterns
    """
    benchmark = get_object_or_404(Benchmark, pk=pk)
    
    if request.method == 'POST':
        try:
            # Обновляем данные бенчмарка
            benchmark.type = request.POST.get('type')
            benchmark.vacancy_id = request.POST.get('vacancy_id')
            benchmark.grade_id = request.POST.get('grade_id')
            benchmark.salary_from = request.POST.get('salary_from')
            benchmark.salary_to = request.POST.get('salary_to') or None
            benchmark.location = request.POST.get('location')
            benchmark.notes = request.POST.get('notes', '')
            benchmark.is_active = request.POST.get('is_active') == 'on'
            
            # Дополнительные поля
            benchmark.work_format = request.POST.get('work_format') or None
            benchmark.compensation = request.POST.get('compensation') or None
            benchmark.benefits = request.POST.get('benefits') or None
            benchmark.development = request.POST.get('development') or None
            benchmark.technologies = request.POST.get('technologies') or None
            benchmark.domain = request.POST.get('domain') or None
            
            # Валидация
            if not benchmark.type or benchmark.type not in ['candidate', 'vacancy']:
                messages.error(request, 'Неверный тип бенчмарка')
            elif not benchmark.vacancy_id:
                messages.error(request, 'Выберите вакансию')
            elif not benchmark.grade_id:
                messages.error(request, 'Выберите грейд')
            elif not benchmark.salary_from or float(benchmark.salary_from) <= 0:
                messages.error(request, 'Зарплата "от" должна быть положительной')
            elif benchmark.salary_to and float(benchmark.salary_to) <= 0:
                messages.error(request, 'Зарплата "до" должна быть положительной')
            elif benchmark.salary_to and float(benchmark.salary_to) <= float(benchmark.salary_from):
                messages.error(request, 'Зарплата "до" должна быть больше зарплаты "от"')
            elif not benchmark.location:
                messages.error(request, 'Укажите локацию')
            else:
                benchmark.save()
                messages.success(request, 'Бенчмарк успешно обновлен')
                return redirect('finance:benchmark_detail', pk=benchmark.pk)
                
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении бенчмарка: {str(e)}')
    
    # Получаем списки для форм
    # Для бенчмарок используем ВСЕ грейды, т.к. они связаны с внешними данными и рынком
    from apps.vacancies.models import Vacancy
    from apps.finance.models import Grade
    vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    grades = Grade.objects.all().order_by('name')
    
    context = {
        'benchmark': benchmark,
        'vacancies': vacancies,
        'grades': grades,
        'benchmark_types': BenchmarkType.choices,
    }
    
    return render(request, 'finance/benchmark_edit.html', context)


@login_required
def benchmark_settings(request):
    """
    Страница настроек бенчмарков
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: данные формы настроек
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - POST данные формы
    - BenchmarkSettings.load(): текущие настройки
    
    ОБРАБОТКА:
    - Обработка GET запроса (отображение формы настроек)
    - Обработка POST запроса (сохранение настроек)
    - Валидация данных формы
    - Обновление настроек бенчмарков
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с формой и текущими настройками
    - render: HTML страница 'finance/benchmark_settings.html'
    - redirect: на дашборд при успешном сохранении
    
    СВЯЗИ:
    - Использует: BenchmarkSettingsForm, BenchmarkSettings
    - Передает данные в: finance/benchmark_settings.html
    - Может вызываться из: finance/ URL patterns
    """
    settings_obj = BenchmarkSettings.load()
    
    if request.method == 'POST':
        try:
            # Обновляем настройки
            settings_obj.average_calculation_period_days = int(request.POST.get('average_calculation_period_days', 90))
            settings_obj.belarus_tax_rate = float(request.POST.get('belarus_tax_rate', 13.0))
            settings_obj.ai_analysis_prompt = request.POST.get('ai_analysis_prompt', '')
            settings_obj.max_daily_tasks = int(request.POST.get('max_daily_tasks', 100))
            
            # Обрабатываем множественный выбор источников данных
            data_sources = request.POST.getlist('data_sources')
            settings_obj.data_sources = data_sources
            
            # Обрабатываем множественный выбор полей вакансий
            vacancy_fields = request.POST.getlist('vacancy_fields')
            # Добавляем обязательные поля
            required_fields = ['vacancy', 'date_added', 'available_grades', 'salary_range', 'location']
            all_fields = list(set(vacancy_fields + required_fields))
            settings_obj.vacancy_fields = all_fields
            
            # Валидация
            settings_obj.clean()
            settings_obj.save()
            messages.success(request, 'Настройки бенчмарков успешно сохранены!')
            return redirect('finance:benchmark_settings')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении настроек: {str(e)}')
            print(f"Ошибка в benchmark_settings: {e}")  # Отладочная информация
    
    context = {
        'settings': settings_obj,
        'data_sources_choices': DataSource.choices,
        'vacancy_fields_choices': VacancyField.choices,
        'required_vacancy_fields': settings_obj.get_required_vacancy_fields(),
        'optional_vacancy_fields': settings_obj.get_optional_vacancy_fields(),
    }
    
    return render(request, 'finance/benchmark_settings.html', context)


# Views для анализа hh.ru и ИИ

@login_required
def hh_analysis_dashboard(request):
    """
    Дашборд для анализа hh.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Benchmark.objects: бенчмарки из hh.ru
    - HHVacancyTemp.objects: временные вакансии
    - BenchmarkSettings.load(): настройки анализа
    
    ОБРАБОТКА:
    - Получение статистики по бенчмаркам
    - Получение статистики по временным вакансиям
    - Получение настроек анализа
    - Создание контекста для дашборда
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными анализа
    - render: HTML страница 'finance/hh_analysis_dashboard.html'
    
    СВЯЗИ:
    - Использует: Benchmark.objects, HHVacancyTemp.objects, BenchmarkSettings
    - Передает данные в: finance/hh_analysis_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    from apps.vacancies.models import Vacancy
    from apps.finance.models import Grade
    
    # Получаем активные вакансии и ВСЕ грейды (для анализа внешних данных и рынка)
    vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    grades = Grade.objects.all().order_by('name')
    
    # Статистика по бенчмаркам
    total_benchmarks = Benchmark.objects.filter(is_active=True).count()
    hh_benchmarks = Benchmark.objects.filter(
        is_active=True,
        notes__icontains='hh.ru'
    ).count()
    
    # Последние бенчмарки
    recent_benchmarks = Benchmark.objects.filter(
        is_active=True
    ).select_related('vacancy', 'grade').order_by('-date_added')[:10]
    
    context = {
        'vacancies': vacancies,
        'grades': grades,
        'total_benchmarks': total_benchmarks,
        'hh_benchmarks': hh_benchmarks,
        'recent_benchmarks': recent_benchmarks,
    }
    
    return render(request, 'finance/hh_analysis_dashboard.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def start_hh_analysis(request):
    """
    Запуск анализа hh.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с параметрами анализа
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - Celery задачи для асинхронного анализа
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация параметров анализа
    - Запуск Celery задачи анализа
    - Возврат ID задачи для отслеживания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с ID задачи и статусом
    
    СВЯЗИ:
    - Использует: Celery задачи, analyze_hh_vacancies_automatic
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        vacancy_id = data.get('vacancy_id')
        grade_id = data.get('grade_id')
        search_query = data.get('search_query', '').strip()
        country = data.get('country', 'belarus')
        area = data.get('area', None)
        
        if not vacancy_id or not grade_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указаны вакансия или грейд'
            })
        
        # Проверяем существование объектов
        # Для анализа hh.ru используем ВСЕ грейды (это анализ внешних данных и рынка)
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
            grade = Grade.objects.get(id=grade_id)
        except (Vacancy.DoesNotExist, Grade.DoesNotExist):
            return JsonResponse({
                'success': False,
                'message': 'Вакансия или грейд не найдены'
            })
        
        # Запускаем Celery задачу
        from .tasks import analyze_hh_vacancies
        task = analyze_hh_vacancies.delay(vacancy_id, grade_id, search_query, country, area)
        
        return JsonResponse({
            'success': True,
            'message': f'Анализ hh.ru запущен для вакансии "{vacancy.name}" (грейд: {grade.name})',
            'task_id': task.id,
            'vacancy_name': vacancy.name,
            'grade_name': grade.name
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        logger.error(f"Ошибка при запуске анализа hh.ru: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при запуске анализа: {str(e)}'
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def start_batch_hh_analysis(request):
    """
    Запуск массового анализа hh.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с параметрами массового анализа
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - Celery задачи для асинхронного массового анализа
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация параметров массового анализа
    - Запуск Celery задачи массового анализа
    - Возврат ID задачи для отслеживания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с ID задачи и статусом
    
    СВЯЗИ:
    - Использует: Celery задачи, analyze_hh_vacancies_batch
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        vacancy_grade_pairs = data.get('vacancy_grade_pairs', [])
        search_queries = data.get('search_queries', {})
        
        if not vacancy_grade_pairs:
            return JsonResponse({
                'success': False,
                'message': 'Не указаны пары вакансия-грейд для анализа'
            })
        
        # Валидируем пары
        valid_pairs = []
        for pair in vacancy_grade_pairs:
            if isinstance(pair, list) and len(pair) == 2:
                vacancy_id, grade_id = pair
                try:
                    Vacancy.objects.get(id=vacancy_id)
                    Grade.objects.get(id=grade_id)
                    valid_pairs.append((vacancy_id, grade_id))
                except (Vacancy.DoesNotExist, Grade.DoesNotExist):
                    continue
        
        if not valid_pairs:
            return JsonResponse({
                'success': False,
                'message': 'Не найдено валидных пар вакансия-грейд'
            })
        
        # Запускаем Celery задачу
        from .tasks import analyze_hh_vacancies_batch
        task = analyze_hh_vacancies_batch.delay(valid_pairs, search_queries)
        
        return JsonResponse({
            'success': True,
            'message': f'Массовый анализ hh.ru запущен для {len(valid_pairs)} пар',
            'task_id': task.id,
            'pairs_count': len(valid_pairs)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        logger.error(f"Ошибка при запуске массового анализа hh.ru: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при запуске массового анализа: {str(e)}'
        })


@login_required
def ai_analysis_dashboard(request):
    """
    Дашборд для ИИ анализа
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Benchmark.objects: бенчмарки из AI анализа
    - HHVacancyTemp.objects: временные вакансии
    - BenchmarkSettings.load(): настройки AI анализа
    
    ОБРАБОТКА:
    - Получение статистики по AI бенчмаркам
    - Получение статистики по временным вакансиям
    - Получение настроек AI анализа
    - Создание контекста для дашборда
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными AI анализа
    - render: HTML страница 'finance/ai_analysis_dashboard.html'
    
    СВЯЗИ:
    - Использует: Benchmark.objects, HHVacancyTemp.objects, BenchmarkSettings
    - Передает данные в: finance/ai_analysis_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    from .ai_analyzer import AIBenchmarkAnalyzer
    
    analyzer = AIBenchmarkAnalyzer()
    
    # Получаем настройки
    settings = BenchmarkSettings.load()
    
    # Статистика по бенчмаркам
    total_benchmarks = Benchmark.objects.filter(is_active=True).count()
    candidate_benchmarks = Benchmark.objects.filter(
        type=BenchmarkType.CANDIDATE,
        is_active=True
    ).count()
    vacancy_benchmarks = Benchmark.objects.filter(
        type=BenchmarkType.VACANCY,
        is_active=True
    ).count()
    
    # Получаем текущий промпт
    current_prompt = analyzer.get_ai_analysis_prompt()
    
    context = {
        'total_benchmarks': total_benchmarks,
        'candidate_benchmarks': candidate_benchmarks,
        'vacancy_benchmarks': vacancy_benchmarks,
        'current_prompt': current_prompt,
        'settings': settings,
    }
    
    return render(request, 'finance/ai_analysis_dashboard.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def run_ai_analysis(request):
    """
    Запуск ИИ анализа бенчмарков
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с параметрами AI анализа
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - AIBenchmarkAnalyzer для анализа
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация параметров AI анализа
    - Запуск AI анализа
    - Возврат результата анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом AI анализа
    
    СВЯЗИ:
    - Использует: AIBenchmarkAnalyzer
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        # Получаем фильтры
        filters = data.get('filters', {})
        custom_prompt = data.get('custom_prompt', '').strip()
        save_to_db = data.get('save_to_db', False)
        
        from .ai_analyzer import AIBenchmarkAnalyzer
        analyzer = AIBenchmarkAnalyzer()
        
        # Подготавливаем данные
        benchmark_data = analyzer.prepare_benchmark_data_for_ai(filters)
        
        # Запускаем анализ
        result = analyzer.analyze_with_ai(benchmark_data, custom_prompt)
        
        # Если нужно сохранить в базу и анализ успешен
        if save_to_db and result.get('success') and result.get('analysis'):
            save_result = analyzer.save_structured_benchmarks_to_db(result['analysis'])
            result['save_result'] = save_result
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        logger.error(f"Ошибка при ИИ анализе: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_ai_prompt(request):
    """
    Обновление промпта для ИИ анализа
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.body: JSON с новым промптом
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - JSON данные из request.body
    - BenchmarkSettings для сохранения промпта
    
    ОБРАБОТКА:
    - Парсинг JSON данных
    - Валидация нового промпта
    - Сохранение промпта в настройках
    - Возврат результата операции
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с результатом операции
    
    СВЯЗИ:
    - Использует: BenchmarkSettings
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        data = json.loads(request.body)
        
        new_prompt = data.get('prompt', '').strip()
        
        if not new_prompt:
            return JsonResponse({
                'success': False,
                'message': 'Промпт не может быть пустым'
            })
        
        from .ai_analyzer import AIBenchmarkAnalyzer
        analyzer = AIBenchmarkAnalyzer()
        
        success = analyzer.update_ai_prompt(new_prompt)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Промпт для ИИ анализа обновлен'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при обновлении промпта'
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        logger.error(f"Ошибка при обновлении промпта: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при обновлении промпта: {str(e)}'
        })


@login_required
def task_status(request, task_id):
    """
    Проверка статуса задачи
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - task_id: ID задачи для проверки статуса
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - URL параметр task_id
    - Celery для получения статуса задачи
    
    ОБРАБОТКА:
    - Получение статуса задачи по ID
    - Формирование ответа со статусом
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ со статусом задачи
    
    СВЯЗИ:
    - Использует: Celery AsyncResult
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id)
        
        if task_result.state == 'PENDING':
            response = {
                'state': task_result.state,
                'status': 'Задача ожидает выполнения'
            }
        elif task_result.state == 'PROGRESS':
            response = {
                'state': task_result.state,
                'status': 'Задача выполняется',
                'progress': task_result.info
            }
        elif task_result.state == 'SUCCESS':
            response = {
                'state': task_result.state,
                'status': 'Задача выполнена успешно',
                'result': task_result.result
            }
        else:  # FAILURE
            response = {
                'state': task_result.state,
                'status': 'Задача завершилась с ошибкой',
                'error': str(task_result.info)
            }
        
        return JsonResponse(response)
        
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса задачи: {e}")
        return JsonResponse({
            'state': 'ERROR',
            'status': 'Ошибка при проверке статуса задачи',
            'error': str(e)
        })


@login_required
def benchmarks_settings(request):
    """
    Страница настроек бенчмарков с управлением hh.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: данные формы настроек
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - POST данные формы
    - BenchmarkSettings.load(): текущие настройки
    
    ОБРАБОТКА:
    - Обработка GET запроса (отображение формы настроек)
    - Обработка POST запроса (сохранение настроек)
    - Валидация данных формы
    - Обновление настроек бенчмарков
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с формой и текущими настройками
    - render: HTML страница 'finance/benchmarks_settings.html'
    - redirect: на дашборд при успешном сохранении
    
    СВЯЗИ:
    - Использует: BenchmarkSettingsForm, BenchmarkSettings
    - Передает данные в: finance/benchmarks_settings.html
    - Может вызываться из: finance/ URL patterns
    """
    settings = BenchmarkSettings.load()
    
    if request.method == 'POST':
        # Обновляем настройки hh.ru
        settings.hh_channel_active = request.POST.get('hh_channel_active') == 'on'
        settings.max_daily_hh_tasks = int(request.POST.get('max_daily_hh_tasks', 100))
        settings.hh_ai_prompt = request.POST.get('hh_ai_prompt', '')
        settings.save()
        
        messages.success(request, 'Настройки hh.ru обновлены')
        return redirect('finance:benchmarks_settings')
    
    # Статистика
    from datetime import date
    today = date.today()
    
    # Статистика по hh.ru
    hh_stats = {
        'temp_vacancies': HHVacancyTemp.objects.count(),
        'processed_today': HHVacancyTemp.objects.filter(
            created_at__date=today,
            processed=True
        ).count(),
        'pending_processing': HHVacancyTemp.objects.filter(processed=False).count(),
        'benchmarks_from_hh': Benchmark.objects.filter(
            hh_vacancy_id__isnull=False,
            is_active=True
        ).count()
    }
    
    context = {
        'settings': settings,
        'hh_stats': hh_stats,
        'available_domains': Domain.choices,
    }
    
    return render(request, 'finance/benchmarks_settings.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def start_hh_collection_manual(request):
    """
    Ручной запуск сбора вакансий с hh.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Celery задачи для сбора вакансий
    
    ОБРАБОТКА:
    - Запуск Celery задачи сбора вакансий
    - Возврат ID задачи для отслеживания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON ответ с ID задачи и статусом
    
    СВЯЗИ:
    - Использует: Celery задачи, fetch_hh_vacancies_task
    - Передает: JSON ответ
    - Может вызываться из: AJAX запросы
    """
    try:
        from .tasks import fetch_hh_vacancies_task
        
        task = fetch_hh_vacancies_task.delay()
        
        return JsonResponse({
            'success': True,
            'message': 'Сбор вакансий с hh.ru запущен',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка при запуске сбора hh.ru: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })
