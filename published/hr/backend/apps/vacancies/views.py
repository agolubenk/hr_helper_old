import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods

from .models import Vacancy
from apps.finance.models import SalaryRange
from .forms import VacancyForm, VacancySearchForm, SalaryRangeForm, SalaryRangeSearchForm
from apps.finance.models import Grade
# from .logic.vacancy_handlers import VacancyHandler  # УДАЛЕНО - логика перенесена в logic/candidate/
# from .logic.salary_range_handlers import SalaryRangeHandler  # УДАЛЕНО - логика перенесена в finance/views_modules/
# from .logic.response_handlers import ResponseHandler  # УДАЛЕНО - заменен на logic/base/response_handler.py

# Импорты новых модулей
from logic.candidate.vacancy_management import (
    vacancy_list, vacancy_detail, vacancy_create, 
    vacancy_update, vacancy_delete, vacancy_duplicate
)
from logic.base.response_handler import UnifiedResponseHandler


@login_required
def dashboard(request):
    """
    Дашборд локальных данных по вакансиям
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - logic.candidate.vacancy_management.vacancy_dashboard
    
    ОБРАБОТКА:
    - Делегирование обработки в logic модуль
    - Получение статистики по вакансиям пользователя
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Результат выполнения vacancy_dashboard()
    
    СВЯЗИ:
    - Использует: logic.candidate.vacancy_management.vacancy_dashboard
    - Передает: request объект
    - Может вызываться из: vacancies/ URL patterns
    """
    # Используем новую логику из logic модуля
    from logic.candidate.vacancy_management import vacancy_dashboard
    return vacancy_dashboard(request)


@login_required
def vacancy_list(request):
    """
    Список вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.GET: search, recruiter, is_active (параметры фильтрации)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - VacancySearchForm для валидации параметров поиска
    - logic.candidate.vacancy_management.vacancy_list для обработки
    
    ОБРАБОТКА:
    - Получение параметров поиска из GET запроса
    - Делегирование обработки в logic модуль
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Результат выполнения logic_vacancy_list()
    
    СВЯЗИ:
    - Использует: VacancySearchForm, logic.candidate.vacancy_management.vacancy_list
    - Передает: request объект с параметрами фильтрации
    - Может вызываться из: vacancies/ URL patterns
    """
    # Получаем параметры поиска
    search_form = VacancySearchForm(request.GET)
    search_query = request.GET.get('search', '')
    recruiter_filter = request.GET.get('recruiter', '')
    status_filter = request.GET.get('is_active', '')
    
    # Используем новую логику из logic модуля
    from logic.candidate.vacancy_management import vacancy_list as logic_vacancy_list
    return logic_vacancy_list(request)


@login_required
def vacancy_detail(request, pk):
    """Детальная информация о вакансии"""
    # Используем новую логику из logic модуля
    from logic.candidate.vacancy_management import vacancy_detail as logic_vacancy_detail
    return logic_vacancy_detail(request, pk)


@login_required
def vacancy_create(request):
    """Создание новой вакансии"""
    if request.method == 'POST':
        form = VacancyForm(request.POST, user=request.user)
        if form.is_valid():
            vacancy = form.save()
            messages.success(request, f'Вакансия "{vacancy.name}" успешно создана!')
            return redirect('vacancies:vacancy_detail', pk=vacancy.pk)
    else:
        form = VacancyForm(user=request.user)
    
    # Получаем все активные зарплатные вилки
    salary_ranges = SalaryRange.objects.filter(is_active=True).order_by('grade__name')
    
    # Получаем активный единый промпт из настроек компании
    from apps.company_settings.models import VacancyPrompt
    common_prompt = None
    has_active_common_prompt = False
    try:
        prompt_obj = VacancyPrompt.get_prompt()
        if prompt_obj.is_active:
            common_prompt = prompt_obj.prompt
            has_active_common_prompt = True
    except Exception:
        pass
    
    context = {
        'form': form,
        'title': 'Создание вакансии',
        'submit_text': 'Создать вакансию',
        'salary_ranges': salary_ranges,
        'common_prompt': common_prompt,
        'has_active_common_prompt': has_active_common_prompt,
    }
    
    return render(request, 'vacancies/vacancy_form.html', context)


