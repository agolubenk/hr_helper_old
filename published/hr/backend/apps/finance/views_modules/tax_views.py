"""Views для работы с налогами"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal
from logic.base.response_handler import UnifiedResponseHandler

@login_required
def add_pln_tax(request):
    """
    Добавление польского налога
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: name (обязательно), tax_rate (обязательно), description (опционально)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы создания польского налога
    
    ОБРАБОТКА:
    - Валидация обязательных полей name и tax_rate
    - Проверка корректности ставки налога (0-100%)
    - Проверка на существование налога с таким же названием
    - Создание нового объекта PLNTax
    - Обработка ошибок и успешного создания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:pln_taxes_dashboard
    
    СВЯЗИ:
    - Использует: PLNTax.objects.create()
    - Передает: результат создания в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import PLNTax
        
        if request.method == 'POST':
            name = request.POST.get('name')
            tax_rate_str = request.POST.get('tax_rate')
            description = request.POST.get('description', '')
            
            if not name or not tax_rate_str:
                messages.error(request, 'Название и ставка налога обязательны')
                return redirect('finance:add_pln_tax')
            
            try:
                tax_rate = Decimal(tax_rate_str)
                if tax_rate < 0 or tax_rate > 100:
                    messages.error(request, 'Ставка налога должна быть от 0 до 100%')
                    return redirect('finance:add_pln_tax')
            except (ValueError, TypeError):
                messages.error(request, 'Неверный формат ставки налога')
                return redirect('finance:add_pln_tax')
            
            # Проверяем, не существует ли уже такой налог
            if PLNTax.objects.filter(name=name).exists():
                messages.error(request, 'Налог с таким названием уже существует')
                return redirect('finance:add_pln_tax')
            
            tax = PLNTax.objects.create(
                name=name,
                tax_rate=tax_rate,
                description=description
            )
            
            messages.success(request, f'Налог "{name}" успешно добавлен')
            return redirect('finance:pln_taxes_dashboard')
        
        context = {
            'title': 'Добавить польский налог',
        }
        
        return render(request, 'finance/add_pln_tax.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка добавления налога: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:pln_taxes_dashboard')

@login_required
def update_pln_tax(request, tax_id):
    """
    Обновление польского налога
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - tax_id: ID польского налога
    - request.POST: name, tax_rate, description
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы обновления польского налога
    - PLNTax.objects: польские налоги из базы данных
    
    ОБРАБОТКА:
    - Получение польского налога по ID
    - Валидация данных формы
    - Проверка корректности ставки налога
    - Обновление объекта PLNTax
    - Обработка ошибок и успешного обновления
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:pln_taxes_dashboard
    
    СВЯЗИ:
    - Использует: PLNTax.objects.get()
    - Передает: результат обновления в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import PLNTax
        
        tax = get_object_or_404(PLNTax, id=tax_id)
        
        if request.method == 'POST':
            name = request.POST.get('name')
            tax_rate_str = request.POST.get('tax_rate')
            description = request.POST.get('description', '')
            
            if not name or not tax_rate_str:
                messages.error(request, 'Название и ставка налога обязательны')
                return redirect('finance:update_pln_tax', tax_id=tax_id)
            
            try:
                tax_rate = Decimal(tax_rate_str)
                if tax_rate < 0 or tax_rate > 100:
                    messages.error(request, 'Ставка налога должна быть от 0 до 100%')
                    return redirect('finance:update_pln_tax', tax_id=tax_id)
            except (ValueError, TypeError):
                messages.error(request, 'Неверный формат ставки налога')
                return redirect('finance:update_pln_tax', tax_id=tax_id)
            
            # Проверяем, не существует ли уже такой налог (кроме текущего)
            if PLNTax.objects.filter(name=name).exclude(id=tax_id).exists():
                messages.error(request, 'Налог с таким названием уже существует')
                return redirect('finance:update_pln_tax', tax_id=tax_id)
            
            tax.name = name
            tax.tax_rate = tax_rate
            tax.description = description
            tax.save()
            
            messages.success(request, f'Налог "{name}" успешно обновлен')
            return redirect('finance:pln_taxes_dashboard')
        
        context = {
            'title': 'Обновить польский налог',
            'tax': tax,
        }
        
        return render(request, 'finance/update_pln_tax.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка обновления налога: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:pln_taxes_dashboard')

@login_required
def delete_pln_tax(request, tax_id):
    """
    Удаление польского налога
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - tax_id: ID польского налога
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - PLNTax.objects: польские налоги из базы данных
    
    ОБРАБОТКА:
    - Получение польского налога по ID
    - Удаление объекта PLNTax
    - Обработка ошибок и успешного удаления
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:pln_taxes_dashboard
    
    СВЯЗИ:
    - Использует: PLNTax.objects.get()
    - Передает: результат удаления в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import PLNTax
        
        tax = get_object_or_404(PLNTax, id=tax_id)
        tax_name = tax.name
        tax.delete()
        
        messages.success(request, f'Налог "{tax_name}" успешно удален')
        return redirect('finance:pln_taxes_dashboard')
        
    except Exception as e:
        messages.error(request, f'Ошибка удаления налога: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:pln_taxes_dashboard')

@login_required
def calculate_pln_taxes(request):
    """
    Расчет польских налогов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: salary (зарплата), tax_id (ID налога)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы расчета налогов
    - PLNTax.objects: польские налоги из базы данных
    
    ОБРАБОТКА:
    - Получение данных из POST запроса
    - Валидация входных данных
    - Получение налога по ID
    - Расчет налоговых отчислений
    - Обработка ошибок и успешного расчета
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:pln_taxes_dashboard
    
    СВЯЗИ:
    - Использует: PLNTax.objects.get()
    - Передает: результат расчета в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import PLNTax
        from decimal import Decimal
        
        if request.method == 'POST':
            net_amount_str = request.POST.get('net_amount')
            
            if not net_amount_str:
                messages.error(request, 'Сумма обязательна')
                return redirect('finance:calculate_pln_taxes')
            
            try:
                net_amount = Decimal(net_amount_str)
            except (ValueError, TypeError):
                messages.error(request, 'Неверный формат суммы')
                return redirect('finance:calculate_pln_taxes')
            
            # Получаем все налоги
            taxes = PLNTax.objects.all()
            
            calculations = []
            total_tax = Decimal('0')
            
            for tax in taxes:
                tax_amount = net_amount * (tax.tax_rate / 100)
                total_tax += tax_amount
                
                calculations.append({
                    'tax': tax,
                    'tax_amount': tax_amount,
                })
            
            gross_amount = net_amount + total_tax
            
            context = {
                'title': 'Расчет польских налогов',
                'net_amount': net_amount,
                'calculations': calculations,
                'total_tax': total_tax,
                'gross_amount': gross_amount,
            }
            
            return render(request, 'finance/tax_calculation_result.html', context)
        
        context = {
            'title': 'Расчет польских налогов',
        }
        
        return render(request, 'finance/calculate_pln_taxes.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка расчета налогов: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:pln_taxes_dashboard')
