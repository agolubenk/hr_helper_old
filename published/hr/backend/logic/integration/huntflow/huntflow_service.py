"""Основной сервис для работы с Huntflow"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from logic.utilities.context_helpers import ContextHelper
from logic.base.response_handler import UnifiedResponseHandler
from apps.huntflow.services import HuntflowService


def get_correct_account_id(user, fallback_account_id=None):
    """
    Получает правильный account_id пользователя из Huntflow API
    
    ВХОДЯЩИЕ ДАННЫЕ: user (пользователь), fallback_account_id (строка)
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService, Huntflow API
    ОБРАБОТКА: Получение account_id из API или использование fallback
    ВЫХОДЯЩИЕ ДАННЫЕ: Правильный account_id
    СВЯЗИ: HuntflowService
    ФОРМАТ: Строка с account_id
    """
    try:
        huntflow_service = HuntflowService(user)
        accounts = huntflow_service.get_accounts()
        
        if accounts and 'items' in accounts and accounts['items']:
            account_id = accounts['items'][0]['id']
            print(f"🔍 Получен account_id из API: {account_id}")
            return account_id
        else:
            print(f"⚠️ Не удалось получить account_id из API, используем fallback: {fallback_account_id}")
            return fallback_account_id
            
    except Exception as e:
        print(f"❌ Ошибка получения account_id: {e}")
        return fallback_account_id


@login_required
def huntflow_dashboard(request):
    """
    Главная страница интеграции с Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: User.huntflow_prod_url, User.huntflow_sandbox_url
    ОБРАБОТКА: Проверка настроек Huntflow и получение статистики
    ВЫХОДЯЩИЕ ДАННЫЕ: context → huntflow/dashboard.html
    СВЯЗИ: HuntflowService
    ФОРМАТ: HTML render
    """
    try:
        # Проверяем, настроен ли Huntflow у пользователя
        if not request.user.huntflow_prod_url and not request.user.huntflow_sandbox_url:
            messages.warning(request, 'Huntflow не настроен. Обратитесь к администратору.')
            return render(request, 'huntflow/dashboard.html', {
                'huntflow_configured': False
            })
        
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Тестируем подключение
        connection_test = huntflow_service.test_connection()
        
        if not connection_test:
            messages.error(request, 'Не удалось подключиться к Huntflow API. Проверьте настройки.')
            return render(request, 'huntflow/dashboard.html', {
                'huntflow_configured': True,
                'connection_test': False
            })
        
        # Получаем список организаций
        accounts = huntflow_service.get_accounts()
        
        # Извлекаем список организаций из ответа API
        accounts_list = accounts.get('items', []) if accounts else []
        
        context = ContextHelper.get_base_context(
            request,
            'Интеграция с Huntflow',
            {
                'huntflow_configured': True,
                'connection_test': True,
                'accounts': accounts_list,
                'accounts_for_menu': {'items': accounts_list},
                'active_system': request.user.active_system,
                'base_url': huntflow_service._get_base_url()
            }
        )
        
        return render(request, 'huntflow/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке данных Huntflow: {str(e)}')
        context = ContextHelper.get_base_context(
            request,
            'Интеграция с Huntflow',
            {
                'huntflow_configured': True,
                'connection_test': False,
                'error': str(e)
            }
        )
        return render(request, 'huntflow/dashboard.html', context)


@login_required
def vacancies_list(request, account_id):
    """
    Список вакансий для организации
    
    ВХОДЯЩИЕ ДАННЫЕ: account_id, request.user
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService, Huntflow API
    ОБРАБОТКА: Получение списка вакансий для организации
    ВЫХОДЯЩИЕ ДАННЫЕ: context → huntflow/vacancies_list.html
    СВЯЗИ: HuntflowService, get_correct_account_id
    ФОРМАТ: HTML render
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Получаем список вакансий
        vacancies = huntflow_service.get_vacancies(correct_account_id)
        
        # Извлекаем список вакансий из ответа API
        vacancies_list = vacancies.get('items', []) if vacancies else []
        
        context = ContextHelper.get_base_context(
            request,
            f'Вакансии организации {correct_account_id}',
            {
                'account_id': correct_account_id,
                'vacancies': vacancies_list,
                'total_count': len(vacancies_list)
            }
        )
        
        return render(request, 'huntflow/vacancies_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке вакансий: {str(e)}')
        return render(request, 'huntflow/vacancies_list.html', {
            'account_id': account_id,
            'vacancies': [],
            'total_count': 0,
            'error': str(e)
        })


