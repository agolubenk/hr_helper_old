from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.huntflow.services import HuntflowService
from apps.huntflow.models import HHResponse

from .models import HHruOAuthAccount
from .views import _get_default_config, _resolve_huntflow_url_to_account_applicant
from .hh_oauth import refresh_access_token, change_negotiation_action


def _get_user_hhru_account(user) -> Optional[HHruOAuthAccount]:
    return HHruOAuthAccount.objects.filter(user=user).order_by("-created_at").first()


def _ensure_valid_access_token(account: HHruOAuthAccount) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (access_token, error_message).
    Refreshes token if needed and possible.
    """
    if account and account.is_token_valid and not account.needs_refresh:
        return account.access_token, None

    cfg = account.config if account else None
    if not cfg:
        cfg = _get_default_config()
    if not cfg or not account or not account.refresh_token:
        return None, "HH.ru не подключен или невозможно обновить токен."

    try:
        data = refresh_access_token(cfg.client_id, cfg.client_secret, account.refresh_token)
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        if not access_token:
            return None, "Не удалось обновить access_token HH.ru."
        account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token
        account.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in) if expires_in else None
        account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        return account.access_token, None
    except Exception as e:
        return None, f"Не удалось обновить токен HH.ru: {e}"


def _normalize_resume_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Remove query/hash for stable matching
    u = u.split("#")[0].split("?")[0]
    return u


def _extract_action_url(raw_data: Any, kind: str) -> Optional[str]:
    """
    Best-effort extraction of HH negotiation action URL from saved HHResponse.raw_data.
    kind: "invite" | "reject"
    """
    if not raw_data:
        return None

    want = kind.lower()
    needles = [want]
    if want == "invite":
        needles += ["invitation", "accept", "approve", "invite"]
    if want == "reject":
        needles += ["rejection", "reject", "decline", "trash"]

    def score(action: Dict[str, Any]) -> int:
        s = 0
        for k in ("id", "name", "title", "type"):
            v = action.get(k)
            if isinstance(v, str):
                t = v.lower()
                for n in needles:
                    if n in t:
                        s += 10
        # explicit url present
        if isinstance(action.get("url"), str) and action["url"].startswith("http"):
            s += 1
        return s

    def walk(obj: Any) -> Optional[str]:
        if isinstance(obj, dict):
            actions = obj.get("actions")
            if isinstance(actions, list):
                best = None
                best_score = 0
                for a in actions:
                    if not isinstance(a, dict):
                        continue
                    u = a.get("url")
                    if not (isinstance(u, str) and u.startswith("http")):
                        continue
                    sc = score(a)
                    if sc > best_score:
                        best = u
                        best_score = sc
                if best and best_score >= 10:
                    return best
            for v in obj.values():
                found = walk(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for it in obj:
                found = walk(it)
                if found:
                    return found
        return None

    return walk(raw_data)


HUNTFLOW_URL_RE = re.compile(
    r"/my/(?P<account>[^/#]+)#/applicants/(?:filter/[^/]+/)?id/(?P<applicant>\d+)|"
    r"/my/(?P<account2>[^/#]+)#/applicants/filter/[^/]+/(?P<applicant2>\d+)|"
    r"/my/(?P<account3>[^/#]+)#/vacancy/(?P<vacancy>\d+)/filter/[^/]+/id/(?P<applicant3>\d+)",
    re.IGNORECASE,
)


def _parse_huntflow_ids(huntflow_url: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    u = (huntflow_url or "").strip()
    if not u:
        return None, None, None
    m = HUNTFLOW_URL_RE.search(u)
    if not m:
        return None, None, None
    account = m.group("account") or m.group("account2") or m.group("account3")
    applicant = m.group("applicant") or m.group("applicant2") or m.group("applicant3")
    vacancy = m.group("vacancy")
    try:
        account_id = int(account) if account and account.isdigit() else None
    except Exception:
        account_id = None
    try:
        applicant_id = int(applicant) if applicant and applicant.isdigit() else None
    except Exception:
        applicant_id = None
    try:
        vacancy_id = int(vacancy) if vacancy and vacancy.isdigit() else None
    except Exception:
        vacancy_id = None
    return account_id, applicant_id, vacancy_id


def _pick_message_status_id(api: HuntflowService, account_id: int) -> Optional[int]:
    """
    Heuristic: pick status that looks like "Message"/"Сообщение"/"Первичный контакт",
    otherwise first non-rejected status.
    """
    data = api.get_vacancy_statuses(account_id) or {}
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None

    def norm(s: Any) -> str:
        return (s or "").__str__().strip().lower()

    preferred = []
    fallback = []
    for st in items:
        if not isinstance(st, dict):
            continue
        sid = st.get("id")
        name = norm(st.get("name"))
        typ = norm(st.get("type"))
        if not sid:
            continue
        if typ in ("rejected", "rejection", "trash"):
            continue
        fallback.append(int(sid))
        if any(x in name for x in ("message", "сообщ", "первич", "контакт")):
            preferred.append(int(sid))

    return preferred[0] if preferred else (fallback[0] if fallback else None)


class HHIntegrationStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        acc = _get_user_hhru_account(request.user)
        connected = bool(acc and (acc.is_token_valid or acc.refresh_token))
        employer_id = (acc.employer_id if acc else "") or ""
        has_db_access = bool(acc and acc.is_token_valid)
        return Response(
            {"connected": connected, "employer_id": employer_id, "has_db_access": has_db_access},
            status=status.HTTP_200_OK,
        )


class HHInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        resume_url = _normalize_resume_url(payload.get("resume_url") or "")
        huntflow_url = (payload.get("huntflow_url") or "").strip()
        portal = (payload.get("portal") or "").strip() or "hh.ru"
        candidate_name = (payload.get("candidate_name") or "").strip()

        if not resume_url or not huntflow_url:
            return Response({"success": False, "message": "Нужны resume_url и huntflow_url."}, status=status.HTTP_400_BAD_REQUEST)

        acc = _get_user_hhru_account(request.user)
        token, err = _ensure_valid_access_token(acc) if acc else (None, "HH.ru не подключен.")
        if err or not token:
            return Response({"success": False, "message": err or "HH.ru не подключен."}, status=status.HTTP_400_BAD_REQUEST)

        # Find HHResponse: по resume_url, huntflow_url (applicant_id), затем по ФИО кандидата
        hh_resp = None
        qs = HHResponse.objects.filter(hh_resume_url__startswith=resume_url).order_by("-hh_updated_at")
        if qs.exists():
            hh_resp = qs.first()
        if not hh_resp:
            qs = HHResponse.objects.filter(hh_resume_url__icontains=resume_url).order_by("-hh_updated_at")
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp:
            qs = _find_hh_response_by_resume_url(resume_url)
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp and huntflow_url:
            qs = _find_hh_response_by_huntflow_url(huntflow_url)
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp and candidate_name:
            hh_resp = _find_hh_response_by_candidate_name(candidate_name, resume_url)

        hh_status = None
        if hh_resp:
            action_url = _extract_action_url(hh_resp.raw_data, "invite")
            if action_url:
                try:
                    ok = change_negotiation_action(token, action_url, message=None, send_sms=False)
                    if ok:
                        hh_status = "Приглашение отправлено"
                    else:
                        hh_status = "HH API не принял действие приглашения"
                except Exception as e:
                    hh_status = f"Ошибка HH API: {e}"
            else:
                hh_status = "Не найдено действие приглашения в HH"
        else:
            hh_status = "HH отклик не найден (HH не обновлён)"

        # Update Huntflow (best-effort, можем работать и без hh_resp)
        if hh_resp:
            hf_account_id, hf_applicant_id, hf_vacancy_id = (hh_resp.account_id, hh_resp.applicant_id, hh_resp.vacancy_id)
        else:
            hf_account_id = hf_applicant_id = hf_vacancy_id = None

        if not (hf_account_id and hf_applicant_id):
            hf_account_id, hf_applicant_id = _resolve_huntflow_url_to_account_applicant(request.user, huntflow_url)
            if hf_vacancy_id is None:
                _, __, hf_vacancy_id = _parse_huntflow_ids(huntflow_url)

        huntflow_status = None
        try:
            if hf_account_id and hf_applicant_id:
                api = HuntflowService(user=request.user)
                status_id = _pick_message_status_id(api, int(hf_account_id))
                comment = f"Invited {portal}"
                if status_id:
                    api.update_applicant_status(
                        account_id=int(hf_account_id),
                        applicant_id=int(hf_applicant_id),
                        status_id=int(status_id),
                        comment=comment,
                        vacancy_id=int(hf_vacancy_id) if hf_vacancy_id else None,
                        rejection_reason_id=None,
                    )
                    huntflow_status = "Статус обновлён"
                else:
                    # no status to set, at least comment via same method not supported without status_id
                    huntflow_status = "Статус не обновлён (не найден подходящий статус)"
        except Exception as e:
            huntflow_status = f"Ошибка обновления Huntflow: {e}"

        return Response(
            {
                "success": True,
                "hh_status": hh_status or "—",
                "huntflow_status": huntflow_status or "—",
            },
            status=status.HTTP_200_OK,
        )


class HHRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        resume_url = _normalize_resume_url(payload.get("resume_url") or "")
        huntflow_url = (payload.get("huntflow_url") or "").strip()
        portal = (payload.get("portal") or "").strip() or "hh.ru"
        status_id = payload.get("status_id")
        rejection_reason_id = payload.get("rejection_reason_id")
        comment = (payload.get("comment") or "").strip()
        candidate_name = (payload.get("candidate_name") or "").strip()

        if not resume_url or not huntflow_url:
            return Response({"success": False, "message": "Нужны resume_url и huntflow_url."}, status=status.HTTP_400_BAD_REQUEST)
        if not status_id or not rejection_reason_id:
            return Response({"success": False, "message": "Нужны status_id и rejection_reason_id."}, status=status.HTTP_400_BAD_REQUEST)

        acc = _get_user_hhru_account(request.user)
        token, err = _ensure_valid_access_token(acc) if acc else (None, "HH.ru не подключен.")
        if err or not token:
            return Response({"success": False, "message": err or "HH.ru не подключен."}, status=status.HTTP_400_BAD_REQUEST)

        # Find HHResponse: по resume_url, huntflow_url (applicant_id), затем по ФИО кандидата
        hh_resp = None
        qs = HHResponse.objects.filter(hh_resume_url__startswith=resume_url).order_by("-hh_updated_at")
        if qs.exists():
            hh_resp = qs.first()
        if not hh_resp:
            qs = HHResponse.objects.filter(hh_resume_url__icontains=resume_url).order_by("-hh_updated_at")
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp:
            qs = _find_hh_response_by_resume_url(resume_url)
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp and huntflow_url:
            qs = _find_hh_response_by_huntflow_url(huntflow_url)
            if qs.exists():
                hh_resp = qs.first()
        if not hh_resp and candidate_name:
            hh_resp = _find_hh_response_by_candidate_name(candidate_name, resume_url)

        hh_status = None
        if hh_resp:
            action_url = _extract_action_url(hh_resp.raw_data, "reject")
            if action_url:
                try:
                    ok = change_negotiation_action(token, action_url, message=comment or None, send_sms=False)
                    if ok:
                        hh_status = "Отказ отправлен"
                    else:
                        hh_status = "HH API не принял действие отказа"
                except Exception as e:
                    hh_status = f"Ошибка HH API: {e}"
            else:
                hh_status = "Не найдено действие отказа в HH"
        else:
            hh_status = "HH отклик не найден (HH не обновлён)"

        # Update Huntflow (required)
        if hh_resp:
            hf_account_id, hf_applicant_id, hf_vacancy_id = (hh_resp.account_id, hh_resp.applicant_id, hh_resp.vacancy_id)
        else:
            hf_account_id = hf_applicant_id = hf_vacancy_id = None

        if not (hf_account_id and hf_applicant_id):
            hf_account_id, hf_applicant_id = _resolve_huntflow_url_to_account_applicant(request.user, huntflow_url)
            if hf_vacancy_id is None:
                _, __, hf_vacancy_id = _parse_huntflow_ids(huntflow_url)

        if not (hf_account_id and hf_applicant_id):
            return Response(
                {"success": False, "message": "Не удалось определить кандидата Huntflow по huntflow_url."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            api = HuntflowService(user=request.user)
            api.update_applicant_status(
                account_id=int(hf_account_id),
                applicant_id=int(hf_applicant_id),
                status_id=int(status_id),
                comment=(f"{comment}\n\nRejected {portal}".strip() if comment else f"Rejected {portal}"),
                vacancy_id=int(hf_vacancy_id) if hf_vacancy_id else None,
                rejection_reason_id=int(rejection_reason_id),
            )
        except Exception as e:
            return Response({"success": False, "message": f"Ошибка обновления Huntflow: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"success": True, "hh_status": hh_status or "—", "huntflow_status": "Статус обновлён"},
            status=status.HTTP_200_OK,
        )


def _resume_ids_from_request(resume_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлекает идентификаторы резюме из URL.
    - path_id: часть пути после /resume/ (для hh.ru и rabota.by в пути).
    - query_resume_id: значение параметра resumeId из query (часто на rabota.by).
    """
    url = (resume_url or "").strip()
    if not url:
        return None, None
    path_id = None
    m = re.search(r"/resume/([^/?#]+)", url, re.IGNORECASE)
    if m:
        path_id = m.group(1)
    query_resume_id = None
    if "?" in url:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        qs = parse_qs(parsed.query or "")
        for key in ("resumeId", "resume_id"):
            vals = qs.get(key, [])
            if vals and str(vals[0]).strip():
                query_resume_id = str(vals[0]).strip()
                break
    return path_id, query_resume_id


