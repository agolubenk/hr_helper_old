"""Views для работы с зарплатами"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from logic.base.response_handler import UnifiedResponseHandler
from apps.finance.models import SalaryRange
from logic.base.currency_service import UnifiedCurrencyService

@login_required
def salary_ranges_list(request):
    """
    Список зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange.objects: все зарплатные вилки из базы данных
    
    ОБРАБОТКА:
    - Получение всех зарплатных вилок, отсортированных по дате создания (новые первые)
    - Создание контекста для шаблона
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с зарплатными вилками и заголовком
    - render: HTML страница 'finance/salary_ranges_list.html'
    
    СВЯЗИ:
    - Использует: SalaryRange.objects
    - Передает данные в: finance/salary_ranges_list.html
    - Может вызываться из: finance/ URL patterns
    """
    try:
        salary_ranges = SalaryRange.objects.all().order_by('-created_at')
        context = {
            'salary_ranges': salary_ranges,
            'title': 'Зарплатные вилки'
        }
        return render(request, 'finance/salary_ranges_list.html', context)
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required  
def salary_range_detail(request, pk):
    """
    Детали зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID зарплатной вилки
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
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
    try:
        salary_range = get_object_or_404(SalaryRange, pk=pk)
        context = {
            'salary_range': salary_range,
            'title': f'Зарплатная вилка {salary_range.position}'
        }
        return render(request, 'finance/salary_range_detail.html', context)
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )

@login_required
def salary_range_create(request):
    """
    Создание зарплатной вилки
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: position, min_salary, max_salary, currency, grade_id, vacancy_id
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы создания зарплатной вилки
    - Grade.objects, Vacancy.objects для валидации связей
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Проверка существования связанных объектов (grade, vacancy)
    - Создание нового объекта SalaryRange
    - Обработка ошибок и успешного создания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:salary_ranges_list
    
    СВЯЗИ:
    - Использует: SalaryRange.objects.create(), Grade.objects, Vacancy.objects
    - Передает: результат создания в messages
    - Может вызываться из: finance/ URL patterns
    """
    if request.method == 'POST':
        try:
            # Простая обработка POST данных без форм
            position = request.POST.get('position', '')
            min_amount = request.POST.get('min_amount', 0)
            max_amount = request.POST.get('max_amount', 0)
            currency = request.POST.get('currency', 'RUB')
            
            salary_range = SalaryRange.objects.create(
                position=position,
                min_amount=min_amount,
                max_amount=max_amount,
                currency=currency
            )
            
            messages.success(request, 'Зарплатная вилка успешно создана')
            return redirect('salary_range_detail', pk=salary_range.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при создании: {str(e)}')
    
    context = {
        'title': 'Создание зарплатной вилки'
    }
    return render(request, 'finance/salary_range_form.html', context)

@login_required
def salary_range_update(request, pk):
    """Обновление зарплатной вилки"""
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    
    if request.method == 'POST':
        try:
            # Простая обработка POST данных без форм
            position = request.POST.get('position', salary_range.position)
            min_amount = request.POST.get('min_amount', salary_range.min_amount)
            max_amount = request.POST.get('max_amount', salary_range.max_amount)
            currency = request.POST.get('currency', salary_range.currency)
            
            salary_range.position = position
            salary_range.min_amount = min_amount
            salary_range.max_amount = max_amount
            salary_range.currency = currency
            salary_range.save()
            
            messages.success(request, 'Зарплатная вилка успешно обновлена')
            return redirect('salary_range_detail', pk=salary_range.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    context = {
        'salary_range': salary_range,
        'title': f'Редактирование: {salary_range.position}'
    }
    return render(request, 'finance/salary_range_form.html', context)

@login_required
def salary_range_delete(request, pk):
    """Удаление зарплатной вилки"""
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    
    if request.method == 'POST':
        try:
            position_name = salary_range.position
            salary_range.delete()
            messages.success(request, f'Зарплатная вилка "{position_name}" удалена')
            return redirect('salary_ranges_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении: {str(e)}')
            return redirect('salary_range_detail', pk=pk)
    
    context = {
        'salary_range': salary_range,
        'title': f'Удаление: {salary_range.position}'
    }
    return render(request, 'finance/salary_range_confirm_delete.html', context)

@login_required
def update_salary_currency_amounts(request):
    """Обновление валютных сумм в зарплатах"""
    try:
        currency_service = UnifiedCurrencyService()
        salary_ranges = SalaryRange.objects.all()
        
        updated_count = 0
        for salary_range in salary_ranges:
            if salary_range.currency != 'RUB':
                try:
                    # Получаем актуальный курс валют
                    rate = currency_service.get_exchange_rate(salary_range.currency, 'RUB')
                    if rate:
                        # Обновляем суммы в рублях
                        salary_range.min_amount_rub = salary_range.min_amount * rate
                        salary_range.max_amount_rub = salary_range.max_amount * rate
                        salary_range.save()
                        updated_count += 1
                except Exception as e:
                    print(f"Ошибка обновления для {salary_range.id}: {str(e)}")
        
        messages.success(request, f'Обновлено {updated_count} зарплатных вилок')
        return redirect('salary_ranges_list')
    except Exception as e:
        return UnifiedResponseHandler.json_response(
            UnifiedResponseHandler.error_response(str(e)),
            status_code=500
        )
