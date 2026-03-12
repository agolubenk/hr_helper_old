"""Views для интеграции HeadHunter.ru: OAuth, дашборд, конфигурации, логи."""
import json
import re
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q

from .models import HHruOAuthConfig, HHruOAuthAccount, HHruApiLog, HHruVacancyLink, HHruResumeHuntflowCheck
from .forms import HHruOAuthConfigForm
from .hh_oauth import (
    build_authorize_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_me,
    get_employer_active_vacancies,
    get_employer_archived_vacancies,
    get_negotiations_meta,
    get_negotiations_collection,
    change_negotiation_action,
    fetch_all_negotiations_for_vacancy,
)
from . import cache_utils


def _get_default_config():
    return HHruOAuthConfig.objects.filter(is_active=True).order_by('-is_default', '-created_at').first()


def _get_user_account(user):
    return HHruOAuthAccount.objects.filter(user=user).order_by('-created_at').first()


@login_required
def root_view(request):
    """Корень /hh_app/: если в GET есть code или error — OAuth callback, иначе редирект на дашборд."""
    if request.GET.get('code'):
        return oauth_callback(request)
    if request.GET.get('error'):
        return oauth_callback(request)
    return redirect('hhru:dashboard')


@login_required
def dashboard(request):
    """Главная страница интеграции HH.ru."""
    account = _get_user_account(request.user)
    config = _get_default_config()
    has_config = config is not None

    connection_status = None
    connection_message = None
    stats = {'total_logs': 0, 'successful_requests': 0, 'failed_requests': 0}
    recent_logs = []

    if account:
        logs = HHruApiLog.objects.filter(account=account).order_by('-created_at')
        stats['total_logs'] = logs.count()
        stats['successful_requests'] = logs.filter(status_code__gte=200, status_code__lt=300).count()
        stats['failed_requests'] = logs.filter(Q(status_code__gte=400) | Q(log_type=HHruApiLog.LogType.ERROR)).count()
        recent_logs = logs[:20]

        if account.is_token_valid:
            connection_status = 'success'
        else:
            connection_status = 'warning'
            connection_message = 'Токен истёк. Обновите токен.'

    return render(request, 'hhru/dashboard.html', {
        'account': account,
        'has_config': has_config,
        'connection_status': connection_status,
        'connection_message': connection_message,
        'stats': stats,
        'recent_logs': recent_logs,
    })


@login_required
def oauth_authorize(request):
    """Редирект на HH.ru для авторизации."""
    config = _get_default_config()
    if not config:
        from django.contrib import messages
        messages.warning(request, 'Сначала создайте конфигурацию OAuth.')
        return redirect('hhru:configuration_create')

    redirect_uri = request.build_absolute_uri(reverse('hhru:oauth_callback'))
    state = secrets.token_urlsafe(32)
    request.session['hhru_oauth_state'] = state
    request.session['hhru_oauth_redirect_uri'] = redirect_uri
    url = build_authorize_url(config.client_id, redirect_uri, state=state)
    return redirect(url)


@login_required
def oauth_callback(request):
    """Обработка редиректа от HH.ru: обмен code на токены, сохранение аккаунта."""
    error = request.GET.get('error')
    if error:
        from django.contrib import messages
        messages.error(request, f'Ошибка авторизации HH.ru: {error}')
        return redirect('hhru:dashboard')

    code = request.GET.get('code')
    if not code:
        return redirect('hhru:dashboard')

    config = _get_default_config()
    if not config:
        from django.contrib import messages
        messages.error(request, 'Конфигурация OAuth не найдена.')
        return redirect('hhru:dashboard')

    redirect_uri = request.session.get('hhru_oauth_redirect_uri') or request.build_absolute_uri(reverse('hhru:oauth_callback'))
    try:
        data = exchange_code_for_tokens(
            config.client_id,
            config.client_secret,
            redirect_uri,
            code,
        )
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'Ошибка обмена кода на токен: {e}')
        return redirect('hhru:dashboard')

    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    expires_in = data.get('expires_in', 3600)
    if not access_token:
        from django.contrib import messages
        messages.error(request, 'Не получен access_token.')
        return redirect('hhru:dashboard')

    expires_at = timezone.now() + timezone.timedelta(seconds=expires_in) if expires_in else None

    try:
        me = get_me(access_token)
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'Ошибка получения профиля: {e}')
        return redirect('hhru:dashboard')

    hh_user_id = str(me.get('id', ''))
    first_name = me.get('first_name', '')
    last_name = me.get('last_name', '')
    middle_name = me.get('middle_name') or ''
    email = me.get('email', '')
    is_employer = me.get('is_employer', False)
    is_admin = me.get('is_admin', False)
    employer_id = ''
    employer_obj = me.get('employer') or {}
    if isinstance(employer_obj, dict) and employer_obj.get('id'):
        employer_id = str(employer_obj['id'])
    if not employer_id:
        employer_relations = me.get('employer_relations') or []
        if employer_relations and isinstance(employer_relations, list) and len(employer_relations) > 0:
            first_emp = employer_relations[0]
            if isinstance(first_emp, dict) and first_emp.get('id'):
                employer_id = str(first_emp['id'])
            elif hasattr(first_emp, 'get') and first_emp.get('id'):
                employer_id = str(first_emp['id'])

    account, _ = HHruOAuthAccount.objects.update_or_create(
        user=request.user,
        hh_user_id=hh_user_id,
        defaults={
            'config': config,
            'access_token': access_token,
            'refresh_token': refresh_token or '',
            'token_expires_at': expires_at,
            'first_name': first_name,
            'last_name': last_name,
            'middle_name': middle_name,
            'email': email,
            'is_employer': is_employer,
            'is_admin': is_admin,
            'employer_id': employer_id,
        },
    )
    if refresh_token and not account.refresh_token:
        account.refresh_token = refresh_token
        account.save(update_fields=['refresh_token'])
    if employer_id and not account.employer_id:
        account.employer_id = employer_id
        account.save(update_fields=['employer_id'])

    from django.contrib import messages
    messages.success(request, 'Аккаунт HeadHunter.ru успешно подключён.')
    return redirect('hhru:dashboard')