def _find_hh_response_by_resume_url(resume_url: str):
    """Ищем HHResponse по resume_url (path_id или query resumeId). Возвращает QuerySet."""
    path_id, query_resume_id = _resume_ids_from_request(resume_url)
    if not path_id and not query_resume_id:
        return HHResponse.objects.none()

    qs = HHResponse.objects.none()
    if path_id:
        qs = HHResponse.objects.filter(hh_resume_url__icontains="/resume/{}".format(path_id))

    if not qs.exists() and query_resume_id:
        try:
            qs = HHResponse.objects.filter(raw_data__resume__id=query_resume_id)
        except Exception:
            pass
        if not qs.exists():
            try:
                qs = HHResponse.objects.filter(raw_data__resume__id=int(query_resume_id))
            except (ValueError, TypeError):
                pass
        if not qs.exists() and path_id:
            qs = HHResponse.objects.filter(raw_data__resume__alternate_url__icontains=path_id)
    return qs


def _find_hh_response_by_huntflow_url(huntflow_url: str):
    """Ищем HHResponse по applicant_id (и account_id) из ссылки Huntflow. Возвращает QuerySet."""
    _, applicant_id, _ = _parse_huntflow_ids(huntflow_url)
    if not applicant_id:
        return HHResponse.objects.none()
    return HHResponse.objects.filter(applicant_id=applicant_id).order_by("-hh_updated_at")


def _normalize_name_part(s: str) -> str:
    """Нормализация части ФИО для поиска: нижний регистр, пробелы, ё->е."""
    if not s or not isinstance(s, str):
        return ""
    return (s.strip().lower().replace("ё", "е").replace("  ", " ") or "")


def _parse_full_name(full_name: str) -> Tuple[str, str, str]:
    """Разбивает «Фамилия Имя Отчество» на (first_name, last_name, middle_name)."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[1], parts[0], ""  # имя, фамилия
    # 3+ частей: фамилия имя отчество
    return parts[1], parts[0], " ".join(parts[2:])


def _find_hh_response_by_candidate_name(
    candidate_name: str, resume_url: str
) -> Optional[HHResponse]:
    """
    Поиск HHResponse по ФИО кандидата (запасной вариант при расхождении URL).
    Уточняем по path_id из resume_url, если есть несколько совпадений.
    """
    candidate_name = (candidate_name or "").strip()
    if not candidate_name or len(candidate_name) < 2:
        return None
    first_name, last_name, middle_name = _parse_full_name(candidate_name)
    fn = _normalize_name_part(first_name)
    ln = _normalize_name_part(last_name)
    if not fn and not ln:
        return None
    from django.db.models import Q
    qs = HHResponse.objects.all().order_by("-hh_updated_at")
    if ln:
        qs = qs.filter(last_name__iexact=ln)
    if fn:
        qs = qs.filter(first_name__iexact=fn)
    if not qs.exists():
        # Мягкий поиск: содержит подстроку (на случай разного написания)
        q = Q()
        if ln:
            q &= Q(last_name__icontains=ln)
        if fn:
            q &= Q(first_name__icontains=fn)
        qs = HHResponse.objects.filter(q).order_by("-hh_updated_at")
    if not qs.exists():
        return None
    path_id, query_resume_id = _resume_ids_from_request(resume_url)
    # Если один результат — берём его
    if qs.count() == 1:
        return qs.first()
    # Несколько: уточняем по path_id или resumeId в raw_data
    for resp in qs[:20]:
        if path_id and (path_id in (resp.hh_resume_url or "")):
            return resp
        if path_id and (resp.raw_data or {}).get("resume", {}).get("alternate_url", "").find(path_id) >= 0:
            return resp
        if query_resume_id:
            rid = (resp.raw_data or {}).get("resume", {}).get("id")
            if rid is not None and str(rid).strip() == str(query_resume_id).strip():
                return resp
    return qs.first()


class HHActionsAvailabilityView(APIView):
    """
    Возвращает, можно ли показывать кнопки Invite/Reject для резюме HH.
    Логика:
    - ищем HHResponse по resume_url (по идентификатору /resume/<id> или по resumeId из query для rabota.by)
    - при неудаче — по huntflow_url (applicant_id из ссылки Huntflow)
    - читаем employer_state.id из raw_data (если есть)
    - маппим через COLLECTION_TO_FOLDER и разрешаем действия
      только для папок 'unseen' (не разобранные) и 'consider' (подумать)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.hhru.views import FOLDER_UNSEEN, FOLDER_CONSIDER

        resume_url = (request.query_params.get("resume_url") or "").strip()
        huntflow_url = (request.query_params.get("huntflow_url") or "").strip()

        if not resume_url and not huntflow_url:
            return Response(
                {"success": False, "actions_allowed": False, "reason": "resume_url or huntflow_url is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = _find_hh_response_by_resume_url(resume_url)
        if not qs.exists() and huntflow_url:
            qs = _find_hh_response_by_huntflow_url(huntflow_url)

        if not qs.exists():
            return Response(
                {"success": True, "actions_allowed": False, "reason": "hh_response_not_found"},
                status=status.HTTP_200_OK,
            )

        allowed_folders = {FOLDER_UNSEEN, FOLDER_CONSIDER}
        actions_allowed = False

        for resp in qs[:10]:
            raw = resp.raw_data or {}
            employer_state = raw.get("employer_state") or {}
            state_id = (employer_state.get("id") or "").strip()
            if not state_id:
                continue
            # Используем ту же маппу, что и страница hh-вакансий
            from apps.hhru.views import COLLECTION_TO_FOLDER

            folder = COLLECTION_TO_FOLDER.get(state_id)
            if folder in allowed_folders:
                actions_allowed = True
                break

        return Response(
            {
                "success": True,
                "actions_allowed": bool(actions_allowed),
                "reason": None if actions_allowed else "employer_state_not_unseen_or_consider",
            },
            status=status.HTTP_200_OK,
        )

