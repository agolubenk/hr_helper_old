"""Views для работы с бенчмарками и AI анализом"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from logic.base.response_handler import UnifiedResponseHandler
from logic.integration.shared.gemini_operations import BaseGeminiOperations
from logic.integration.shared.gemini_operations import GeminiPromptManager
from apps.finance.models import Benchmark

class BenchmarkGeminiService(BaseGeminiOperations):
    """
    Сервис для работы с бенчмарками через Gemini AI
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - benchmark_data: данные бенчмарка
    - prompt_source: источник промпта (по умолчанию 'finance')
    
    ИСТОЧНИКИ ДАННЫХ:
    - BaseGeminiOperations: базовый класс для работы с Gemini AI
    - GeminiPromptManager: менеджер промптов
    - Gemini AI API: для выполнения анализа
    
    ОБРАБОТКА:
    - Наследование от BaseGeminiOperations
    - Получение промпта из Finance
    - Формирование данных для анализа
    - Выполнение prompt-based анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Результат анализа от Gemini AI
    
    СВЯЗИ:
    - Использует: BaseGeminiOperations, GeminiPromptManager, Gemini AI API
    - Передает: результат анализа
    - Может вызываться из: Benchmark views
    """
    
    def __init__(self):
        super().__init__("", "https://generativelanguage.googleapis.com", timeout=30)
    
    def analyze_salary_benchmark(self, benchmark_data, prompt_source='finance'):
        """Анализ зарплатного бенчмарка с использованием промпта из Finance"""
        try:
            # Получаем промпт из Finance
            prompt_manager = GeminiPromptManager()
            prompt = prompt_manager.get_prompt('finance', 'salary_benchmark_analysis')
            
            # Формируем данные для анализа
            analysis_data = {
                'benchmark': benchmark_data,
                'prompt': prompt,
                'analysis_type': 'salary_benchmark'
            }
            
            # Выполняем prompt-based анализ
            response = self.prompt_based_analysis(analysis_data, prompt_source)
            return response
            
        except Exception as e:
            raise Exception(f"Ошибка анализа бенчмарка: {str(e)}")

@login_required
def benchmark_list(request):
    """
    Список бенчмарков
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: все бенчмарки из базы данных
    
    ОБРАБОТКА:
    - Получение всех бенчмарков
    - Сортировка по дате создания
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с бенчмарками
    - render: HTML страница 'finance/benchmark_list.html'
    
    СВЯЗИ:
    - Использует: Benchmark модель
    - Передает данные в: finance/benchmark_list.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        benchmarks = Benchmark.objects.all().order_by('-created_at')
        context = {
            'benchmarks': benchmarks,
            'title': 'Бенчмарки зарплат'
        }
        return render(request, 'finance/benchmark_list.html', context)
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def benchmark_detail(request, pk):
    """
    Детали бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными бенчмарка
    - render: HTML страница 'finance/benchmark_detail.html'
    
    СВЯЗИ:
    - Использует: Benchmark модель
    - Передает данные в: finance/benchmark_detail.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        benchmark = get_object_or_404(Benchmark, pk=pk)
        context = {
            'benchmark': benchmark,
            'title': f'Бенчмарк: {benchmark.title}'
        }
        return render(request, 'finance/benchmark_detail.html', context)
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def benchmark_create(request):
    """
    Создание бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: данные формы создания бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы создания бенчмарка
    
    ОБРАБОТКА:
    - Валидация данных формы
    - Создание нового бенчмарка
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате создания
    - redirect: на finance:benchmark_list
    
    СВЯЗИ:
    - Использует: Benchmark.objects.create()
    - Передает: HTTP redirect
    - Может вызываться из: finance/ URL patterns
    """
    if request.method == 'POST':
        try:
            # Простая обработка POST данных без форм
            title = request.POST.get('title', '')
            description = request.POST.get('description', '')
            
            benchmark = Benchmark.objects.create(
                title=title,
                description=description
            )
            
            # Автоматический AI анализ нового бенчмарка
            try:
                gemini_service = BenchmarkGeminiService()
                analysis_result = gemini_service.analyze_salary_benchmark(benchmark)
                
                # Сохраняем результат анализа
                if analysis_result and analysis_result.get('success'):
                    benchmark.ai_analysis = analysis_result.get('analysis', '')
                    benchmark.save()
                    messages.success(request, 'Бенчмарк создан и проанализирован AI')
                else:
                    messages.warning(request, 'Бенчмарк создан, но AI анализ не удался')
                    
            except Exception as ai_error:
                messages.warning(request, f'Бенчмарк создан, но AI анализ не удался: {str(ai_error)}')
            
            return redirect('benchmark_detail', pk=benchmark.pk)
                
        except Exception as e:
            messages.error(request, f'Ошибка при создании: {str(e)}')
    
    context = {
        'title': 'Создание бенчмарка'
    }
    return render(request, 'finance/benchmark_form.html', context)

@login_required
def benchmark_update(request, pk):
    """
    Обновление бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка
    - request.POST: данные формы обновления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы обновления бенчмарка
    - Benchmark.objects: бенчмарки из базы данных
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Валидация данных формы
    - Обновление бенчмарка
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате обновления
    - redirect: на finance:benchmark_detail
    
    СВЯЗИ:
    - Использует: Benchmark.objects.get()
    - Передает: HTTP redirect
    - Может вызываться из: finance/ URL patterns
    """
    benchmark = get_object_or_404(Benchmark, pk=pk)
    
    if request.method == 'POST':
        try:
            # Простая обработка POST данных без форм
            title = request.POST.get('title', benchmark.title)
            description = request.POST.get('description', benchmark.description)
            
            benchmark.title = title
            benchmark.description = description
            benchmark.save()
            
            # Обновляем AI анализ
            try:
                gemini_service = BenchmarkGeminiService()
                analysis_result = gemini_service.analyze_salary_benchmark(benchmark)
                
                if analysis_result and analysis_result.get('success'):
                    benchmark.ai_analysis = analysis_result.get('analysis', '')
                    benchmark.save()
                    messages.success(request, 'Бенчмарк обновлен и переанализирован AI')
                else:
                    messages.warning(request, 'Бенчмарк обновлен, но AI анализ не удался')
                    
            except Exception as ai_error:
                messages.warning(request, f'Бенчмарк обновлен, но AI анализ не удался: {str(ai_error)}')
            
            return redirect('benchmark_detail', pk=benchmark.pk)
                
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    context = {
        'benchmark': benchmark,
        'title': f'Редактирование: {benchmark.title}'
    }
    return render(request, 'finance/benchmark_form.html', context)

@login_required
def benchmark_delete(request, pk):
    """
    Удаление бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Удаление бенчмарка
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате удаления
    - redirect: на finance:benchmark_list
    
    СВЯЗИ:
    - Использует: Benchmark.objects.get()
    - Передает: HTTP redirect
    - Может вызываться из: finance/ URL patterns
    """
    benchmark = get_object_or_404(Benchmark, pk=pk)
    
    if request.method == 'POST':
        try:
            title = benchmark.title
            benchmark.delete()
            messages.success(request, f'Бенчмарк "{title}" удален')
            return redirect('benchmark_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении: {str(e)}')
            return redirect('benchmark_detail', pk=pk)
    
    context = {
        'benchmark': benchmark,
        'title': f'Удаление: {benchmark.title}'
    }
    return render(request, 'finance/benchmark_confirm_delete.html', context)

@login_required
def benchmark_ai_analysis(request, pk):
    """
    AI анализ бенчмарка
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID бенчмарка
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Benchmark.objects: бенчмарки из базы данных
    - BenchmarkGeminiService: сервис для AI анализа
    
    ОБРАБОТКА:
    - Получение бенчмарка по ID
    - Запуск AI анализа через BenchmarkGeminiService
    - Обработка ошибок анализа
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с результатами AI анализа
    - render: HTML страница 'finance/benchmark_ai_analysis.html'
    
    СВЯЗИ:
    - Использует: Benchmark модель, BenchmarkGeminiService
    - Передает данные в: finance/benchmark_ai_analysis.html
    - Может вызываться из: finance/ URL patterns
    """
    benchmark = get_object_or_404(Benchmark, pk=pk)
    
    try:
        gemini_service = BenchmarkGeminiService()
        analysis_result = gemini_service.analyze_salary_benchmark(benchmark)
        
        if analysis_result and analysis_result.get('success'):
            benchmark.ai_analysis = analysis_result.get('analysis', '')
            benchmark.save()
            messages.success(request, 'AI анализ выполнен успешно')
        else:
            error_msg = analysis_result.get('error', 'Неизвестная ошибка') if analysis_result else 'Нет ответа от AI'
            messages.error(request, f'Ошибка AI анализа: {error_msg}')
            
    except Exception as e:
        messages.error(request, f'Ошибка при запуске AI анализа: {str(e)}')
    
    return redirect('benchmark_detail', pk=benchmark.pk)
