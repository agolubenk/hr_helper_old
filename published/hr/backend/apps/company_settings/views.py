from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied
import json

from .models import CompanySettings, RejectionTemplate, VacancyPrompt, VacancyPromptHistory
from .forms import CompanySettingsForm, RejectionTemplateForm


def check_staff_permission(user):
    """Проверка прав доступа"""
    if not user.is_staff:
        raise PermissionDenied("Только сотрудники могут изменять настройки компании")


def get_available_calendars(user):
    """Получает список доступных календарей для пользователя"""
    available_calendars = []
    available_calendar_ids = []
    
    if hasattr(user, 'google_oauth_account'):
        try:
            from apps.google_oauth.models import GoogleOAuthAccount
            from apps.google_oauth.services import GoogleCalendarService
            
            oauth_account = GoogleOAuthAccount.objects.filter(user=user).first()
            if oauth_account and oauth_account.is_token_valid():
                calendar_service = GoogleCalendarService(oauth_account)
                calendars = calendar_service.get_calendar_list()
                
                if calendars and 'items' in calendars:
                    available_calendars = [
                        {
                            'id': cal.get('id'),
                            'name': cal.get('summary', cal.get('id')),
                            'description': cal.get('description', '')
                        }
                        for cal in calendars['items']
                    ]
                    available_calendar_ids = [cal.get('id') for cal in calendars['items']]
        except Exception as e:
            print(f"Ошибка получения календарей: {e}")
    
    return available_calendars, available_calendar_ids