@login_required
def vacancy_edit(request, pk):
    """Редактирование вакансии"""
    vacancy = get_object_or_404(Vacancy, pk=pk)
    
    if request.method == 'POST':
        form = VacancyForm(request.POST, instance=vacancy, user=request.user)
        if form.is_valid():
            vacancy = form.save()
            messages.success(request, f'Вакансия "{vacancy.name}" успешно обновлена!')
            return redirect('vacancies:vacancy_detail', pk=vacancy.pk)
    else:
        form = VacancyForm(instance=vacancy, user=request.user)
    
    # Получаем только зарплатные вилки для ЭТОЙ вакансии
    salary_ranges = SalaryRange.objects.filter(vacancy=vacancy).order_by('grade__name')
    
    # Получаем активный единый промпт из настроек компании
    from apps.company_settings.models import VacancyPrompt
    common_prompt = None
    has_active_common_prompt = False
    try:
        prompt_obj = VacancyPrompt.get_prompt()
        if prompt_obj.is_active:
            common_prompt = prompt_obj.prompt
            has_active_common_prompt = True
    except Exception:
        pass
    
    context = {
        'form': form,
        'vacancy': vacancy,
        'title': f'Редактирование вакансии "{vacancy.name}"',
        'submit_text': 'Сохранить изменения',
        'salary_ranges': salary_ranges,
        'common_prompt': common_prompt,
        'has_active_common_prompt': has_active_common_prompt,
    }
    
    return render(request, 'vacancies/vacancy_form.html', context)


@login_required
@require_POST
def vacancy_delete(request, pk):
    """Удаление вакансии"""
    vacancy = get_object_or_404(Vacancy, pk=pk)
    vacancy_name = vacancy.name
    
    try:
        vacancy.delete()
        messages.success(request, f'Вакансия "{vacancy_name}" успешно удалена!')
        return redirect('vacancies:vacancy_list')
    except Exception as e:
        messages.error(request, f'Ошибка при удалении вакансии: {str(e)}')
        return redirect('vacancies:vacancy_detail', pk=pk)


@login_required
@require_POST
def vacancy_toggle_active(request, pk):
    """Переключение статуса активности вакансии"""
    result = VacancyHandler.toggle_active_logic(pk, request)
    
    if result['success']:
        return ResponseHandler.success_response(
            {'is_active': result['is_active']},
            result['message']
        )
    else:
        return ResponseHandler.error_response(result['message'])


# Представления для зарплатных вилок

@login_required
def salary_ranges_list(request):
    """Список зарплатных вилок"""
    # Получаем параметры поиска
    search_form = SalaryRangeSearchForm(request.GET)
    search_query = request.GET.get('search', '')
    vacancy_filter = request.GET.get('vacancy', '')
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('is_active', '')
    
    # Используем обработчик поиска
    search_params = {
        'query': search_query,
        'vacancy_id': vacancy_filter,
        'grade_id': grade_filter,
        'is_active': status_filter
    }
    # Получаем зарплатные вилки с фильтрацией
    salary_ranges = SalaryRange.objects.all()
    
    # Применяем фильтры
    if search_query:
        salary_ranges = salary_ranges.filter(
            Q(vacancy__name__icontains=search_query) |
            Q(grade__name__icontains=search_query)
        )
    
    if vacancy_filter:
        salary_ranges = salary_ranges.filter(vacancy_id=vacancy_filter)
    
    if grade_filter:
        salary_ranges = salary_ranges.filter(grade_id=grade_filter)
    
    if status_filter and status_filter != '':
        if status_filter == 'true':
            salary_ranges = salary_ranges.filter(is_active=True)
        elif status_filter == 'false':
            salary_ranges = salary_ranges.filter(is_active=False)
    
    salary_ranges = salary_ranges.order_by('-created_at')
    total_count = salary_ranges.count()
    active_count = salary_ranges.filter(is_active=True).count()
    inactive_count = salary_ranges.filter(is_active=False).count()

    # Пагинация
    paginator = Paginator(salary_ranges, 10)  # 10 вилок на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    from django.utils import timezone

    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'search_query': search_query,
        'vacancy_filter': vacancy_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'page_generated_at': timezone.now()
    }
    
    response = render(request, 'vacancies/salary_ranges_list.html', context)
    
    # Добавляем заголовки для предотвращения кэширования
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response


@login_required
def salary_range_detail(request, pk):
    """Детальная информация о зарплатной вилке"""
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    
    context = {
        'salary_range': salary_range,
    }
    
    return render(request, 'vacancies/salary_range_detail.html', context)


@login_required
def salary_range_create(request):
    """Создание новой зарплатной вилки"""
    if request.method == 'POST':
        form = SalaryRangeForm(request.POST)
        if form.is_valid():
            salary_range = form.save()
            messages.success(request, f'Зарплатная вилка для грейда "{salary_range.grade.name}" успешно создана!')
            
            # Проверяем параметр next для редиректа
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('vacancies:salary_range_detail', pk=salary_range.pk)
    else:
        form = SalaryRangeForm()
    
    context = {
        'form': form,
        'title': 'Создание зарплатной вилки',
        'submit_text': 'Создать зарплатную вилку',
        'next_url': request.GET.get('next', ''),
    }
    
    return render(request, 'vacancies/salary_range_form.html', context)


@login_required
def salary_range_edit(request, pk):
    """Редактирование зарплатной вилки"""
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    
    if request.method == 'POST':
        form = SalaryRangeForm(request.POST, instance=salary_range)
        if form.is_valid():
            salary_range = form.save()
            messages.success(request, f'Зарплатная вилка для грейда "{salary_range.grade.name}" успешно обновлена!')
            
            # Проверяем параметр next для редиректа
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('vacancies:salary_range_detail', pk=salary_range.pk)
    else:
        form = SalaryRangeForm(instance=salary_range)
    
    context = {
        'form': form,
        'salary_range': salary_range,
        'title': f'Редактирование зарплатной вилки для грейда "{salary_range.grade.name}"',
        'submit_text': 'Сохранить изменения',
        'next_url': request.GET.get('next', ''),
    }
    
    return render(request, 'vacancies/salary_range_form.html', context)


@login_required
@require_POST
def salary_range_delete(request, pk):
    """Удаление зарплатной вилки"""
    salary_range = get_object_or_404(SalaryRange, pk=pk)
    grade_name = salary_range.grade.name
    
    try:
        salary_range.delete()
        messages.success(request, f'Зарплатная вилка для грейда "{grade_name}" успешно удалена!')
        return redirect('vacancies:salary_ranges_list')
    except Exception as e:
        messages.error(request, f'Ошибка при удалении зарплатной вилки: {str(e)}')
        return redirect('vacancies:salary_range_detail', pk=pk)


@login_required
@require_POST
def salary_range_toggle_active(request, pk):
    """Переключение статуса активности зарплатной вилки"""
    result = SalaryRangeHandler.toggle_active_logic(pk, request)

    if result['success']:
        return ResponseHandler.success_response(
            {'is_active': result['is_active']},
            result['message']
        )
    else:
        return ResponseHandler.error_response(result['message'])


@login_required
@require_http_methods(['GET'])
def salary_ranges_export_json(request):
    """Скачивание всех зарплатных вилок в виде JSON-файла."""
    from apps.finance.export_import import export_salary_ranges_json
    data = export_salary_ranges_json()
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    from django.utils import timezone
    filename = f'salary_ranges_export_{timezone.now().strftime("%Y%m%d_%H%M")}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['POST'])
def salary_ranges_import_json(request):
    """Импорт зарплатных вилок из загруженного JSON-файла."""
    from apps.finance.export_import import import_salary_ranges_json

    if not request.FILES.get('json_file'):
        messages.error(request, 'Выберите JSON-файл для импорта.')
        return redirect('vacancies:salary_ranges_list')

    try:
        raw = request.FILES['json_file'].read().decode('utf-8')
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        messages.error(request, f'Неверный формат JSON: {e}')
        return redirect('vacancies:salary_ranges_list')

    created, updated, errors = import_salary_ranges_json(data)
    if errors:
        for err in errors[:10]:
            messages.warning(request, err)
        if len(errors) > 10:
            messages.warning(request, f'... и ещё {len(errors) - 10} ошибок.')
    if created or updated:
        messages.success(request, f'Импорт завершён: создано {created}, обновлено {updated}.')
    elif not errors:
        messages.info(request, 'Нет данных для импорта.')
    return redirect('vacancies:salary_ranges_list')


