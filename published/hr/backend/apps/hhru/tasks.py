"""Фоновые задачи для кэширования данных HH.ru (активные вакансии, отклики по вакансиям)."""
import logging
from celery import shared_task
from django.utils import timezone

from .hh_oauth import (
    get_employer_active_vacancies,
    refresh_access_token,
    fetch_all_negotiations_for_vacancy,
)
from .cache_utils import (
    set_cached_active_vacancies,
    set_cached_negotiations,
    CACHE_TTL,
)
from .models import HHruOAuthAccount

logger = logging.getLogger(__name__)

# Максимум вакансий, по которым подгружаем отклики за один прогон (чтобы не превысить лимит задачи)
MAX_VACANCIES_TO_WARM = 25


def _ensure_token_valid(account):
    """При необходимости обновляет токен аккаунта. Возвращает True, если токен пригоден."""
    if account.is_token_valid:
        return True
    config = account.config
    if not config or not account.refresh_token:
        return False
    try:
        data = refresh_access_token(
            config.client_id,
            config.client_secret,
            account.refresh_token,
        )
        account.access_token = data.get('access_token') or account.access_token
        if data.get('refresh_token'):
            account.refresh_token = data['refresh_token']
        expires_in = data.get('expires_in', 3600)
        from datetime import timedelta
        account.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        account.save(update_fields=['access_token', 'refresh_token', 'token_expires_at'])
        return True
    except Exception as e:
        logger.warning('HHru: не удалось обновить токен для account %s: %s', account.pk, e)
        return False


@shared_task(name='apps.hhru.tasks.refresh_hhru_vacancies_and_responses_cache')
def refresh_hhru_vacancies_and_responses_cache(account_id=None):
    """
    Фоново подгружает и кэширует активные вакансии и отклики по ним для HH.ru.
    Если account_id передан — только для этого аккаунта, иначе для всех с employer_id и токеном.
    """
    if account_id is not None:
        accounts = HHruOAuthAccount.objects.filter(pk=account_id)
    else:
        accounts = HHruOAuthAccount.objects.filter(
            access_token__isnull=False,
        ).exclude(access_token='').exclude(employer_id='')

    total_vacancies = 0
    total_responses = 0
    errors = 0

    for account in accounts:
        if not _ensure_token_valid(account):
            logger.debug('HHru cache: пропуск account %s (нет валидного токена)', account.pk)
            continue
        employer_id = (account.employer_id or '').strip()
        if not employer_id:
            continue
        try:
            active_data = get_employer_active_vacancies(
                account.access_token, employer_id, page=0, per_page=100
            )
        except Exception as e:
            logger.warning('HHru cache: ошибка загрузки активных вакансий account %s: %s', account.pk, e)
            errors += 1
            continue
        set_cached_active_vacancies(account.pk, active_data)
        items = active_data.get('items') or []
        total_vacancies += len(items)
        vacancy_ids = [str(v.get('id')) for v in items if v.get('id')][:MAX_VACANCIES_TO_WARM]
        for vac in items[:MAX_VACANCIES_TO_WARM]:
            vid = vac.get('id')
            if not vid:
                continue
            vid = str(vid)
            title = vac.get('name') or vac.get('title') or ''
            try:
                all_items = fetch_all_negotiations_for_vacancy(account.access_token, vid)
                set_cached_negotiations(account.pk, vid, all_items, vacancy_title=title)
                total_responses += len(all_items)
            except Exception as e:
                logger.debug('HHru cache: ошибка откликов vacancy %s account %s: %s', vid, account.pk, e)
                errors += 1

    logger.info(
        'HHru cache: обновлено вакансий=%s, откликов=%s, ошибок=%s',
        total_vacancies, total_responses, errors,
    )
    return {'vacancies': total_vacancies, 'responses': total_responses, 'errors': errors}
