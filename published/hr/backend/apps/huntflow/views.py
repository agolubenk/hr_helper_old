# Импорты из новых модулей
from logic.integration.huntflow.huntflow_service import (
    huntflow_dashboard, vacancies_list, candidates_list,
    huntflow_settings, huntflow_sync, huntflow_test_connection,
    huntflow_clear_cache
)
from logic.base.response_handler import UnifiedResponseHandler

# Старые импорты (для совместимости)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import json
import logging

from .services import HuntflowService
from .forms import CreateApplicantForm

logger = logging.getLogger(__name__)


def get_correct_account_id(user, fallback_account_id=None):
    """
    Получает правильный account_id пользователя из Huntflow API
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - user: пользователь Django
    - fallback_account_id: резервный account_id если не удалось получить из API
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение списка аккаунтов пользователя
    
    ОБРАБОТКА:
    - Создание HuntflowService для пользователя
    - Получение списка аккаунтов из API
    - Извлечение первого доступного account_id
    - Обработка ошибок с fallback значением
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - account_id: правильный ID аккаунта для работы с Huntflow API
    
    СВЯЗИ:
    - Использует: HuntflowService, Huntflow API
    - Передает: account_id для использования в других функциях
    - Может вызываться из: huntflow views, services
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
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь с настройками Huntflow
    
    ИСТОЧНИКИ ДАННЫЕ:
    - request.user.huntflow_prod_url, request.user.huntflow_sandbox_url
    - HuntflowService для получения данных из API
    
    ОБРАБОТКА:
    - Проверка настройки Huntflow у пользователя
    - Получение статистики из Huntflow API
    - Обработка ошибок и отображение соответствующих сообщений
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными Huntflow и статистикой
    - render: HTML страница 'huntflow/dashboard.html'
    
    СВЯЗИ:
    - Использует: HuntflowService, messages
    - Передает данные в: huntflow/dashboard.html
    - Может вызываться из: huntflow/ URL patterns
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
        
        context = {
            'huntflow_configured': True,
            'connection_test': True,
            'accounts': accounts_list,  # Для dashboard.html
            'accounts_for_menu': {'items': accounts_list},  # Для template tag
            'active_system': request.user.active_system,
            'base_url': huntflow_service._get_base_url()
        }
        
        return render(request, 'huntflow/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке данных Huntflow: {str(e)}')
        return render(request, 'huntflow/dashboard.html', {
            'huntflow_configured': True,
            'connection_test': False,
            'error': str(e)
        })


@login_required
def vacancies_list(request, account_id):
    """
    Список вакансий для организации
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - request.GET: page, count, state (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение списка вакансий и статусов
    
    ОБРАБОТКА:
    - Получение правильного account_id через get_correct_account_id
    - Фильтрация вакансий по статусу
    - Получение статусов для фильтрации
    - Получение информации об организации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с вакансиями, статусами и информацией об организации
    - render: HTML страница 'huntflow/vacancies_list.html'
    
    СВЯЗИ:
    - Использует: HuntflowService, get_correct_account_id
    - Передает данные в: huntflow/vacancies_list.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем параметры фильтрации
        page = request.GET.get('page', 1)
        count = request.GET.get('count', 30)
        state = request.GET.get('state', '')
        
        # Получаем вакансии с правильным account_id
        vacancies = huntflow_service.get_vacancies(
            account_id=correct_account_id,
            page=page,
            count=count,
            state=state if state else None
        )
        
        # Получаем статусы для фильтрации
        statuses = huntflow_service.get_vacancy_statuses(correct_account_id)
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {account_id}'
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == account_id:
                    account_name = account.get('name', account_name)
                    break
        
        context = {
            'account_id': correct_account_id,  # Используем правильный account_id
            'account_name': account_name,
            'accounts': accounts,  # Добавляем для sidebar menu
            'vacancies': vacancies,
            'statuses': statuses,
            'current_page': int(page),
            'current_count': int(count),
            'current_state': state
        }
        
        return render(request, 'huntflow/vacancies_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке вакансий: {str(e)}')
        return redirect('huntflow:dashboard')


@login_required
def vacancy_detail(request, account_id, vacancy_id):
    """
    Детальная информация о вакансии
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - vacancy_id: ID вакансии
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение информации о вакансии и дополнительных полей
    
    ОБРАБОТКА:
    - Получение правильного account_id через get_correct_account_id
    - Получение информации о вакансии
    - Получение дополнительных полей вакансии
    - Получение информации об организации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными вакансии и дополнительными полями
    - render: HTML страница 'huntflow/vacancy_detail.html'
    
    СВЯЗИ:
    - Использует: HuntflowService, get_correct_account_id
    - Передает данные в: huntflow/vacancy_detail.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем информацию о вакансии с правильным account_id
        vacancy = huntflow_service.get_vacancy(correct_account_id, vacancy_id)
        
        if not vacancy:
            messages.error(request, 'Вакансия не найдена')
            return redirect('huntflow:vacancies_list', account_id=correct_account_id)
        
        # Получаем дополнительные поля
        additional_fields = huntflow_service.get_vacancy_additional_fields(correct_account_id)
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {account_id}'
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == account_id:
                    account_name = account.get('name', account_name)
                    break
        
        context = {
            'account_id': correct_account_id,  # Используем правильный account_id
            'account_name': account_name,
            'accounts': accounts,  # Добавляем для sidebar menu
            'vacancy': vacancy,
            'vacancy_name': vacancy.get('position', f'Вакансия {vacancy_id}') if vacancy else f'Вакансия {vacancy_id}',
            'additional_fields': additional_fields
        }
        
        return render(request, 'huntflow/vacancy_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке вакансии: {str(e)}')
        return redirect('huntflow:vacancies_list', account_id=account_id)


@login_required
def applicants_list(request, account_id):
    """
    Список кандидатов для организации
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - request.GET: page, count, status, vacancy (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение списка кандидатов, статусов и вакансий
    
    ОБРАБОТКА:
    - Получение правильного account_id через get_correct_account_id
    - Фильтрация кандидатов по статусу и вакансии
    - Получение статусов и вакансий для фильтрации
    - Обогащение данных кандидатов информацией о статусах и вакансиях
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с кандидатами, статусами и вакансиями
    - render: HTML страница 'huntflow/applicants_list.html'
    
    СВЯЗИ:
    - Использует: HuntflowService, get_correct_account_id
    - Передает данные в: huntflow/applicants_list.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем параметры фильтрации
        page = request.GET.get('page', 1)
        count = request.GET.get('count', 30)
        status = request.GET.get('status', '')
        vacancy = request.GET.get('vacancy', '')
        
        # Получаем кандидатов с правильным account_id
        applicants = huntflow_service.get_applicants(
            account_id=correct_account_id,
            page=page,
            count=count,
            status=status if status else None,
            vacancy=vacancy if vacancy else None
        )
        
        # Получаем статусы для фильтрации
        statuses = huntflow_service.get_vacancy_statuses(correct_account_id)
        
        # Получаем вакансии для фильтрации
        vacancies = huntflow_service.get_vacancies(correct_account_id, count=100)
        
        # Создаем словари для быстрого поиска
        statuses_dict = {}
        if statuses and 'items' in statuses:
            for status_item in statuses['items']:
                statuses_dict[status_item['id']] = status_item
        
        vacancies_dict = {}
        if vacancies and 'items' in vacancies:
            for vacancy_item in vacancies['items']:
                vacancies_dict[vacancy_item['id']] = vacancy_item
        
        # Обогащаем данные кандидатов
        if applicants and 'items' in applicants:
            for applicant in applicants['items']:
                if applicant.get('links') and len(applicant['links']) > 0:
                    link = applicant['links'][0]
                    if 'status' in link and link['status'] in statuses_dict:
                        applicant['status_info'] = statuses_dict[link['status']]
                    if 'vacancy' in link and link['vacancy'] in vacancies_dict:
                        applicant['vacancy_info'] = vacancies_dict[link['vacancy']]
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {account_id}'
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == account_id:
                    account_name = account.get('name', account_name)
                    break
        
        context = {
            'account_id': correct_account_id,  # Используем правильный account_id
            'account_name': account_name,
            'accounts': accounts,  # Добавляем для sidebar menu
            'applicants': applicants,
            'statuses': statuses,
            'vacancies': vacancies,
            'current_page': int(page),
            'current_count': int(count),
            'current_status': status,
            'current_vacancy': vacancy
        }
        
        return render(request, 'huntflow/applicants_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке кандидатов: {str(e)}')
        return redirect('huntflow:dashboard')


@login_required
def applicant_detail(request, account_id, applicant_id):
    """
    Детальная информация о кандидате
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - applicant_id: ID кандидата
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение информации о кандидате, анкете, логах, статусах, вакансиях и метках
    
    ОБРАБОТКА:
    - Получение правильного account_id через get_correct_account_id
    - Получение информации о кандидате и его анкете
    - Получение схемы анкеты
    - Получение логов кандидата для поиска комментариев
    - Обогащение данных кандидата информацией о статусах, вакансиях и метках
    - Обработка логов для отображения истории изменений
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными кандидата, анкетой, логами и комментариями
    - render: HTML страница 'huntflow/applicant_detail.html'
    
    СВЯЗИ:
    - Использует: HuntflowService, get_correct_account_id
    - Передает данные в: huntflow/applicant_detail.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем информацию о кандидате с правильным account_id
        applicant = huntflow_service.get_applicant(correct_account_id, applicant_id)
        
        if not applicant:
            messages.error(request, 'Кандидат не найден')
            return redirect('huntflow:applicants_list', account_id=correct_account_id)
        
        # Получаем анкету кандидата
        questionary = huntflow_service.get_applicant_questionary(correct_account_id, applicant_id)
        
        # Получаем схему анкеты
        questionary_schema = huntflow_service.get_applicant_questionary_schema(correct_account_id)
        
        # Получаем логи кандидата для поиска комментариев
        applicant_logs = huntflow_service.get_applicant_logs(correct_account_id, applicant_id)
        # print(f"DEBUG: Получены логи кандидата {applicant_id}: {applicant_logs}")
        
        # Получаем статусы, вакансии и метки для обогащения данных
        statuses = huntflow_service.get_vacancy_statuses(correct_account_id)
        vacancies = huntflow_service.get_vacancies(correct_account_id, count=100)
        tags = huntflow_service.get_tags(correct_account_id)
        
        # Создаем словари для быстрого поиска
        statuses_dict = {}
        if statuses and 'items' in statuses:
            for status_item in statuses['items']:
                statuses_dict[status_item['id']] = status_item
        
        vacancies_dict = {}
        if vacancies and 'items' in vacancies:
            for vacancy_item in vacancies['items']:
                vacancies_dict[vacancy_item['id']] = vacancy_item
        
        tags_dict = {}
        if tags and 'items' in tags:
            for tag_item in tags['items']:
                tags_dict[tag_item['id']] = tag_item
        
        # Извлекаем логи кандидата (все типы)
        applicant_logs_processed = []
        if applicant_logs and 'items' in applicant_logs:
            for log in applicant_logs['items']:
                # Получаем информацию о статусе, если есть
                status_info = None
                if log.get('status') and log['status'] in statuses_dict:
                    status_info = statuses_dict[log['status']]
                
                # Получаем информацию о вакансии, если есть
                vacancy_info = None
                if log.get('vacancy') and log['vacancy'] in vacancies_dict:
                    vacancy_info = vacancies_dict[log['vacancy']]
                
                # Определяем тип лога для отображения
                log_type_display = {
                    'ADD': 'Создан',
                    'UPDATE': 'Обновлен',
                    'VACANCY-ADD': 'Добавлен к вакансии',
                    'STATUS': 'Изменен статус',
                    'COMMENT': 'Комментарий',
                    'DOUBLE': 'Дублирование',
                    'AGREEMENT': 'Согласие',
                    'MAIL': 'Письмо',
                    'RESPONSE': 'Ответ'
                }.get(log.get('type'), log.get('type', 'Неизвестно'))
                
                # Обрабатываем комментарий - убираем префикс "Изменение статуса:"
                comment_text = log.get('comment', '')
                if comment_text and comment_text.startswith('Изменение статуса:'):
                    comment_text = comment_text.replace('Изменение статуса:', '').strip()
                
                # Создаем объект лога для отображения
                log_item = {
                    'type': log.get('type'),
                    'type_display': log_type_display,
                    'created': log.get('created'),
                    'author': log.get('account_info', {}).get('name') or log.get('account_info', {}).get('email', 'Неизвестно'),
                    'status': status_info,
                    'vacancy': vacancy_info,
                    'vacancy_id': log.get('vacancy'),
                    'comment': comment_text,
                    'files': log.get('files', []),
                    'email': log.get('email'),
                    'im': log.get('im'),
                    'sms': log.get('sms')
                }
                
                # Если это лог изменения статуса, но нет комментария, создаем его из статуса
                if log.get('type') == 'STATUS' and not log.get('comment') and status_info:
                    log_item['comment'] = f"Статус изменен на: {status_info['name']}"
                
                applicant_logs_processed.append(log_item)
        
        # Отдельно извлекаем комментарии для карточки комментариев
        comments = [log for log in applicant_logs_processed if log['comment']]
        
        # Подсчитываем количество комментариев с содержимым
        comments_count = len(comments)
        
        # Обогащаем данные кандидата
        if applicant.get('links') and len(applicant['links']) > 0:
            link = applicant['links'][0]
            if 'status' in link and link['status'] in statuses_dict:
                applicant['status_info'] = statuses_dict[link['status']]
            if 'vacancy' in link and link['vacancy'] in vacancies_dict:
                applicant['vacancy_info'] = vacancies_dict[link['vacancy']]
        
        # Обогащаем метки кандидата
        if applicant.get('tags'):
            enriched_tags = []
            for tag in applicant['tags']:
                if isinstance(tag, dict) and 'tag' in tag:
                    tag_id = tag['tag']
                    if tag_id in tags_dict:
                        enriched_tags.append(tags_dict[tag_id])
                    else:
                        # Если метка не найдена в словаре, создаем базовую структуру
                        enriched_tags.append({
                            'id': tag_id,
                            'name': f'Метка {tag_id}',
                            'color': '#6c757d'
                        })
                else:
                    # Если метка уже в правильном формате
                    enriched_tags.append(tag)
            applicant['enriched_tags'] = enriched_tags
        
        # Объединяем данные анкеты со схемой
        enriched_questionary = {}
        if questionary and questionary_schema:
            for field_key, field_value in questionary.items():
                if field_key in questionary_schema:
                    enriched_questionary[field_key] = {
                        'title': questionary_schema[field_key].get('title', field_key),
                        'value': field_value,
                        'type': questionary_schema[field_key].get('type', 'unknown'),
                        'required': questionary_schema[field_key].get('required', False),
                        'options': questionary_schema[field_key].get('options', questionary_schema[field_key].get('choices', questionary_schema[field_key].get('values', []))),  # Добавляем опции для select полей
                        'schema': questionary_schema[field_key]  # Передаем полную схему поля
                    }
                else:
                    enriched_questionary[field_key] = {
                        'title': field_key,
                        'value': field_value,
                        'type': 'unknown',
                        'required': False,
                        'options': [],
                        'schema': {}
                    }
        elif questionary:
            # Если нет схемы, создаем простую структуру
            for field_key, field_value in questionary.items():
                enriched_questionary[field_key] = {
                    'title': field_key,
                    'value': field_value,
                    'type': 'unknown',
                    'required': False
                }
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {account_id}'
        account_slug = None  # Для формирования URL
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == account_id:
                    account_name = account.get('name', account_name)
                    # Формируем slug для URL (название в нижнем регистре, без пробелов и спецсимволов)
                    import re
                    account_slug = re.sub(r'[^a-z0-9]', '', account_name.lower()) if account_name else None
                    break
        
        # Получаем ID вакансии для формирования ссылки
        vacancy_id_for_link = None
        if applicant.get('vacancy_info') and applicant['vacancy_info'].get('id'):
            vacancy_id_for_link = applicant['vacancy_info']['id']
        elif applicant.get('links') and len(applicant['links']) > 0:
            # Пытаемся получить из links
            link = applicant['links'][0]
            if 'vacancy' in link:
                vacancy_id_for_link = link['vacancy']
        
        # Формируем имя кандидата для хлебных крошек
        applicant_name = f'Кандидат {applicant_id}'
        if applicant.get('first_name') or applicant.get('last_name'):
            applicant_name = f"{applicant.get('first_name', '')} {applicant.get('last_name', '')}".strip()
        
        # Формируем ссылку на кандидата в Huntflow
        huntflow_link = None
        if account_slug and vacancy_id_for_link:
            base_url = huntflow_service._get_base_url()
            # Извлекаем домен из base_url (например, https://api.huntflow.ru/v2 -> https://huntflow.ru)
            if 'api.huntflow' in base_url:
                domain = base_url.replace('api.huntflow', 'huntflow').replace('/v2', '').replace('/api', '').rstrip('/')
            elif 'huntflow.ru' in base_url or 'huntflow.dev' in base_url:
                domain = base_url.replace('/v2', '').replace('/api', '').rstrip('/')
            else:
                domain = 'https://huntflow.ru'
            
            huntflow_link = f"{domain}/my/{account_slug}#/vacancy/{vacancy_id_for_link}/filter/workon/id/{applicant_id}"
        
        context = {
            'account_id': correct_account_id,  # Используем правильный account_id
            'account_name': account_name,
            'account_slug': account_slug,
            'accounts': accounts,  # Добавляем для sidebar menu
            'applicant': applicant,
            'applicant_name': applicant_name,
            'questionary': enriched_questionary,
            'questionary_schema': questionary_schema,
            'applicant_logs': applicant_logs_processed,
            'comments': comments,
            'comments_count': comments_count,
            'huntflow_link': huntflow_link,
            'vacancy_id_for_link': vacancy_id_for_link
        }
        
        
        # print(f"DEBUG: Финальные данные кандидата для отображения: {applicant}")
        # print(f"DEBUG: Количество логов: {len(applicant_logs_processed)}")
        # print(f"DEBUG: Количество комментариев: {comments_count}")
        
        return render(request, 'huntflow/applicant_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке кандидата: {str(e)}')
        return redirect('huntflow:applicants_list', account_id=account_id)


@login_required
def applicant_edit(request, account_id, applicant_id):
    """
    Редактирование кандидата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - applicant_id: ID кандидата
    - request.user: аутентифицированный пользователь
    - request.POST: данные для обновления кандидата (first_name, last_name, email, phone, tags, status_id, status_comment, questionary_*)
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение и обновление информации о кандидате
    
    ОБРАБОТКА:
    - Получение правильного account_id через get_correct_account_id
    - Получение текущих данных кандидата
    - Обработка POST запроса для обновления данных
    - Обновление основных полей кандидата
    - Обновление меток кандидата
    - Обновление анкеты кандидата
    - Обновление статуса кандидата с комментарием
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными кандидата для редактирования
    - render: HTML страница 'huntflow/applicant_edit.html'
    - redirect: на страницу детальной информации о кандидате после успешного обновления
    
    СВЯЗИ:
    - Использует: HuntflowService, get_correct_account_id
    - Передает данные в: huntflow/applicant_edit.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user, account_id)
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем информацию о кандидате с правильным account_id
        applicant = huntflow_service.get_applicant(correct_account_id, applicant_id)
        
        if not applicant:
            messages.error(request, 'Кандидат не найден')
            return redirect('huntflow:applicants_list', account_id=correct_account_id)
        
        # Получаем анкету кандидата
        questionary = huntflow_service.get_applicant_questionary(correct_account_id, applicant_id)
        
        # Получаем схему анкеты
        questionary_schema = huntflow_service.get_applicant_questionary_schema(correct_account_id)
        
        # Получаем статусы, вакансии и метки для обогащения данных
        statuses = huntflow_service.get_vacancy_statuses(correct_account_id)
        vacancies = huntflow_service.get_vacancies(correct_account_id, count=100)
        tags = huntflow_service.get_tags(correct_account_id)
        
        # Создаем словари для быстрого поиска
        statuses_dict = {}
        if statuses and 'items' in statuses:
            for status_item in statuses['items']:
                statuses_dict[status_item['id']] = status_item
        
        vacancies_dict = {}
        if vacancies and 'items' in vacancies:
            for vacancy_item in vacancies['items']:
                vacancies_dict[vacancy_item['id']] = vacancy_item
        
        tags_dict = {}
        if tags and 'items' in tags:
            for tag_item in tags['items']:
                tags_dict[tag_item['id']] = tag_item
        
        # Обогащаем данные кандидата
        if applicant.get('links') and len(applicant['links']) > 0:
            link = applicant['links'][0]
            if 'status' in link and link['status'] in statuses_dict:
                applicant['status_info'] = statuses_dict[link['status']]
            if 'vacancy' in link and link['vacancy'] in vacancies_dict:
                applicant['vacancy_info'] = vacancies_dict[link['vacancy']]
        
        # Обогащаем метки кандидата
        if applicant.get('tags'):
            enriched_tags = []
            for tag in applicant['tags']:
                if isinstance(tag, dict) and 'tag' in tag:
                    tag_id = tag['tag']
                    if tag_id in tags_dict:
                        enriched_tags.append(tags_dict[tag_id])
                    else:
                        # Если метка не найдена в словаре, создаем базовую структуру
                        enriched_tags.append({
                            'id': tag_id,
                            'name': f'Метка {tag_id}',
                            'color': '#6c757d'
                        })
                else:
                    # Если метка уже в правильном формате
                    enriched_tags.append(tag)
            applicant['enriched_tags'] = enriched_tags
        
        # Объединяем данные анкеты со схемой
        enriched_questionary = {}
        if questionary and questionary_schema:
            for field_key, field_value in questionary.items():
                if field_key in questionary_schema:
                    enriched_questionary[field_key] = {
                        'title': questionary_schema[field_key].get('title', field_key),
                        'value': field_value,
                        'type': questionary_schema[field_key].get('type', 'unknown'),
                        'required': questionary_schema[field_key].get('required', False),
                        'options': questionary_schema[field_key].get('options', questionary_schema[field_key].get('choices', questionary_schema[field_key].get('values', []))),  # Добавляем опции для select полей
                        'schema': questionary_schema[field_key]  # Передаем полную схему поля
                    }
                else:
                    enriched_questionary[field_key] = {
                        'title': field_key,
                        'value': field_value,
                        'type': 'unknown',
                        'required': False,
                        'options': [],
                        'schema': {}
                    }
        elif questionary:
            # Если нет схемы, создаем простую структуру
            for field_key, field_value in questionary.items():
                enriched_questionary[field_key] = {
                    'title': field_key,
                    'value': field_value,
                    'type': 'unknown',
                    'required': False
                }
        elif questionary_schema:
            # Если есть схема, но нет данных анкеты, создаем пустые поля
            for field_key, field_info in questionary_schema.items():
                enriched_questionary[field_key] = {
                    'title': field_info.get('title', field_key),
                    'value': None,
                    'type': field_info.get('type', 'unknown'),
                    'required': field_info.get('required', False),
                    'options': field_info.get('options', field_info.get('choices', field_info.get('values', []))),
                    'schema': field_info
                }
        
        if request.method == 'POST':
            # Обработка формы редактирования
            try:
                print(f"DEBUG: POST данные: {dict(request.POST)}")
                success_messages = []
                error_messages = []
                
                # 1. Собираем все данные для обновления в один запрос
                update_data = {}
                
                # Основные поля - всегда отправляем, даже если пустые
                if 'first_name' in request.POST:
                    update_data['first_name'] = request.POST['first_name'].strip() or None
                if 'last_name' in request.POST:
                    update_data['last_name'] = request.POST['last_name'].strip() or None
                if 'middle_name' in request.POST:
                    update_data['middle_name'] = request.POST['middle_name'].strip() or None
                if 'email' in request.POST:
                    update_data['email'] = request.POST['email'].strip() or None
                if 'phone' in request.POST:
                    update_data['phone'] = request.POST['phone'].strip() or None
                if 'money' in request.POST:
                    update_data['money'] = request.POST['money'].strip() or None
                if 'telegram' in request.POST:
                    # Обновляем Telegram в социальных сетях
                    telegram_value = request.POST['telegram'].strip()
                    if telegram_value:
                        # Если есть существующие социальные сети, обновляем Telegram
                        if 'social' not in update_data:
                            update_data['social'] = applicant.get('social', [])
                        
                        # Ищем существующий Telegram
                        telegram_found = False
                        for social in update_data['social']:
                            if social.get('social_type') == 'TELEGRAM':
                                social['value'] = telegram_value
                                telegram_found = True
                                break
                        
                        # Если Telegram не найден, добавляем новый
                        if not telegram_found:
                            update_data['social'].append({
                                'social_type': 'TELEGRAM',
                                'value': telegram_value
                            })
                    else:
                        # Если поле пустое, удаляем Telegram
                        if 'social' not in update_data:
                            update_data['social'] = applicant.get('social', [])
                        update_data['social'] = [s for s in update_data['social'] if s.get('social_type') != 'TELEGRAM']
                
                # Добавляем метки в общий запрос (пробуем разные форматы)
                if 'tags' in request.POST:
                    tag_ids = [int(tag_id) for tag_id in request.POST.getlist('tags') if tag_id]
                    # Пробуем разные форматы для меток
                    # Формат 1: [{"tag": id}] - простой формат
                    # Формат 2: [{"tag": id, "id": internal_id}] - с внутренним ID
                    # Формат 3: просто массив ID
                    update_data['tags'] = [{'tag': tag_id} for tag_id in tag_ids]
                    # Также добавляем альтернативные форматы
                    update_data['tag_ids'] = tag_ids
                    update_data['tags_simple'] = tag_ids
                    print(f"DEBUG: Добавлены метки в общий запрос - Формат объектов: {update_data['tags']}")
                    print(f"DEBUG: Альтернативные форматы меток: tag_ids={tag_ids}, tags_simple={tag_ids}")
                
                # Собираем данные анкеты для отдельного обновления
                questionary_data = {}
                for key, value in request.POST.items():
                    if key.startswith('questionary_'):
                        field_key = key.replace('questionary_', '')
                        if value.strip():  # Только непустые значения
                            questionary_data[field_key] = value.strip()
                
                if questionary_data:
                    print(f"DEBUG: Данные анкеты для отдельного обновления: {questionary_data}")
                
                # Выполняем общий запрос обновления
                if update_data:
                    print(f"DEBUG: Общий запрос обновления - Данные: {update_data}")
                    print(f"DEBUG: Количество полей для обновления: {len(update_data)}")
                    for key, value in update_data.items():
                        print(f"DEBUG: Поле '{key}': '{value}'")
                    
                    updated_applicant = huntflow_service.update_applicant(correct_account_id, applicant_id, update_data)
                    print(f"DEBUG: Результат общего обновления: {updated_applicant}")
                    
                    if updated_applicant:
                        success_messages.append('Данные обновлены')
                    else:
                        error_messages.append('Ошибка при обновлении данных')
                else:
                    print("DEBUG: Нет данных для обновления в основном запросе")
                
                # 2. Обновляем метки отдельно
                if 'tags' in request.POST:
                    tag_ids = [int(tag_id) for tag_id in request.POST.getlist('tags') if tag_id]
                    tags_result = huntflow_service.update_applicant_tags(
                        correct_account_id, applicant_id, tag_ids
                    )
                    if tags_result:
                        success_messages.append('Метки обновлены')
                    else:
                        error_messages.append('Ошибка при обновлении меток')
                
                # 3. Обновляем анкету отдельно
                if questionary_data:
                    questionary_result = huntflow_service.update_applicant_questionary(
                        correct_account_id, applicant_id, questionary_data
                    )
                    if questionary_result:
                        success_messages.append('Анкета обновлена')
                    else:
                        error_messages.append('Ошибка при обновлении анкеты')
                
                # 4. Обновляем статус с привязкой к вакансии
                if 'status_id' in request.POST and request.POST['status_id']:
                    status_id = int(request.POST['status_id'])
                    status_comment = request.POST.get('status_comment', '')
                    
                    # Получаем текущую вакансию из данных кандидата
                    vacancy_id = None
                    if applicant.get('links'):
                        vacancy_id = applicant['links'][0].get('vacancy')
                    
                    # Отладочная информация
                    print(f"DEBUG: Обновление статуса - ID: {status_id}, Вакансия: {vacancy_id}, Комментарий: {status_comment}")
                    
                    # Обновляем статус с комментарием и привязкой к вакансии
                    status_result = huntflow_service.update_applicant_status(
                        account_id, applicant_id, status_id, 
                        status_comment.strip() if status_comment.strip() else None,
                        vacancy_id
                    )
                    print(f"DEBUG: Результат обновления статуса: {status_result}")
                    
                    if status_result:
                        success_messages.append('Статус обновлен')
                    else:
                        error_messages.append('Ошибка при обновлении статуса')
                
                
                # Показываем результаты
                if success_messages:
                    for msg in success_messages:
                        messages.success(request, msg)
                if error_messages:
                    for msg in error_messages:
                        messages.error(request, msg)
                
                # Если есть успешные обновления, перенаправляем
                if success_messages:
                    # Принудительно обновляем данные кандидата после изменений
                    print(f"DEBUG: Принудительно обновляем данные кандидата {applicant_id}")
                    # Добавляем небольшую задержку для синхронизации с Huntflow
                    import time
                    time.sleep(1)
                    return redirect('huntflow:applicant_detail', account_id=correct_account_id, applicant_id=applicant_id)
                    
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении: {str(e)}')
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {correct_account_id}'
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == correct_account_id:
                    account_name = account.get('name', account_name)
                    break
        
        # Формируем имя кандидата для хлебных крошек
        applicant_name = f'Кандидат {applicant_id}'
        if applicant.get('first_name') or applicant.get('last_name'):
            applicant_name = f"{applicant.get('first_name', '')} {applicant.get('last_name', '')}".strip()
        
        context = {
            'account_id': correct_account_id,  # Используем правильный account_id
            'account_name': account_name,
            'accounts': accounts,  # Добавляем для sidebar menu
            'applicant': applicant,
            'applicant_name': applicant_name,
            'questionary': enriched_questionary,
            'questionary_schema': questionary_schema,
            'statuses': statuses,
            'vacancies': vacancies,
            'tags': tags
        }
        
        return render(request, 'huntflow/applicant_edit.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке кандидата: {str(e)}')
        return redirect('huntflow:applicants_list', account_id=correct_account_id)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def test_connection_ajax(request):
    """
    AJAX endpoint для тестирования подключения к Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    
    ОБРАБОТКА:
    - Создание HuntflowService для пользователя
    - Тестирование подключения к Huntflow API
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатом тестирования подключения
    
    СВЯЗИ:
    - Использует: HuntflowService
    - Передает: JsonResponse
    - Может вызываться из: AJAX запросы
    """
    try:
        huntflow_service = HuntflowService(request.user)
        connection_success = huntflow_service.test_connection()
        
        return JsonResponse({
            'success': connection_success,
            'message': 'Подключение успешно' if connection_success else 'Ошибка подключения'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def create_comment_ajax(request, account_id, applicant_id):
    """
    AJAX endpoint для создания комментария к кандидату
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - applicant_id: ID кандидата
    - request.POST: comment (текст комментария)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение информации о кандидате и создание комментария
    
    ОБРАБОТКА:
    - Валидация текста комментария
    - Получение информации о кандидате
    - Извлечение текущей вакансии и статуса из данных кандидата
    - Создание комментария с привязкой к вакансии и статусу
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатом создания комментария
    
    СВЯЗИ:
    - Использует: HuntflowService
    - Передает: JsonResponse
    - Может вызываться из: AJAX запросы
    """
    try:
        huntflow_service = HuntflowService(request.user)
        
        # Получаем данные из запроса
        comment_text = request.POST.get('comment', '').strip()
        
        if not comment_text:
            return JsonResponse({
                'success': False,
                'message': 'Комментарий не может быть пустым'
            })
        
        # Получаем информацию о кандидате для получения вакансии и статуса
        applicant = huntflow_service.get_applicant(account_id, applicant_id)
        if not applicant:
            return JsonResponse({
                'success': False,
                'message': 'Кандидат не найден'
            })
        
        # Получаем текущую вакансию и статус из данных кандидата
        vacancy_id = None
        status_id = None
        if applicant.get('links'):
            vacancy_id = applicant['links'][0].get('vacancy')
            status_id = applicant['links'][0].get('status')
        
        if not vacancy_id or not status_id:
            return JsonResponse({
                'success': False,
                'message': 'У кандидата нет привязанной вакансии или статуса'
            })
        
        # Создаем комментарий с привязкой к вакансии и статусу
        result = huntflow_service.create_applicant_comment(
            account_id, applicant_id, comment_text, vacancy_id, status_id
        )
        
        if result:
            return JsonResponse({
                'success': True,
                'message': 'Комментарий успешно добавлен',
                'comment_id': result.get('id'),
                'created': result.get('created')
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при создании комментария'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def get_vacancies_ajax(request, account_id):
    """
    AJAX endpoint для получения вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - request.GET: page, count, state (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение списка вакансий
    
    ОБРАБОТКА:
    - Получение параметров фильтрации из GET запроса
    - Получение списка вакансий через HuntflowService
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с данными вакансий
    
    СВЯЗИ:
    - Использует: HuntflowService
    - Передает: JsonResponse
    - Может вызываться из: AJAX запросы
    """
    try:
        huntflow_service = HuntflowService(request.user)
        
        # Получаем параметры
        page = request.GET.get('page', 1)
        count = request.GET.get('count', 30)
        state = request.GET.get('state', '')
        
        # Получаем вакансии
        vacancies = huntflow_service.get_vacancies(
            account_id=account_id,
            page=page,
            count=count,
            state=state if state else None
        )
        
        return JsonResponse({
            'success': True,
            'data': vacancies
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def get_applicants_ajax(request, account_id):
    """
    AJAX endpoint для получения кандидатов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации
    - request.GET: page, count, status, vacancy (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: сервис для работы с Huntflow API
    - Huntflow API: получение списка кандидатов
    
    ОБРАБОТКА:
    - Получение параметров фильтрации из GET запроса
    - Получение списка кандидатов через HuntflowService
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с данными кандидатов
    
    СВЯЗИ:
    - Использует: HuntflowService
    - Передает: JsonResponse
    - Может вызываться из: AJAX запросы
    """
    try:
        huntflow_service = HuntflowService(request.user)
        
        # Получаем параметры
        page = request.GET.get('page', 1)
        count = request.GET.get('count', 30)
        status = request.GET.get('status', '')
        vacancy = request.GET.get('vacancy', '')
        
        # Получаем кандидатов
        applicants = huntflow_service.get_applicants(
            account_id=account_id,
            page=page,
            count=count,
            status=status if status else None,
            vacancy=vacancy if vacancy else None
        )
        
        return JsonResponse({
            'success': True,
            'data': applicants
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })


# ==================== HH.RU ИНТЕГРАЦИЯ ====================

@login_required
def hh_vacancy_select(request, account_id):
    """
    Страница выбора вакансии для работы с HH.ru откликами
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService: получение списка вакансий
    - HHSyncConfiguration: сохраненные конфигурации синхронизации
    
    ОБРАБОТКА:
    - Получение списка вакансий из Huntflow
    - Получение сохраненных конфигураций синхронизации
    - Отображение страницы выбора вакансии
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с вакансиями и конфигурациями
    - render: HTML страница 'huntflow/hh_vacancy_select.html'
    """
    try:
        from apps.huntflow.models import HHSyncConfiguration
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем список вакансий
        vacancies_data = huntflow_service.get_vacancies(account_id)
        vacancies = vacancies_data.get('items', []) if vacancies_data else []
        
        # Получаем сохраненные конфигурации
        sync_configs = HHSyncConfiguration.objects.filter(
            user=request.user,
            account_id=account_id,
            enabled=True
        )
        
        # Создаем словарь конфигураций по vacancy_id для быстрого доступа
        configs_by_vacancy = {config.vacancy_id: config for config in sync_configs}
        
        context = {
            'account_id': account_id,
            'vacancies': vacancies,
            'sync_configs': configs_by_vacancy,
            'total_vacancies': len(vacancies)
        }
        
        return render(request, 'huntflow/hh_vacancy_select.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке вакансий: {str(e)}')
        return render(request, 'huntflow/hh_vacancy_select.html', {
            'account_id': account_id,
            'vacancies': [],
            'error': str(e)
        })


@login_required
def hh_responses_list(request, account_id, vacancy_id):
    """
    Страница просмотра откликов из HH.ru для вакансии
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - vacancy_id: ID вакансии в Huntflow
    - request.GET: параметры фильтрации и пагинации
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API: получение откликов напрямую из HH.ru
    - HHResponse: сохраненные отклики из БД (для связи)
    - HHSyncConfiguration: конфигурация синхронизации
    
    ОБРАБОТКА:
    - Получение информации о вакансии
    - Получение откликов напрямую из HH.ru API
    - Проверка, какие отклики уже обработаны
    - Применение фильтров
    - Отображение откликов с возможностью управления
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с откликами, вакансией и фильтрами
    - render: HTML страница 'huntflow/hh_responses_list.html'
    """
    try:
        from apps.huntflow.models import HHResponse, HHSyncConfiguration
        from apps.huntflow.hh_integration import HHResponsesHandler
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем информацию о вакансии
        vacancy = huntflow_service.get_vacancy(account_id, vacancy_id)
        
        # Получаем конфигурацию синхронизации для получения hh_vacancy_id
        sync_config = HHSyncConfiguration.objects.filter(
            user=request.user,
            account_id=account_id,
            vacancy_id=vacancy_id
        ).first()
        
        # Получаем hh_vacancy_id из конфигурации или запроса
        hh_vacancy_id = None
        if sync_config:
            hh_vacancy_id = sync_config.hh_vacancy_id
        else:
            hh_vacancy_id = request.GET.get('hh_vacancy_id')
        
        # Получаем отклики из Huntflow API (они уже там есть)
        page = max(int(request.GET.get('page', 1)), 1)  # Huntflow использует 1-based пагинацию
        per_page = min(int(request.GET.get('count', 20)), 30)  # Максимум 30 для Huntflow
        
        try:
            # Получаем отклики из Huntflow
            huntflow_responses_data = huntflow_service.get_vacancy_responses(
                account_id=account_id,
                vacancy_id=vacancy_id,
                count=per_page,
                page=page
            )
            
            if not huntflow_responses_data:
                messages.error(request, "Ошибка получения откликов из Huntflow")
                huntflow_responses = []
                total_responses = 0
                total_pages = 1
            else:
                huntflow_responses = huntflow_responses_data.get('items', [])
                total_responses = huntflow_responses_data.get('total', 0)
                total_applicants = huntflow_responses_data.get('total_applicants', 0)
                total_pages = huntflow_responses_data.get('total_pages', 1)
                logger.info(f"Получено откликов из Huntflow: {len(huntflow_responses)} из {total_responses} (страница {page} из {total_pages})")
        except Exception as e:
            logger.error(f"Ошибка при получении откликов из Huntflow: {e}")
            messages.error(request, f'Ошибка при загрузке откликов: {str(e)}')
            huntflow_responses = []
            total_responses = 0
            total_pages = 1
        
        # Проверяем, какие отклики уже обработаны (сохранены в БД)
        imported_hh_response_ids = set()
        if hh_vacancy_id:
            imported_hh_response_ids = set(
                HHResponse.objects.filter(
                    account_id=account_id,
                    vacancy_id=vacancy_id,
                    hh_vacancy_id=hh_vacancy_id
                ).values_list('hh_response_id', flat=True)
            )
        else:
            # Если hh_vacancy_id не указан, проверяем все отклики для вакансии
            imported_hh_response_ids = set(
                HHResponse.objects.filter(
                    account_id=account_id,
                    vacancy_id=vacancy_id
                ).values_list('hh_response_id', flat=True)
            )
        
        # Получаем фильтры из GET параметров или используем сохраненные
        hh_filters = {}
        if sync_config:
            hh_filters = sync_config.get_filters()
        
        # Переопределяем фильтры из GET параметров, если они есть
        if request.GET.get('min_age'):
            hh_filters['min_age'] = int(request.GET.get('min_age'))
        if request.GET.get('max_age'):
            hh_filters['max_age'] = int(request.GET.get('max_age'))
        if request.GET.get('min_experience_years'):
            hh_filters['min_experience_years'] = int(request.GET.get('min_experience_years'))
        if request.GET.get('max_experience_years'):
            hh_filters['max_experience_years'] = int(request.GET.get('max_experience_years'))
        if request.GET.get('allowed_locations'):
            hh_filters['allowed_locations'] = request.GET.get('allowed_locations').split(',')
        if request.GET.get('allowed_genders'):
            hh_filters['allowed_genders'] = [request.GET.get('allowed_genders')]
        
        # Обогащаем данные откликов
        enriched_responses = []
        passed_filters = []
        rejected_by_filters = []
        
        for response in huntflow_responses:
            response_id = response.get('id')  # ID отклика в Huntflow
            response_foreign = response.get('foreign', '')  # Foreign ID (из HH.ru)
            applicant = response.get('applicant', {})
            vacancy_external = response.get('vacancy_external', {})
            
            # Проверяем, обработан ли отклик (по foreign ID)
            is_processed = False
            hh_response_db = None
            if response_foreign and hh_vacancy_id:
                is_processed = str(response_foreign) in imported_hh_response_ids
                if is_processed:
                    hh_response_db = HHResponse.objects.filter(
                        hh_response_id=str(response_foreign)
                    ).first()
            
            # Извлекаем данные резюме из applicant
            resume = {}
            if applicant:
                # Получаем резюме из externals кандидата
                externals = applicant.get('externals', [])
                for external in externals:
                    if external.get('auth_type') == 'HH':  # HeadHunter
                        resume_data = external.get('data', {})
                        resume = external.get('resume', {}) or resume_data
                        break
                
                # Если резюме не найдено, используем данные из applicant как fallback
                if not resume:
                    resume = {
                        'first_name': applicant.get('first_name', ''),
                        'last_name': applicant.get('last_name', ''),
                        'middle_name': applicant.get('middle_name', ''),
                        'area': applicant.get('area', {}),
                        'contacts': []
                    }
                    # Добавляем контакты из applicant
                    if applicant.get('email'):
                        resume['contacts'] = resume.get('contacts', []) + [{
                            'type': {'id': 'email'},
                            'value': applicant.get('email')
                        }]
                    if applicant.get('phone'):
                        resume['contacts'] = resume.get('contacts', []) + [{
                            'type': {'id': 'phone'},
                            'value': applicant.get('phone')
                        }]
            
            # Применяем фильтры HH.ru к отклику
            passes_filter = True
            filter_reasons = []
            
            if hh_filters and any([
                hh_filters.get('min_age') is not None or hh_filters.get('max_age') is not None,
                hh_filters.get('min_experience_years') is not None or hh_filters.get('max_experience_years') is not None,
                hh_filters.get('allowed_locations'),
                hh_filters.get('allowed_genders') and 'any' not in hh_filters.get('allowed_genders', [])
            ]):
                # Проверяем возраст
                age = None
                birth_date_str = resume.get('birth_date')
                if birth_date_str:
                    try:
                        from datetime import datetime, date
                        if 'T' in birth_date_str:
                            birthday = datetime.fromisoformat(birth_date_str.replace('Z', '+00:00')).date()
                        else:
                            birthday = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                        today = date.today()
                        age = today.year - birthday.year - (
                            (today.month, today.day) < (birthday.month, birthday.day)
                        )
                    except:
                        pass
                
                if age is not None:
                    min_age = hh_filters.get('min_age')
                    max_age = hh_filters.get('max_age')
                    if min_age is not None or max_age is not None:
                        min_age = min_age if min_age is not None else 0
                        max_age = max_age if max_age is not None else 200
                        if not (min_age <= age <= max_age):
                            passes_filter = False
                            filter_reasons.append(f'Возраст {age} не в диапазоне {min_age}-{max_age}')
                
                # Проверяем опыт (если есть данные в резюме)
                experience_list = resume.get('experience', [])
                if experience_list:
                    total_days = 0
                    today = date.today()
                    for exp in experience_list:
                        try:
                            start_str = exp.get('start', '')
                            end_str = exp.get('end')
                            
                            if 'T' in start_str:
                                start = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
                            else:
                                start = datetime.strptime(start_str, '%Y-%m-%d').date()
                            
                            if end_str:
                                if 'T' in end_str:
                                    end = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
                                else:
                                    end = datetime.strptime(end_str, '%Y-%m-%d').date()
                            else:
                                end = today
                            
                            total_days += (end - start).days
                        except:
                            pass
                    
                    experience_years = total_days / 365.25 if total_days > 0 else 0
                    min_exp = hh_filters.get('min_experience_years')
                    max_exp = hh_filters.get('max_experience_years')
                    if min_exp is not None or max_exp is not None:
                        min_exp = min_exp if min_exp is not None else 0
                        max_exp = max_exp if max_exp is not None else 200
                        if not (min_exp <= experience_years <= max_exp):
                            passes_filter = False
                            filter_reasons.append(f'Опыт {experience_years:.1f} лет не в диапазоне {min_exp}-{max_exp}')
                
                # Проверяем локацию
                area = resume.get('area', {})
                location_id = str(area.get('id', '')) if area else None
                if location_id:
                    allowed_locations = hh_filters.get('allowed_locations', [])
                    if allowed_locations and location_id not in allowed_locations:
                        passes_filter = False
                        filter_reasons.append(f'Локация не в списке разрешенных')
                
                # Проверяем пол
                gender_obj = resume.get('gender', {})
                gender = gender_obj.get('id', '') if isinstance(gender_obj, dict) else str(gender_obj) if gender_obj else None
                if gender:
                    allowed_genders = hh_filters.get('allowed_genders', ['any'])
                    if 'any' not in allowed_genders and gender not in allowed_genders:
                        passes_filter = False
                        filter_reasons.append(f'Пол не соответствует фильтру')
            
            # Парсим дату создания отклика
            created_at = None
            created_at_str = response.get('created_at')
            if created_at_str:
                try:
                    from datetime import datetime
                    if 'T' in created_at_str:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
                except:
                    pass
            
            # Получаем информацию о вакансии из отклика
            response_vacancy = response.get('vacancy', {})
            vacancy_external = response.get('vacancy_external', {})
            
            response_data = {
                'huntflow_response': response,  # Полный объект отклика из Huntflow
                'response_id': response_id,  # ID отклика в Huntflow (например, 17800665)
                'response_foreign': response_foreign,  # Foreign ID (из HH.ru)
                'applicant': applicant,  # Данные кандидата
                'resume': resume,  # Данные резюме
                'is_processed': is_processed,  # Обработан ли отклик
                'hh_response_db': hh_response_db,  # Запись в БД
                'created_at': created_at,  # Дата создания отклика
                'vacancy': response_vacancy,  # Информация о вакансии
                'vacancy_external': vacancy_external,  # Внешняя публикация вакансии
                'passes_hh_filters': passes_filter,  # Прошел ли фильтры
                'filter_reasons': filter_reasons  # Причины отклонения фильтрами
            }
            
            enriched_responses.append(response_data)
            
            if passes_filter:
                passed_filters.append(response_data)
            else:
                rejected_by_filters.append(response_data)
        
        # Статистика
        imported_count = len([r for r in enriched_responses if r['is_processed']])
        not_imported_count = len(enriched_responses) - imported_count
        passed_hh_filters = len(passed_filters)
        rejected_by_hh_filters = len(rejected_by_filters)
        
        # Применяем фильтры из GET параметров для отображения
        source_filter = request.GET.get('source', '')
        filter_status = request.GET.get('filter_status', '')
        
        if source_filter == 'processed':
            enriched_responses = [r for r in enriched_responses if r['is_processed']]
        elif source_filter == 'new':
            enriched_responses = [r for r in enriched_responses if not r['is_processed']]
        
        if filter_status == 'passed':
            enriched_responses = [r for r in enriched_responses if r['passes_hh_filters']]
        elif filter_status == 'rejected':
            enriched_responses = [r for r in enriched_responses if not r['passes_hh_filters']]
        
        # Получаем название статуса отклика (если есть)
        response_status_name = None
        
        context = {
            'account_id': account_id,
            'vacancy_id': vacancy_id,
            'vacancy': vacancy,
            'sync_config': sync_config,
            'hh_vacancy_id': hh_vacancy_id,
            'responses': enriched_responses,
            'total_responses': total_responses,
            'imported_count': imported_count,
            'not_imported_count': not_imported_count,
            'passed_hh_filters': passed_hh_filters,
            'rejected_by_hh_filters': rejected_by_hh_filters,
            'current_page': page + 1,  # Для отображения (1-based)
            'total_pages': total_pages,
            'hh_filters': hh_filters,
            'response_status_name': response_status_name,
            'current_filters': {
                'source': source_filter,
                'filter_status': filter_status,
                'min_age': hh_filters.get('min_age'),
                'max_age': hh_filters.get('max_age'),
                'min_experience_years': hh_filters.get('min_experience_years'),
                'max_experience_years': hh_filters.get('max_experience_years'),
                'allowed_locations': ','.join(hh_filters.get('allowed_locations', [])),
                'allowed_genders': hh_filters.get('allowed_genders', ['any'])[0] if hh_filters.get('allowed_genders') else 'any'
            },
            'pagination': {
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'previous_page': page - 1,
                'next_page': page + 1,
                'current_page': page,
                'total_pages': total_pages
            }
        }
        
        return render(request, 'huntflow/hh_responses_list.html', context)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Ошибка в hh_responses_list: {e}")
        messages.error(request, f'Ошибка при загрузке откликов: {str(e)}')
        return render(request, 'huntflow/hh_responses_list.html', {
            'account_id': account_id,
            'vacancy_id': vacancy_id,
            'error': str(e),
            'responses': []
        })


@login_required
@require_http_methods(["POST"])
def hh_import_responses_ajax(request, account_id, vacancy_id):
    """
    AJAX endpoint для импорта откликов из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - vacancy_id: ID вакансии в Huntflow
    - request.POST: hh_vacancy_id, filters (JSON)
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API: получение откликов
    - HuntflowOperations: импорт в Huntflow
    
    ОБРАБОТКА:
    - Получение откликов из HH.ru
    - Фильтрация по критериям
    - Импорт в Huntflow
    - Сохранение в БД
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатами импорта
    """
    try:
        from logic.integration.shared.huntflow_operations import HuntflowOperations
        import json
        
        hh_vacancy_id = request.POST.get('hh_vacancy_id')
        filters_json = request.POST.get('filters', '{}')
        
        if not hh_vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Требуется hh_vacancy_id'
            }, status=400)
        
        try:
            filters = json.loads(filters_json) if filters_json else {}
        except json.JSONDecodeError:
            filters = {}
        
        operations = HuntflowOperations(request.user)
        result = operations.get_and_import_hh_responses(
            account_id=int(account_id),
            vacancy_id=int(vacancy_id),
            hh_vacancy_id=hh_vacancy_id,
            filters=filters
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def hh_reject_response_ajax(request, account_id, vacancy_id):
    """
    AJAX endpoint для отклонения отклика в HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - vacancy_id: ID вакансии в Huntflow
    - request.POST: negotiation_id, hh_vacancy_id, message (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API: отклонение отклика
    - HHResponse: сохранение статуса в БД
    
    ОБРАБОТКА:
    - Отклонение отклика в HH.ru
    - Сохранение информации об отклонении в БД
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатами операции
    """
    try:
        from apps.huntflow.hh_integration import HHResponsesHandler
        from apps.huntflow.models import HHResponse
        
        negotiation_id = request.POST.get('negotiation_id')
        hh_vacancy_id = request.POST.get('hh_vacancy_id')
        message = request.POST.get('message', '')
        
        if not negotiation_id or not hh_vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Требуется negotiation_id и hh_vacancy_id'
            }, status=400)
        
        handler = HHResponsesHandler(request.user)
        result = handler.reject_response(negotiation_id, hh_vacancy_id, message)
        
        # Сохраняем информацию об отклонении в БД
        if result['success']:
            HHResponse.objects.update_or_create(
                hh_response_id=negotiation_id,
                defaults={
                    'account_id': account_id,
                    'vacancy_id': vacancy_id,
                    'hh_vacancy_id': hh_vacancy_id,
                    'import_status': 'filtered',
                    'response_state': 'rejected',
                    'imported_by': request.user,
                }
            )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении отклика: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def hh_archive_response_ajax(request, account_id, vacancy_id):
    """
    AJAX endpoint для архивирования отклика в HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - vacancy_id: ID вакансии в Huntflow
    - request.POST: negotiation_id
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API: архивирование отклика
    
    ОБРАБОТКА:
    - Архивирование отклика в HH.ru
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатами операции
    """
    try:
        from apps.huntflow.hh_integration import HHResponsesHandler
        
        negotiation_id = request.POST.get('negotiation_id')
        
        if not negotiation_id:
            return JsonResponse({
                'success': False,
                'message': 'Требуется negotiation_id'
            }, status=400)
        
        handler = HHResponsesHandler(request.user)
        result = handler.archive_response(negotiation_id)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Ошибка при архивировании отклика: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def hh_mark_viewed_ajax(request, account_id, vacancy_id):
    """
    AJAX endpoint для отметки отклика как просмотренного в HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - account_id: ID организации в Huntflow
    - vacancy_id: ID вакансии в Huntflow
    - request.POST: negotiation_id
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API: отметка как просмотренный
    
    ОБРАБОТКА:
    - Отметка отклика как просмотренного в HH.ru
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JsonResponse с результатами операции
    """
    try:
        from apps.huntflow.hh_integration import HHResponsesHandler
        
        negotiation_id = request.POST.get('negotiation_id')
        
        if not negotiation_id:
            return JsonResponse({
                'success': False,
                'message': 'Требуется negotiation_id'
            }, status=400)
        
        handler = HHResponsesHandler(request.user)
        result = handler.mark_as_viewed(negotiation_id)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Ошибка при отметке отклика: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)


@login_required
def create_applicant(request):
    """
    Страница для создания кандидата и привязки к вакансии
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    - request.POST: данные формы создания кандидата
    
    ИСТОЧНИКИ ДАННЫХ:
    - CreateApplicantForm: форма для создания кандидата
    - Vacancy.objects: список активных вакансий
    - HuntflowService: сервис для создания кандидата в Huntflow
    
    ОБРАБОТКА:
    - Отображение формы с активными вакансиями
    - Валидация данных формы
    - Создание кандидата в Huntflow через API
    - Привязка кандидата к выбранной вакансии
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с формой и данными
    - render: HTML страница 'huntflow/create_applicant.html'
    - redirect: перенаправление на страницу кандидата после создания
    
    СВЯЗИ:
    - Использует: CreateApplicantForm, HuntflowService, Vacancy
    - Передает данные в: huntflow/create_applicant.html
    - Может вызываться из: huntflow/ URL patterns
    """
    try:
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user)
        
        if not correct_account_id:
            messages.error(request, 'Не удалось определить организацию Huntflow. Проверьте настройки.')
            return redirect('huntflow:dashboard')
        
        huntflow_service = HuntflowService(request.user)
        
        # Получаем информацию об организации для хлебных крошек
        accounts = huntflow_service.get_accounts()
        account_name = f'Организация {correct_account_id}'
        if accounts and 'items' in accounts:
            for account in accounts['items']:
                if account['id'] == correct_account_id:
                    account_name = account.get('name', account_name)
                    break
        
        if request.method == 'POST':
            form = CreateApplicantForm(request.POST, request.FILES, user=request.user)
            
            if form.is_valid():
                try:
                    # Проверяем, загружен ли файл резюме
                    resume_file = form.cleaned_data.get('resume_file')
                    parsed_data = None
                    parsed_file_id = request.POST.get('parsed_file_id')  # ID файла из AJAX парсинга
                    
                    # Если загружен файл, парсим его через Huntflow
                    if resume_file:
                        try:
                            # Читаем файл
                            file_data = resume_file.read()
                            file_name = resume_file.name
                            
                            logger.info(f"Загружен файл резюме: {file_name} ({len(file_data)} байт)")
                            
                            # Загружаем и парсим файл через Huntflow API
                            parsed_data = huntflow_service.upload_file(
                                account_id=correct_account_id,
                                file_data=file_data,
                                file_name=file_name,
                                parse_file=True
                            )
                            
                            if parsed_data:
                                logger.info(f"Файл успешно обработан парсером Huntflow")
                                
                                # Извлекаем данные из распарсенного файла
                                fields = parsed_data.get('fields', {})
                                name_data = fields.get('name', {})
                                
                                # Автозаполняем форму данными из парсера, если поля пустые
                                if not form.cleaned_data.get('first_name') and name_data.get('first'):
                                    form.cleaned_data['first_name'] = name_data.get('first')
                                
                                if not form.cleaned_data.get('last_name') and name_data.get('last'):
                                    form.cleaned_data['last_name'] = name_data.get('last')
                                
                                if not form.cleaned_data.get('middle_name') and name_data.get('middle'):
                                    form.cleaned_data['middle_name'] = name_data.get('middle')
                                
                                if not form.cleaned_data.get('email') and fields.get('email'):
                                    form.cleaned_data['email'] = fields.get('email')
                                
                                if not form.cleaned_data.get('phone') and fields.get('phones'):
                                    phones = fields.get('phones', [])
                                    if phones and len(phones) > 0:
                                        form.cleaned_data['phone'] = phones[0]
                                
                                if not form.cleaned_data.get('position') and fields.get('position'):
                                    form.cleaned_data['position'] = fields.get('position')
                                
                                if not form.cleaned_data.get('salary') and fields.get('salary'):
                                    form.cleaned_data['salary'] = str(fields.get('salary'))
                                
                                # Если текст резюме не заполнен, используем текст из парсера
                                if not form.cleaned_data.get('resume_text') and parsed_data.get('text'):
                                    form.cleaned_data['resume_text'] = parsed_data.get('text')
                                
                                messages.info(request, 'Файл резюме успешно обработан. Данные автоматически заполнены.')
                            else:
                                messages.warning(request, 'Не удалось обработать файл через парсер Huntflow. Продолжаем с введенными данными.')
                                
                        except Exception as e:
                            logger.error(f"Ошибка при обработке файла: {e}")
                            messages.warning(request, f'Ошибка при обработке файла: {str(e)}. Продолжаем с введенными данными.')
                    
                    # Получаем данные из формы (возможно уже заполненные парсером)
                    candidate_data = {
                        'first_name': form.cleaned_data['first_name'],
                        'last_name': form.cleaned_data['last_name'],
                        'middle_name': form.cleaned_data.get('middle_name', ''),
                        'email': form.cleaned_data.get('email', ''),
                        'phone': form.cleaned_data.get('phone', ''),
                        'position': form.cleaned_data.get('position', ''),
                        'company': form.cleaned_data.get('company', ''),
                        'salary': form.cleaned_data.get('salary', ''),
                        'resume_text': form.cleaned_data.get('resume_text', '')
                    }
                    
                    # Получаем ID вакансии из Huntflow (external_id из нашей БД)
                    vacancy = form.cleaned_data['vacancy']
                    vacancy_id = int(vacancy.external_id) if vacancy.external_id else None
                    
                    if not vacancy_id:
                        messages.error(request, 'У выбранной вакансии не указан ID для связи с Huntflow')
                        form = CreateApplicantForm(user=request.user)
                    else:
                        # Если есть распарсенные данные, используем create_applicant_from_parsed_data
                        # для более полного использования данных парсера
                        if parsed_data:
                            # Добавляем ID файла в parsed_data если он был загружен
                            if parsed_data.get('id') or parsed_file_id:
                                file_id = parsed_data.get('id') or parsed_file_id
                                if file_id and 'id' not in parsed_data:
                                    parsed_data['id'] = file_id
                                
                                # Используем create_applicant_from_parsed_data для полной поддержки парсера
                                created_applicant = huntflow_service.create_applicant_from_parsed_data(
                                    account_id=correct_account_id,
                                    parsed_data=parsed_data,
                                    vacancy_id=vacancy_id
                                )
                            else:
                                # Если файл не был сохранен, используем обычный метод
                                created_applicant = huntflow_service.create_applicant_manual(
                                    account_id=correct_account_id,
                                    candidate_data=candidate_data,
                                    vacancy_id=vacancy_id
                                )
                        else:
                            # Создаем кандидата в Huntflow обычным способом
                            created_applicant = huntflow_service.create_applicant_manual(
                                account_id=correct_account_id,
                                candidate_data=candidate_data,
                                vacancy_id=vacancy_id
                            )
                        
                        if created_applicant:
                            applicant_id = created_applicant.get('id')
                            messages.success(
                                request, 
                                f'Кандидат успешно создан и привязан к вакансии "{vacancy.name}"'
                            )
                            return redirect('huntflow:applicant_detail', 
                                          account_id=correct_account_id, 
                                          applicant_id=applicant_id)
                        else:
                            messages.error(request, 'Не удалось создать кандидата в Huntflow. Проверьте данные и попробуйте снова.')
                            form = CreateApplicantForm(request.POST, request.FILES, user=request.user)
                            
                except Exception as e:
                    logger.error(f"Ошибка при создании кандидата: {e}")
                    import traceback
                    traceback.print_exc()
                    messages.error(request, f'Ошибка при создании кандидата: {str(e)}')
                    form = CreateApplicantForm(request.POST, request.FILES, user=request.user)
        else:
            form = CreateApplicantForm(user=request.user)
        
        context = {
            'form': form,
            'account_id': correct_account_id,
            'account_name': account_name,
            'accounts': accounts,
        }
        
        return render(request, 'huntflow/create_applicant.html', context)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы создания кандидата: {e}")
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('huntflow:dashboard')


@login_required
@require_http_methods(["POST"])
def parse_resume_file_ajax(request):
    """
    AJAX endpoint для парсинга файла резюме через Huntflow API
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.FILES: загруженный файл резюме
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowService.upload_file: загрузка и парсинг файла
    
    ОБРАБОТКА:
    - Загрузка файла
    - Парсинг через Huntflow API
    - Возврат распарсенных данных для автозаполнения формы
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON с распарсенными данными кандидата
    
    СВЯЗИ:
    - Использует: HuntflowService
    - Передает: JSON ответ с данными для автозаполнения
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'Файл не загружен'
            }, status=400)
        
        resume_file = request.FILES['file']
        
        # Получаем правильный account_id
        correct_account_id = get_correct_account_id(request.user)
        
        if not correct_account_id:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось определить организацию Huntflow'
            }, status=400)
        
        huntflow_service = HuntflowService(request.user)
        
        # Читаем файл
        file_data = resume_file.read()
        file_name = resume_file.name
        
        logger.info(f"Парсинг файла резюме: {file_name} ({len(file_data)} байт)")
        
        # Загружаем и парсим файл через Huntflow API
        parsed_data = huntflow_service.upload_file(
            account_id=correct_account_id,
            file_data=file_data,
            file_name=file_name,
            parse_file=True
        )
        
        if not parsed_data:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось обработать файл через парсер Huntflow'
            }, status=400)
        
        # Проверяем, что parsed_data - это словарь
        if not isinstance(parsed_data, dict):
            logger.error(f"parsed_data не является словарем: {type(parsed_data)}")
            return JsonResponse({
                'success': False,
                'message': 'Неверный формат данных от парсера Huntflow'
            }, status=400)
        
        # Извлекаем данные из распарсенного файла (безопасно)
        fields = parsed_data.get('fields') if parsed_data else {}
        if not fields or not isinstance(fields, dict):
            fields = {}
        
        name_data = fields.get('name') if fields else {}
        if not name_data or not isinstance(name_data, dict):
            name_data = {}
        
        # Формируем ответ с данными для автозаполнения
        response_data = {
            'success': True,
            'parsed_data': parsed_data,  # Полные распарсенные данные для создания кандидата
            'data': {
                'first_name': name_data.get('first', ''),
                'last_name': name_data.get('last', ''),
                'middle_name': name_data.get('middle', ''),
                'email': fields.get('email', ''),
                'phone': fields.get('phones', [None])[0] if fields.get('phones') else '',
                'position': fields.get('position', ''),
                'salary': str(fields.get('salary', '')) if fields.get('salary') else '',
                'resume_text': parsed_data.get('text', ''),
                'file_id': parsed_data.get('id'),  # ID загруженного файла для привязки
            }
        }
        
        logger.info(f"Файл успешно обработан. Извлечено: {response_data['data']['first_name']} {response_data['data']['last_name']}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге файла: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при обработке файла: {str(e)}'
        }, status=500)


@login_required
def chrome_extension_management(request):
    """
    Страница управления данными Chrome расширения
    
    Показывает:
    - Список всех LinkedIn → Huntflow связей пользователя
    - Список всех Thread → Profile маппингов
    - Статистику
    - Кнопки уровней из Huntflow
    """
    from .models import LinkedInHuntflowLink, LinkedInThreadProfile, ResumeHuntflowLink, MeetHuntflowLink, GDriveHuntflowLink
    from apps.google_oauth.cache_service import HuntflowAPICache

    # Получаем все связи LinkedIn → Huntflow (общие для всех)
    links = LinkedInHuntflowLink.objects.all().order_by('-created_at')

    # Получаем все маппинги Thread → Profile (персональные)
    thread_mappings = LinkedInThreadProfile.objects.filter(user=request.user).order_by('-last_accessed_at')
    # Связи резюме (hh.ru/rabota.by) → Huntflow (общие для всех)
    resume_links = ResumeHuntflowLink.objects.all().order_by('-updated_at')
    # Связи Google Meet → Huntflow (общие для всех)
    meet_links = MeetHuntflowLink.objects.all().order_by('-updated_at')
    # Связи Google Drive → Huntflow (общие для всех)
    gdrive_links = GDriveHuntflowLink.objects.all().order_by('-updated_at')

    # Статистика
    stats = {
        'total_links': links.count(),
        'total_thread_mappings': thread_mappings.count(),
        'total_resume_links': resume_links.count(),
        'total_meet_links': meet_links.count(),
        'total_gdrive_links': gdrive_links.count(),
        'links_with_vacancy': links.exclude(vacancy_id__isnull=True).count(),
        'recent_links': links.filter(created_at__gte=timezone.now() - timedelta(days=7)).count(),
    }
    
    # Вакансии — из apps.vacancies (БД). Грейды — из Huntflow (схема анкеты, поле «Уровень»).
    from .models import LevelText
    from apps.vacancies.models import Vacancy

    level_texts = {}
    try:
        for lt in LevelText.objects.all().order_by('vacancy_name', 'level'):
            level_texts[(lt.vacancy_name, lt.level)] = lt.text
    except Exception as e:
        logger.warning(f"LevelText lookup failed: {e}")

    # Грейды из Huntflow: схема анкеты, поле «Уровень» / level / grade
    levels_from_huntflow = []
    account_id = get_correct_account_id(request.user)
    try:
        api = HuntflowService(user=request.user)
        if account_id:
            schema = api.get_applicant_questionary_schema(account_id)
            if isinstance(schema, dict):
                fields_dict = {}
                if 'fields' in schema:
                    for f in schema.get('fields', []) or []:
                        if isinstance(f, dict):
                            fid = f.get('id') or f.get('key')
                            if fid:
                                fields_dict[fid] = f
                else:
                    fields_dict = schema
                for _fid, finfo in fields_dict.items():
                    if not isinstance(finfo, dict):
                        continue
                    title = (finfo.get('title') or '').lower()
                    if 'уровень' in title or 'level' in title or 'grade' in title or 'грейд' in title:
                        if finfo.get('type') == 'select' and finfo.get('values'):
                            for v in finfo.get('values', []) or []:
                                n = v.get('name') or v.get('value') or v.get('id') if isinstance(v, dict) else v
                                if n:
                                    levels_from_huntflow.append(str(n))
                        break
            levels_from_huntflow = sorted(set(levels_from_huntflow))
    except Exception as e:
        logger.warning(f"Huntflow levels: {e}")

    # Все вакансии из БД (apps.vacancies). У каждой — одни и те же грейды из Huntflow.
    vacancy_list = []
    for v in Vacancy.objects.all().order_by('name'):
        vacancy_list.append({
            'id': v.external_id,
            'name': v.name,
            'levels': levels_from_huntflow,
        })

    vacancies_with_levels = vacancy_list
    
    # Базовый URL для AJAX: при открытии через /extension/ — /extension, иначе — /huntflow/chrome-extension
    extension_base_url = '/extension' if (request.path or '').startswith('/extension') else '/huntflow/chrome-extension'
    context = {
        'links': links,
        'thread_mappings': thread_mappings,
        'resume_links': resume_links,
        'meet_links': meet_links,
        'gdrive_links': gdrive_links,
        'stats': stats,
        'vacancies_with_levels': vacancies_with_levels,
        'level_texts': level_texts,
        'extension_base_url': extension_base_url,
    }
    
    return render(request, 'huntflow/chrome_extension_management.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def chrome_extension_level_text_ajax(request, vacancy_name, level):
    """
    AJAX endpoint для получения или сохранения текста для уровня по вакансии.
    """
    from .models import LevelText
    from urllib.parse import unquote
    
    vacancy_name = unquote(vacancy_name)
    
    if request.method == 'GET':
        try:
            level_text = LevelText.objects.get(
                vacancy_name=vacancy_name, level=level
            )
            return JsonResponse({'success': True, 'text': level_text.text})
        except LevelText.DoesNotExist:
            return JsonResponse({'success': True, 'text': ''})
    
    elif request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            level_text, created = LevelText.objects.get_or_create(
                vacancy_name=vacancy_name,
                level=level,
                defaults={'text': text, 'created_by': request.user, 'updated_by': request.user},
            )
            if not created:
                level_text.text = text
                level_text.updated_by = request.user
                level_text.save()
            return JsonResponse({'success': True, 'message': 'Текст сохранен'})
        except Exception as e:
            logger.error(f"Error saving level text: {e}")
            return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def chrome_extension_link_ajax(request, link_id):
    """
    AJAX endpoint для обновления или удаления LinkedIn → Huntflow связи
    """
    from .models import LinkedInHuntflowLink
    
    try:
        link = LinkedInHuntflowLink.objects.get(id=link_id)
    except LinkedInHuntflowLink.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Связь не найдена'
        }, status=404)
    
    if request.method == 'DELETE':
        link.delete()
        return JsonResponse({
            'success': True,
            'message': 'Связь удалена'
        })
    
    # PATCH - обновление
    data = json.loads(request.body)
    
    if 'linkedin_url' in data:
        link.linkedin_url = data['linkedin_url']
    if 'target_url' in data:
        link.target_url = data['target_url']
    if 'account_id' in data:
        try:
            link.account_id = int(data['account_id']) if data['account_id'] and str(data['account_id']).strip() else None
        except (ValueError, TypeError):
            link.account_id = None
    if 'applicant_id' in data:
        try:
            link.applicant_id = int(data['applicant_id']) if data['applicant_id'] and str(data['applicant_id']).strip() else None
        except (ValueError, TypeError):
            link.applicant_id = None
    if 'vacancy_id' in data:
        try:
            link.vacancy_id = int(data['vacancy_id']) if data['vacancy_id'] and str(data['vacancy_id']).strip() else None
        except (ValueError, TypeError):
            link.vacancy_id = None

    link.updated_by = request.user
    link.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Связь обновлена',
        'data': {
            'id': link.id,
            'linkedin_url': link.linkedin_url,
            'target_url': link.target_url,
            'account_id': link.account_id,
            'applicant_id': link.applicant_id,
            'vacancy_id': link.vacancy_id,
            'created_at': link.created_at.isoformat(),
            'updated_at': link.updated_at.isoformat(),
        }
    })


@login_required
@require_http_methods(["DELETE"])
def chrome_extension_resume_link_delete_ajax(request, link_id):
    """
    AJAX endpoint для удаления связи hh.ru/rabota.by → Huntflow (ResumeHuntflowLink).
    """
    from .models import ResumeHuntflowLink

    try:
        link = ResumeHuntflowLink.objects.get(id=link_id)
    except ResumeHuntflowLink.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Связь не найдена',
        }, status=404)

    link.delete()
    return JsonResponse({
        'success': True,
        'message': 'Связь удалена',
    })


@login_required
@require_http_methods(["PATCH", "DELETE"])
def chrome_extension_thread_ajax(request, thread_id):
    """
    AJAX endpoint для обновления или удаления Thread → Profile маппинга
    """
    from .models import LinkedInThreadProfile
    
    try:
        thread = LinkedInThreadProfile.objects.get(id=thread_id, user=request.user)
    except LinkedInThreadProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Маппинг не найден'
        }, status=404)
    
    if request.method == 'DELETE':
        thread.delete()
        return JsonResponse({
            'success': True,
            'message': 'Маппинг удален'
        })
    
    # PATCH - обновление
    data = json.loads(request.body)
    
    if 'thread_id' in data:
        thread.thread_id = data['thread_id']
    if 'profile_url' in data:
        thread.profile_url = data['profile_url']
    
    thread.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Маппинг обновлен',
        'data': {
            'id': thread.id,
            'thread_id': thread.thread_id,
            'profile_url': thread.profile_url,
            'created_at': thread.created_at.isoformat(),
            'last_accessed_at': thread.last_accessed_at.isoformat(),
        }
    })


@login_required
@require_http_methods(["POST"])
def chrome_extension_clear_cache_ajax(request):
    """
    AJAX endpoint для очистки кэша расширения
    """
    from apps.google_oauth.cache_service import HuntflowAPICache
    
    try:
        HuntflowAPICache.invalidate_user_cache(request.user.id)
        return JsonResponse({
            'success': True,
            'message': 'Кэш очищен'
        })
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка очистки кэша: {str(e)}'
        }, status=500)
