"""Ключи и TTL кэша для данных HH.ru (активные вакансии, отклики по вакансии)."""
from django.core.cache import cache

CACHE_PREFIX = 'hhru'
CACHE_TTL = 600  # 10 минут


def active_vacancies_cache_key(account_id):
    return f'{CACHE_PREFIX}:active_vacancies:{account_id}'


def vacancy_responses_cache_key(account_id, vacancy_id):
    return f'{CACHE_PREFIX}:responses:{account_id}:{vacancy_id}'


def get_cached_active_vacancies(account_id):
    """Возвращает закэшированный ответ API активных вакансий или None."""
    try:
        return cache.get(active_vacancies_cache_key(account_id))
    except Exception:
        return None


def set_cached_active_vacancies(account_id, data):
    """Сохраняет ответ API активных вакансий в кэш."""
    try:
        cache.set(active_vacancies_cache_key(account_id), data, timeout=CACHE_TTL)
    except Exception:
        pass


def get_cached_negotiations(account_id, vacancy_id):
    """
    Возвращает закэшированные данные по откликам: dict с ключами
    'all_items' (list) и 'vacancy_title' (str), или None.
    """
    try:
        return cache.get(vacancy_responses_cache_key(account_id, vacancy_id))
    except Exception:
        return None


def set_cached_negotiations(account_id, vacancy_id, all_items, vacancy_title=''):
    """Сохраняет список откликов и название вакансии в кэш."""
    try:
        payload = {'all_items': all_items or [], 'vacancy_title': vacancy_title or ''}
        cache.set(vacancy_responses_cache_key(account_id, vacancy_id), payload, timeout=CACHE_TTL)
    except Exception:
        pass