# ——— Конфигурации ———
@login_required
def configurations_list(request):
    configs = HHruOAuthConfig.objects.all()
    return render(request, 'hhru/configurations_list.html', {'configurations': configs})


@login_required
def configuration_create(request):
    if request.method == 'POST':
        form = HHruOAuthConfigForm(request.POST)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, 'Конфигурация создана.')
            return redirect('hhru:configurations_list')
    else:
        from django.conf import settings as django_settings
        redirect_uri = request.build_absolute_uri(reverse('hhru:oauth_callback'))
        initial = {'redirect_uri': redirect_uri}
        if getattr(django_settings, 'HH_RU_CLIENT_ID', None):
            initial['client_id'] = django_settings.HH_RU_CLIENT_ID
        if getattr(django_settings, 'HH_RU_CLIENT_SECRET', None):
            initial['client_secret'] = django_settings.HH_RU_CLIENT_SECRET
        if getattr(django_settings, 'HH_RU_REDIRECT_URI', None):
            initial['redirect_uri'] = django_settings.HH_RU_REDIRECT_URI
        if initial.get('client_id'):
            initial.setdefault('name', 'HR_Helper')
        form = HHruOAuthConfigForm(initial=initial)
    return render(request, 'hhru/configuration_form.html', {
        'form': form,
        'title': 'Создать конфигурацию OAuth',
        'submit_text': 'Создать',
    })


@login_required
def configuration_edit(request, pk):
    config = get_object_or_404(HHruOAuthConfig, pk=pk)
    if request.method == 'POST':
        form = HHruOAuthConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, 'Конфигурация обновлена.')
            return redirect('hhru:configurations_list')
    else:
        form = HHruOAuthConfigForm(instance=config)
    return render(request, 'hhru/configuration_form.html', {
        'form': form,
        'title': 'Редактировать конфигурацию',
        'submit_text': 'Сохранить',
    })


@login_required
@require_POST
@csrf_protect
def configuration_delete(request, pk):
    config = get_object_or_404(HHruOAuthConfig, pk=pk)
    config.delete()
    from django.contrib import messages
    messages.success(request, 'Конфигурация удалена.')
    return redirect('hhru:configurations_list')


# ——— Аккаунты ———
@login_required
def accounts_list(request):
    accounts = HHruOAuthAccount.objects.filter(user=request.user)
    items = [
        {
            'account': acc,
            'token_valid': acc.is_token_valid,
            'needs_refresh': acc.needs_refresh,
        }
        for acc in accounts
    ]
    return render(request, 'hhru/accounts_list.html', {'accounts': items})


