"""Управление интервьюерами"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.interviewers.models import Interviewer, InterviewRule
from apps.interviewers.forms import InterviewerForm, InterviewerSearchForm, InterviewRuleForm, InterviewRuleSearchForm
from logic.utilities.context_helpers import ContextHelper


@login_required
def interviewer_list(request):
    """Список интервьюеров"""
    # Получаем параметры поиска
    search_form = InterviewerSearchForm(request.GET)
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('is_active', '')
    
    # Базовый queryset
    interviewers = Interviewer.objects.all()
    
    # Применяем фильтры
    if search_query:
        interviewers = interviewers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if status_filter:
        is_active = status_filter.lower() == 'true'
        interviewers = interviewers.filter(is_active=is_active)
    
    # Пагинация
    paginator = Paginator(interviewers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Список интервьюеров',
        {
            'page_obj': page_obj,
            'search_form': search_form,
            'search_query': search_query,
            'status_filter': status_filter,
            'total_count': interviewers.count(),
            'active_count': interviewers.filter(is_active=True).count(),
            'inactive_count': interviewers.filter(is_active=False).count(),
        }
    )
    
    return render(request, 'interviewers/interviewer_list.html', context)


@login_required
def interviewer_detail(request, pk):
    """Детальная информация об интервьюере"""
    interviewer = get_object_or_404(Interviewer, pk=pk)
    
    context = ContextHelper.get_base_context(
        request,
        f'Интервьюер {interviewer.get_full_name()}',
        {
            'interviewer': interviewer,
        }
    )
    
    return render(request, 'interviewers/interviewer_detail.html', context)


@login_required
def interviewer_create(request):
    """Создание нового интервьюера"""
    if request.method == 'POST':
        # Простая обработка POST данных без форм
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        middle_name = request.POST.get('middle_name', '')
        email = request.POST.get('email', '')
        calendar_link = request.POST.get('calendar_link', '')
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            interviewer = Interviewer.objects.create(
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                email=email,
                calendar_link=calendar_link,
                is_active=is_active
            )
            messages.success(request, f'Интервьюер {interviewer.get_full_name()} успешно создан!')
            return redirect('interviewers:interviewer_detail', pk=interviewer.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при создании: {str(e)}')
    else:
        # Создаем пустую форму для отображения
        form = InterviewerForm()
    
    context = ContextHelper.get_base_context(
        request,
        'Создание интервьюера',
        {
            'form': form,
            'title': 'Создание интервьюера',
            'submit_text': 'Создать интервьюера',
        }
    )
    
    return render(request, 'interviewers/interviewer_form.html', context)


@login_required
def interviewer_edit(request, pk):
    """Редактирование интервьюера"""
    interviewer = get_object_or_404(Interviewer, pk=pk)
    
    if request.method == 'POST':
        # Простая обработка POST данных без форм
        interviewer.first_name = request.POST.get('first_name', interviewer.first_name)
        interviewer.last_name = request.POST.get('last_name', interviewer.last_name)
        interviewer.middle_name = request.POST.get('middle_name', interviewer.middle_name)
        interviewer.email = request.POST.get('email', interviewer.email)
        interviewer.calendar_link = request.POST.get('calendar_link', interviewer.calendar_link)
        interviewer.is_active = request.POST.get('is_active') == 'on'
        
        try:
            interviewer.save()
            messages.success(request, f'Интервьюер {interviewer.get_full_name()} успешно обновлен!')
            return redirect('interviewers:interviewer_detail', pk=interviewer.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    else:
        # Создаем форму с данными интервьюера
        form = InterviewerForm(instance=interviewer)
    
    context = ContextHelper.get_base_context(
        request,
        f'Редактирование интервьюера {interviewer.get_full_name()}',
        {
            'form': form,
            'interviewer': interviewer,
            'title': f'Редактирование интервьюера {interviewer.get_full_name()}',
            'submit_text': 'Сохранить изменения',
        }
    )
    
    return render(request, 'interviewers/interviewer_form.html', context)


@login_required
def interviewer_delete(request, pk):
    """Удаление интервьюера"""
    interviewer = get_object_or_404(Interviewer, pk=pk)
    
    if request.method == 'POST':
        try:
            interviewer_name = interviewer.get_full_name()
            interviewer.delete()
            messages.success(request, f'Интервьюер {interviewer_name} успешно удален!')
            return redirect('interviewers:interviewer_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении: {str(e)}')
    
    context = ContextHelper.get_base_context(
        request,
        f'Удаление интервьюера {interviewer.get_full_name()}',
        {
            'interviewer': interviewer,
        }
    )
    
    return render(request, 'interviewers/interviewer_confirm_delete.html', context)


@login_required
@require_POST
def interviewer_toggle_active(request, pk):
    """Переключение активности интервьюера"""
    interviewer = get_object_or_404(Interviewer, pk=pk)
    
    try:
        interviewer.is_active = not interviewer.is_active
        interviewer.save()
        
        status_text = "активирован" if interviewer.is_active else "деактивирован"
        return JsonResponse({
            'success': True,
            'message': f'Интервьюер {interviewer.get_full_name()} {status_text}',
            'is_active': interviewer.is_active
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=400)


# Функции для работы с правилами интервью

@login_required
def interview_rule_list(request):
    """Список правил интервью"""
    search_form = InterviewRuleSearchForm(request.GET)
    search_query = request.GET.get('search', '')
    
    rules = InterviewRule.objects.all()
    
    if search_query:
        rules = rules.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    paginator = Paginator(rules, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Правила интервью',
        {
            'page_obj': page_obj,
            'search_form': search_form,
            'search_query': search_query,
            'total_count': rules.count(),
        }
    )
    
    return render(request, 'interviewers/rule_list.html', context)


@login_required
def interview_rule_detail(request, pk):
    """Детальная информация о правиле интервью"""
    rule = get_object_or_404(InterviewRule, pk=pk)
    
    context = ContextHelper.get_base_context(
        request,
        f'Правило: {rule.name}',
        {
            'rule': rule,
        }
    )
    
    return render(request, 'interviewers/rule_detail.html', context)


@login_required
def interview_rule_create(request):
    """Создание нового правила интервью"""
    if request.method == 'POST':
        # Простая обработка POST данных без форм
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        duration_minutes = request.POST.get('duration_minutes', 60)
        
        try:
            rule = InterviewRule.objects.create(
                name=name,
                description=description,
                duration_minutes=int(duration_minutes) if duration_minutes else 60
            )
            messages.success(request, f'Правило "{rule.name}" успешно создано!')
            return redirect('interviewers:rule_detail', pk=rule.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при создании: {str(e)}')
    else:
        form = InterviewRuleForm()
    
    context = ContextHelper.get_base_context(
        request,
        'Создание правила интервью',
        {
            'form': form,
            'title': 'Создание правила интервью',
            'submit_text': 'Создать правило',
        }
    )
    
    return render(request, 'interviewers/rule_form.html', context)


@login_required
def interview_rule_edit(request, pk):
    """Редактирование правила интервью"""
    rule = get_object_or_404(InterviewRule, pk=pk)
    
    if request.method == 'POST':
        # Простая обработка POST данных без форм
        rule.name = request.POST.get('name', rule.name)
        rule.description = request.POST.get('description', rule.description)
        duration_minutes = request.POST.get('duration_minutes', rule.duration_minutes)
        
        try:
            rule.duration_minutes = int(duration_minutes) if duration_minutes else rule.duration_minutes
            rule.save()
            messages.success(request, f'Правило "{rule.name}" успешно обновлено!')
            return redirect('interviewers:rule_detail', pk=rule.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    else:
        form = InterviewRuleForm(instance=rule)
    
    context = ContextHelper.get_base_context(
        request,
        f'Редактирование правила: {rule.name}',
        {
            'form': form,
            'rule': rule,
            'title': f'Редактирование правила: {rule.name}',
            'submit_text': 'Сохранить изменения',
        }
    )
    
    return render(request, 'interviewers/rule_form.html', context)


@login_required
def interview_rule_delete(request, pk):
    """Удаление правила интервью"""
    rule = get_object_or_404(InterviewRule, pk=pk)
    
    if request.method == 'POST':
        try:
            rule_name = rule.name
            rule.delete()
            messages.success(request, f'Правило "{rule_name}" успешно удалено!')
            return redirect('interviewers:rule_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении: {str(e)}')
    
    context = ContextHelper.get_base_context(
        request,
        f'Удаление правила: {rule.name}',
        {
            'rule': rule,
        }
    )
    
    return render(request, 'interviewers/rule_confirm_delete.html', context)
