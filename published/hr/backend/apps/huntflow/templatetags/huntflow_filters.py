from django import template
from datetime import datetime
import re

register = template.Library()

@register.filter
def format_iso_date(iso_string):
    """
    Форматирует ISO строку даты в формат dd.mm.yy hh:mm
    
    Примеры:
    - '2025-09-04T18:55:50+03:00' -> '04.09.25 18:55'
    - '2025-09-04T18:55:50' -> '04.09.25 18:55'
    """
    if not iso_string:
        return ''
    
    try:
        # Убираем часовой пояс если есть
        clean_iso = re.sub(r'[+-]\d{2}:\d{2}$', '', str(iso_string))
        
        # Парсим дату
        dt = datetime.fromisoformat(clean_iso)
        
        # Форматируем в нужный формат
        return dt.strftime('%d.%m.%y %H:%M')
        
    except (ValueError, TypeError):
        # Если не удалось распарсить, возвращаем исходную строку
        return str(iso_string)


@register.filter
def get_contrast_color(hex_color):
    """
    Определяет контрастный цвет текста (белый или черный) для заданного hex цвета фона
    
    Args:
        hex_color: Hex цвет без # (например: 'FF0000' или '#FF0000')
        
    Returns:
        '#000000' для светлых цветов, '#ffffff' для темных цветов
    """
    if not hex_color:
        return '#000000'
    
    # Убираем # если есть
    hex_color = str(hex_color).replace('#', '')
    
    # Проверяем, что это валидный hex цвет
    if len(hex_color) != 6:
        return '#000000'
    
    try:
        # Конвертируем hex в RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Вычисляем яркость по формуле W3C
        # Используем веса для учета восприятия яркости человеческим глазом
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        
        # Возвращаем черный для светлых цветов, белый для темных
        return '#000000' if brightness > 128 else '#ffffff'
        
    except (ValueError, TypeError):
        # Если не удалось распарсить, возвращаем черный по умолчанию
        return '#000000'


@register.inclusion_tag('huntflow/breadcrumbs.html', takes_context=True)
def huntflow_breadcrumbs(context):
    """
    Генерирует хлебные крошки для иерархической навигации Huntflow
    
    Структура: Дашборд -> Организация -> Вакансия -> Кандидаты
    """
    request = context['request']
    url_name = request.resolver_match.url_name
    url_kwargs = request.resolver_match.kwargs
    
    breadcrumbs = []
    
    # Всегда добавляем дашборд как корень
    breadcrumbs.append({
        'name': 'Дашборд',
        'url': 'huntflow:dashboard',
        'icon': 'fas fa-tachometer-alt',
        'active': url_name == 'dashboard'
    })
    
    # Если есть account_id, добавляем организацию
    if 'account_id' in url_kwargs:
        account_id = url_kwargs['account_id']
        
        # Получаем информацию об организации из контекста
        account_name = context.get('account_name', f'Организация {account_id}')
        
        breadcrumbs.append({
            'name': account_name,
            'url': 'huntflow:vacancies_list',
            'url_kwargs': {'account_id': account_id},
            'icon': 'fas fa-building',
            'active': url_name in ['vacancies_list', 'vacancy_detail', 'applicants_list', 'applicant_detail', 'applicant_edit']
        })
        
        # Если есть vacancy_id, добавляем вакансию
        if 'vacancy_id' in url_kwargs:
            vacancy_id = url_kwargs['vacancy_id']
            vacancy_name = context.get('vacancy_name', f'Вакансия {vacancy_id}')
            
            breadcrumbs.append({
                'name': vacancy_name,
                'url': 'huntflow:vacancy_detail',
                'url_kwargs': {'account_id': account_id, 'vacancy_id': vacancy_id},
                'icon': 'fas fa-briefcase',
                'active': url_name == 'vacancy_detail'
            })
        
        # Если есть applicant_id, добавляем кандидата
        if 'applicant_id' in url_kwargs:
            applicant_id = url_kwargs['applicant_id']
            applicant_name = context.get('applicant_name', f'Кандидат {applicant_id}')
            
            breadcrumbs.append({
                'name': applicant_name,
                'url': 'huntflow:applicant_detail',
                'url_kwargs': {'account_id': account_id, 'applicant_id': applicant_id},
                'icon': 'fas fa-user',
                'active': url_name in ['applicant_detail', 'applicant_edit']
            })
    
    return {
        'breadcrumbs': breadcrumbs,
        'current_url_name': url_name
    }


@register.inclusion_tag('huntflow/sidebar_menu.html', takes_context=True)
def huntflow_sidebar_menu(context):
    """
    Генерирует иерархическое меню для боковой панели Huntflow
    
    Структура: Дашборд -> Организация -> Вакансия -> Кандидаты
    """
    request = context['request']
    url_name = request.resolver_match.url_name
    url_kwargs = request.resolver_match.kwargs
    
    menu_items = []
    
    # 1. Дашборд - всегда первый элемент
    menu_items.append({
        'type': 'dashboard',
        'name': 'Дашборд',
        'url': 'huntflow:dashboard',
        'icon': 'fas fa-tachometer-alt',
        'active': url_name == 'dashboard',
        'children': []
    })
    
    # 2. Организации - всегда показываем, но с разной детализацией
    # Получаем список организаций для отображения
    accounts = context.get('accounts_for_menu', context.get('accounts', []))
    if hasattr(accounts, 'get') and 'items' in accounts:
        accounts_list = accounts['items']
    else:
        accounts_list = accounts if isinstance(accounts, list) else []
    
    # Создаем элемент организации
    organization_item = {
        'type': 'organization',
        'name': 'Организации',
        'icon': 'fas fa-building',
        'active': url_name in ['vacancies_list', 'vacancy_detail', 'applicants_list', 'applicant_detail', 'applicant_edit'],
        'children': []
    }
    
    # Добавляем все организации как дочерние элементы
    for account in accounts_list:
        # Проверяем, является ли это текущей организацией
        is_current = 'account_id' in url_kwargs and account['id'] == url_kwargs['account_id']
        
        # Создаем элемент организации
        account_item = {
            'type': 'account',
            'name': account.get('name', f'Организация {account["id"]}'),
            'icon': 'fas fa-briefcase',
            'active': is_current,
            'children': []
        }
        
        # Всегда добавляем URL для организаций
        account_item['url'] = 'huntflow:vacancies_list'
        account_item['url_kwargs'] = {'account_id': account['id']}
        
        organization_item['children'].append(account_item)
        
        # Если это текущая организация, добавляем её подразделы
        if is_current and 'account_id' in url_kwargs:
            account_id = url_kwargs['account_id']
            
            # Вакансии
            organization_item['children'][-1]['children'].append({
                'type': 'vacancies',
                'name': 'Вакансии',
                'url': 'huntflow:vacancies_list',
                'url_kwargs': {'account_id': account_id},
                'icon': 'fas fa-briefcase',
                'active': url_name == 'vacancies_list',
                'children': []
            })
            
            # Кандидаты
            organization_item['children'][-1]['children'].append({
                'type': 'applicants',
                'name': 'Кандидаты',
                'url': 'huntflow:applicants_list',
                'url_kwargs': {'account_id': account_id},
                'icon': 'fas fa-users',
                'active': url_name in ['applicants_list', 'applicant_detail', 'applicant_edit'],
                'children': []
            })
            
            # Если есть конкретная вакансия
            if 'vacancy_id' in url_kwargs:
                vacancy_id = url_kwargs['vacancy_id']
                vacancy_name = context.get('vacancy_name', f'Вакансия {vacancy_id}')
                
                organization_item['children'][-1]['children'][0]['children'].append({
                    'type': 'vacancy',
                    'name': vacancy_name,
                    'url': 'huntflow:vacancy_detail',
                    'url_kwargs': {'account_id': account_id, 'vacancy_id': vacancy_id},
                    'icon': 'fas fa-briefcase',
                    'active': url_name == 'vacancy_detail',
                    'children': []
                })
            
            # Если есть конкретный кандидат
            if 'applicant_id' in url_kwargs:
                applicant_id = url_kwargs['applicant_id']
                applicant_name = context.get('applicant_name', f'Кандидат {applicant_id}')
                
                organization_item['children'][-1]['children'][1]['children'].append({
                    'type': 'applicant',
                    'name': applicant_name,
                    'url': 'huntflow:applicant_detail',
                    'url_kwargs': {'account_id': account_id, 'applicant_id': applicant_id},
                    'icon': 'fas fa-user',
                    'active': url_name in ['applicant_detail', 'applicant_edit'],
                    'children': []
                })
    
    menu_items.append(organization_item)
    
    # 3. Управление Chrome расширением (отдельный пункт меню /extension/)
    namespace = getattr(request.resolver_match, 'namespace', None) or ''
    menu_items.append({
        'type': 'chrome_extension',
        'name': 'Chrome расширение',
        'url': 'extension:management',
        'icon': 'fab fa-chrome',
        'active': (namespace == 'extension' and url_name == 'management'),
        'children': []
    })
    
    # 4. Gemini AI
    menu_items.append({
        'type': 'gemini',
        'name': 'Gemini AI',
        'url': 'gemini:dashboard',
        'icon': 'fas fa-robot',
        'active': url_name.startswith('gemini:'),
        'children': []
    })
    
    # 5. Админ панель - всегда последний элемент
    menu_items.append({
        'type': 'admin',
        'name': 'Админ панель',
        'url': 'admin:index',
        'icon': 'fas fa-cog',
        'active': False,
        'children': []
    })
    
    return {
        'menu_items': menu_items,
        'current_url_name': url_name
    }
