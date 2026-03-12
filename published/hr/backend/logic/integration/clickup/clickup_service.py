"""Основной сервис для работы с ClickUp"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
import json
import logging

from logic.utilities.context_helpers import ContextHelper
from logic.base.response_handler import UnifiedResponseHandler
from apps.clickup_int.services import ClickUpService, ClickUpCacheService, ClickUpAPIError
from apps.clickup_int.models import ClickUpSettings, ClickUpTask, ClickUpSyncLog, ClickUpBulkImport

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    Главная страница интеграции с ClickUp
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: ClickUpSettings, ClickUpTask, ClickUpSyncLog
    ОБРАБОТКА: Получение настроек, статистики и последних данных
    ВЫХОДЯЩИЕ ДАННЫЕ: context → clickup/dashboard.html
    СВЯЗИ: ClickUpSettings, ClickUpTask, ClickUpSyncLog
    ФОРМАТ: HTML render
    """
    user = request.user
    
    # Получаем настройки пользователя
    try:
        settings = ClickUpSettings.objects.get(user=user)
        is_configured = bool(user.clickup_api_key and settings.team_id and settings.space_id and settings.list_id)
    except ClickUpSettings.DoesNotExist:
        settings = None
        is_configured = False
    
    # Получаем статистику
    tasks_count = ClickUpTask.objects.filter(user=user).count()
    recent_tasks = ClickUpTask.objects.filter(user=user).order_by('-date_updated')[:5]
    
    # Получаем последние логи синхронизации
    recent_syncs = ClickUpSyncLog.objects.filter(user=user).order_by('-created_at')[:5]
    
    context = ContextHelper.get_base_context(
        request,
        'Интеграция с ClickUp',
        {
            'settings': settings,
            'is_configured': is_configured,
            'tasks_count': tasks_count,
            'recent_tasks': recent_tasks,
            'recent_syncs': recent_syncs
        }
    )
    
    return render(request, 'clickup_int/dashboard.html', context)


@login_required
def settings(request):
    """
    Страница настроек ClickUp
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user, request.POST (team_id, space_id, list_id)
    ИСТОЧНИКИ ДАННЫЕ: ClickUpSettings, POST данные формы
    ОБРАБОТКА: Получение/создание настроек, обработка POST запроса
    ВЫХОДЯЩИЕ ДАННЫЕ: context → clickup/settings.html или redirect
    СВЯЗИ: ClickUpSettings
    ФОРМАТ: HTML render или HTTP redirect
    """
    user = request.user
    
    try:
        settings_obj = ClickUpSettings.objects.get(user=user)
    except ClickUpSettings.DoesNotExist:
        settings_obj = None
    
    if request.method == 'POST':
        # Простая обработка POST данных
        team_id = request.POST.get('team_id', '')
        space_id = request.POST.get('space_id', '')
        list_id = request.POST.get('list_id', '')
        
        try:
            if settings_obj:
                settings_obj.team_id = team_id
                settings_obj.space_id = space_id
                settings_obj.list_id = list_id
                settings_obj.save()
            else:
                settings_obj = ClickUpSettings.objects.create(
                    user=user,
                    team_id=team_id,
                    space_id=space_id,
                    list_id=list_id
                )
            
            messages.success(request, 'Настройки ClickUp успешно сохранены')
            return redirect('clickup_int:dashboard')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении настроек: {str(e)}')
    
    context = ContextHelper.get_base_context(
        request,
        'Настройки ClickUp',
        {
            'settings': settings_obj,
            'user': user
        }
    )
    
    return render(request, 'clickup_int/settings.html', context)


@login_required
def tasks_list(request):
    """
    Список задач ClickUp
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user, request.GET (search, status, priority, page)
    ИСТОЧНИКИ ДАННЫЕ: ClickUpTask
    ОБРАБОТКА: Фильтрация и пагинация задач
    ВЫХОДЯЩИЕ ДАННЫЕ: context → clickup/tasks_list.html
    СВЯЗИ: ClickUpTask
    ФОРМАТ: HTML render
    """
    user = request.user
    
    # Параметры поиска и фильтрации
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    
    # Базовый queryset
    tasks = ClickUpTask.objects.filter(user=user)
    
    # Применяем фильтры
    if search_query:
        tasks = tasks.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Пагинация
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Задачи ClickUp',
        {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'priority_filter': priority_filter,
            'total_count': tasks.count()
        }
    )
    
    return render(request, 'clickup_int/tasks_list.html', context)