@login_required
@require_http_methods(['GET'])
def vacancies_export_json(request):
    """Скачивание всех вакансий в виде JSON-файла."""
    from .export_import import export_vacancies_json
    data = export_vacancies_json()
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    from django.utils import timezone
    filename = f'vacancies_export_{timezone.now().strftime("%Y%m%d_%H%M")}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['POST'])
def vacancies_import_json(request):
    """Импорт вакансий из загруженного JSON-файла."""
    from .export_import import import_vacancies_json

    if not request.FILES.get('json_file'):
        messages.error(request, 'Выберите JSON-файл для импорта.')
        return redirect('vacancies:vacancy_list')

    try:
        raw = request.FILES['json_file'].read().decode('utf-8')
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        messages.error(request, f'Неверный формат JSON: {e}')
        return redirect('vacancies:vacancy_list')

    created, updated, errors = import_vacancies_json(data)
    if errors:
        for err in errors[:10]:
            messages.warning(request, err)
        if len(errors) > 10:
            messages.warning(request, f'... и ещё {len(errors) - 10} ошибок.')
    if created or updated:
        messages.success(request, f'Импорт завершён: создано {created}, обновлено {updated}.')
    elif not errors:
        messages.info(request, 'Нет данных для импорта.')
    return redirect('vacancies:vacancy_list')


@login_required
@require_POST
def update_scorecards(request, pk):
    """Обновление будущих скоркардов для вакансии"""
    from datetime import datetime
    from apps.google_oauth.services import GoogleDriveService, GoogleSheetsService, GoogleOAuthService
    from apps.google_oauth.models import Invite
    import re
    
    try:
        # Получаем вакансию
        vacancy = get_object_or_404(Vacancy, pk=pk)
        
        # Проверяем права доступа (основной или один из дополнительных рекрутеров)
        if not (request.user == vacancy.recruiter or vacancy.additional_recruiters.filter(pk=request.user.pk).exists() or request.user.is_superuser):
            return JsonResponse({
                'success': False,
                'message': 'Недостаточно прав для обновления скоркардов'
            })
        
        # Проверяем наличие ссылки на шаблон
        if not vacancy.scorecard_link:
            return JsonResponse({
                'success': False,
                'message': 'Не указана ссылка на шаблон scorecard'
            })
        
        # Проверяем, что у пользователя есть Google OAuth аккаунт
        try:
            from apps.google_oauth.models import GoogleOAuthAccount
            oauth_account = GoogleOAuthAccount.objects.get(user=request.user)
            if not oauth_account.is_token_valid():
                return JsonResponse({
                    'success': False,
                    'message': 'Google OAuth токен истек. Пожалуйста, повторно авторизуйтесь в Google OAuth.'
                })
            
            # Проверяем необходимые scopes
            required_scopes = [
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            
            missing_scopes = []
            for scope in required_scopes:
                if scope not in oauth_account.scopes:
                    missing_scopes.append(scope)
            
            if missing_scopes:
                return JsonResponse({
                    'success': False,
                    'message': f'Недостаточно разрешений Google. Требуются: {", ".join(missing_scopes)}. Пожалуйста, повторно авторизуйтесь в Google OAuth.'
                })
                
        except GoogleOAuthAccount.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'У пользователя не настроена авторизация Google. Пожалуйста, авторизуйтесь в Google OAuth.'
            })
        
        # Извлекаем ID файла из ссылки на шаблон
        def extract_file_id_from_url(url):
            """Извлечь ID файла из URL Google Sheets"""
            patterns = [
                r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
                r'id=([a-zA-Z0-9-_]+)',
                r'/([a-zA-Z0-9-_]+)/edit'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None
        
        template_file_id = extract_file_id_from_url(vacancy.scorecard_link)
        if not template_file_id:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось извлечь ID файла из ссылки на шаблон'
            })
        
        # Инициализируем сервисы
        print(f"DEBUG UPDATE: Инициализируем Google сервисы для пользователя {request.user}")
        try:
            oauth_service = GoogleOAuthService(request.user)
            drive_service = GoogleDriveService(oauth_service)
            sheets_service = GoogleSheetsService(oauth_service)
            print(f"DEBUG UPDATE: ✅ Google сервисы инициализированы успешно")
        except Exception as e:
            print(f"DEBUG UPDATE: ❌ Ошибка инициализации Google сервисов: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Ошибка инициализации Google сервисов: {str(e)}'
            })
        
        # Проверяем доступность шаблона
        if not drive_service.file_exists(template_file_id):
            return JsonResponse({
                'success': False,
                'message': 'Шаблон scorecard недоступен или не найден'
            })
        
        # Получаем содержимое шаблона
        print(f"DEBUG UPDATE: Получаем содержимое шаблона {template_file_id}")
        try:
            template_content = sheets_service.get_spreadsheet_content(template_file_id)
            if not template_content:
                return JsonResponse({
                    'success': False,
                    'message': 'Не удалось получить содержимое шаблона'
                })
            print(f"DEBUG UPDATE: ✅ Содержимое шаблона получено успешно")
        except Exception as e:
            print(f"DEBUG UPDATE: ❌ Ошибка получения шаблона: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Ошибка получения содержимого шаблона: {str(e)}'
            })
        
        # Находим предстоящие интервью
        from apps.google_oauth.models import Invite
        from django.utils import timezone
        
        # Отладочная информация
        all_invites = Invite.objects.filter(vacancy_id=str(vacancy.external_id))
        print(f"DEBUG: Всего инвайтов для вакансии {vacancy.id} (external_id={vacancy.external_id}): {all_invites.count()}")
        
        for invite in all_invites:
            print(f"DEBUG: Инвайт {invite.id}: дата={invite.interview_datetime}, статус={invite.status}, google_drive_file_id={invite.google_drive_file_id}")
        
        # Дополнительная отладочная информация
        current_time = timezone.now()
        print(f"DEBUG: Текущее время: {current_time}")
        print(f"DEBUG: Тип vacancy.id: {type(vacancy.id)}, значение: {vacancy.id}")
        print(f"DEBUG: vacancy_id для фильтра: {str(vacancy.id)}")
        
        # Проверяем инвайты с разными фильтрами
        future_invites = Invite.objects.filter(
            vacancy_id=str(vacancy.external_id),
            interview_datetime__gte=current_time
        )
        print(f"DEBUG: Инвайтов в будущем: {future_invites.count()}")
        
        active_invites = Invite.objects.filter(
            vacancy_id=str(vacancy.external_id),
            status__in=['pending', 'sent']
        )
        print(f"DEBUG: Активных инвайтов: {active_invites.count()}")
        
        # Проверяем все возможные форматы vacancy_id
        print(f"DEBUG: Проверяем разные форматы vacancy_id...")
        invites_int = Invite.objects.filter(vacancy_id=int(vacancy.external_id))
        print(f"DEBUG: Инвайтов с vacancy_id={int(vacancy.external_id)} (int): {invites_int.count()}")
        
        invites_str = Invite.objects.filter(vacancy_id=str(vacancy.external_id))
        print(f"DEBUG: Инвайтов с vacancy_id='{str(vacancy.external_id)}' (str): {invites_str.count()}")
        
        # Проверяем все уникальные vacancy_id в базе
        all_vacancy_ids = Invite.objects.values_list('vacancy_id', flat=True).distinct()
        print(f"DEBUG: Все vacancy_id в базе: {list(all_vacancy_ids)}")
        
        # Проверяем external_id вакансии
        print(f"DEBUG: external_id вакансии: {vacancy.external_id}")
        
        # Проверяем инвайты по external_id
        invites_by_external_id = Invite.objects.filter(vacancy_id=str(vacancy.external_id))
        print(f"DEBUG: Инвайтов с vacancy_id='{vacancy.external_id}' (external_id): {invites_by_external_id.count()}")
        
        # Проверяем инвайты без фильтра по вакансии
        all_invites_no_filter = Invite.objects.all()
        print(f"DEBUG: Всего инвайтов в системе: {all_invites_no_filter.count()}")
        
        for invite in all_invites_no_filter[:10]:  # Показываем первые 10
            print(f"DEBUG: Инвайт {invite.id}: vacancy_id='{invite.vacancy_id}', дата={invite.interview_datetime}, статус={invite.status}")
        
        # Исправляем фильтр: используем external_id вместо внутреннего ID
        # Сначала пробуем по internal ID, потом по external_id
        upcoming_interviews = Invite.objects.filter(
            vacancy_id=str(vacancy.external_id),  # Используем external_id
            interview_datetime__gte=timezone.now(),
            status__in=['pending', 'sent']  # Только активные инвайты
        )
        
        print(f"DEBUG: Предстоящих интервью найдено по external_id: {upcoming_interviews.count()}")
        
        # Если не найдено по external_id, пробуем по internal ID
        if upcoming_interviews.count() == 0:
            upcoming_interviews = Invite.objects.filter(
                vacancy_id=str(vacancy.id),  # Пробуем internal ID
                interview_datetime__gte=timezone.now(),
                status__in=['pending', 'sent']
            )
            print(f"DEBUG: Предстоящих интервью найдено по internal ID: {upcoming_interviews.count()}")
        
        print(f"DEBUG: Предстоящих интервью найдено: {upcoming_interviews.count()}")
        
        if not upcoming_interviews:
            # Сохраняем историю операции даже если нет интервью
            try:
                from .models import ScorecardUpdateHistory
                
                ScorecardUpdateHistory.objects.create(
                    vacancy=vacancy,
                    user=request.user,
                    action_type='bulk_update',
                    updated_count=0,
                    total_found=0,
                    date_range_from=timezone.now().date(),
                    date_range_to=timezone.now().date(),
                    errors=[],
                    updated_interviews=[]
                )
                print(f"DEBUG UPDATE: ✅ История операции сохранена (нет интервью)")
            except Exception as e:
                print(f"DEBUG UPDATE: ❌ Ошибка сохранения истории (нет интервью): {str(e)}")
                # Не прерываем выполнение из-за ошибки сохранения истории
            
            return JsonResponse({
                'success': True,
                'message': 'Нет предстоящих интервью для пересоздания скоркардов',
                'updated_count': 0,
                'total_found': 0,
                'errors_count': 0,
                'errors': [],
                'updated_interviews': []
            })
        
        # Обновляем каждый скоркард
        updated_count = 0
        errors = []
        updated_interviews = []
        
        for invite in upcoming_interviews:
            try:
                print(f"DEBUG RECREATE: Обрабатываем инвайт {invite.id} для {invite.candidate_name}")
                
                # Шаг 1: Удаляем старый скоркард (если есть)
                if invite.google_drive_file_id:
                    print(f"DEBUG RECREATE: Удаляем старый скоркард {invite.google_drive_file_id}")
                    try:
                        drive_service.delete_file(invite.google_drive_file_id)
                        print(f"DEBUG RECREATE: ✅ Старый скоркард удален")
                    except Exception as e:
                        print(f"DEBUG RECREATE: ⚠️ Не удалось удалить старый скоркард: {str(e)}")
                        # Продолжаем работу, возможно файл уже не существует
                
                # Шаг 2: Создаем новую структуру Google Drive (ТОЛЬКО ФАЙЛЫ!)
                print(f"DEBUG RECREATE: Создаем новую структуру Google Drive для {invite.candidate_name}")
                try:
                    # Получаем информацию о вакансии (используем уже полученную вакансию)
                    scorecard_title = vacancy.scorecard_title
                    scorecard_template_url = vacancy.scorecard_link
                    
                    # Создаем структуру папок напрямую через Google Drive API
                    from apps.google_oauth.services import GoogleDriveService
                    drive_service = GoogleDriveService(oauth_service)
                    
                    # Генерируем путь папки
                    folder_path, filename_base = invite._generate_fallback_path_structure()
                    folder_id = drive_service.create_folder_structure(folder_path)
                    
                    if not folder_id:
                        error_msg = f"Не удалось создать папку для {invite.candidate_name}"
                        print(f"DEBUG RECREATE: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    # Извлекаем ID шаблона и копируем файл
                    template_file_id = invite._extract_file_id_from_url(scorecard_template_url)
                    if not template_file_id:
                        error_msg = f"Не удалось извлечь ID шаблона для {invite.candidate_name}"
                        print(f"DEBUG RECREATE: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    new_file_name = f"{filename_base} {scorecard_title}"
                    new_file_id = drive_service.copy_file(template_file_id, new_file_name, folder_id)
                    
                    if not new_file_id:
                        error_msg = f"Не удалось скопировать файл для {invite.candidate_name}"
                        print(f"DEBUG RECREATE: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    new_file_url = f"https://docs.google.com/spreadsheets/d/{new_file_id}/edit"
                    
                    print(f"DEBUG RECREATE: ✅ Структура Google Drive создана")
                    print(f"DEBUG RECREATE: Новый файл ID: {new_file_id}")
                except Exception as e:
                    error_msg = f"Ошибка создания структуры Google Drive для {invite.candidate_name}: {str(e)}"
                    print(f"DEBUG RECREATE: {error_msg}")
                    errors.append(error_msg)
                    continue
                
                # Шаг 3: Обрабатываем новый скоркард (только Google таблицу)
                print(f"DEBUG RECREATE: Обрабатываем новый скоркард для {invite.candidate_name}")
                try:
                    # Обрабатываем новый файл напрямую через Google Sheets API
                    from apps.google_oauth.services import GoogleSheetsService
                    sheets_service = GoogleSheetsService(oauth_service)
                    
                    # Получаем список всех листов в таблице
                    sheets = sheets_service.get_sheets(new_file_id)
                    if not sheets:
                        error_msg = f"Не удалось получить список листов для {invite.candidate_name}"
                        print(f"DEBUG RECREATE: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    # Определяем листы для сохранения
                    sheets_to_keep = ['all', 'score']
                    if invite.candidate_grade:
                        sheets_to_keep.append(invite.candidate_grade)
                    
                    # Удаляем лишние листы
                    for sheet in sheets:
                        sheet_title = sheet.get('properties', {}).get('title', sheet.get('title', 'Unknown'))
                        sheet_id = sheet.get('properties', {}).get('sheetId', sheet.get('sheetId'))
                        
                        if sheet_title not in sheets_to_keep:
                            try:
                                sheets_service.delete_sheet(new_file_id, sheet_id)
                                print(f"DEBUG RECREATE: Удален лист: {sheet_title}")
                            except Exception as e:
                                print(f"DEBUG RECREATE: Не удалось удалить лист {sheet_title}: {str(e)}")
                    
                    print(f"DEBUG RECREATE: ✅ Скоркард обработан")
                except Exception as e:
                    error_msg = f"Ошибка обработки скоркарда для {invite.candidate_name}: {str(e)}"
                    print(f"DEBUG RECREATE: {error_msg}")
                    errors.append(error_msg)
                    continue
                
                # Шаг 4: Сохраняем только новые ссылки на файлы в инвайте
                try:
                    # Обновляем только поля, связанные с Google Drive
                    invite.google_drive_folder_id = folder_id
                    invite.google_drive_file_id = new_file_id
                    invite.google_drive_file_url = new_file_url
                    invite.save()
                    print(f"DEBUG RECREATE: ✅ Инвайт сохранен с новыми ссылками")
                except Exception as e:
                    error_msg = f"Ошибка сохранения инвайта для {invite.candidate_name}: {str(e)}"
                    print(f"DEBUG RECREATE: {error_msg}")
                    errors.append(error_msg)
                    continue
                
                # Шаг 5: Обновляем ссылку в Huntflow
                print(f"DEBUG RECREATE: Обновляем ссылку в Huntflow для {invite.candidate_name}")
                try:
                    invite._update_huntflow_scorecard_field()
                    print(f"DEBUG RECREATE: ✅ Ссылка в Huntflow обновлена")
                except Exception as e:
                    print(f"DEBUG RECREATE: ⚠️ Не удалось обновить ссылку в Huntflow: {str(e)}")
                    # Это не критическая ошибка, продолжаем
                
                # Успешно пересоздан
                updated_count += 1
                updated_interviews.append({
                    'candidate_name': invite.candidate_name,
                    'interview_date': invite.interview_datetime.strftime('%Y-%m-%d %H:%M'),
                    'scorecard_url': invite.google_drive_file_url or 'Не указан'
                })
                print(f"DEBUG RECREATE: ✅ Успешно пересоздан скоркард для {invite.candidate_name}")
                    
            except Exception as e:
                error_msg = f"Общая ошибка для {invite.candidate_name}: {str(e)}"
                print(f"DEBUG RECREATE: {error_msg}")
                errors.append(error_msg)
        
        # Формируем результат
        result = {
            'success': True,
            'updated_count': updated_count,
            'total_found': len(upcoming_interviews),
            'errors_count': len(errors),
            'date_range': {
                'from': min(inv.interview_datetime for inv in upcoming_interviews).strftime('%Y-%m-%d'),
                'to': max(inv.interview_datetime for inv in upcoming_interviews).strftime('%Y-%m-%d')
            },
            'errors': errors,
            'updated_interviews': updated_interviews
        }
        
        print(f"DEBUG UPDATE: Итоговый результат: обновлено {updated_count} из {len(upcoming_interviews)}, ошибок: {len(errors)}")
        print(f"DEBUG UPDATE: Список ошибок: {errors}")
        print(f"DEBUG UPDATE: Обновленные интервью: {[inv['candidate_name'] for inv in updated_interviews]}")
        
        # Сохраняем историю операции
        try:
            from .models import ScorecardUpdateHistory
            
            ScorecardUpdateHistory.objects.create(
                vacancy=vacancy,
                user=request.user,
                action_type='bulk_update',
                updated_count=updated_count,
                total_found=len(upcoming_interviews),
                date_range_from=min(inv.interview_datetime.date() for inv in upcoming_interviews),
                date_range_to=max(inv.interview_datetime.date() for inv in upcoming_interviews),
                errors=errors,
                updated_interviews=updated_interviews
            )
            print(f"DEBUG UPDATE: ✅ История операции сохранена")
        except Exception as e:
            print(f"DEBUG UPDATE: ❌ Ошибка сохранения истории: {str(e)}")
            # Не прерываем выполнение из-за ошибки сохранения истории
        
        if updated_count > 0:
            result['message'] = f"Успешно пересоздано {updated_count} из {len(upcoming_interviews)} скоркардов"
        else:
            result['message'] = "Не удалось пересоздать ни одного скоркарда"
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при обновлении скоркардов: {str(e)}'
        })


@login_required
@require_POST
def get_upcoming_interviews(request, pk):
    """Получение информации о предстоящих интервью для вакансии"""
    from apps.google_oauth.models import Invite
    from django.utils import timezone
    
    try:
        # Получаем вакансию
        vacancy = get_object_or_404(Vacancy, pk=pk)
        
        # Проверяем права доступа (основной или один из дополнительных рекрутеров)
        if not (request.user == vacancy.recruiter or vacancy.additional_recruiters.filter(pk=request.user.pk).exists() or request.user.is_superuser):
            return JsonResponse({
                'success': False,
                'message': 'Недостаточно прав для просмотра предстоящих интервью'
            })
        
        # Отладочная информация
        print(f"DEBUG GET_UPCOMING: Вакансия {vacancy.id}, external_id: {vacancy.external_id}")
        
        # Находим предстоящие интервью
        upcoming_interviews = Invite.objects.filter(
            vacancy_id=str(vacancy.external_id),
            interview_datetime__gte=timezone.now(),
            status__in=['pending', 'sent']
        ).order_by('interview_datetime')
        
        print(f"DEBUG GET_UPCOMING: Найдено по external_id: {upcoming_interviews.count()}")
        
        # Если не найдено по external_id, пробуем по internal ID
        if upcoming_interviews.count() == 0:
            upcoming_interviews = Invite.objects.filter(
                vacancy_id=str(vacancy.id),
                interview_datetime__gte=timezone.now(),
                status__in=['pending', 'sent']
            ).order_by('interview_datetime')
            print(f"DEBUG GET_UPCOMING: Найдено по internal ID: {upcoming_interviews.count()}")
        
        print(f"DEBUG GET_UPCOMING: Итого найдено: {upcoming_interviews.count()}")
        
        # Формируем данные для ответа
        interviews_data = []
        for invite in upcoming_interviews:
            interviews_data.append({
                'id': invite.id,
                'candidate_name': invite.candidate_name or 'Не указано',
                'interview_datetime': invite.interview_datetime.strftime('%Y-%m-%d %H:%M'),
                'interview_datetime_formatted': invite.get_formatted_interview_datetime(),
                'status': invite.get_status_display(),
                'has_scorecard': bool(invite.google_drive_file_id),
                'scorecard_url': invite.google_drive_file_url or None,
                'candidate_url': invite.candidate_url
            })
        
        return JsonResponse({
            'success': True,
            'vacancy_name': vacancy.name,
            'total_count': len(interviews_data),
            'interviews': interviews_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при получении предстоящих интервью: {str(e)}'
        })