@login_required
def company_settings_overview(request):
    """Главная страница настроек компании - обзор по блокам"""
    check_staff_permission(request.user)
    
    settings_obj = CompanySettings.get_settings()
    available_calendars, available_calendar_ids = get_available_calendars(request.user)
    calendar_id_in_list = settings_obj.main_calendar_id in available_calendar_ids if settings_obj.main_calendar_id else False
    
    # Получаем информацию о шаблонах отказов
    from apps.finance.models import Grade
    active_grades = settings_obj.active_grades.all()
    
    # Подсчитываем шаблоны по типам
    templates_stats = {
        'office_format': RejectionTemplate.objects.filter(is_active=True, rejection_type='office_format', grade__isnull=True).count(),
        'finance': RejectionTemplate.objects.filter(is_active=True, rejection_type='finance', grade__isnull=True).count(),
        'finance_more': RejectionTemplate.objects.filter(is_active=True, rejection_type='finance_more', grade__isnull=True).count(),
        'finance_less': RejectionTemplate.objects.filter(is_active=True, rejection_type='finance_less', grade__isnull=True).count(),
        'general': RejectionTemplate.objects.filter(is_active=True, rejection_type='general', grade__isnull=True).count(),
        'grade': {}
    }
    
    # Подсчитываем шаблоны для каждого активного грейда
    for grade in active_grades:
        templates_stats['grade'][grade.id] = {
            'name': grade.name,
            'count': RejectionTemplate.objects.filter(is_active=True, rejection_type='grade', grade=grade).count()
        }
    
    context = {
        'settings': settings_obj,
        'available_calendars': available_calendars,
        'calendar_id_in_list': calendar_id_in_list,
        'active_grades': active_grades,
        'templates_stats': templates_stats,
    }
    
    return render(request, 'company_settings/overview.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def company_settings_basic(request):
    """Страница базовых настроек компании"""
    check_staff_permission(request.user)
    
    settings_obj = CompanySettings.get_settings()
    
    if request.method == 'POST':
        form = CompanySettingsForm(request.POST, instance=settings_obj)
        
        if form.is_valid():
            # Сохраняем все поля через форму
            form.save()
            
            messages.success(request, 'Базовые настройки успешно сохранены')
            return redirect('company_settings:basic')
        else:
            messages.error(request, 'Ошибка при сохранении настроек. Проверьте введенные данные.')
    else:
        # Создаем форму только с базовыми полями
        form = CompanySettingsForm(instance=settings_obj)
    
    available_calendars, available_calendar_ids = get_available_calendars(request.user)
    calendar_id_in_list = settings_obj.main_calendar_id in available_calendar_ids if settings_obj.main_calendar_id else False
    
    context = {
        'form': form,
        'settings': settings_obj,
        'available_calendars': available_calendars,
        'calendar_id_in_list': calendar_id_in_list,
        'org_structure_json': json.dumps(settings_obj.org_structure, ensure_ascii=False, indent=2) if settings_obj.org_structure else '{}',
    }
    
    return render(request, 'company_settings/basic.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def company_settings_grades(request):
    """Страница настроек грейдов компании"""
    check_staff_permission(request.user)
    
    settings_obj = CompanySettings.get_settings()
    
    if request.method == 'POST':
        from apps.finance.models import Grade
        grade_ids = request.POST.getlist('active_grades')
        settings_obj.active_grades.set(Grade.objects.filter(id__in=grade_ids))
        settings_obj.save()
        messages.success(request, 'Настройки грейдов успешно сохранены')
        return redirect('company_settings:grades')
    
    from apps.finance.models import Grade
    all_grades = Grade.objects.all().order_by('name')
    
    context = {
        'settings': settings_obj,
        'all_grades': all_grades,
        'active_grades': settings_obj.active_grades.all()
    }
    
    return render(request, 'company_settings/grades.html', context)


@login_required
@require_http_methods(["GET"])
def company_settings_templates(request):
    """Страница настроек шаблонов отказов"""
    check_staff_permission(request.user)
    
    settings_obj = CompanySettings.get_settings()
    active_grades = settings_obj.active_grades.all()
    
    # Получаем все шаблоны по типам (включая неактивные для редактирования)
    templates_by_type = {
        'office_format': RejectionTemplate.objects.filter(rejection_type='office_format', grade__isnull=True).order_by('title'),
        'finance': RejectionTemplate.objects.filter(rejection_type='finance', grade__isnull=True).order_by('title'),
        'finance_more': RejectionTemplate.objects.filter(rejection_type='finance_more', grade__isnull=True).order_by('title'),
        'finance_less': RejectionTemplate.objects.filter(rejection_type='finance_less', grade__isnull=True).order_by('title'),
        'general': RejectionTemplate.objects.filter(rejection_type='general', grade__isnull=True).order_by('title'),
    }
    
    # Получаем шаблоны для каждого активного грейда
    grade_templates = {}
    for grade in active_grades:
        grade_templates[grade.id] = {
            'grade': grade,
            'templates': RejectionTemplate.objects.filter(rejection_type='grade', grade=grade).order_by('title')
        }
    
    # Форма для создания нового шаблона
    form = RejectionTemplateForm()
    
    context = {
        'settings': settings_obj,
        'active_grades': active_grades,
        'templates_by_type': templates_by_type,
        'grade_templates': grade_templates,
        'form': form,
    }
    
    return render(request, 'company_settings/templates.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def company_settings_vacancy_prompt(request):
    """Страница настроек единого промпта для вакансий"""
    check_staff_permission(request.user)
    
    prompt_obj = VacancyPrompt.get_prompt()
    history = VacancyPromptHistory.objects.filter(prompt=prompt_obj).order_by('-updated_at')[:50]  # Последние 50 записей
    
    if request.method == 'POST':
        prompt_text = request.POST.get('prompt', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not prompt_text:
            messages.error(request, 'Текст промпта не может быть пустым')
        else:
            prompt_obj.prompt = prompt_text
            prompt_obj.is_active = is_active
            prompt_obj.save(updated_by=request.user)
            messages.success(request, 'Промпт успешно сохранен')
            return redirect('company_settings:vacancy_prompt')
    
    context = {
        'settings': CompanySettings.get_settings(),
        'prompt': prompt_obj,
        'history': history,
    }
    
    return render(request, 'company_settings/vacancy-prompt.html', context)


@login_required
@require_http_methods(["GET"])
def vacancy_prompt_api(request):
    """API для получения единого промпта для вакансий"""
    try:
        prompt_obj = VacancyPrompt.get_prompt()
        
        # Возвращаем данные в формате, который ожидает фронтенд
        return JsonResponse({
            'prompt': prompt_obj.prompt,
            'is_active': prompt_obj.is_active,
            'created_at': prompt_obj.created_at.isoformat() if prompt_obj.created_at else None,
            'updated_at': prompt_obj.updated_at.isoformat() if prompt_obj.updated_at else None,
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


# Оставляем старую функцию для обратной совместимости
@login_required
@require_http_methods(["GET", "POST"])
def company_settings_view(request):
    """Страница настроек компании (старая версия - редирект на обзор)"""
    return redirect('company_settings:overview')


@login_required
@require_http_methods(["POST"])
def company_settings_api(request):
    """API для сохранения настроек компании через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        data = json.loads(request.body)
        settings_obj = CompanySettings.get_settings()
        
        # Обновляем поля
        if 'company_name' in data:
            settings_obj.company_name = data['company_name']
        if 'theme' in data:
            settings_obj.theme = data['theme']
        if 'main_calendar_id' in data:
            settings_obj.main_calendar_id = data['main_calendar_id']
        if 'org_structure' in data:
            settings_obj.org_structure = data['org_structure']
        if 'active_grades' in data:
            from apps.finance.models import Grade
            grade_ids = data['active_grades']
            settings_obj.active_grades.set(Grade.objects.filter(id__in=grade_ids))
        if 'ignore_non_accepted_meetings' in data:
            settings_obj.ignore_non_accepted_meetings = bool(data['ignore_non_accepted_meetings'])
        
        settings_obj.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Настройки сохранены успешно'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["GET"])
def rejection_templates_api(request):
    """API для получения шаблонов отказов"""
    rejection_type = request.GET.get('rejection_type')
    grade_id = request.GET.get('grade_id')
    
    # Получаем все шаблоны (включая неактивные для редактирования)
    templates = RejectionTemplate.objects.all()
    
    if rejection_type:
        templates = templates.filter(rejection_type=rejection_type)
    
    if grade_id:
        templates = templates.filter(grade_id=grade_id)
    elif rejection_type and rejection_type != 'grade':
        # Для не-грейдовых типов grade должен быть null
        templates = templates.filter(grade__isnull=True)
    
    templates_data = []
    for template in templates.order_by('title'):
        templates_data.append({
            'id': template.id,
            'rejection_type': template.rejection_type,
            'rejection_type_display': template.get_rejection_type_display(),
            'grade_id': template.grade.id if template.grade else None,
            'grade_name': template.grade.name if template.grade else None,
            'title': template.title,
            'message': template.message,
            'is_active': template.is_active,
            'created_at': template.created_at.isoformat() if template.created_at else None,
            'updated_at': template.updated_at.isoformat() if template.updated_at else None,
        })
    
    return JsonResponse({
        'success': True,
        'templates': templates_data
    })


@login_required
@require_http_methods(["GET"])
def active_grades_api(request):
    """API для получения активных грейдов компании"""
    settings = CompanySettings.get_settings()
    active_grades = settings.active_grades.all()
    
    grades_data = []
    for grade in active_grades:
        grades_data.append({
            'id': grade.id,
            'name': grade.name,
        })
    
    return JsonResponse({
        'success': True,
        'active_grades': grades_data
    })


@login_required
@require_http_methods(["POST"])
def rejection_template_create_api(request):
    """API для создания шаблона отказа через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        data = json.loads(request.body)
        # Обрабатываем поле grade - если rejection_type не 'grade', устанавливаем grade в None
        if data.get('rejection_type') != 'grade':
            data['grade'] = None
        elif 'grade' in data and not data['grade']:
            return JsonResponse({
                'success': False,
                'error': 'Для типа отказа "Грейд" обязательно укажите грейд',
                'errors': {'grade': ['Для типа отказа "Грейд" обязательно укажите грейд']}
            })
        
        form = RejectionTemplateForm(data)
        
        if form.is_valid():
            template = form.save(commit=False)
            template.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Шаблон успешно создан',
                'template': {
                    'id': template.id,
                    'rejection_type': template.rejection_type,
                    'rejection_type_display': template.get_rejection_type_display(),
                    'grade_id': template.grade.id if template.grade else None,
                    'grade_name': template.grade.name if template.grade else None,
                    'title': template.title,
                    'message': template.message,
                    'is_active': template.is_active,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ошибка валидации',
                'errors': form.errors
            })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def rejection_template_update_api(request, template_id):
    """API для обновления шаблона отказа через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        template = RejectionTemplate.objects.get(id=template_id)
        data = json.loads(request.body)
        # Обрабатываем поле grade - если rejection_type не 'grade', устанавливаем grade в None
        if data.get('rejection_type') != 'grade':
            data['grade'] = None
        elif 'grade' in data and not data['grade']:
            return JsonResponse({
                'success': False,
                'error': 'Для типа отказа "Грейд" обязательно укажите грейд',
                'errors': {'grade': ['Для типа отказа "Грейд" обязательно укажите грейд']}
            })
        
        form = RejectionTemplateForm(data, instance=template)
        
        if form.is_valid():
            template = form.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Шаблон успешно обновлен',
                'template': {
                    'id': template.id,
                    'rejection_type': template.rejection_type,
                    'rejection_type_display': template.get_rejection_type_display(),
                    'grade_id': template.grade.id if template.grade else None,
                    'grade_name': template.grade.name if template.grade else None,
                    'title': template.title,
                    'message': template.message,
                    'is_active': template.is_active,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ошибка валидации',
                'errors': form.errors
            })
    except RejectionTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Шаблон не найден'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["DELETE", "POST"])
def rejection_template_delete_api(request, template_id):
    """API для удаления шаблона отказа через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        template = RejectionTemplate.objects.get(id=template_id)
        template_title = template.title
        template.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Шаблон "{template_title}" успешно удален'
        })
    except RejectionTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Шаблон не найден'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["GET"])
def rejection_template_get_api(request, template_id):
    """API для получения данных шаблона отказа"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        template = RejectionTemplate.objects.get(id=template_id)
        
        return JsonResponse({
            'success': True,
            'template': {
                'id': template.id,
                'rejection_type': template.rejection_type,
                'rejection_type_display': template.get_rejection_type_display(),
                'grade_id': template.grade.id if template.grade else None,
                'grade_name': template.grade.name if template.grade else None,
                'title': template.title,
                'message': template.message,
                'is_active': template.is_active,
            }
        })
    except RejectionTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Шаблон не найден'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

