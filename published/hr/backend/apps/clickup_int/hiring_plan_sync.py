"""
Синхронизация данных папки ClickUp в заявки плана найма (ClickUpHiringRequest).
Сохраняет и обновляет заявки по clickup_task_id; данные изолированы от задач выгрузки в Huntflow.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import ClickUpHiringRequest
from .services import ClickUpService, ClickUpAPIError

User = get_user_model()
logger = logging.getLogger(__name__)


def _parse_ts(value: Any) -> Optional[datetime]:
    """Парсит timestamp из ClickUp: миллисекунды (int/float/строка с числом) или строка ISO."""
    if value is None:
        return None
    # Строка с числом (ClickUp иногда отдаёт даты как "1707123456789")
    if isinstance(value, str) and value.strip().isdigit():
        try:
            value = int(value.strip())
        except (ValueError, TypeError):
            pass
    if isinstance(value, (int, float)):
        try:
            if value > 1e12:  # миллисекунды
                return timezone.make_aware(datetime.fromtimestamp(value / 1000.0))
            if value > 1e9:  # секунды
                return timezone.make_aware(datetime.fromtimestamp(value))
            return None
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            from dateutil.parser import parse as date_parse
            dt = date_parse(value)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except Exception:
            return None
    return None


def _status_name(task: Dict) -> str:
    """Извлекает имя статуса из задачи (status может быть объектом)."""
    s = task.get('status')
    if not s:
        return ''
    if isinstance(s, dict):
        return (s.get('status') or s.get('name') or '').strip()
    return str(s).strip()


def _request_type_from_name(task_name: str) -> str:
    """
    Определяет тип заявки по названию задачи:
    - Слово в конце после последнего «-»: «Hire» → hiring, «Transfer» → transfer.
    - Если в названии нет разделителя «-» → группа (group).
    """
    name = (task_name or '').strip()
    if not name:
        return 'unknown'
    if '-' not in name:
        return 'group'
    last_part = name.rsplit('-', 1)[-1].strip().lower()
    if last_part == 'hire':
        return 'hiring'
    if last_part == 'transfer':
        return 'transfer'
    return 'unknown'


def _request_type_from_custom_fields(custom_fields: List[Dict]) -> str:
    """Определяет тип заявки (hiring/transfer) из custom_fields (fallback)."""
    for cf in (custom_fields or []):
        name = (cf.get('name') or '').lower()
        if 'request type' in name or 'тип заявки' in name or 'type' in name:
            val = cf.get('value') or cf.get('type')
            if isinstance(val, str) and 'transfer' in val.lower():
                return 'transfer'
            if isinstance(val, str) and ('hiring' in val.lower() or 'найм' in val.lower()):
                return 'hiring'
            if isinstance(val, (int, float)) and val:
                return 'hiring'
        if 'transfer' in name or 'перевод' in name:
            return 'transfer'
    return 'unknown'


def _department_from_custom_fields(custom_fields: List[Dict]) -> str:
    """Извлекает отдел/группу из custom_fields."""
    for cf in (custom_fields or []):
        name = (cf.get('name') or '').lower()
        if 'department' in name or 'отдел' in name or 'группа' in name:
            val = cf.get('value') or cf.get('type')
            if isinstance(val, str):
                return val.strip()[:255]
    return ''


def _assignees_list(task: Dict) -> List[Dict]:
    """Список ответственных с email."""
    assignees = task.get('assignees') or []
    out = []
    for a in assignees:
        if isinstance(a, dict):
            out.append({
                'id': a.get('id'),
                'email': (a.get('email') or '').strip(),
                'username': a.get('username'),
            })
    return out


def _find_recruiter_by_assignees(assignees: List[Dict], user_queryset=None) -> Optional[User]:
    """По первому email из assignees ищет пользователя (рекрутера)."""
    if user_queryset is None:
        user_queryset = User.objects.all()
    for a in assignees:
        email = (a.get('email') or '').strip()
        if not email:
            continue
        u = user_queryset.filter(email__iexact=email).first()
        if u:
            return u
    return None


def sync_folder_to_hiring_requests(
    user: User,
    folder_data: Dict[str, Any],
    service: ClickUpService,
    fetch_full_task: bool = True,
) -> Tuple[int, int]:
    """
    Сохраняет/обновляет заявки плана найма из folder_data.
    - fetch_full_task: подтягивать ли полную задачу (GET /task/{id}) для custom_fields.
    Возвращает (created_count, updated_count).
    """
    created, updated = 0, 0
    folder_id = (folder_data.get('folder_id') or '').strip()
    lists_data = folder_data.get('lists') or []

    for list_item in lists_data:
        list_id = str(list_item.get('id') or list_item.get('list_id') or '')
        list_name = (list_item.get('name') or '').strip()
        tasks = list_item.get('tasks') or []

        for task in tasks:
            task_id = task.get('id') or task.get('task_id')
            if not task_id:
                continue
            task_id = str(task_id)

            full_task = task
            if fetch_full_task:
                try:
                    full_task = service.get_task(task_id) or task
                except ClickUpAPIError:
                    full_task = task

            custom_fields_raw = full_task.get('custom_fields') or []
            task_name = (full_task.get('name') or '').strip()
            request_type = _request_type_from_name(task_name)
            if request_type == 'unknown':
                request_type = _request_type_from_custom_fields(custom_fields_raw)
            department = _department_from_custom_fields(custom_fields_raw)
            assignees = _assignees_list(full_task)
            recruiter = _find_recruiter_by_assignees(assignees)

            # Нормализованный статус пока = имя статуса в ClickUp (маппинг можно добавить позже)
            clickup_status = _status_name(full_task)
            normalized_status = clickup_status

            defaults = {
                'name': (full_task.get('name') or full_task.get('title') or '')[:500],
                'clickup_status': clickup_status[:100],
                'date_created': _parse_ts(full_task.get('date_created')),
                'date_updated': _parse_ts(full_task.get('date_updated')),
                'start_date': _parse_ts(full_task.get('start_date')),
                'due_date': _parse_ts(full_task.get('due_date')),
                'list_id': list_id[:100],
                'list_name': list_name[:255],
                'folder_id': folder_id[:100],
                'request_type': request_type,
                'normalized_status': normalized_status[:100],
                'recruiter': recruiter,
                'department': department[:255],
                'assignees': assignees,
                'creator': full_task.get('creator') if isinstance(full_task.get('creator'), dict) else {},
                'custom_fields': list(custom_fields_raw) if custom_fields_raw else [],
                'raw_task': {
                    'id': full_task.get('id'),
                    'name': full_task.get('name'),
                    'status': full_task.get('status'),
                    'date_updated': full_task.get('date_updated'),
                },
            }

            obj, was_created = ClickUpHiringRequest.objects.update_or_create(
                user=user,
                clickup_task_id=task_id,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

    return created, updated


def format_clickup_task_for_notes(task_data: Dict[str, Any]) -> str:
    """
    Форматирует данные задачи ClickUp в текст для поля «Заметки» заявки на найм.
    Используется при связывании заявки с задачей (clickup_task_id).
    """
    if not task_data:
        return ''
    lines = []
    task_id = task_data.get('id') or task_data.get('task_id') or ''
    lines.append(f"--- Данные из ClickUp (задача {task_id}) ---")
    lines.append(f"Название: {task_data.get('name') or task_data.get('title') or '—'}")
    status = task_data.get('status')
    if isinstance(status, dict):
        status = status.get('status') or status.get('name') or '—'
    lines.append(f"Статус: {status or '—'}")
    lines.append(f"Список (list_id): {task_data.get('list_id') or '—'}")
    if task_data.get('folder'):
        folder = task_data['folder']
        name = folder.get('name') if isinstance(folder, dict) else str(folder)
        lines.append(f"Папка: {name or '—'}")
    for key, label in [
        ('date_created', 'Дата создания'),
        ('date_updated', 'Дата обновления'),
        ('start_date', 'Дата начала'),
        ('due_date', 'Срок (due)'),
    ]:
        val = task_data.get(key)
        if val is not None:
            dt = _parse_ts(val)
            lines.append(f"{label}: {dt.strftime('%d.%m.%Y %H:%M') if dt else val}")
        else:
            lines.append(f"{label}: —")
    assignees = task_data.get('assignees') or []
    if assignees:
        parts = []
        for a in assignees:
            if isinstance(a, dict):
                parts.append(a.get('username') or a.get('email') or str(a.get('id', '')))
        if parts:
            lines.append("Ответственные: " + ", ".join(parts))
    creator = task_data.get('creator')
    if creator and isinstance(creator, dict):
        lines.append(f"Создатель: {creator.get('username') or creator.get('email') or '—'}")
    custom_fields = task_data.get('custom_fields') or []
    if custom_fields:
        lines.append("Кастомные поля:")
        for cf in custom_fields:
            name = cf.get('name') or cf.get('id') or '—'
            val = cf.get('value')
            if isinstance(val, list) and val and isinstance(val[0], dict):
                val_str = "; ".join(
                    str(x.get('username') or x.get('email') or x.get('value', '')) for x in val[:5]
                )
            elif val is not None and val != '':
                val_str = str(val)[:200]
            else:
                val_str = '—'
            lines.append(f"  • {name}: {val_str}")
    desc = task_data.get('description')
    if desc:
        desc_plain = (desc[:500] + '…') if len(str(desc)) > 500 else desc
        lines.append(f"Описание: {desc_plain}")
    lines.append("--- Конец данных ClickUp ---")
    return "\n".join(lines)
