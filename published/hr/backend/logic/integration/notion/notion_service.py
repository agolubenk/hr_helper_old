"""Основной сервис для работы с Notion"""
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
from apps.notion_int.services import NotionService, NotionCacheService, NotionAPIError
from apps.notion_int.models import NotionSettings, NotionPage, NotionSyncLog, NotionBulkImport

logger = logging.getLogger(__name__)


@login_required
def settings(request):
    """
    Страница настроек Notion
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user, request.POST (database_id, page_title)
    ИСТОЧНИКИ ДАННЫЕ: NotionSettings, User.notion_integration_token
    ОБРАБОТКА: Получение/создание настроек, обработка POST запроса
    ВЫХОДЯЩИЕ ДАННЫЕ: context → notion/settings.html или redirect
    СВЯЗИ: NotionSettings
    ФОРМАТ: HTML render или HTTP redirect
    """
    user = request.user
    
    try:
        settings_obj = NotionSettings.objects.get(user=user)
    except NotionSettings.DoesNotExist:
        settings_obj = None
    
    # Проверяем, очищены ли настройки из-за изменения integration токена
    settings_cleared = False
    if (settings_obj and user.notion_integration_token and 
        not settings_obj.database_id):
        settings_cleared = True
        messages.warning(request, 
            'Настройки базы данных Notion были очищены из-за изменения integration токена. '
            'Пожалуйста, выберите новую базу данных.')
    
    if request.method == 'POST':
        # Простая обработка POST данных
        database_id = request.POST.get('database_id', '')
        page_title = request.POST.get('page_title', '')
        
        try:
            if settings_obj:
                settings_obj.database_id = database_id
                settings_obj.page_title = page_title
                settings_obj.save()
            else:
                settings_obj = NotionSettings.objects.create(
                    user=user,
                    database_id=database_id,
                    page_title=page_title
                )
            
            messages.success(request, 'Настройки Notion успешно сохранены')
            return redirect('notion_int:dashboard')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении настроек: {str(e)}')
    
    context = ContextHelper.get_base_context(
        request,
        'Настройки Notion',
        {
            'settings': settings_obj,
            'user': user,
            'settings_cleared': settings_cleared
        }
    )
    
    return render(request, 'notion_int/settings.html', context)


@login_required
def dashboard(request):
    """Главная страница интеграции с Notion"""
    user = request.user
    
    # Получаем настройки пользователя
    try:
        settings = NotionSettings.objects.get(user=user)
        is_configured = bool(user.notion_integration_token and settings.database_id)
    except NotionSettings.DoesNotExist:
        settings = None
        is_configured = False
    
    # Получаем статистику
    pages_count = NotionPage.objects.filter(user=user).count()
    recent_pages = NotionPage.objects.filter(user=user).order_by('-last_edited_time')[:5]
    
    # Получаем последние логи синхронизации
    recent_syncs = NotionSyncLog.objects.filter(user=user).order_by('-created_at')[:5]
    
    context = ContextHelper.get_base_context(
        request,
        'Интеграция с Notion',
        {
            'settings': settings,
            'is_configured': is_configured,
            'pages_count': pages_count,
            'recent_pages': recent_pages,
            'recent_syncs': recent_syncs
        }
    )
    
    return render(request, 'notion_int/dashboard.html', context)


@login_required
def pages_list(request):
    """Список страниц Notion"""
    user = request.user
    
    # Параметры поиска и фильтрации
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    # Базовый queryset
    pages = NotionPage.objects.filter(user=user)
    
    # Применяем фильтры
    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query)
        )
    
    if status_filter:
        pages = pages.filter(status=status_filter)
    
    # Пагинация
    paginator = Paginator(pages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Страницы Notion',
        {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'total_count': pages.count()
        }
    )
    
    return render(request, 'notion_int/pages_list.html', context)


@login_required
def page_detail(request, page_id):
    """Детальная информация о странице Notion"""
    user = request.user
    page = get_object_or_404(NotionPage, id=page_id, user=user)
    
    context = ContextHelper.get_base_context(
        request,
        f'Страница: {page.title}',
        {
            'page': page
        }
    )
    
    return render(request, 'notion_int/page_detail.html', context)


@login_required
@require_POST
def test_connection(request):
    """Тестирование подключения к Notion API"""
    try:
        user = request.user
        
        if not user.notion_integration_token:
            return JsonResponse({
                'success': False,
                'message': 'Integration токен Notion не настроен'
            })
        
        # Создаем сервис Notion
        notion_service = NotionService(user.notion_integration_token)
        
        # Тестируем подключение
        connection_result = notion_service.test_connection()
        
        if connection_result:
            return JsonResponse({
                'success': True,
                'message': 'Подключение к Notion API успешно'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось подключиться к Notion API'
            })
            
    except NotionAPIError as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка Notion API: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Ошибка тестирования подключения Notion: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при тестировании подключения: {str(e)}'
        })


@login_required
@require_POST
def sync_pages(request):
    """Синхронизация страниц с Notion"""
    try:
        user = request.user
        
        if not user.notion_integration_token:
            return JsonResponse({
                'success': False,
                'message': 'Integration токен Notion не настроен'
            })
        
        # Получаем настройки пользователя
        try:
            settings = NotionSettings.objects.get(user=user)
        except NotionSettings.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Настройки Notion не найдены'
            })
        
        # Создаем сервис Notion
        notion_service = NotionService(user.notion_integration_token)
        
        # Синхронизируем страницы
        sync_result = notion_service.sync_pages(settings.database_id, user)
        
        if sync_result:
            return JsonResponse({
                'success': True,
                'message': 'Синхронизация страниц завершена успешно'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при синхронизации страниц'
            })
            
    except NotionAPIError as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка Notion API: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Ошибка синхронизации Notion: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при синхронизации: {str(e)}'
        })


@login_required
def sync_logs(request):
    """Логи синхронизации Notion"""
    user = request.user
    
    # Получаем логи синхронизации
    logs = NotionSyncLog.objects.filter(user=user).order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = ContextHelper.get_base_context(
        request,
        'Логи синхронизации Notion',
        {
            'page_obj': page_obj,
            'total_count': logs.count()
        }
    )
    
    return render(request, 'notion_int/sync_logs.html', context)


@login_required
def bulk_import_view(request):
    """Страница массового импорта страниц Notion"""
    from logic.utilities.context_helpers import ContextHelper
    user = request.user
    
    # Получаем настройки пользователя
    try:
        settings = NotionSettings.objects.get(user=user)
        is_configured = bool(user.notion_integration_token and settings.database_id)
    except NotionSettings.DoesNotExist:
        settings = None
        is_configured = False
    
    # Получаем последние массовые импорты
    recent_imports = NotionBulkImport.objects.filter(user=user).order_by('-created_at')[:10]
    
    context = ContextHelper.get_base_context(
        request,
        'Массовый импорт страниц Notion',
        {
            'settings': settings,
            'is_configured': is_configured,
            'recent_imports': recent_imports,
        }
    )
    
    return render(request, 'notion_int/bulk_import.html', context)


@login_required
@require_POST
def bulk_import(request):
    """API для запуска массового импорта страниц Notion"""
    try:
        user = request.user
        
        if not user.notion_integration_token:
            return JsonResponse({
                'success': False,
                'message': 'Integration токен Notion не настроен'
            })
        
        # Получаем настройки пользователя
        try:
            settings = NotionSettings.objects.get(user=user)
            if not settings.database_id:
                return JsonResponse({
                    'success': False,
                    'message': 'База данных Notion не настроена'
                })
        except NotionSettings.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Настройки Notion не найдены'
            })
        
        # Создаем запись о массовом импорте
        bulk_import_obj = NotionBulkImport.objects.create(
            user=user,
            status='running',
            total_pages=0
        )
        
        # Запускаем Celery задачу
        try:
            from apps.notion_int.tasks import bulk_import_notion_pages
            # Передаем bulk_import_id в задачу, чтобы использовать существующий объект
            # Передаем все аргументы позиционно: user_id, database_id, bulk_import_id, max_pages
            bulk_import_notion_pages.delay(user.id, settings.database_id, bulk_import_obj.id, 100)
            logger.info(f"Запущена Celery задача для массового импорта #{bulk_import_obj.id} (user_id={user.id}, database_id={settings.database_id})")
        except Exception as e:
            logger.error(f"Ошибка запуска Celery задачи: {e}")
            bulk_import_obj.status = 'failed'
            bulk_import_obj.error_message = f"Ошибка запуска задачи: {str(e)}"
            bulk_import_obj.save()
            return JsonResponse({
                'success': False,
                'message': f'Ошибка запуска задачи: {str(e)}'
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Массовый импорт запущен',
            'bulk_import_id': bulk_import_obj.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка массового импорта Notion: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при запуске массового импорта: {str(e)}'
        })


@login_required
def bulk_import_status(request, bulk_import_id):
    """Статус массового импорта Notion"""
    user = request.user
    bulk_import_obj = get_object_or_404(NotionBulkImport, id=bulk_import_id, user=user)
    
    context = ContextHelper.get_base_context(
        request,
        'Статус массового импорта',
        {
            'bulk_import': bulk_import_obj
        }
    )
    
    return render(request, 'notion_int/bulk_import_status.html', context)