@login_required
def account_detail(request, pk):
    account = get_object_or_404(HHruOAuthAccount, pk=pk, user=request.user)
    token_valid = account.is_token_valid
    profile_data = None
    if token_valid:
        try:
            me = get_me(account.access_token)
            profile_data = json.dumps(me, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return render(request, 'hhru/account_detail.html', {
        'account': account,
        'token_valid': token_valid,
        'profile_data': profile_data,
    })


# ——— ID работодателя (ручная настройка, если не определился из /me) ———
@login_required
def employer_id_set(request):
    """Страница ввода/изменения ID работодателя HH.ru (если не подтянулся из API)."""
    account = _get_user_account(request.user)
    if not account:
        return redirect('hhru:dashboard')
    if request.method == 'POST':
        from django.contrib import messages
        eid = (request.POST.get('employer_id') or '').strip()
        if eid:
            account.employer_id = eid
            account.save(update_fields=['employer_id'])
            messages.success(request, 'ID работодателя сохранён.')
            return redirect('hhru:vacancies_active')
        messages.warning(request, 'Введите ID работодателя.')
    return render(request, 'hhru/employer_id_set.html', {
        'account': account,
        'employer_id': account.employer_id or '',
    })


# ——— Вакансии HH.ru (активные и архивные) + связь с локальными по huntflow_id ———
def _ensure_employer_id(account):
    """Если employer_id пустой, пробуем взять из /me: employer.id (профиль работодателя) или employer_relations[0].id."""
    if account.employer_id:
        return account.employer_id
    try:
        me = get_me(account.access_token)
        employer_obj = me.get('employer') or {}
        if isinstance(employer_obj, dict) and employer_obj.get('id'):
            account.employer_id = str(employer_obj['id'])
            account.save(update_fields=['employer_id'])
            return account.employer_id
        employer_relations = me.get('employer_relations') or []
        if employer_relations and isinstance(employer_relations, list) and len(employer_relations) > 0:
            first_emp = employer_relations[0]
            if isinstance(first_emp, dict) and first_emp.get('id'):
                account.employer_id = str(first_emp['id'])
                account.save(update_fields=['employer_id'])
                return account.employer_id
    except Exception:
        pass
    return None


# Папки откликов на странице вакансии: маппинг employer_state/collection id -> ключ папки
FOLDER_UNSEEN = 'unseen'           # не разобранные
FOLDER_CONSIDER = 'consider'       # подумать
FOLDER_PRIMARY = 'primary'        # первичный контакт
FOLDER_REJECTIONS = 'rejections'  # отказы

COLLECTION_TO_FOLDER = {
    'response': FOLDER_UNSEEN,
    'consider': FOLDER_CONSIDER,
    'invitation': FOLDER_PRIMARY,
    'phone_interview': FOLDER_PRIMARY,
    'interview': FOLDER_PRIMARY,
    'assessment': FOLDER_PRIMARY,
    'offer': FOLDER_PRIMARY,
    'hired': FOLDER_PRIMARY,
    'discard': FOLDER_REJECTIONS,
    'discard_after_interview': FOLDER_REJECTIONS,
    'discard_by_employer': FOLDER_REJECTIONS,
}


def _resume_id_from_negotiation_item(item):
    """Извлекает resume_id из элемента отклика (resume.id или из alternate_url)."""
    resume = (item or {}).get('resume') or {}
    rid = resume.get('id')
    if rid:
        return str(rid)
    url = resume.get('alternate_url') or ''
    m = re.search(r'/resume/([^/?#]+)', url, re.IGNORECASE)
    return m.group(1) if m else None


def _resolve_huntflow_url_to_account_applicant(user, huntflow_url):
    """
    Извлекает (account_id, applicant_id) из ссылки Huntflow.
    Поддерживает: .../accounts/123/applicants/456/ и huntflow.ru/my/account#/applicants/.../id/456
    Возвращает (account_id, applicant_id) или (None, None).
    """
    if not huntflow_url or not str(huntflow_url).strip():
        return (None, None)
    from urllib.parse import unquote
    url = unquote(str(huntflow_url).strip())
    m = re.search(r'/accounts/(\d+)/applicants/(\d+)', url)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r'/my/([^/#]+)#/applicants/filter/[^/]+/id/(\d+)', url)
    if m:
        account_name, applicant_id = m.group(1), int(m.group(2))
    else:
        m = re.search(r'/my/([^/#]+)#/applicants/filter/[^/]+/(\d+)', url)
        if m:
            account_name, applicant_id = m.group(1), int(m.group(2))
        else:
            m = re.search(r'/my/([^/#]+)#/applicants/id/(\d+)', url)
            if m:
                account_name, applicant_id = m.group(1), int(m.group(2))
            else:
                m = re.search(r'/my/([^/#]+)#/vacancy/(\d+)/filter/[^/]+/id/(\d+)', url)
                if m:
                    account_name, applicant_id = m.group(1), int(m.group(3))
                else:
                    return (None, None)
    try:
        from apps.huntflow.services import HuntflowService
        api = HuntflowService(user=user)
        accounts = api.get_accounts()
        if not accounts or 'items' not in accounts:
            return (None, None)
        aname = (account_name or '').lower()
        for acc in accounts.get('items', []):
            if ((acc.get('name') or '').lower() == aname or
                    (acc.get('nick') or '').lower() == aname):
                return (acc.get('id'), applicant_id)
    except Exception:
        pass
    return (None, None)


def _get_applicant_status_info(user, huntflow_url):
    """
    Загружает из Huntflow актуальный статус кандидата и причину отказа (если отказ).
    Возвращает dict: status_name, rejection_reason_name (или пустые строки).
    """
    account_id, applicant_id = _resolve_huntflow_url_to_account_applicant(user, huntflow_url)
    if not account_id or not applicant_id:
        return {'status_name': '', 'rejection_reason_name': ''}
    try:
        from apps.huntflow.services import HuntflowService
        api = HuntflowService(user=user)
        applicant_data = api.get_applicant(account_id, applicant_id)
        if not applicant_data:
            return {'status_name': '', 'rejection_reason_name': ''}
        links = applicant_data.get('links') or []
        vacancy_statuses = applicant_data.get('vacancy_statuses') or []
        status_id = None
        rejection_reason = None
        if vacancy_statuses:
            sorted_v = sorted(vacancy_statuses, key=lambda x: x.get('changed', ''), reverse=True)
            latest = sorted_v[0]
            st = latest.get('status')
            status_id = st.get('id') if isinstance(st, dict) else st
            rejection_reason = latest.get('rejection_reason')
        if status_id is None and links:
            link = links[0]
            st = link.get('status')
            status_id = st.get('id') if isinstance(st, dict) else st
            rejection_reason = link.get('rejection_reason')
        status_name = ''
        if status_id and account_id:
            statuses_data = api.get_vacancy_statuses(account_id)
            if statuses_data and statuses_data.get('items'):
                for s in statuses_data['items']:
                    if s.get('id') == status_id:
                        status_name = s.get('name') or ''
                        break
        rejection_reason_name = ''
        if rejection_reason:
            rejection_reason_name = rejection_reason.get('name', '') if isinstance(rejection_reason, dict) else str(rejection_reason or '')
        return {'status_name': status_name, 'rejection_reason_name': rejection_reason_name}
    except Exception:
        return {'status_name': '', 'rejection_reason_name': ''}


