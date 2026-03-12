"""Views для работы с валютами"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.currency_service import currency_service

@login_required
def update_currency_rates(request):
    """
    Обновление курсов валют используя UnifiedCurrencyService
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    - request.headers: заголовки запроса для определения типа ответа
    
    ИСТОЧНИКИ ДАННЫХ:
    - UnifiedCurrencyService: сервис для работы с валютами
    - NBRB API: API Национального банка Беларуси
    
    ОБРАБОТКА:
    - Вызов метода update_currency_rates_in_db() из UnifiedCurrencyService
    - Обработка результата обновления
    - Определение типа ответа (JSON или HTML)
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате обновления
    - redirect: на finance:dashboard (для HTML)
    - JSON response: для API запросов
    
    СВЯЗИ:
    - Использует: UnifiedCurrencyService, NBRB API
    - Передает: HTTP redirect или JSON response
    - Может вызываться из: finance/ URL patterns
    """
    try:
        # Используем существующую архитектуру - новый метод
        result = currency_service.update_currency_rates_in_db()
        updated_count = result['updated_count']
        
        if updated_count > 0:
            messages.success(request, f'Курсы валют успешно обновлены ({updated_count} валют)')
        else:
            messages.warning(request, 'Не удалось обновить ни одного курса валют')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.success_response(
                    message=f"Курсы валют успешно обновлены ({updated_count} валют)",
                    data=result
                )
            )
        
        return redirect('finance:dashboard')
        
    except Exception as e:
        messages.error(request, f'Ошибка обновления курсов: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:dashboard')