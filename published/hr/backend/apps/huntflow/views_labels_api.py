from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _tag_color_to_hex(tag_obj: Dict[str, Any]) -> Optional[str]:
    raw = (
        tag_obj.get("color")
        or tag_obj.get("background_color")
        or tag_obj.get("bg_color")
        or tag_obj.get("border_color")
        or tag_obj.get("hex")
    )
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("hex") or raw.get("value") or raw.get("color")
    if raw is None:
        return None
    if isinstance(raw, int):
        return "#{:06x}".format(raw & 0xFFFFFF)

    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("#"):
        return s if len(s) in (4, 7) else "#" + s[-6:].lower()
    if len(s) in (3, 6) and all(c in "0123456789aAbBcCdDeEfF" for c in s):
        return "#" + s.lower()
    return s


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def huntflow_labels(request):
    """
    GET /api/v1/huntflow/labels/?account_id=123

    Возвращает список доступных меток Huntflow (tags) для UI расширения.
    Формат ответа сделан максимально совместимым с extension:
    - { success: true, items: [{id,name,color?,account_id,account_name}] }
    """
    try:
        from apps.huntflow.services import HuntflowService

        api = HuntflowService(user=request.user)
        account_id_qs = (request.query_params.get("account_id") or "").strip()

        accounts_data = api.get_accounts()
        accounts: List[Dict[str, Any]] = []
        if accounts_data and isinstance(accounts_data, dict) and isinstance(accounts_data.get("items"), list):
            accounts = accounts_data["items"]

        if account_id_qs:
            try:
                account_id = int(account_id_qs)
            except ValueError:
                return Response(
                    {"success": False, "error": "account_id должен быть числом"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            accounts = [a for a in accounts if a.get("id") == account_id]

        if not accounts:
            return Response(
                {"success": True, "items": [], "message": "Организации Huntflow не найдены или недоступны"},
                status=status.HTTP_200_OK,
            )

        out: List[Dict[str, Any]] = []
        seen = set()

        for acc in accounts:
            acc_id = acc.get("id")
            if acc_id is None:
                continue
            acc_name = (acc.get("name") or acc.get("nick") or "").strip()

            tags_data = api.get_tags(acc_id)
            items = []
            if tags_data and isinstance(tags_data, dict) and isinstance(tags_data.get("items"), list):
                items = tags_data["items"]

            for t in items:
                tid = t.get("id")
                name = (t.get("name") or t.get("title") or "").strip()
                if not name:
                    continue

                key = (str(name).lower(), int(acc_id))
                if key in seen:
                    continue
                seen.add(key)

                obj: Dict[str, Any] = {"name": name, "account_id": acc_id}
                if acc_name:
                    obj["account_name"] = acc_name
                if tid is not None:
                    obj["id"] = tid
                color = _tag_color_to_hex(t) if isinstance(t, dict) else None
                if color:
                    obj["color"] = color
                out.append(obj)

        return Response({"success": True, "items": out}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Failed to fetch Huntflow labels")
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

