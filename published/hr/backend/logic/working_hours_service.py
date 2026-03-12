"""
Сервис эффективных рабочих часов.
Определяет work_start_hour, work_end_hour, meeting_interval_minutes
с приоритетом: профиль пользователя -> настройки компании -> значения по умолчанию (10-18).
"""
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model
    User = get_user_model()


def _hour_from_time(value: Any) -> Optional[int]:
    """Извлечь час из time или строки вида 'HH:MM'."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return dt_time.fromisoformat(value).hour
        except (ValueError, TypeError):
            return None
    if hasattr(value, 'hour'):
        return value.hour
    return None


def get_effective_working_hours(
    user: "User",
    company_settings: Optional[Any] = None,
    user_is_participant: bool = True,
    company_hours_priority: bool = False,
) -> dict:
    """
    Возвращает эффективные рабочие часы и интервал между встречами.

    Приоритет для work_start_hour / work_end_hour (по умолчанию user > company):
    1. По умолчанию: work_start_hour=10, work_end_hour=18.
    2. Слоты компании: если в CompanySettings заданы work_start_time, work_end_time — переопределяют дефолт.
    3. Слоты пользователя: если user_is_participant=True и у пользователя заданы interview_start_time /
       interview_end_time — переопределяют слоты компании (наивысший приоритет).
    Если company_hours_priority=True (страница календаря): приоритет компания > пользователь.
    Если пользователь не участник встречи (user_is_participant=False) — слоты пользователя не учитываются,
    используются только слоты компании или дефолт.

    meeting_interval_minutes — из пользователя только если user_is_participant=True, иначе 15.

    Returns:
        dict с ключами: work_start_hour (int), work_end_hour (int), meeting_interval_minutes (int).
    """
    work_start_hour = 10
    work_end_hour = 18
    meeting_interval_minutes = 15

    # 1. Слоты компании переопределяют дефолт
    company_start_h = None
    company_end_h = None
    if company_settings is not None:
        company_start_h = _hour_from_time(getattr(company_settings, 'work_start_time', None))
        company_end_h = _hour_from_time(getattr(company_settings, 'work_end_time', None))
        if company_start_h is not None and company_end_h is not None:
            work_start_hour = company_start_h
            work_end_hour = company_end_h

    # 2. Слоты пользователя
    user_start_h = None
    user_end_h = None
    if user_is_participant and user is not None:
        user_start_h = _hour_from_time(getattr(user, 'interview_start_time', None))
        user_end_h = _hour_from_time(getattr(user, 'interview_end_time', None))

    # Приоритет: company_hours_priority=True → компания > пользователь; иначе пользователь > компания
    if company_hours_priority:
        # Сначала применяем пользователя, затем компания перезаписывает (компания выше)
        if user_start_h is not None:
            work_start_hour = user_start_h
        if user_end_h is not None:
            work_end_hour = user_end_h
        if company_start_h is not None:
            work_start_hour = company_start_h
        if company_end_h is not None:
            work_end_hour = company_end_h
    else:
        # Стандартный приоритет: пользователь перезаписывает компанию
        if user_start_h is not None:
            work_start_hour = user_start_h
        if user_end_h is not None:
            work_end_hour = user_end_h

    # meeting_interval_minutes — из пользователя только если он участник (пока в компании нет поля)
    if user_is_participant and user is not None and getattr(user, 'meeting_interval_minutes', None) is not None:
        try:
            meeting_interval_minutes = int(user.meeting_interval_minutes)
        except (TypeError, ValueError):
            pass

    return {
        'work_start_hour': work_start_hour,
        'work_end_hour': work_end_hour,
        'meeting_interval_minutes': meeting_interval_minutes,
    }