def _build_candidate_card(neg_item, vacancy_title, huntflow_link=None, huntflow_status_info=None):
    """Собирает данные карточки кандидата из элемента отклика HH и опциональной связи Huntflow."""
    resume = (neg_item or {}).get('resume') or {}
    employer_state = (neg_item or {}).get('employer_state') or {}
    state_name = employer_state.get('name') or ''
    state_id = employer_state.get('id') or ''

    first = (resume.get('first_name') or '').strip()
    last = (resume.get('last_name') or '').strip()
    middle = (resume.get('middle_name') or '').strip()
    fio = ' '.join(x for x in (last, first, middle) if x).strip() or '—'

    area = resume.get('area') or {}
    location = area.get('name') if isinstance(area, dict) else '—'

    total_exp = resume.get('total_experience') or {}
    if isinstance(total_exp, dict) and 'months' in total_exp:
        months = total_exp.get('months') or 0
        years = months // 12
        exp_str = f'{years} г.' if years else f'{months} мес.'
    else:
        exp_str = '—'

    gender_obj = resume.get('gender') or {}
    gender = gender_obj.get('name') if isinstance(gender_obj, dict) else (gender_obj if isinstance(gender_obj, str) else '—')

    age_val = resume.get('age')
    age_str = str(age_val) if age_val is not None and age_val != '' else '—'

    contacts = []
    if resume.get('email'):
        contacts.append(resume.get('email'))
    phone = (resume.get('phone') or {}).get('number') if isinstance(resume.get('phone'), dict) else resume.get('phone')
    if phone:
        contacts.append(phone)
    contacts_str = ', '.join(contacts) if contacts else '—'

    resume_id = _resume_id_from_negotiation_item(neg_item)
    in_huntflow = huntflow_link is not None
    huntflow_url = huntflow_link.huntflow_url if huntflow_link else ''
    huntflow_link_id = huntflow_link.id if huntflow_link else None
    huntflow_status = '—'
    huntflow_last_contact = '—'
    huntflow_rejection_reason = ''
    if huntflow_link:
        if huntflow_status_info:
            huntflow_status = (huntflow_status_info.get('status_name') or '').strip() or 'В Huntflow'
            huntflow_rejection_reason = (huntflow_status_info.get('rejection_reason_name') or '').strip()
        else:
            huntflow_status = 'В Huntflow'
        if getattr(huntflow_link, 'updated_at', None):
            huntflow_last_contact = huntflow_link.updated_at.strftime('%d.%m.%Y') if hasattr(huntflow_link.updated_at, 'strftime') else str(huntflow_link.updated_at)

    is_rejection = state_id in ('discard', 'discard_after_interview', 'discard_by_employer')
    reject_reason = state_name if is_rejection else ''
    blacklist = False
    relations = resume.get('relations') or []
    if isinstance(relations, list) and 'blacklisted' in relations:
        blacklist = True

    actions = []
    for a in (neg_item.get('actions') or []):
        if a.get('method') == 'PUT' and a.get('url') and not a.get('hidden'):
            actions.append({
                'id': a.get('id'),
                'name': a.get('name') or a.get('id'),
                'url': a.get('url'),
            })

    return {
        'negotiation_id': neg_item.get('id'),
        'fio': fio,
        'vacancy_title': vacancy_title,
        'experience': exp_str,
        'location': location,
        'gender': gender,
        'age': age_str,
        'contacts': contacts_str,
        'in_huntflow': in_huntflow,
        'huntflow_url': huntflow_url,
        'huntflow_link_id': huntflow_link_id,
        'huntflow_status': huntflow_status,
        'huntflow_last_contact': huntflow_last_contact,
        'huntflow_rejection_reason': huntflow_rejection_reason,
        'reject_reason': reject_reason,
        'blacklist': blacklist,
        'resume_id': resume_id,
        'resume_alternate_url': resume.get('alternate_url') or '',
        'actions': actions,
    }


def _vacancy_title_from_active_archived(account, employer_id, hh_vacancy_id):
    """Получает название вакансии из кэша активных или из API (активные + архивные)."""
    cached = cache_utils.get_cached_active_vacancies(account.pk)
    if cached:
        for v in (cached.get('items') or []):
            if str(v.get('id')) == hh_vacancy_id:
                return v.get('name') or v.get('title') or ''
    try:
        active_data = get_employer_active_vacancies(account.access_token, employer_id, page=0, per_page=100)
        for v in (active_data.get('items') or []):
            if str(v.get('id')) == hh_vacancy_id:
                return v.get('name') or v.get('title') or ''
        archived_data = get_employer_archived_vacancies(account.access_token, employer_id, page=0, per_page=100)
        for v in (archived_data.get('items') or []):
            if str(v.get('id')) == hh_vacancy_id:
                return v.get('name') or v.get('title') or ''
    except Exception:
        pass
    return ''


@login_required
def vacancy_responses(request, hh_vacancy_id):
    """Страница вакансии на нашем сайте: отклики по папкам. Данные берутся из кэша при наличии."""
    account = _get_user_account(request.user)
    if not account:
        return redirect('hhru:dashboard')
    if not account.is_token_valid:
        from django.contrib import messages
        messages.warning(request, 'Токен HH.ru истёк. Обновите токен.')
        return redirect('hhru:dashboard')
    employer_id = _ensure_employer_id(account)
    if not employer_id:
        from django.contrib import messages
        messages.warning(request, 'Не удалось определить ID работодателя. Укажите его вручную.')
        return redirect('hhru:employer_id_set')

    hh_vacancy_id = (hh_vacancy_id or '').strip()
    if not hh_vacancy_id:
        from django.contrib import messages
        messages.error(request, 'Не указана вакансия.')
        return redirect('hhru:vacancies_active')

    cached_responses = cache_utils.get_cached_negotiations(account.pk, hh_vacancy_id)
    if cached_responses is not None:
        all_items = cached_responses.get('all_items') or []
        vacancy_title = (cached_responses.get('vacancy_title') or '').strip() or f'Вакансия {hh_vacancy_id}'
    else:
        vacancy_title = _vacancy_title_from_active_archived(account, employer_id, hh_vacancy_id) or f'Вакансия {hh_vacancy_id}'
        try:
            all_items = fetch_all_negotiations_for_vacancy(account.access_token, hh_vacancy_id)
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Не удалось загрузить отклики: {e}')
            return redirect('hhru:vacancies_active')
        cache_utils.set_cached_negotiations(account.pk, hh_vacancy_id, all_items, vacancy_title=vacancy_title)
        try:
            from .tasks import refresh_hhru_vacancies_and_responses_cache
            refresh_hhru_vacancies_and_responses_cache.delay(account.pk)
        except Exception:
            pass

    # Синхронизация откликов в HHResponse (база HH/rabota.by общая) — чтобы расширение находило запись по resume_url
    try:
        from .sync_responses import sync_negotiations_to_hh_response
        sync_negotiations_to_hh_response(account.pk, hh_vacancy_id, all_items, vacancy_title=vacancy_title)
    except Exception:
        pass

    folders = {
        FOLDER_UNSEEN: [],
        FOLDER_CONSIDER: [],
        FOLDER_PRIMARY: [],
        FOLDER_REJECTIONS: [],
    }

    try:
        from apps.huntflow.models import ResumeHuntflowLink
        huntflow_by_resume = {link.resume_id: link for link in ResumeHuntflowLink.objects.all() if link.resume_id}
    except Exception:
        huntflow_by_resume = {}

    check_by_resume = {
        c.resume_id: 'not_found'
        for c in HHruResumeHuntflowCheck.objects.filter(status=HHruResumeHuntflowCheck.Status.NOT_FOUND)
    }

    # Статус из Huntflow не подгружаем массово при открытии страницы (слишком много API-вызовов).
    # Он подтягивается при нажатии «Проверить в Huntflow» и возвращается в AJAX.
    status_by_resume_id = {}

    resume_ids_without_link = list(
        dict.fromkeys(
            _resume_id_from_negotiation_item(it)
            for it in all_items
            if _resume_id_from_negotiation_item(it) and _resume_id_from_negotiation_item(it) not in huntflow_by_resume
        )
    )[:2]
    for rid in resume_ids_without_link:
        alt_url = next(
            (it.get('resume', {}).get('alternate_url') or '' for it in all_items if _resume_id_from_negotiation_item(it) == rid),
            f'https://hh.ru/resume/{rid}',
        )
        _run_huntflow_check_for_resume(request, rid, alt_url)
    try:
        from apps.huntflow.models import ResumeHuntflowLink
        huntflow_by_resume = {link.resume_id: link for link in ResumeHuntflowLink.objects.all() if link.resume_id}
    except Exception:
        pass
    check_by_resume = {
        c.resume_id: 'not_found'
        for c in HHruResumeHuntflowCheck.objects.filter(status=HHruResumeHuntflowCheck.Status.NOT_FOUND)
    }

    seen_ids = set()
    for it in all_items:
        nid = it.get('id')
        if nid in seen_ids:
            continue
        seen_ids.add(nid)
        state_id = ((it.get('employer_state') or {}).get('id') or '').strip()
        folder_key = COLLECTION_TO_FOLDER.get(state_id) or FOLDER_UNSEEN
        resume_id = _resume_id_from_negotiation_item(it)
        huntflow_link = huntflow_by_resume.get(resume_id) if resume_id else None
        huntflow_status_info = status_by_resume_id.get(resume_id) if resume_id else None
        card = _build_candidate_card(it, vacancy_title, huntflow_link, huntflow_status_info=huntflow_status_info)
        if not card.get('in_huntflow') and resume_id:
            card['huntflow_check_status'] = check_by_resume.get(resume_id)
        folders[folder_key].append(card)

    folder_labels = {
        FOLDER_UNSEEN: 'Не разобранные',
        FOLDER_CONSIDER: 'Подумать',
        FOLDER_PRIMARY: 'Первичный контакт',
        FOLDER_REJECTIONS: 'Отказы',
    }
    folder_list = [
        {'key': k, 'label': v, 'items': folders[k]}
        for k, v in folder_labels.items()
    ]

    return render(request, 'hhru/vacancy_responses.html', {
        'account': account,
        'hh_vacancy_id': hh_vacancy_id,
        'vacancy_title': vacancy_title,
        'folder_list': folder_list,
    })


@login_required
def vacancies_active(request):
    """Список активных вакансий HH.ru с привязкой к локальным по huntflow_id. Данные берутся из кэша при наличии."""
    account = _get_user_account(request.user)
    if not account:
        return redirect('hhru:dashboard')
    if not account.is_token_valid:
        from django.contrib import messages
        messages.warning(request, 'Токен HH.ru истёк. Обновите токен.')
        return redirect('hhru:dashboard')
    employer_id = _ensure_employer_id(account)
    if not employer_id:
        from django.contrib import messages
        messages.warning(request, 'Не удалось определить ID работодателя. Укажите его вручную на странице настроек.')
        return redirect('hhru:employer_id_set')
    try:
        page = int(request.GET.get('page', 0))
    except ValueError:
        page = 0
    per_page = 20
    data = None
    cached = cache_utils.get_cached_active_vacancies(account.pk)
    if cached and page * per_page < len(cached.get('items') or []):
        items = (cached.get('items') or [])[page * per_page:(page + 1) * per_page]
        found = cached.get('found', len(cached.get('items') or []))
        pages = max(1, (found + per_page - 1) // per_page)
        data = {'items': items, 'page': page, 'pages': pages, 'found': found}
    if data is None:
        try:
            data = get_employer_active_vacancies(account.access_token, employer_id, page=page, per_page=per_page)
            if page == 0:
                cache_utils.set_cached_active_vacancies(account.pk, data)
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Ошибка загрузки вакансий: {e}')
            return redirect('hhru:dashboard')
    items = data.get('items') or []
    links_map = {link.hh_vacancy_id: link for link in HHruVacancyLink.objects.filter(account=account)}
    from apps.vacancies.models import Vacancy
    vacancy_list = []
    for v in items:
        vid = str(v.get('id', ''))
        link = links_map.get(vid)
        huntflow_id = (link.huntflow_id or '').strip() if link else ''
        local_vacancies = list(Vacancy.objects.filter(huntflow_id=huntflow_id).order_by('name')) if huntflow_id else []
        vacancy_list.append({
            'hh': v,
            'hh_id': vid,
            'link': link,
            'huntflow_id': huntflow_id,
            'local_vacancies': local_vacancies,
        })
    page = data.get('page', 0)
    pages = data.get('pages', 0)
    return render(request, 'hhru/vacancies_active.html', {
        'account': account,
        'vacancy_list': vacancy_list,
        'pagination': {
            'page': page,
            'pages': pages,
            'found': data.get('found', 0),
            'next_page': page + 1 if page + 1 < pages else None,
            'prev_page': page - 1 if page > 0 else None,
        },
    })


@login_required
def vacancies_archived(request):
    """Список архивных вакансий HH.ru с привязкой к локальным по huntflow_id."""
    account = _get_user_account(request.user)
    if not account:
        return redirect('hhru:dashboard')
    if not account.is_token_valid:
        from django.contrib import messages
        messages.warning(request, 'Токен HH.ru истёк. Обновите токен.')
        return redirect('hhru:dashboard')
    employer_id = _ensure_employer_id(account)
    if not employer_id:
        from django.contrib import messages
        messages.warning(request, 'Не удалось определить ID работодателя. Укажите его вручную на странице настроек.')
        return redirect('hhru:employer_id_set')
    try:
        page = int(request.GET.get('page', 0))
        data = get_employer_archived_vacancies(account.access_token, employer_id, page=page, per_page=20)
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'Ошибка загрузки архивных вакансий: {e}')
        return redirect('hhru:dashboard')
    items = data.get('items') or []
    links_map = {link.hh_vacancy_id: link for link in HHruVacancyLink.objects.filter(account=account)}
    from apps.vacancies.models import Vacancy
    vacancy_list = []
    for v in items:
        vid = str(v.get('id', ''))
        link = links_map.get(vid)
        huntflow_id = (link.huntflow_id or '').strip() if link else ''
        local_vacancies = list(Vacancy.objects.filter(huntflow_id=huntflow_id).order_by('name')) if huntflow_id else []
        vacancy_list.append({
            'hh': v,
            'hh_id': vid,
            'link': link,
            'huntflow_id': huntflow_id,
            'local_vacancies': local_vacancies,
        })
    page = data.get('page', 0)
    pages = data.get('pages', 0)
    return render(request, 'hhru/vacancies_archived.html', {
        'account': account,
        'vacancy_list': vacancy_list,
        'pagination': {
            'page': page,
            'pages': pages,
            'found': data.get('found', 0),
            'next_page': page + 1 if page + 1 < pages else None,
            'prev_page': page - 1 if page > 0 else None,
        },
    })