@login_required
def candidates_list(request, account_id):
    """
    Список кандидатов для организации
    
    ВХОДЯЩИЕ ДАННЫЕ: account_id, request.user
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService, Huntflow API
    ОБРАБОТКА: Получение списка кандидатов для организации
    ВЫХОДЯЩИЕ ДАННЫЕ: context → huntflow/candidates_list.html
    СВЯЗИ: HuntflowService, get_correct_account_id
    ФОРМАТ: HTML render
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Получаем список кандидатов
        candidates = huntflow_service.get_candidates(correct_account_id)
        
        # Извлекаем список кандидатов из ответа API
        candidates_list = candidates.get('items', []) if candidates else []
        
        context = ContextHelper.get_base_context(
            request,
            f'Кандидаты организации {correct_account_id}',
            {
                'account_id': correct_account_id,
                'candidates': candidates_list,
                'total_count': len(candidates_list)
            }
        )
        
        return render(request, 'huntflow/candidates_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке кандидатов: {str(e)}')
        return render(request, 'huntflow/candidates_list.html', {
            'account_id': account_id,
            'candidates': [],
            'total_count': 0,
            'error': str(e)
        })


@login_required
def huntflow_settings(request):
    """
    Настройки интеграции с Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: User.active_system
    ОБРАБОТКА: Получение настроек пользователя
    ВЫХОДЯЩИЕ ДАННЫЕ: context → huntflow/settings.html
    СВЯЗИ: ContextHelper
    ФОРМАТ: HTML render
    """
    try:
        context = ContextHelper.get_base_context(
            request,
            'Настройки Huntflow',
            {
                'user': request.user,
                'active_system': request.user.active_system
            }
        )
        
        return render(request, 'huntflow/settings.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке настроек: {str(e)}')
        return render(request, 'huntflow/settings.html', {
            'user': request.user,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def huntflow_sync(request):
    """
    Синхронизация данных с Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: request.POST (sync_type, account_id), request.user
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService, Huntflow API
    ОБРАБОТКА: Синхронизация вакансий и кандидатов
    ВЫХОДЯЩИЕ ДАННЫЕ: JsonResponse с результатом синхронизации
    СВЯЗИ: HuntflowService, get_correct_account_id
    ФОРМАТ: JSON
    """
    try:
        # Получаем параметры синхронизации
        sync_type = request.POST.get('sync_type', 'all')
        account_id = request.POST.get('account_id')
        
        if not account_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID организации'
            })
        
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Выполняем синхронизацию в зависимости от типа
        if sync_type == 'vacancies':
            result = huntflow_service.sync_vacancies(correct_account_id)
        elif sync_type == 'candidates':
            result = huntflow_service.sync_candidates(correct_account_id)
        elif sync_type == 'all':
            # Синхронизируем все данные
            vacancies_result = huntflow_service.sync_vacancies(correct_account_id)
            candidates_result = huntflow_service.sync_candidates(correct_account_id)
            result = {
                'vacancies': vacancies_result,
                'candidates': candidates_result
            }
        else:
            return JsonResponse({
                'success': False,
                'message': f'Неизвестный тип синхронизации: {sync_type}'
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Синхронизация завершена успешно',
            'result': result
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при синхронизации: {str(e)}'
        })


@login_required
def huntflow_test_connection(request):
    """
    Тестирование подключения к Huntflow API
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService
    ОБРАБОТКА: Тестирование подключения к Huntflow API
    ВЫХОДЯЩИЕ ДАННЫЕ: JsonResponse с результатом теста
    СВЯЗИ: HuntflowService
    ФОРМАТ: JSON
    """
    try:
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Тестируем подключение
        connection_test = huntflow_service.test_connection()
        
        if connection_test:
            return JsonResponse({
                'success': True,
                'message': 'Подключение к Huntflow API успешно',
                'connection_status': 'connected'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось подключиться к Huntflow API',
                'connection_status': 'failed'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при тестировании подключения: {str(e)}',
            'connection_status': 'error'
        })


@login_required
def huntflow_clear_cache(request):
    """
    Очистка кэша Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: request.user
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService
    ОБРАБОТКА: Очистка кэша Huntflow
    ВЫХОДЯЩИЕ ДАННЫЕ: HTTP redirect на dashboard
    СВЯЗИ: HuntflowService
    ФОРМАТ: HTTP redirect
    """
    try:
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(request.user)
        
        # Очищаем кэш
        clear_result = huntflow_service.clear_cache()
        
        if clear_result:
            messages.success(request, 'Кэш Huntflow успешно очищен')
        else:
            messages.warning(request, 'Не удалось очистить кэш Huntflow')
        
        return redirect('huntflow:dashboard')
        
    except Exception as e:
        messages.error(request, f'Ошибка при очистке кэша: {str(e)}')
        return redirect('huntflow:dashboard')
