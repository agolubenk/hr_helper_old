"""Views для дашборда Finance"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from logic.base.response_handler import UnifiedResponseHandler

@login_required
def benchmarks_dashboard(request):
    """
    Дашборд для бенчмарков с аналитикой и статистикой
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    - Grade.objects: грейды для статистики
    - BenchmarkType.objects: типы бенчмарков для фильтрации
    
    ОБРАБОТКА:
    - Подсчет общей статистики по бенчмаркам
    - Получение последних бенчмарков
    - Получение типов бенчмарков для фильтрации
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь со статистикой и данными бенчмарков
    - render: HTML страница 'finance/benchmarks_dashboard.html'
    
    СВЯЗИ:
    - Использует: Benchmark, Grade, BenchmarkType модели
    - Передает данные в: finance/benchmarks_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import Benchmark, Grade, BenchmarkType
        
        # Получаем статистику
        total_benchmarks = Benchmark.objects.count()
        active_benchmarks = Benchmark.objects.filter(is_active=True).count()
        total_grades = Grade.objects.count()
        
        # Получаем последние бенчмарки
        recent_benchmarks = Benchmark.objects.select_related('grade', 'benchmark_type').order_by('-created_at')[:10]
        
        # Получаем типы бенчмарков для фильтрации
        benchmark_types = BenchmarkType.objects.all()
        
        context = {
            'title': 'Benchmarks Dashboard',
            'total_benchmarks': total_benchmarks,
            'active_benchmarks': active_benchmarks,
            'total_grades': total_grades,
            'recent_benchmarks': recent_benchmarks,
            'benchmark_types': benchmark_types,
        }
        
        return render(request, 'finance/benchmarks_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда: {str(e)}')
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def dashboard(request):
    """
    Главный дашборд Finance приложения
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    - Grade.objects: грейды для статистики
    - SalaryRange.objects: зарплатные вилки для статистики
    
    ОБРАБОТКА:
    - Подсчет общей статистики по бенчмаркам, грейдам и зарплатным вилкам
    - Получение последних записей
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь со статистикой и данными
    - render: HTML страница 'finance/dashboard.html'
    
    СВЯЗИ:
    - Использует: Benchmark, Grade, SalaryRange модели
    - Передает данные в: finance/dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import Benchmark, Grade, SalaryRange
        
        # Статистика
        stats = {
            'total_benchmarks': Benchmark.objects.count(),
            'total_grades': Grade.objects.count(),
            'total_salary_ranges': SalaryRange.objects.count(),
        }
        
        # Последние данные
        recent_benchmarks = Benchmark.objects.select_related('grade').order_by('-created_at')[:5]
        
        context = {
            'title': 'Finance Dashboard',
            'stats': stats,
            'recent_benchmarks': recent_benchmarks,
            'user': request.user,
        }
        
        return render(request, 'finance/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда: {str(e)}')
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def pln_taxes_dashboard(request):
    """
    Дашборд для польских налогов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - PLNTax.objects: польские налоги из базы данных
    
    ОБРАБОТКА:
    - Получение всех польских налогов
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными польских налогов
    - render: HTML страница 'finance/pln_taxes_dashboard.html'
    
    СВЯЗИ:
    - Использует: PLNTax модель
    - Передает данные в: finance/pln_taxes_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import PLNTax
        
        taxes = PLNTax.objects.all().order_by('-created_at')
        
        context = {
            'title': 'PLN Taxes Dashboard',
            'taxes': taxes,
        }
        
        return render(request, 'finance/pln_taxes_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда налогов: {str(e)}')
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def hh_analysis_dashboard(request):
    """
    Дашборд для анализа HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HHVacancyTemp.objects: временные данные вакансий с HH.ru
    
    ОБРАБОТКА:
    - Получение временных данных вакансий с HH.ru
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными анализа HH.ru
    - render: HTML страница 'finance/hh_analysis_dashboard.html'
    
    СВЯЗИ:
    - Использует: HHVacancyTemp модель
    - Передает данные в: finance/hh_analysis_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import BenchmarkSettings
        
        settings = BenchmarkSettings.objects.first()
        
        context = {
            'title': 'HH Analysis Dashboard',
            'settings': settings,
        }
        
        return render(request, 'finance/hh_analysis_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда анализа: {str(e)}')
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def ai_analysis_dashboard(request):
    """
    Дашборд для AI анализа
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - BenchmarkSettings.objects: настройки бенчмарков
    
    ОБРАБОТКА:
    - Получение настроек бенчмарков
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с настройками AI анализа
    - render: HTML страница 'finance/ai_analysis_dashboard.html'
    
    СВЯЗИ:
    - Использует: BenchmarkSettings модель
    - Передает данные в: finance/ai_analysis_dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import BenchmarkSettings
        
        settings = BenchmarkSettings.objects.first()
        
        context = {
            'title': 'AI Analysis Dashboard',
            'settings': settings,
        }
        
        return render(request, 'finance/ai_analysis_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда AI анализа: {str(e)}')
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )
