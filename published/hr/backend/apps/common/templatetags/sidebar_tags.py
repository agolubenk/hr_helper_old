from django import template
from django.templatetags.static import static
from django.urls import reverse, NoReverseMatch
from django.utils.safestring import mark_safe

register = template.Library()

# Конфигурация многоуровневого меню
SIDEBAR_MENU = {
    'chat_helper': {
        'title': 'Главная',
        'icon': 'hrhelper-logo',
        'url': 'google_oauth:chat_workflow',
        'submenu': {}
    },
    'huntflow': {
        'title': 'Huntflow',
        'icon': 'fas fa-users',
        'url': 'huntflow:dashboard',
        'submenu': {}
    },
    'google_oauth': {
        'title': 'Google OAuth', 
        'icon': 'fab fa-google',
        'url': 'google_oauth:dashboard',
        'submenu': {
            'calendar': {
                'title': 'Календарь',
                'icon': 'fas fa-calendar',
                'url': 'google_oauth:calendar_events'
            },
            'invites': {
                'title': 'Инвайты',
                'icon': 'fas fa-envelope',
                'url': 'google_oauth:invite_dashboard',
                'submenu': {
                    'list': {
                        'title': 'Список инвайтов',
                        'icon': 'fas fa-list',
                        'url': 'google_oauth:invite_list'
                    },
                    'create': {
                        'title': 'Создать инвайт',
                        'icon': 'fas fa-plus',
                        'url': 'google_oauth:invite_create'
                    }
                }
            },
            'scorecard_settings': {
                'title': 'Настройки Scorecard',
                'icon': 'fas fa-folder-tree',
                'url': 'google_oauth:scorecard_path_settings'
            }
        }
    },
    'extension': {
        'title': 'Chrome расширение',
        'icon': 'fab fa-chrome',
        'url': 'extension:management',
        'submenu': {}
    },
    'gemini': {
        'title': 'Gemini AI',
        'icon': 'fas fa-robot',
        'url': 'gemini:dashboard',
        'submenu': {}
    },
    'answer_library': {
        'title': 'Библиотека ответов',
        'icon': 'fas fa-book',
        'url': 'answer_library:index',
        'submenu': {}
    },
    'vacancies_finance': {
        'title': 'Вакансии и финансы',
        'icon': 'fas fa-briefcase',
        'url': 'vacancies:dashboard',
        'submenu': {
            'dashboard': {
                'title': 'Дашборд',
                'icon': 'fas fa-tachometer-alt',
                'url': 'vacancies:dashboard'
            },
            'vacancies': {
                'title': 'Вакансии',
                'icon': 'fas fa-list',
                'url': 'vacancies:vacancy_list'
            },
            'hiring_plans': {
                'title': 'Заявки на найм',
                'icon': 'fas fa-users',
                'url': 'hiring_plan:hiring_requests_list',
                'submenu': {
                    'requests': {
                        'title': 'Все заявки',
                        'icon': 'fas fa-list',
                        'url': 'hiring_plan:hiring_requests_list'
                    },
                    'metrics': {
                        'title': 'Метрики и KPI',
                        'icon': 'fas fa-chart-bar',
                        'url': 'hiring_plan:metrics_dashboard'
                    },
                    'sla': {
                        'title': 'Управление SLA',
                        'icon': 'fas fa-clock',
                        'url': 'hiring_plan:sla_list'
                    },
                    'yearly': {
                        'title': 'Годовая таблица',
                        'icon': 'fas fa-calendar-alt',
                        'url': 'hiring_plan:yearly_hiring_plan'
                    }
                }
            },
            'salary_ranges': {
                'title': 'Зарплатные вилки',
                'icon': 'fas fa-money-bill-wave',
                'url': 'vacancies:salary_ranges_list'
            },
            'grades_currency': {
                'title': 'Грейды, налоги и курсы',
                'icon': 'fas fa-chart-line',
                'url': 'finance:dashboard'
            },
            'benchmarks': {
                'title': 'Бенчмарки',
                'icon': 'fas fa-chart-bar',
                'url': 'finance:benchmarks_dashboard',
                'submenu': {
                    'dashboard': {
                        'title': 'Dashboard',
                        'icon': 'fas fa-tachometer-alt',
                        'url': 'finance:benchmarks_dashboard'
                    },
                    'list': {
                        'title': 'Все бенчмарки',
                        'icon': 'fas fa-list',
                        'url': 'finance:benchmarks_list'
                    },
                    'settings': {
                        'title': 'Настройки',
                        'icon': 'fas fa-cog',
                        'url': 'finance:benchmark_settings'
                    }
                }
            }
        }
    },
    'interviewers': {
        'title': 'Интервьюеры',
        'icon': 'fas fa-user-tie',
        'url': 'interviewers:interviewer_dashboard',
        'submenu': {
            'list': {
                'title': 'Интервьюеры',
                'icon': 'fas fa-users',
                'url': 'interviewers:interviewer_list'
            },
            'rules': {
                'title': 'Правила привлечения',
                'icon': 'fas fa-gavel',
                'url': 'interviewers:rule_list'
            }
        }
    },
    'integrations': {
        'title': 'Интеграции',
        'icon': 'fas fa-plug',
        'url': 'clickup_int:dashboard',
        'submenu': {
            'clickup': {
                'title': 'ClickUp',
                'icon': 'fas fa-tasks',
                'url': 'clickup_int:dashboard',
                'submenu': {
                    'dashboard': {
                        'title': 'Главная',
                        'icon': 'fas fa-tachometer-alt',
                        'url': 'clickup_int:dashboard'
                    },
                    'lists': {
                        'title': 'Списки',
                        'icon': 'fas fa-list',
                        'url': 'clickup_int:tasks_list'
                    },
                    'import': {
                        'title': 'Импорт',
                        'icon': 'fas fa-upload',
                        'url': 'clickup_int:bulk_import'
                    },
                    'logs': {
                        'title': 'Логи',
                        'icon': 'fas fa-history',
                        'url': 'clickup_int:sync_logs'
                    },
                    'settings': {
                        'title': 'Настройки',
                        'icon': 'fas fa-cog',
                        'url': 'clickup_int:settings'
                    }
                }
            },
            'hhru': {
                'title': 'HeadHunter.ru',
                'icon': 'fas fa-briefcase',
                'url': 'hhru:dashboard',
                'submenu': {
                    'dashboard': {
                        'title': 'Главная',
                        'icon': 'fas fa-tachometer-alt',
                        'url': 'hhru:dashboard'
                    },
                    'configurations': {
                        'title': 'Конфигурации OAuth',
                        'icon': 'fas fa-cog',
                        'url': 'hhru:configurations_list'
                    },
                    'accounts': {
                        'title': 'Мои аккаунты',
                        'icon': 'fas fa-user-circle',
                        'url': 'hhru:accounts_list'
                    },
                    'logs': {
                        'title': 'Логи',
                        'icon': 'fas fa-history',
                        'url': 'hhru:logs_list'
                    },
                    'vacancies_active': {
                        'title': 'Вакансии (активные)',
                        'icon': 'fas fa-briefcase',
                        'url': 'hhru:vacancies_active'
                    },
                    'vacancies_archived': {
                        'title': 'Вакансии (архив)',
                        'icon': 'fas fa-archive',
                        'url': 'hhru:vacancies_archived'
                    }
                }
            }
        }
    },
    'wiki': {
        'title': 'Вики',
        'icon': 'fas fa-book',
        'url': 'wiki:list',
        'submenu': {}
    },
    'reporting': {
        'title': 'Отчетность',
        'icon': 'fas fa-chart-bar',
        'url': 'reporting:dashboard',
        'submenu': {
            'dashboard': {
                'title': 'Главная',
                'icon': 'fas fa-tachometer-alt',
                'url': 'reporting:dashboard'
            },
            'company': {
                'title': 'По компании',
                'icon': 'fas fa-building',
                'url': 'reporting:company_report'
            },
            'recruiter': {
                'title': 'По рекрутеру',
                'icon': 'fas fa-user-tie',
                'url': 'reporting:recruiter_list'
            },
            'vacancy': {
                'title': 'По вакансии',
                'icon': 'fas fa-briefcase',
                'url': 'reporting:vacancy_list'
            },
            'interviewer': {
                'title': 'По интервьюеру',
                'icon': 'fas fa-user-check',
                'url': 'reporting:interviewer_list'
            }
        }
    }
}