@login_required
@require_POST
@csrf_protect
def vacancy_link_save_ajax(request):
    """Сохранение связи HH вакансия → huntflow_id."""
    account = _get_user_account(request.user)
    if not account:
        return JsonResponse({'success': False, 'error': 'Аккаунт не найден'})
    hh_vacancy_id = (request.POST.get('hh_vacancy_id') or '').strip()
    huntflow_id = (request.POST.get('huntflow_id') or '').strip()
    if not hh_vacancy_id:
        return JsonResponse({'success': False, 'error': 'hh_vacancy_id обязателен'})
    link, _ = HHruVacancyLink.objects.update_or_create(
        account=account,
        hh_vacancy_id=hh_vacancy_id,
        defaults={'huntflow_id': huntflow_id},
    )
    return JsonResponse({'success': True, 'huntflow_id': link.huntflow_id})


def _run_huntflow_check_for_resume(request, resume_id, resume_url=None):
    """
    Проверяет, есть ли кандидат с данным HH resume_id в Huntflow.
    Сначала проверяет сохранённую связь (ResumeHuntflowLink из расширения/ранее созданную).
    Если связи нет — ищет по API (externals[].data.hh_id).
    Возвращает dict: found, error, huntflow_url, huntflow_link_id, status_name, rejection_reason_name.
    """
    resume_id = (resume_id or '').strip()
    if not resume_id:
        return {'found': False, 'error': 'resume_id обязателен', 'huntflow_url': None, 'huntflow_link_id': None, 'status_name': '', 'rejection_reason_name': ''}
    resume_url = (resume_url or '').strip() or f'https://hh.ru/resume/{resume_id}'
    try:
        from apps.huntflow.views import get_correct_account_id
        from apps.huntflow.services import HuntflowService
        from apps.huntflow.models import ResumeHuntflowLink
    except ImportError:
        return {'found': False, 'error': 'Интеграция Huntflow недоступна', 'huntflow_url': None, 'huntflow_link_id': None, 'status_name': '', 'rejection_reason_name': ''}
    account_id = get_correct_account_id(request.user)
    if not account_id:
        return {'found': False, 'error': 'Не настроен аккаунт Huntflow', 'huntflow_url': None, 'huntflow_link_id': None, 'status_name': '', 'rejection_reason_name': ''}
    now = timezone.now()

    link = ResumeHuntflowLink.objects.filter(resume_id=resume_id).first()
    if link and link.huntflow_url:
        HHruResumeHuntflowCheck.objects.update_or_create(
            resume_id=resume_id,
            defaults={'status': HHruResumeHuntflowCheck.Status.FOUND, 'huntflow_url': link.huntflow_url, 'checked_at': now},
        )
        status_info = _get_applicant_status_info(request.user, link.huntflow_url)
        return {
            'found': True, 'error': None, 'huntflow_url': link.huntflow_url,
            'huntflow_link_id': link.id,
            'status_name': status_info.get('status_name', ''),
            'rejection_reason_name': status_info.get('rejection_reason_name', ''),
        }

    try:
        api = HuntflowService(user=request.user)
        result = api.find_applicant_by_hh_resume_id(account_id, resume_id)
    except Exception as e:
        return {'found': False, 'error': str(e), 'huntflow_url': None, 'huntflow_link_id': None, 'status_name': '', 'rejection_reason_name': ''}
    if result:
        applicant_id = result.get('applicant_id')
        acc_id = result.get('account_id', account_id)
        huntflow_url = request.build_absolute_uri(f'/huntflow/accounts/{acc_id}/applicants/{applicant_id}/')
        canonical_resume_url = resume_url
        if '?' in canonical_resume_url:
            canonical_resume_url = canonical_resume_url.split('?')[0]
        if 'hh.ru' not in canonical_resume_url and 'headhunter' not in canonical_resume_url:
            canonical_resume_url = f'https://hh.ru/resume/{resume_id}'
        link, created = ResumeHuntflowLink.objects.update_or_create(
            resume_id=resume_id,
            defaults={
                'resume_url': canonical_resume_url,
                'huntflow_url': huntflow_url,
                'updated_by': request.user,
            },
        )
        if created:
            link.created_by = request.user
            link.save(update_fields=['created_by'])
        HHruResumeHuntflowCheck.objects.update_or_create(
            resume_id=resume_id,
            defaults={'status': HHruResumeHuntflowCheck.Status.FOUND, 'huntflow_url': huntflow_url, 'checked_at': now},
        )
        status_info = _get_applicant_status_info(request.user, huntflow_url)
        return {
            'found': True, 'error': None, 'huntflow_url': huntflow_url,
            'huntflow_link_id': link.id,
            'status_name': status_info.get('status_name', ''),
            'rejection_reason_name': status_info.get('rejection_reason_name', ''),
        }
    HHruResumeHuntflowCheck.objects.update_or_create(
        resume_id=resume_id,
        defaults={'status': HHruResumeHuntflowCheck.Status.NOT_FOUND, 'huntflow_url': '', 'checked_at': now},
    )
    return {'found': False, 'error': None, 'huntflow_url': None, 'huntflow_link_id': None, 'status_name': '', 'rejection_reason_name': ''}


