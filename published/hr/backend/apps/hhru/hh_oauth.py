"""Клиент OAuth 2.0 для HeadHunter.ru (authorize, token exchange, refresh)."""
import urllib.parse
import requests
from django.conf import settings as django_settings

HH_AUTHORIZE_URL = 'https://hh.ru/oauth/authorize'
HH_TOKEN_URL = 'https://api.hh.ru/token'
HH_ME_URL = 'https://api.hh.ru/me'


def build_authorize_url(client_id, redirect_uri, state=None):
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
    }
    if state:
        params['state'] = state
    return f"{HH_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(client_id, client_secret, redirect_uri, code):
    """Обмен authorization code на access_token и refresh_token. POST https://api.hh.ru/token."""
    data = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    resp = requests.post(
        HH_TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(client_id, client_secret, refresh_token_value):
    """Обновление access_token по refresh_token. POST https://api.hh.ru/token."""
    data = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token_value,
    }
    resp = requests.post(
        HH_TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_me(access_token):
    """GET https://api.hh.ru/me — данные текущего пользователя."""
    resp = requests.get(
        HH_ME_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


HH_EMPLOYER_ACTIVE_VACANCIES = 'https://api.hh.ru/employers/{employer_id}/vacancies/active'
HH_EMPLOYER_ARCHIVED_VACANCIES = 'https://api.hh.ru/employers/{employer_id}/vacancies/archived'


def get_employer_active_vacancies(access_token, employer_id, page=0, per_page=50):
    """GET /employers/{employer_id}/vacancies/active — список опубликованных вакансий."""
    url = HH_EMPLOYER_ACTIVE_VACANCIES.format(employer_id=employer_id)
    resp = requests.get(
        url,
        headers={'Authorization': f'Bearer {access_token}'},
        params={'page': page, 'per_page': per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_employer_archived_vacancies(access_token, employer_id, page=0, per_page=50):
    """GET /employers/{employer_id}/vacancies/archived — список архивных вакансий."""
    url = HH_EMPLOYER_ARCHIVED_VACANCIES.format(employer_id=employer_id)
    resp = requests.get(
        url,
        headers={'Authorization': f'Bearer {access_token}'},
        params={'page': page, 'per_page': per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


HH_NEGOTIATIONS_URL = 'https://api.hh.ru/negotiations'


def get_negotiations_meta(access_token, vacancy_id):
    """
    GET /negotiations?vacancy_id=X&with_generated_collections=true
    Возвращает коллекции и сгенерированные коллекции откликов по вакансии.
    """
    resp = requests.get(
        HH_NEGOTIATIONS_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        params={'vacancy_id': vacancy_id, 'with_generated_collections': 'true'},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_negotiations_collection(access_token, collection_url, page=0, per_page=50):
    """
    GET по URL коллекции откликов (из meta).
    Возвращает список откликов/приглашений с резюме и employer_state.
    """
    resp = requests.get(
        collection_url,
        headers={'Authorization': f'Bearer {access_token}'},
        params={'page': page, 'per_page': per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def change_negotiation_action(access_token, action_url, message=None, send_sms=False):
    """
    PUT по URL действия отклика (из item.actions[].url).
    Меняет статус отклика. Тело — application/x-www-form-urlencoded (message, send_sms и т.д.).
    Успех — 204 No Content.
    """
    data = {}
    if message is not None and str(message).strip():
        data['message'] = str(message).strip()
    if send_sms:
        data['send_sms'] = 'true'
    resp = requests.put(
        action_url,
        headers={'Authorization': f'Bearer {access_token}'},
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.status_code == 204


def _collect_negotiation_collection_urls(meta):
    """Собирает список (id, url) коллекций откликов из meta API."""
    urls = []
    for c in (meta.get('generated_collections') or []):
        u = c.get('url')
        if u:
            urls.append((c.get('id') or '', u))
    for c in (meta.get('collections') or []):
        u = c.get('url')
        if u:
            urls.append((c.get('id') or '', u))
        for sub in (c.get('sub_collections') or []):
            su = sub.get('url')
            if su:
                urls.append((sub.get('id') or c.get('id') or '', su))
    return urls


def fetch_all_negotiations_for_vacancy(access_token, vacancy_id, per_page=50):
    """
    Загружает все отклики по вакансии (все коллекции, все страницы).
    Возвращает список элементов откликов (all_items). При ошибке API — пустой список.
    """
    try:
        meta = get_negotiations_meta(access_token, vacancy_id)
    except Exception:
        return []
    all_items = []
    for _coll_id, url in _collect_negotiation_collection_urls(meta):
        page = 0
        while True:
            try:
                data = get_negotiations_collection(access_token, url, page=page, per_page=per_page)
            except Exception:
                break
            items = data.get('items') or []
            for it in items:
                all_items.append(it)
            pages = data.get('pages') or 0
            if page + 1 >= pages or not items:
                break
            page += 1
    return all_items