def is_menu_active(request, menu_config):
    """Проверяет, активен ли пункт меню - точное совпадение или начало пути"""
    try:
        # Проверка точного совпадения URL
        try:
            menu_url = reverse(menu_config['url'])
            if request.path == menu_url:
                return True
        except NoReverseMatch:
            pass
            
        # Проверка по началу пути для вложенных страниц
        try:
            menu_url = reverse(menu_config['url'])
            if request.path.startswith(menu_url.rstrip('/')):
                return True
        except NoReverseMatch:
            pass
            
    except Exception:
        pass
    
    return False

def has_active_submenu(request, submenu):
    """Проверяет, есть ли активные пункты в подменю"""
    for key, item in submenu.items():
        if is_menu_active(request, item):
            return True
        if 'submenu' in item and has_active_submenu(request, item['submenu']):
            return True
    return False

def render_menu_item(request, key, item, level=0):
    """Рендерит пункт меню"""
    try:
        url = reverse(item['url'])
    except NoReverseMatch:
        url = '#'
    
    is_active = is_menu_active(request, item)
    has_submenu = 'submenu' in item and item['submenu']
    has_active_child = has_submenu and has_active_submenu(request, item['submenu'])
    should_expand = is_active or has_active_child
    
    # CSS классы
    nav_classes = ['nav-link']
    # Добавляем active для активного элемента ИЛИ если есть активный дочерний элемент
    if is_active or has_active_child:
        nav_classes.append('active')
    if has_submenu:
        nav_classes.append('menu-toggle')
    
    # Отступы для вложенности
    margin_class = f'ms-{level}' if level > 0 else ''
    
    # ID для collapse
    submenu_id = f"{key}-submenu-{level}" if has_submenu else ""
    
    if item['icon'] == 'hrhelper-logo':
        light_url = static('img/light.png')
        dark_url = static('img/dark.png')
        logo_html = (
            f'<span class="hrhelper-logo-adaptive sidebar-logo-wrap" '
            f'style="width: 38px; height: 38px; margin-top: -12px; margin-left: -11px; margin-bottom: -12px; margin-right: -4px; display: inline-flex; align-items: center;">'
            f'<img src="{light_url}" class="sidebar-logo-img light-theme-logo" alt="" style="width:38px;height:38px;object-fit:contain">'
            f'<img src="{dark_url}" class="sidebar-logo-img dark-theme-logo" alt="" style="width:38px;height:38px;object-fit:contain">'
            f'</span>'
        )
    else:
        logo_html = f'<i class="{item["icon"]} me-2"></i>'
    
    html = f'''
    <li class="nav-item {margin_class} {'has-submenu' if has_submenu else ''}">
        <a class="{' '.join(nav_classes)}" 
           href="{url}"
           {'data-bs-toggle="collapse"' if has_submenu else ''}
           {'data-bs-target="#' + submenu_id + '"' if has_submenu else ''}
           {'aria-expanded="' + ('true' if should_expand else 'false') + '"' if has_submenu else ''}>
            {logo_html}
            {item['title']}
            {'<i class="fas fa-chevron-down submenu-arrow ms-auto"></i>' if has_submenu else ''}
        </a>'''
    
    if has_submenu:
        html += f'''
        <div class="collapse {'show' if should_expand else ''}" id="{submenu_id}">
            <ul class="nav flex-column">'''
        
        for sub_key, sub_item in item['submenu'].items():
            html += render_menu_item(request, sub_key, sub_item, level + 1)
        
        html += '''
            </ul>
        </div>'''
    
    html += '</li>'
    return html

@register.simple_tag(takes_context=True)
def render_sidebar_menu(context):
    """Рендерит полное многоуровневое меню"""
    request = context['request']
    
    html = '<ul class="nav flex-column">'
    
    for key, item in SIDEBAR_MENU.items():
        html += render_menu_item(request, key, item)
    
    html += '</ul>'
    
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def get_admin_url(context):
    """Возвращает URL админки для текущего приложения"""
    request = context['request']
    namespace = request.resolver_match.namespace if request.resolver_match else None
    
    # Маппинг namespace -> admin app name
    namespace_to_admin = {
        'wiki': 'wiki',
        'company_settings': 'company_settings',
        'finance': 'finance',
        'vacancies': 'vacancies',
        'hiring_plan': 'hiring_plan',
        'google_oauth': 'google_oauth',
        'gemini': 'gemini',
        'answer_library': 'answer_library',
        'interviewers': 'interviewers',
        'accounts': 'accounts',
        'clickup_int': 'clickup_int',
        'huntflow': 'huntflow',
        'extension': 'huntflow',
        'reporting': 'reporting',
    }
    
    if namespace and namespace in namespace_to_admin:
        admin_app = namespace_to_admin[namespace]
        return f'/admin/{admin_app}/'
    
    return '/admin/'
