"""
Синхронизация откликов HH/rabota.by в таблицу HHResponse при загрузке откликов по вакансии.
База HH и rabota.by общая — отклики приходят из одного API, сохраняем их в HHResponse,
чтобы расширение могло находить запись по resume_url и выполнять пригласить/отказать.
"""
import logging
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


def _parse_dt(s):
    if not s:
        return timezone.now()
    try:
        if "T" in str(s):
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return datetime.strptime(str(s)[:10], "%Y-%m-%d")
    except Exception:
        return timezone.now()


def _resume_url(item):
    """URL резюме из элемента отклика (HH API возвращает url или alternate_url)."""
    resume = (item or {}).get("resume") or {}
    return (resume.get("url") or resume.get("alternate_url") or "").strip()


def sync_negotiations_to_hh_response(account_id, hh_vacancy_id, all_items, vacancy_title=""):
    """
    Сохраняет/обновляет отклики в HHResponse по списку из API (negotiations).
    Вызывать при загрузке откликов по вакансии (страница откликов или фоновое обновление кэша).
    """
    from apps.huntflow.models import HHResponse

    if not all_items:
        return 0
    hh_vacancy_id = str(hh_vacancy_id or "")
    updated = 0
    for item in all_items:
        if not isinstance(item, dict):
            continue
        hh_response_id = str(item.get("id") or "").strip()
        if not hh_response_id:
            continue
        resume = item.get("resume") or {}
        url = _resume_url(item)
        created_at = _parse_dt(item.get("created_at"))
        updated_at = _parse_dt(item.get("updated_at"))

        def _email():
            for c in resume.get("contacts") or []:
                if (c.get("type") or {}).get("id") == "email":
                    return (c.get("value") or "")[:254]
            return ""

        def _phone():
            for c in resume.get("contacts") or []:
                if (c.get("type") or {}).get("id") == "phone":
                    return (c.get("value") or "")[:20]
            return ""

        # Маппинг employer_state.id из API (response, consider, discard, ...) в RESPONSE_STATE_CHOICES
        employer_state = item.get("employer_state") or item.get("state") or {}
        raw_state = ((employer_state.get("id") or "") if isinstance(employer_state, dict) else "") or ""
        raw_state = str(raw_state).strip().lower()
        if raw_state in ("invitation", "invited"):
            state_val = "invitation"
        elif raw_state in ("discard", "discard_after_interview", "discard_by_employer"):
            state_val = "rejected"
        elif raw_state in ("response", "consider", "phone_interview", "interview", "assessment", "offer", "hired"):
            state_val = "applied"
        else:
            state_val = "applied"
        defaults = {
            "hh_vacancy_id": hh_vacancy_id,
            "first_name": (resume.get("first_name") or "")[:100],
            "last_name": (resume.get("last_name") or "")[:100],
            "middle_name": (resume.get("middle_name") or "")[:100],
            "email": _email(),
            "phone": _phone(),
            "hh_resume_url": url[:500] if url else "",
            "raw_data": item,
            "hh_created_at": created_at,
            "hh_updated_at": updated_at,
            "response_state": state_val,
        }
        try:
            # update_or_create: не трогаем applicant_id/account_id/vacancy_id при обновлении (остаются от импорта)
            obj, created = HHResponse.objects.update_or_create(
                hh_response_id=hh_response_id,
                defaults=defaults,
            )
            updated += 1
        except Exception as e:
            logger.warning("hhru sync_responses: не удалось сохранить отклик %s: %s", hh_response_id, e)
    return updated