@login_required
@require_POST
@csrf_protect
def update_huntflow_link_ajax(request):
    """Обновление ссылки на Huntflow для связи резюме (редактирование связи)."""
    link_id = request.POST.get('link_id')
    huntflow_url = (request.POST.get('huntflow_url') or '').strip()
    if not link_id or not huntflow_url:
        return JsonResponse({'success': False, 'error': 'Нужны link_id и huntflow_url'})
    try:
        from apps.huntflow.models import ResumeHuntflowLink
        link = ResumeHuntflowLink.objects.get(pk=link_id)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Связь не найдена'})
    if 'huntflow' not in huntflow_url.lower():
        return JsonResponse({'success': False, 'error': 'Укажите ссылку на Huntflow'})
    link.huntflow_url = huntflow_url
    link.updated_by = request.user
    link.save(update_fields=['huntflow_url', 'updated_by', 'updated_at'])
    return JsonResponse({'success': True, 'huntflow_url': link.huntflow_url})


@login_required
@require_POST
@csrf_protect
def check_huntflow_ajax(request):
    """Проверка наличия кандидата (HH resume_id) в Huntflow; при нахождении — создание связи."""
    resume_id = (request.POST.get('resume_id') or '').strip()
    resume_url = (request.POST.get('resume_url') or '').strip()
    if not resume_id:
        return JsonResponse({'success': False, 'error': 'resume_id обязателен', 'found': False})
    result = _run_huntflow_check_for_resume(request, resume_id, resume_url)
    if result.get('error') and not result.get('found'):
        return JsonResponse({'success': False, 'error': result['error'], 'found': False})
    return JsonResponse({
        'success': True,
        'found': result['found'],
        'huntflow_url': result.get('huntflow_url'),
        'huntflow_link_id': result.get('huntflow_link_id'),
        'status_name': result.get('status_name') or '',
        'rejection_reason_name': result.get('rejection_reason_name') or '',
    })


@login_required
@require_POST
@csrf_protect
def change_negotiation_status_ajax(request):
    """Смена статуса отклика HH.ru: PUT по action_url с токеном пользователя."""
    account = _get_user_account(request.user)
    if not account:
        return JsonResponse({'success': False, 'error': 'Аккаунт не найден'})
    if not account.is_token_valid:
        return JsonResponse({'success': False, 'error': 'Токен HH.ru истёк. Обновите токен.'})
    action_url = (request.POST.get('action_url') or '').strip()
    if not action_url:
        return JsonResponse({'success': False, 'error': 'action_url обязателен'})
    if not action_url.startswith('https://api.hh.ru/negotiations/'):
        return JsonResponse({'success': False, 'error': 'Недопустимый URL действия'})
    message = (request.POST.get('message') or '').strip()
    send_sms = request.POST.get('send_sms') in ('1', 'true', 'yes')
    try:
        change_negotiation_action(account.access_token, action_url, message=message or None, send_sms=send_sms)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ——— Логи ———
@login_required
def logs_list(request):
    account = _get_user_account(request.user)
    logs = HHruApiLog.objects.filter(account=account).order_by('-created_at') if account else HHruApiLog.objects.none()
    log_type = request.GET.get('log_type')
    method = request.GET.get('method')
    if log_type:
        logs = logs.filter(log_type=log_type)
    if method:
        logs = logs.filter(method=method)
    logs = logs[:500]
    log_types = HHruApiLog.LogType.choices
    return render(request, 'hhru/logs_list.html', {
        'logs': logs,
        'log_types': log_types,
    })


# ——— AJAX ———
@login_required
@require_POST
@csrf_protect
def test_connection_ajax(request):
    account_id = request.POST.get('account_id')
    if account_id:
        account = get_object_or_404(HHruOAuthAccount, pk=account_id, user=request.user)
    else:
        account = _get_user_account(request.user)
    if not account:
        return JsonResponse({'success': False, 'error': 'Аккаунт не найден'})
    try:
        me = get_me(account.access_token)
        return JsonResponse({'success': True, 'message': f"Подключено: {me.get('first_name', '')} {me.get('last_name', '')}"})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
@csrf_protect
def refresh_token_ajax(request):
    account_id = request.POST.get('account_id')
    if account_id:
        account = get_object_or_404(HHruOAuthAccount, pk=account_id, user=request.user)
    else:
        account = _get_user_account(request.user)
    if not account:
        return JsonResponse({'success': False, 'error': 'Аккаунт не найден'})
    config = account.config or _get_default_config()
    if not config or not account.refresh_token:
        return JsonResponse({'success': False, 'error': 'Невозможно обновить токен'})
    try:
        data = refresh_access_token(config.client_id, config.client_secret, account.refresh_token)
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        expires_in = data.get('expires_in', 3600)
        if not access_token:
            return JsonResponse({'success': False, 'error': 'Не получен access_token'})
        expires_at = timezone.now() + timezone.timedelta(seconds=expires_in) if expires_in else None
        account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token
        account.token_expires_at = expires_at
        account.save(update_fields=['access_token', 'refresh_token', 'token_expires_at', 'updated_at'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
