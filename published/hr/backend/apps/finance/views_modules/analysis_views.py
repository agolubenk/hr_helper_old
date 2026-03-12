"""Views для финансового анализа"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from logic.base.response_handler import UnifiedResponseHandler
from logic.integration.shared.gemini_operations import BaseGeminiOperations
from apps.finance.models import SalaryRange, Benchmark
from django.db.models import Avg, Min, Max, Count

class FinanceAnalysisService(BaseGeminiOperations):
    """
    Сервис для финансового анализа через Gemini AI
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - analysis_type: тип анализа
    - data: данные для анализа
    
    ИСТОЧНИКИ ДАННЫХ:
    - BaseGeminiOperations: базовый класс для работы с Gemini AI
    - Gemini AI API: для выполнения анализа
    
    ОБРАБОТКА:
    - Наследование от BaseGeminiOperations
    - Формирование запроса для анализа
    - Выполнение прямого анализа через Gemini AI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Результат анализа от Gemini AI
    
    СВЯЗИ:
    - Использует: BaseGeminiOperations, Gemini AI API
    - Передает: результат анализа
    - Может вызываться из: Finance analysis views
    """
    
    def __init__(self):
        super().__init__("", "https://generativelanguage.googleapis.com", timeout=30)
    
    def analyze_finance_data(self, analysis_type, data):
        """Прямой анализ финансовых данных без промптов"""
        try:
            # Формируем данные для прямого анализа
            analysis_request = {
                'type': analysis_type,
                'data': data,
                'timestamp': data.get('timestamp'),
                'user_id': data.get('user_id')
            }
            
            # Выполняем прямой анализ
            response = self.direct_analysis(analysis_request)
            return response
            
        except Exception as e:
            raise Exception(f"Ошибка финансового анализа: {str(e)}")

@login_required
def finance_dashboard_analysis(request):
    """
    Анализ дашборда финансов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange.objects: зарплатные вилки
    - Benchmark.objects: бенчмарки
    - FinanceAnalysisService: сервис для AI анализа
    
    ОБРАБОТКА:
    - Сбор базовой статистики по зарплатам и бенчмаркам
    - Запуск AI анализа через FinanceAnalysisService
    - Обработка ошибок анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с результатами анализа
    - render: HTML страница 'finance/analysis/dashboard.html'
    
    СВЯЗИ:
    - Использует: SalaryRange, Benchmark модели, FinanceAnalysisService
    - Передает данные в: finance/analysis/dashboard.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        # Собираем базовую статистику
        salary_stats = {
            'total_ranges': SalaryRange.objects.count(),
            'avg_min_salary': SalaryRange.objects.aggregate(avg=Avg('min_amount_rub'))['avg'] or 0,
            'avg_max_salary': SalaryRange.objects.aggregate(avg=Avg('max_amount_rub'))['avg'] or 0,
            'total_benchmarks': Benchmark.objects.count(),
        }
        
        # Запускаем AI анализ
        try:
            analysis_service = FinanceAnalysisService()
            analysis_data = {
                'salary_stats': salary_stats,
                'analysis_type': 'finance_dashboard',
                'timestamp': request.user.date_joined,
                'user_id': request.user.id
            }
            
            ai_result = analysis_service.analyze_finance_data('dashboard', analysis_data)
            
            if ai_result and ai_result.get('success'):
                ai_insights = ai_result.get('analysis', {})
            else:
                ai_insights = {'error': 'AI анализ недоступен'}
                
        except Exception as ai_error:
            ai_insights = {'error': f'Ошибка AI анализа: {str(ai_error)}'}
        
        context = {
            'salary_stats': salary_stats,
            'ai_insights': ai_insights,
            'title': 'Финансовый анализ'
        }
        return render(request, 'finance/finance_dashboard_analysis.html', context)
        
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def salary_trends_analysis(request):
    """
    Анализ трендов зарплат
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange.objects: зарплатные вилки
    - FinanceAnalysisService: сервис для AI анализа
    
    ОБРАБОТКА:
    - Сбор данных по зарплатным вилкам
    - Анализ трендов через AI
    - Обработка ошибок анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с результатами анализа трендов
    - render: HTML страница 'finance/analysis/salary_trends.html'
    
    СВЯЗИ:
    - Использует: SalaryRange модель, FinanceAnalysisService
    - Передает данные в: finance/analysis/salary_trends.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        # Анализируем тренды по позициям
        position_trends = SalaryRange.objects.values('position').annotate(
            avg_min=Avg('min_amount_rub'),
            avg_max=Avg('max_amount_rub'),
            count=Count('id')
        ).order_by('-avg_max')
        
        # Анализируем по валютам
        currency_trends = SalaryRange.objects.values('currency').annotate(
            count=Count('id'),
            avg_min=Avg('min_amount'),
            avg_max=Avg('max_amount')
        )
        
        trends_data = {
            'position_trends': list(position_trends),
            'currency_trends': list(currency_trends),
            'analysis_type': 'salary_trends',
            'timestamp': request.user.date_joined,
            'user_id': request.user.id
        }
        
        # Запускаем AI анализ трендов
        try:
            analysis_service = FinanceAnalysisService()
            ai_result = analysis_service.analyze_finance_data('trends', trends_data)
            
            if ai_result and ai_result.get('success'):
                ai_trends = ai_result.get('analysis', {})
            else:
                ai_trends = {'error': 'AI анализ трендов недоступен'}
                
        except Exception as ai_error:
            ai_trends = {'error': f'Ошибка AI анализа трендов: {str(ai_error)}'}
        
        context = {
            'position_trends': position_trends,
            'currency_trends': currency_trends,
            'ai_trends': ai_trends,
            'title': 'Анализ трендов зарплат'
        }
        return render(request, 'finance/salary_trends_analysis.html', context)
        
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def benchmark_comparison_analysis(request):
    """
    Анализ сравнения бенчмарков
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки
    - FinanceAnalysisService: сервис для AI анализа
    
    ОБРАБОТКА:
    - Сбор данных по бенчмаркам
    - Анализ сравнения через AI
    - Обработка ошибок анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с результатами анализа сравнения
    - render: HTML страница 'finance/analysis/benchmark_comparison.html'
    
    СВЯЗИ:
    - Использует: Benchmark модель, FinanceAnalysisService
    - Передает данные в: finance/analysis/benchmark_comparison.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        # Получаем все бенчмарки
        benchmarks = Benchmark.objects.all().order_by('-created_at')
        
        # Подготавливаем данные для сравнения
        comparison_data = []
        for benchmark in benchmarks:
            comparison_data.append({
                'id': benchmark.id,
                'title': benchmark.title,
                'description': benchmark.description,
                'created_at': benchmark.created_at,
                'ai_analysis': benchmark.ai_analysis
            })
        
        analysis_data = {
            'benchmarks': comparison_data,
            'analysis_type': 'benchmark_comparison',
            'timestamp': request.user.date_joined,
            'user_id': request.user.id
        }
        
        # Запускаем AI сравнительный анализ
        try:
            analysis_service = FinanceAnalysisService()
            ai_result = analysis_service.analyze_finance_data('benchmark_comparison', analysis_data)
            
            if ai_result and ai_result.get('success'):
                ai_comparison = ai_result.get('analysis', {})
            else:
                ai_comparison = {'error': 'AI сравнительный анализ недоступен'}
                
        except Exception as ai_error:
            ai_comparison = {'error': f'Ошибка AI сравнительного анализа: {str(ai_error)}'}
        
        context = {
            'benchmarks': benchmarks,
            'ai_comparison': ai_comparison,
            'title': 'Сравнительный анализ бенчмарков'
        }
        return render(request, 'finance/benchmark_comparison_analysis.html', context)
        
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def custom_finance_analysis(request):
    """
    Кастомный финансовый анализ
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    - request.POST: параметры анализа
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange.objects: зарплатные вилки
    - Benchmark.objects: бенчмарки
    - FinanceAnalysisService: сервис для AI анализа
    
    ОБРАБОТКА:
    - Получение параметров анализа из POST
    - Сбор данных по заданным критериям
    - Выполнение кастомного анализа через AI
    - Обработка ошибок анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с результатами кастомного анализа
    - render: HTML страница 'finance/analysis/custom.html'
    
    СВЯЗИ:
    - Использует: SalaryRange, Benchmark модели, FinanceAnalysisService
    - Передает данные в: finance/analysis/custom.html
    - Может вызываться из: finance/ URL patterns
    """
    if request.method == 'POST':
        try:
            analysis_type = request.POST.get('analysis_type', 'custom')
            analysis_params = {
                'date_from': request.POST.get('date_from'),
                'date_to': request.POST.get('date_to'),
                'currency': request.POST.get('currency', 'RUB'),
                'position_filter': request.POST.get('position_filter', ''),
                'analysis_type': analysis_type,
                'timestamp': request.user.date_joined,
                'user_id': request.user.id
            }
            
            # Запускаем кастомный AI анализ
            analysis_service = FinanceAnalysisService()
            ai_result = analysis_service.analyze_finance_data('custom', analysis_params)
            
            if ai_result and ai_result.get('success'):
                ai_custom = ai_result.get('analysis', {})
                messages.success(request, 'Кастомный анализ выполнен успешно')
            else:
                ai_custom = {'error': 'Кастомный AI анализ недоступен'}
                messages.error(request, 'Ошибка при выполнении кастомного анализа')
                
            context = {
                'analysis_params': analysis_params,
                'ai_custom': ai_custom,
                'title': 'Кастомный финансовый анализ'
            }
            return render(request, 'finance/custom_finance_analysis.html', context)
            
        except Exception as e:
            messages.error(request, f'Ошибка при выполнении анализа: {str(e)}')
    
    context = {
        'title': 'Кастомный финансовый анализ'
    }
    return render(request, 'finance/custom_finance_analysis_form.html', context)