@login_required
def task_detail(request, task_id):
    """
    Детальная информация о задаче ClickUp
    
    ВХОДЯЩИЕ ДАННЫЕ: task_id, request.user
    ИСТОЧНИКИ ДАННЫЕ: ClickUpTask
    ОБРАБОТКА: Получение детальной информации о задаче
    ВЫХОДЯЩИЕ ДАННЫЕ: context → clickup/task_detail.html
    СВЯЗИ: ClickUpTask
    ФОРМАТ: HTML render
    """
    user = request.user
    task = get_object_or_404(ClickUpTask, id=task_id, user=user)
    
    context = ContextHelper.get_base_context(
        request,
        f'Задача: {task.name}',
        {
            'task': task
        }
    )
    
    return render(request, 'clickup_int/task_detail.html', context)


@login_required
@require_POST
def test_connection(request):
    """
    Тестирование подключения к ClickUp API
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: ClickUpService
    ОБРАБОТКА: Тестирование подключения к ClickUp API
    ВЫХОДЯЩИЕ ДАННЫЕ: JsonResponse с результатом теста
    СВЯЗИ: ClickUpService
    ФОРМАТ: JSON
    """
    try:
        user = request.user
        
        if not user.clickup_api_key:
            return JsonResponse({
                'success': False,
                'message': 'API ключ ClickUp не настроен'
            })
        
        # Создаем сервис ClickUp
        clickup_service = ClickUpService(user.clickup_api_key)
        
        # Тестируем подключение
        connection_result = clickup_service.test_connection()
        
        if connection_result:
            return JsonResponse({
                'success': True,
                'message': 'Подключение к ClickUp API успешно'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось подключиться к ClickUp API'
            })
            
    except ClickUpAPIError as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка ClickUp API: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Ошибка тестирования подключения ClickUp: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при тестировании подключения: {str(e)}'
        })


@login_required
@require_POST
def sync_tasks(request):
    """Синхронизация задач с ClickUp"""
    try:
        user = request.user
        
        if not user.clickup_api_key:
            return JsonResponse({
                'success': False,
                'message': 'API ключ ClickUp не настроен'
            })
        
        # Получаем настройки пользователя
        try:
            settings = ClickUpSettings.objects.get(user=user)
        except ClickUpSettings.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Настройки ClickUp не найдены'
            })
        
        # Создаем сервис ClickUp
        clickup_service = ClickUpService(user.clickup_api_key)
        
        # Синхронизируем задачи
        sync_result = clickup_service.sync_tasks(settings.team_id, settings.space_id, settings.list_id, user)
        
        if sync_result:
            return JsonResponse({
                'success': True,
                'message': 'Синхронизация задач завершена успешно'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при синхронизации задач'
            })
            
    except ClickUpAPIError as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка ClickUp API: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Ошибка синхронизации ClickUp: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при синхронизации: {str(e)}'
        })


@login_required
def sync_logs(request):
    """Логи синхронизации ClickUp"""
    user = request.user
    
    # Получаем логи синхронизации
    logs = ClickUpSyncLog.objects.filter(user=user).order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Логи синхронизации ClickUp',
        {
            'page_obj': page_obj,
            'total_count': logs.count()
        }
    )
    
    return render(request, 'clickup_int/sync_logs.html', context)


@login_required
@require_POST
def bulk_import(request):
    """Массовый импорт задач ClickUp"""
    try:
        user = request.user
        
        if not user.clickup_api_key:
            return JsonResponse({
                'success': False,
                'message': 'API ключ ClickUp не настроен'
            })
        
        # Получаем настройки пользователя
        try:
            settings = ClickUpSettings.objects.get(user=user)
        except ClickUpSettings.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Настройки ClickUp не найдены'
            })
        
        # Создаем запись о массовом импорте
        bulk_import_obj = ClickUpBulkImport.objects.create(
            user=user,
            status='PENDING',
            total_tasks=0
        )
        
        # Здесь должна быть логика запуска Celery задачи
        # bulk_import_clickup_tasks.delay(bulk_import_obj.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Массовый импорт запущен',
            'bulk_import_id': bulk_import_obj.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка массового импорта ClickUp: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при запуске массового импорта: {str(e)}'
        })


@login_required
def bulk_import_status(request, bulk_import_id):
    """Статус массового импорта ClickUp"""
    user = request.user
    bulk_import_obj = get_object_or_404(ClickUpBulkImport, id=bulk_import_id, user=user)
    
    context = ContextHelper.get_base_context(
        request,
        'Статус массового импорта',
        {
            'bulk_import': bulk_import_obj
        }
    )
    
    return render(request, 'clickup_int/bulk_import_status.html', context)
