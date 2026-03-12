from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from .models import HuntflowCache, HuntflowLog, LinkedInHuntflowLink, LinkedInThreadProfile, MeetHuntflowLink, ResumeHuntflowLink, _extract_resume_id_from_url
from .serializers import (
    HuntflowCacheSerializer, HuntflowLogSerializer, HuntflowLogCreateSerializer,
    HuntflowStatsSerializer, HuntflowApiRequestSerializer
)
from logic.integration.huntflow.huntflow_api import (
    HuntflowCacheViewSet as LogicHuntflowCacheViewSet,
    HuntflowLogViewSet as LogicHuntflowLogViewSet,
    HuntflowApiRequestViewSet as LogicHuntflowApiRequestViewSet
)
from urllib.parse import urlparse, unquote
import re
import logging

logger = logging.getLogger(__name__)


class HuntflowCacheViewSet(LogicHuntflowCacheViewSet):
    """
    ViewSet для просмотра кэша Huntflow - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowCache.objects: кэш Huntflow
    - HuntflowCacheSerializer
    
    ОБРАБОТКА:
    - Наследование от LogicHuntflowCacheViewSet
    - Фильтрация по cache_key
    - Поиск по cache_key
    - Сортировка по дате обновления
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными кэша
    
    СВЯЗИ:
    - Использует: LogicHuntflowCacheViewSet, HuntflowCacheSerializer
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['cache_key']
    search_fields = ['cache_key']
    ordering_fields = ['created_at', 'updated_at', 'expires_at']
    ordering = ['-updated_at']


class HuntflowLogViewSet(LogicHuntflowLogViewSet):
    """
    ViewSet для просмотра логов Huntflow - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowLog.objects: логи Huntflow
    - HuntflowLogSerializer, HuntflowLogCreateSerializer
    
    ОБРАБОТКА:
    - Наследование от LogicHuntflowLogViewSet
    - Фильтрация по log_type, method, status_code, user
    - Поиск по endpoint, error_message
    - Сортировка по дате создания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными логов
    
    СВЯЗИ:
    - Использует: LogicHuntflowLogViewSet, HuntflowLogSerializer
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['log_type', 'method', 'status_code', 'user']
    search_fields = ['endpoint', 'error_message']
    ordering_fields = ['created_at', 'status_code']
    ordering = ['-created_at']


class HuntflowApiRequestViewSet(LogicHuntflowApiRequestViewSet):
    """
    ViewSet для выполнения API запросов к Huntflow - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    - request.data: параметры API запроса (endpoint, method, data, params, use_cache, cache_timeout)
    
    ИСТОЧНИКИ ДАННЫХ:
    - HuntflowApiRequestSerializer
    - HuntflowService для выполнения API запросов
    
    ОБРАБОТКА:
    - Наследование от LogicHuntflowApiRequestViewSet
    - Валидация параметров API запроса
    - Выполнение запросов к Huntflow API
    - Кэширование результатов
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с результатами API запросов
    
    СВЯЗИ:
    - Использует: LogicHuntflowApiRequestViewSet, HuntflowApiRequestSerializer
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    permission_classes = [permissions.IsAuthenticated]


class HHResponsesViewSet(viewsets.ViewSet):
    """
    ViewSet для работы с откликами из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (POST)
    - request.user: аутентифицированный пользователь
    - request.data: параметры импорта (account_id, vacancy_id, hh_vacancy_id, filters)
    
    ИСТОЧНИКИ ДАННЫХ:
    - HH.ru API
    - HuntflowOperations для импорта
    
    ОБРАБОТКА:
    - Получение откликов из HH.ru
    - Фильтрация по критериям
    - Импорт в Huntflow
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с результатами импорта
    
    СВЯЗИ:
    - Использует: HuntflowOperations, HH.ru API
    - Передает: DRF API responses
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='import-hh-responses')
    def import_hh_responses(self, request):
        """
        Импорт откликов из HH.ru в Huntflow
        
        POST /api/v1/huntflow/hh-responses/import-hh-responses/
        
        Входящие данные (JSON):
        {
            "account_id": 123,
            "vacancy_id": 456,
            "hh_vacancy_id": "789",
            "filters": {
                "allowed_locations": ["1", "2"],
                "allowed_genders": ["any"],
                "min_age": 18,
                "max_age": 65,
                "check_existing": true,
                "min_experience_years": 1,
                "max_experience_years": 50
            }
        }
        
        Выходящие данные:
        {
            "success": true,
            "imported": 5,
            "filtered_out": 3,
            "errors": 0,
            "imported_candidates": [...],
            "filter_results": {...}
        }
        """
        
        try:
            from logic.integration.shared.huntflow_operations import HuntflowOperations
            from logic.base.response_handler import UnifiedResponseHandler
            
            account_id = request.data.get('account_id')
            vacancy_id = request.data.get('vacancy_id')
            hh_vacancy_id = request.data.get('hh_vacancy_id')
            filters = request.data.get('filters')
            
            if not all([account_id, vacancy_id, hh_vacancy_id]):
                return Response(
                    UnifiedResponseHandler.error_response(
                        "Требуются account_id, vacancy_id и hh_vacancy_id"
                    ),
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            operations = HuntflowOperations(request.user)
            result = operations.get_and_import_hh_responses(
                account_id, vacancy_id, hh_vacancy_id, filters
            )
            
            if result.get('success'):
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(
                    UnifiedResponseHandler.error_response(result.get('message', 'Ошибка импорта')),
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def _normalize_linkedin_profile_url(raw_url: str) -> str | None:
    """
    Приводит LinkedIn URL к каноничному виду: https://www.linkedin.com/in/<slug>/
    Возвращает None, если URL не похож на ссылку профиля LinkedIn.
    """
    if not raw_url:
        return None

    raw_url = raw_url.strip()

    # Иногда прилетает без схемы
    if raw_url.startswith("www.linkedin.com/") or raw_url.startswith("linkedin.com/"):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return None

    netloc = parsed.netloc.lower()
    if not netloc.endswith("linkedin.com"):
        return None

    # Ищем /in/<slug>
    parts = [p for p in parsed.path.split("/") if p]
    if "in" not in parts:
        return None

    try:
        idx = parts.index("in")
        slug = parts[idx + 1]
    except Exception:
        return None

    if not slug:
        return None

    return f"https://www.linkedin.com/in/{slug}/"


def _update_communication_field_if_empty(api, account_id, applicant_id, linkedin_url):
    """
    Обновляет поле "Где ведется коммуникация" ссылкой на LinkedIn, если оно пустое
    
    Args:
        api: HuntflowService instance
        account_id: ID организации
        applicant_id: ID кандидата
        linkedin_url: URL профиля LinkedIn
        
    Returns:
        True если поле было обновлено, False если нет
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем схему анкеты для поиска поля "Где ведется коммуникация"
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            logger.warning(f"Cannot get questionary schema for account_id={account_id}")
            return False
        
        logger.info(f"Questionary schema received, {len(questionary_schema)} fields")
        
        # Ищем поле "Где ведется коммуникация"
        communication_field_id = None
        for field_id, field_info in questionary_schema.items():
            if isinstance(field_info, dict):
                field_title = field_info.get('title', '').lower()
                # Ищем поле по различным вариантам названия
                if ('коммуникация' in field_title or 'communication' in field_title) and \
                   ('ведется' in field_title or 'где' in field_title or 'where' in field_title or 'place' in field_title):
                    communication_field_id = field_id
                    logger.info(f"Found communication field: {field_id} - {field_info.get('title')}")
                    break
        
        # Если не нашли точное совпадение, ищем просто по слову "коммуникация"
        if not communication_field_id:
            for field_id, field_info in questionary_schema.items():
                if isinstance(field_info, dict):
                    field_title = field_info.get('title', '').lower()
                    if 'коммуникация' in field_title or 'communication' in field_title:
                        communication_field_id = field_id
                        logger.info(f"Found communication field (loose match): {field_id} - {field_info.get('title')}")
                        break
        
        if not communication_field_id:
            logger.warning(f"Communication field not found in questionary schema")
            # Логируем все поля для отладки
            logger.info(f"Available fields in schema (first 20):")
            for i, (field_id, field_info) in enumerate(list(questionary_schema.items())[:20]):
                if isinstance(field_info, dict):
                    logger.info(f"  {i+1}. {field_id}: '{field_info.get('title', '')}' (type: {field_info.get('type', '')})")
            return False
        
        # Получаем текущую анкету кандидата
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary:
            logger.warning(f"Cannot get questionary for applicant_id={applicant_id}")
            return False
        
        logger.info(f"Questionary received, {len(questionary)} fields")
        
        # Проверяем, заполнено ли поле
        current_value = questionary.get(communication_field_id)
        logger.info(f"Current value of communication field {communication_field_id}: {current_value} (type: {type(current_value)})")
        
        # Проверяем, заполнено ли поле (None, пустая строка, или только пробелы считаются пустыми)
        if current_value is not None:
            current_value_str = str(current_value).strip()
            if current_value_str:
                logger.info(f"Communication field already filled: {current_value_str}")
                return False
        
        logger.info(f"Communication field is empty, will update with: {linkedin_url}")
        
        # Используем прямой PATCH запрос через requests, как в успешном примере update_candidate_field
        import requests
        url = f"{api._get_base_url()}/v2/accounts/{account_id}/applicants/{applicant_id}/questionary"
        questionary_data = {communication_field_id: linkedin_url}
        
        logger.info(f"Updating communication field {communication_field_id} with value: {linkedin_url}")
        logger.info(f"PATCH {url} with data: {questionary_data}")
        
        # Получаем заголовки для запроса
        headers = api._get_headers()
        
        try:
            response = requests.patch(
                url,
                headers=headers,
                json=questionary_data,
                timeout=30
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text[:500]}")
            
            if response.status_code == 200:
                logger.info(f"✅ Communication field successfully updated with LinkedIn URL: {linkedin_url}")
                # Очищаем кэш кандидата
                from apps.google_oauth.cache_service import HuntflowAPICache
                HuntflowAPICache.clear_candidate(api.user.id, account_id, applicant_id)
                return True
            else:
                logger.warning(f"❌ Failed to update communication field: HTTP {response.status_code} - {response.text[:500]}")
                return False
        except Exception as e:
            logger.error(f"Error in PATCH request: {e}", exc_info=True)
            return False
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating communication field: {e}", exc_info=True)
        return False

def _get_candidate_level(api, account_id, applicant_id):
    """
    Получает значение поля "Уровень" для кандидата
    
    Args:
        api: HuntflowService instance
        account_id: ID организации
        applicant_id: ID кандидата
        
    Returns:
        Значение поля или None
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем схему анкеты для поиска поля "Уровень"
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            logger.warning(f"Cannot get questionary schema for account_id={account_id}")
            return None
        
        # Обрабатываем разные структуры схемы
        # Схема может быть словарем с ключом 'fields' или просто словарем с полями
        fields_dict = {}
        if isinstance(questionary_schema, dict):
            if 'fields' in questionary_schema:
                # Если есть ключ 'fields', это список полей
                fields_list = questionary_schema.get('fields', [])
                for field in fields_list:
                    if isinstance(field, dict):
                        field_id = field.get('id') or field.get('key')
                        if field_id:
                            fields_dict[field_id] = field
            else:
                # Если это просто словарь, где ключи - это ID полей
                fields_dict = questionary_schema
        
        if not fields_dict:
            logger.warning(f"Questionary schema is empty or has unexpected structure")
            return None
        
        # Логируем структуру схемы для отладки
        logger.info(f"Questionary schema: {len(fields_dict)} fields")
        sample_keys = list(fields_dict.keys())[:5]
        logger.info(f"Sample schema keys: {sample_keys}")
        
        # Ищем поле "Уровень"
        level_field_id = None
        # Сначала пробуем найти по точному совпадению
        for field_id, field_info in fields_dict.items():
            if isinstance(field_info, dict):
                field_title = field_info.get('title', '').lower()
                # Ищем поле по различным вариантам названия
                if 'уровень' in field_title or 'level' in field_title or 'grade' in field_title or 'грейд' in field_title:
                    level_field_id = field_id
                    logger.info(f"Found level field: {field_id} - {field_info.get('title')} (type: {field_info.get('type', 'unknown')})")
                    break
        
        # Если не нашли, пробуем найти по ключу поля (может быть string_field_*, custom_field_*)
        if not level_field_id:
            for field_id, field_info in fields_dict.items():
                if isinstance(field_info, dict):
                    field_title = field_info.get('title', '').lower()
                    field_key = str(field_id).lower()
                    # Ищем по ключу или названию
                    if 'level' in field_key or 'grade' in field_key or 'уровень' in field_key or 'грейд' in field_key:
                        level_field_id = field_id
                        logger.info(f"Found level field by key: {field_id} - {field_info.get('title')}")
                        break
        
        if not level_field_id:
            logger.warning(f"Level field not found in questionary schema. Available fields: {list(fields_dict.keys())[:10]}")
            # Логируем все названия полей для отладки
            all_titles = [f.get('title', '') for f in fields_dict.values() if isinstance(f, dict)]
            logger.info(f"Available field titles: {all_titles[:20]}")
            return None
        
        # Получаем текущую анкету кандидата
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary:
            logger.warning(f"Cannot get questionary for applicant_id={applicant_id}")
            return None
        
        # Получаем значение поля
        level_value = questionary.get(level_field_id)
        if level_value:
            # Обрабатываем разные форматы значений
            # 1. Если это объект с полем "name" (для select полей)
            if isinstance(level_value, dict):
                # Пробуем получить name, value или id
                level_value_str = level_value.get('name') or level_value.get('value') or level_value.get('id')
                if level_value_str:
                    level_value_str = str(level_value_str).strip()
                    if level_value_str:
                        logger.info(f"Level field value (from object): {level_value_str}")
                        return level_value_str
            # 2. Если это список (для множественного выбора)
            elif isinstance(level_value, list):
                if level_value:
                    # Берем первый элемент
                    first_item = level_value[0]
                    if isinstance(first_item, dict):
                        level_value_str = first_item.get('name') or first_item.get('value') or first_item.get('id')
                    else:
                        level_value_str = str(first_item)
                    if level_value_str:
                        level_value_str = str(level_value_str).strip()
                        if level_value_str:
                            logger.info(f"Level field value (from list): {level_value_str}")
                            return level_value_str
            # 3. Если это простое значение (строка, число)
            else:
                level_value_str = str(level_value).strip()
                if level_value_str:
                    logger.info(f"Level field value (direct): {level_value_str}")
                    return level_value_str
        
        return None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting level field: {e}", exc_info=True)
        return None


def _get_candidate_scorecard(api, account_id, applicant_id):
    """
    Получает значение поля "Scorecard" для кандидата
    
    Args:
        api: HuntflowService instance
        account_id: ID организации
        applicant_id: ID кандидата
        
    Returns:
        URL scorecard или None
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем схему анкеты для поиска поля "Scorecard"
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            logger.warning(f"Cannot get questionary schema for account_id={account_id}")
            return None
        
        # Обрабатываем разные структуры схемы
        fields_dict = {}
        if isinstance(questionary_schema, dict):
            if 'fields' in questionary_schema:
                fields_list = questionary_schema.get('fields', [])
                for field in fields_list:
                    if isinstance(field, dict):
                        field_id = field.get('id') or field.get('key')
                        if field_id:
                            fields_dict[field_id] = field
            else:
                fields_dict = questionary_schema
        
        if not fields_dict:
            logger.warning(f"Questionary schema is empty or has unexpected structure")
            return None
        
        # Ищем поле "Scorecard"
        scorecard_field_id = None
        for field_id, field_info in fields_dict.items():
            if isinstance(field_info, dict):
                field_title = field_info.get('title', '').lower()
                field_type = field_info.get('type', '').lower()
                # Ищем поле по названию и типу (должно быть url)
                if ('scorecard' in field_title or 'скоркард' in field_title) and field_type == 'url':
                    scorecard_field_id = field_id
                    logger.info(f"Found scorecard field: {field_id} - {field_info.get('title')} (type: {field_info.get('type')})")
                    break
        
        if not scorecard_field_id:
            logger.warning(f"Scorecard field not found in questionary schema")
            return None
        
        # Получаем текущую анкету кандидата
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary:
            logger.warning(f"Cannot get questionary for applicant_id={applicant_id}")
            return None
        
        # Получаем значение поля
        scorecard_value = questionary.get(scorecard_field_id)
        if scorecard_value:
            # Обрабатываем разные форматы значений
            if isinstance(scorecard_value, str):
                scorecard_value = scorecard_value.strip()
                if scorecard_value:
                    logger.info(f"Scorecard field value: {scorecard_value}")
                    return scorecard_value
            elif isinstance(scorecard_value, dict):
                # Если это объект, пробуем получить value или url
                scorecard_url = scorecard_value.get('value') or scorecard_value.get('url') or scorecard_value.get('name')
                if scorecard_url:
                    scorecard_url = str(scorecard_url).strip()
                    if scorecard_url:
                        logger.info(f"Scorecard field value (from object): {scorecard_url}")
                        return scorecard_url
        
        logger.info(f"Scorecard field is empty for applicant_id={applicant_id}")
        return None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting candidate scorecard: {e}", exc_info=True)
        return None


def _build_extra_fields_from_questionary(api, account_id, applicant_id):
    """
    Собирает все заполненные поля анкеты кандидата в словарь {название: значение}.
    Исключает поле «Где ведется коммуникация» (оно отдается отдельно как communication).
    """
    try:
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            return {}
        fields_dict = {}
        if isinstance(questionary_schema, dict):
            if "fields" in questionary_schema:
                for field in questionary_schema.get("fields", []) or []:
                    if isinstance(field, dict):
                        fid = field.get("id") or field.get("key")
                        if fid is not None:
                            fields_dict[fid] = field
            else:
                for fid, finfo in questionary_schema.items():
                    if isinstance(finfo, dict):
                        fields_dict[fid] = finfo
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary or not isinstance(questionary, dict):
            return {}
        # ID поля «Где ведется коммуникация» — исключаем из extra_fields
        communication_field_id = None
        for fid, finfo in fields_dict.items():
            if not isinstance(finfo, dict):
                continue
            title = (finfo.get("title") or "").lower()
            if ("коммуникация" in title or "communication" in title) and (
                "ведется" in title or "ведётся" in title or "где" in title or "where" in title
            ):
                communication_field_id = fid
                break
        if not communication_field_id:
            for fid, finfo in fields_dict.items():
                if isinstance(finfo, dict) and ("коммуникация" in (finfo.get("title") or "").lower() or "communication" in (finfo.get("title") or "").lower()):
                    communication_field_id = fid
                    break
        result = {}
        for field_id, value in questionary.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if field_id == communication_field_id:
                continue
            finfo = fields_dict.get(field_id) if isinstance(field_id, (str, int)) else None
            title = None
            if isinstance(finfo, dict):
                title = (finfo.get("title") or "").strip()
            if not title:
                title = str(field_id)
            if isinstance(value, dict):
                value = (value.get("name") or value.get("value") or value.get("id") or "").strip() or str(value)
            else:
                value = str(value).strip()
            if value:
                result[title] = value
        return result
    except Exception as e:
        logger.debug("_build_extra_fields_from_questionary: %s", e)
        return {}


def _get_questionary_value_by_title_keywords(api, account_id, applicant_id, keywords):
    """
    Ищет в анкете поле по ключевым словам в названии и возвращает значение.
    keywords: список строк для поиска в title (например ["telegram"] или ["офис", "готовность"]).
    """
    try:
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            return None
        fields_dict = {}
        if isinstance(questionary_schema, dict):
            if 'fields' in questionary_schema:
                for field in questionary_schema.get('fields', []) or []:
                    if isinstance(field, dict):
                        fid = field.get('id') or field.get('key')
                        if fid is not None:
                            fields_dict[fid] = field
            else:
                for fid, finfo in questionary_schema.items():
                    if isinstance(finfo, dict):
                        fields_dict[fid] = finfo
        field_id = None
        keywords_lower = [k.lower() for k in keywords]
        for fid, finfo in fields_dict.items():
            if not isinstance(finfo, dict):
                continue
            title = (finfo.get('title') or '').lower()
            if any(kw in title for kw in keywords_lower):
                field_id = fid
                break
        if not field_id:
            return None
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary:
            return None
        val = questionary.get(field_id)
        if val is None:
            return None
        if isinstance(val, dict):
            return (val.get('name') or val.get('value') or val.get('id') or '').strip() or None
        return str(val).strip() or None
    except Exception as e:
        logger.debug("_get_questionary_value_by_title_keywords: %s", e)
        return None


def _normalize_url_for_compare(url: str) -> str:
    """Нормализует URL для сравнения (убирает trailing slash, схему, lowercase)."""
    if not url:
        return ""
    u = str(url).strip().lower()
    if u.startswith("https://"):
        u = u[8:]
    elif u.startswith("http://"):
        u = u[7:]
    u = u.rstrip("/")
    return u


def _detect_link_type_from_url(url: str) -> str:
    """Определяет тип соцсети по URL (viber://, t.me, wa.me и т.д.)."""
    if not url:
        return "communication"
    u = (url or "").lower()
    if "viber://" in u or "viber.me" in u or "viber.chat" in u:
        return "viber"
    if "t.me" in u or "telegram.me" in u or "telegram.dog" in u:
        return "telegram"
    if "wa.me" in u or "whatsapp.com" in u or "api.whatsapp.com" in u:
        return "whatsapp"
    if "linkedin.com" in u or "linked.in" in u:
        return "linkedin"
    return "communication"


def _extract_username_from_url(url: str, link_type: str) -> str | None:
    """Извлекает никнейм/идентификатор из URL для копирования."""
    if not url or not link_type:
        return None
    u = (url or "").strip()
    if link_type == "telegram":
        m = re.search(r"(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)", u, re.I)
        if m:
            return m.group(1)
        m = re.search(r"@([a-zA-Z0-9_]{5,32})", u)
        if m:
            return m.group(1)
    if link_type == "viber":
        m = re.search(r"viber://chat\?number=%2B?(\d+)", u, re.I)
        if m:
            return "+" + m.group(1)
        m = re.search(r"viber\.me/(\+?\d+)", u, re.I)
        if m:
            return m.group(1)
    if link_type == "whatsapp":
        m = re.search(r"wa\.me/(\+?\d+)", u, re.I)
        if m:
            return m.group(1)
    if link_type == "linkedin":
        m = re.search(r"linkedin\.com/in/([a-zA-Z0-9_-]+)", u, re.I)
        if m:
            return m.group(1)
    return None


def _get_communication_field_value(api, account_id, applicant_id):
    """
    Получает значение поля "Где ведется коммуникация" для кандидата
    
    Args:
        api: HuntflowService instance
        account_id: ID организации
        applicant_id: ID кандидата
        
    Returns:
        Значение поля или None
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем схему анкеты для поиска поля "Где ведется коммуникация"
        questionary_schema = api.get_applicant_questionary_schema(account_id)
        if not questionary_schema:
            logger.warning(f"Cannot get questionary schema for account_id={account_id}")
            return None
        
        # Ищем поле "Где ведется коммуникация"
        communication_field_id = None
        for field_id, field_info in questionary_schema.items():
            if isinstance(field_info, dict):
                field_title = field_info.get('title', '').lower()
                # Ищем поле по различным вариантам названия
                if ('коммуникация' in field_title or 'communication' in field_title) and \
                   ('ведется' in field_title or 'где' in field_title or 'where' in field_title or 'place' in field_title):
                    communication_field_id = field_id
                    logger.info(f"Found communication field: {field_id} - {field_info.get('title')}")
                    break
        
        # Если не нашли точное совпадение, ищем просто по слову "коммуникация"
        if not communication_field_id:
            for field_id, field_info in questionary_schema.items():
                if isinstance(field_info, dict):
                    field_title = field_info.get('title', '').lower()
                    if 'коммуникация' in field_title or 'communication' in field_title:
                        communication_field_id = field_id
                        logger.info(f"Found communication field (loose match): {field_id} - {field_info.get('title')}")
                        break
        
        if not communication_field_id:
            logger.warning(f"Communication field not found in questionary schema")
            return None
        
        # Получаем текущую анкету кандидата
        questionary = api.get_applicant_questionary(account_id, applicant_id)
        if not questionary:
            logger.warning(f"Cannot get questionary for applicant_id={applicant_id}")
            return None
        
        # Получаем значение поля
        communication_value = questionary.get(communication_field_id)
        if communication_value:
            communication_value_str = str(communication_value).strip()
            if communication_value_str:
                logger.info(f"Communication field value: {communication_value_str}")
                return communication_value_str
        
        return None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting communication field: {e}", exc_info=True)
        return None

class LinkedInApplicantsViewSet(viewsets.ViewSet):
    """
    API под Chrome-расширение:
    - Проверка, есть ли кандидат в Huntflow по LinkedIn URL
    
    ВАЖНО: создание/сохранение из расширения отключено. Расширение ориентируется
    только на связи, сохранённые в нашей БД (LinkedInHuntflowLink).
    """

    permission_classes = [permissions.IsAuthenticated]

    def _build_app_url(self, request, account_id: int, applicant_id: int) -> str:
        # Веб-интерфейс приложения hrhelper (не Huntflow ATS)
        return request.build_absolute_uri(f"/huntflow/accounts/{account_id}/applicants/{applicant_id}/")

    def _get_link(self, request, linkedin_url: str) -> LinkedInHuntflowLink | None:
        return LinkedInHuntflowLink.objects.filter(linkedin_url=linkedin_url).first()

    def _normalize_target_url(self, request, raw_url: str) -> str | None:
        if not raw_url:
            return None
        u = unquote(str(raw_url).strip())
        if u.startswith("/"):
            return request.build_absolute_uri(u)
        # если вставили без схемы
        if u.startswith("www.") or u.startswith("localhost") or u.startswith("127.0.0.1"):
            u = "http://" + u
        parsed = urlparse(u)
        if not parsed.scheme or not parsed.netloc:
            return None
        return u
    
    def _extract_huntflow_ids(self, url: str) -> dict:
        """
        Извлекает account_name и applicant_id из Huntflow URL.
        
        Поддерживаемые форматы:
        - https://huntflow.ru/my/softnetix#/applicants/filter/all/79149055
        - https://huntflow.ru/my/softnetix#/vacancy/3936868/filter/workon/id/79149055
        
        Возвращает: {"account_name": "softnetix", "applicant_id": 79149055, "vacancy_id": 3936868 или None}
        """
        result = {"account_name": None, "applicant_id": None, "vacancy_id": None}
        if not url:
            return result
        url = unquote(str(url))
        # Формат 1a: /my/{account}#/applicants/filter/all/id/{applicant_id}
        m1a = re.search(r'/my/([^/#]+)#/applicants/filter/[^/]+/id/(\d+)', url)
        if m1a:
            result["account_name"] = m1a.group(1)
            result["applicant_id"] = int(m1a.group(2))
            return result
        # Формат 1b: /my/{account}#/applicants/filter/all/{applicant_id}
        m1 = re.search(r'/my/([^/#]+)#/applicants/filter/[^/]+/(\d+)', url)
        if m1:
            result["account_name"] = m1.group(1)
            result["applicant_id"] = int(m1.group(2))
            return result

        # Формат 2: /my/{account}#/vacancy/{vacancy_id}/filter/{status}/id/{applicant_id}
        m2 = re.search(r'/my/([^/#]+)#/vacancy/(\d+)/filter/[^/]+/id/(\d+)', url)
        if m2:
            result["account_name"] = m2.group(1)
            result["vacancy_id"] = int(m2.group(2))
            result["applicant_id"] = int(m2.group(3))
            return result
        
        if "huntflow" in url.lower() and "/my/" in url:
            logger.debug("Huntflow URL not matched by regex (missing fragment?): %s", url[:120])
        return result

    def _get_vacancy_with_latest_activity(self, applicant_data) -> tuple:
        """
        Возвращает (vacancy_id, status_id) для вакансии с последней активностью.
        Использует vacancy_statuses, отсортированные по полю changed (последняя активность).
        При отсутствии vacancy_statuses — fallback на links[0].
        """
        def _vacancy_id(v):
            if v is None:
                return None
            if isinstance(v, dict):
                return v.get("id")
            return int(v) if v is not None else None

        def _status_id(v):
            if v is None:
                return None
            if isinstance(v, dict):
                return v.get("id")
            return int(v) if v is not None else None

        vacancies = applicant_data.get("vacancy_statuses", []) or []
        if vacancies:
            sorted_v = sorted(vacancies, key=lambda x: x.get("changed", ""), reverse=True)
            latest = sorted_v[0]
            vid = _vacancy_id(latest.get("vacancy"))
            sid = _status_id(latest.get("status"))
            if vid:
                return (vid, sid)

        links = applicant_data.get("links", []) or []
        if links:
            vac = links[0].get("vacancy")
            st = links[0].get("status")
            vid = _vacancy_id(vac)
            sid = _status_id(st)
            if vid:
                return (vid, sid)

        return (None, None)

    def _resolve_huntflow_url_to_ids(self, request, huntflow_url: str):
        """
        По huntflow_url возвращает account_id, applicant_id, vacancy_id и нормализованный app_url.
        Используется для страниц резюме (rabota.by, hh.ru), где нет linkedin_url.
        Возвращает dict или None при ошибке.
        """
        if not huntflow_url or not huntflow_url.strip():
            return None
        raw = (huntflow_url or "").strip()
        target_url = self._normalize_target_url(request, raw)
        if not target_url:
            return None
        ids = self._extract_huntflow_ids(target_url)
        if not ids.get("account_name") or not ids.get("applicant_id"):
            return None
        from apps.huntflow.services import HuntflowService
        api = HuntflowService(user=request.user)
        accounts = api.get_accounts()
        account_id = None
        if accounts and "items" in accounts:
            aname = (ids.get("account_name") or "").lower()
            for acc in accounts["items"]:
                if ((acc.get("name") or "").lower() == aname or
                        (acc.get("nick") or "").lower() == aname):
                    account_id = acc.get("id")
                    break
        if not account_id:
            return None
        applicant_id = ids["applicant_id"]
        vacancy_id = ids.get("vacancy_id")
        if not vacancy_id:
            applicant_data = api.get_applicant(account_id, applicant_id)
            if applicant_data:
                vacancy_id, _ = self._get_vacancy_with_latest_activity(applicant_data)
        app_url, _, _ = self._normalize_huntflow_url_to_vacancy_format(
            target_url, user=request.user
        )
        return {
            "account_id": account_id,
            "applicant_id": applicant_id,
            "vacancy_id": vacancy_id,
            "app_url": app_url or target_url,
        }
    
    def _normalize_huntflow_url_to_vacancy_format(self, url: str, user=None):
        """
        Приводит ссылку Huntflow к формату с вакансией.
        
        Вход: https://huntflow.ru/my/softnetix#/applicants/filter/all/80312638
        Выход: (https://huntflow.ru/my/softnetix#/vacancy/3936534/filter/workon/id/80312638, account_id, vacancy_id)
        
        Если URL уже в формате vacancy/.../id/..., возвращается (url, None, None).
        Если не удалось определить вакансию, возвращается (исходный_url, None, None).
        """
        ids = self._extract_huntflow_ids(url)
        if ids.get("vacancy_id"):
            return (url, None, None)
        if not ids.get("account_name") or not ids.get("applicant_id"):
            return (url, None, None)
        api_user = user or getattr(self, "request", None) and self.request.user
        if not api_user:
            return (url, None, None)
        try:
            account_id, vacancy_id = self._get_latest_vacancy_for_applicant(
                ids["account_name"], ids["applicant_id"], user=api_user
            )
            if vacancy_id:
                normalized = (
                    f"https://huntflow.ru/my/{ids['account_name']}#/"
                    f"vacancy/{vacancy_id}/filter/workon/id/{ids['applicant_id']}"
                )
                logger.info("Huntflow URL normalized to vacancy format: %s -> %s", url[:80], normalized[:80])
                return (normalized, account_id, vacancy_id)
        except Exception as e:
            logger.warning("Could not normalize Huntflow URL to vacancy format: %s", e)
        return (url, None, None)
    
    def _get_latest_vacancy_for_applicant(self, account_name: str, applicant_id: int, user=None) -> tuple[int | None, int | None]:
        """
        Получает ID вакансии кандидата с последней активностью через Huntflow API.
        
        Логика: vacancy_statuses сортируются по полю changed (последняя активность).
        При отсутствии vacancy_statuses — fallback на links[0].
        
        Возвращает: (account_id, vacancy_id) или (None, None)
        """
        try:
            from apps.huntflow.services import HuntflowService
            
            logger.info(f"Getting vacancy for account={account_name}, applicant={applicant_id}")
            
            # Используем переданного пользователя или self.request.user
            api_user = user or self.request.user
            api = HuntflowService(user=api_user)
            
            # Получаем account_id по имени
            accounts_response = api.get_accounts()
            
            # Проверяем формат ответа (может быть dict с 'items' или list)
            if isinstance(accounts_response, dict) and 'items' in accounts_response:
                accounts = accounts_response['items']
            elif isinstance(accounts_response, list):
                accounts = accounts_response
            else:
                logger.warning(f"Unexpected accounts response format: {type(accounts_response)}")
                return (None, None)
            
            logger.info(f"Found {len(accounts)} accounts")
            
            # Ищем аккаунт (сравниваем по name и nick, игнорируя регистр)
            account = None
            for a in accounts:
                if (a.get('name', '').lower() == account_name.lower() or 
                    a.get('nick', '').lower() == account_name.lower()):
                    account = a
                    break
            
            if not account:
                logger.warning(f"Account '{account_name}' not found")
                return (None, None)
            
            account_id = account['id']
            logger.info(f"Account ID: {account_id}")
            
            # Получаем статусы кандидата по всем вакансиям
            applicant_data = api.get_applicant(account_id, applicant_id)
            if not applicant_data:
                logger.warning(f"Applicant {applicant_id} not found in Huntflow (404).")
                return (None, None)
            
            vacancy_id, _ = self._get_vacancy_with_latest_activity(applicant_data)
            if vacancy_id:
                logger.info(f"Vacancy with latest activity: {vacancy_id}")
                return (account_id, vacancy_id)
            
        except Exception as e:
            # Логируем ошибку, но не падаем
            logger.error(f"Error getting vacancy for applicant {applicant_id}: {e}", exc_info=True)
            return (None, None)

    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/status/?linkedin_url=... или ?huntflow_url=...
        Параметры:
        - linkedin_url: URL профиля LinkedIn (приоритет для LinkedIn)
        - huntflow_url: URL кандидата в Huntflow (для страниц резюме rabota.by / hh.ru)
        - force_refresh: если true, инвалидирует кэш кандидата в Huntflow
        """
        try:
            force_refresh = request.query_params.get("force_refresh", "").lower() == "true"
            huntflow_url_param = (request.query_params.get("huntflow_url") or "").strip()

            # Ветка по huntflow_url (страницы резюме): без linkedin_url
            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = resolved["account_id"]
                applicant_id = resolved["applicant_id"]
                vacancy_id = resolved.get("vacancy_id")
                app_url = resolved["app_url"]
                if force_refresh:
                    from apps.google_oauth.cache_service import HuntflowAPICache
                    HuntflowAPICache.clear_candidate(request.user.id, account_id, applicant_id)
                from apps.huntflow.services import HuntflowService
                api = HuntflowService(user=request.user)
                applicant_data = api.get_applicant(account_id, applicant_id)
                if not applicant_data:
                    return Response(
                        {"success": False, "message": "Кандидат не найден в Huntflow."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                vacancy_name = None
                status_name = None
                status_id = None
                # Вакансия с последней активностью (при нескольких — та, по которой была последняя активность)
                vid, sid = self._get_vacancy_with_latest_activity(applicant_data)
                if vid:
                    vacancy_id = vid
                    status_id = sid
                    # app_url должен указывать на вакансию с последней активностью
                    ids = self._extract_huntflow_ids(huntflow_url_param)
                    if ids.get("account_name") and ids.get("applicant_id"):
                        app_url = (
                            f"https://huntflow.ru/my/{ids['account_name']}#/"
                            f"vacancy/{vid}/filter/workon/id/{ids['applicant_id']}"
                        )
                links = applicant_data.get("links", []) or []
                # rejection_reason — из link, соответствующего выбранной вакансии
                def _link_vacancy_id(link):
                    v = link.get("vacancy")
                    return v.get("id", v) if isinstance(v, dict) else v

                link_for_vacancy = next((l for l in links if _link_vacancy_id(l) == vacancy_id), links[0] if links else None)
                if vacancy_id and account_id:
                    try:
                        vacancy_data = api.get_vacancy(account_id, vacancy_id)
                        if vacancy_data:
                            vacancy_name = vacancy_data.get("position")
                    except Exception:
                        pass
                if status_id and account_id:
                    try:
                        statuses_data = api.get_vacancy_statuses(account_id)
                        if statuses_data and statuses_data.get("items"):
                            for s in statuses_data["items"]:
                                if s.get("id") == status_id:
                                    status_name = s.get("name")
                                    break
                    except Exception:
                        pass
                last_comment_datetime = None
                try:
                    logs_data = api.get_applicant_logs(account_id, applicant_id)
                    if logs_data and isinstance(logs_data.get("items"), list):
                        for log in reversed(logs_data["items"]):
                            comment = (log.get("comment") or log.get("comment_text") or "").strip()
                            if comment and re.search(r"\d{1,2}\s+[а-я]+\s*⋅\s*\d{1,2}:\d{2}–\d{1,2}:\d{2}", comment, re.I):
                                last_comment_datetime = comment
                                break
                except Exception:
                    pass
                rejection_reason_id = None
                rejection_reason_name = None
                if link_for_vacancy:
                    rr = link_for_vacancy.get("rejection_reason")
                    if rr is not None:
                        rejection_reason_id = int(rr.get("id", rr)) if isinstance(rr, dict) else int(rr)
                        rejection_reason_name = rr.get("name") if isinstance(rr, dict) else None
                return Response(
                    {
                        "success": True,
                        "exists": True,
                        "linkedin_url": None,
                        "huntflow_url": app_url,
                        "account_id": account_id,
                        "applicant_id": applicant_id,
                        "app_url": app_url,
                        "vacancy_name": vacancy_name,
                        "status_name": status_name,
                        "status_id": int(status_id) if status_id is not None else None,
                        "rejection_reason_id": rejection_reason_id,
                        "rejection_reason_name": rejection_reason_name,
                        "last_comment_datetime": last_comment_datetime,
                    },
                    status=status.HTTP_200_OK,
                )

            raw_url = request.query_params.get("linkedin_url") or request.query_params.get("url") or ""
            linkedin_url = _normalize_linkedin_profile_url(raw_url)
            if not linkedin_url:
                return Response(
                    {"success": False, "message": "Нужен корректный LinkedIn URL профиля (/in/<slug>/)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            link = self._get_link(request, linkedin_url)
            if not link:
                # Кандидат не найден в БД — показываем инпут
                return Response(
                    {"success": True, "exists": False, "linkedin_url": linkedin_url},
                    status=status.HTTP_200_OK,
                )

            if link.target_url:
                app_url = link.target_url
            elif link.account_id is not None and link.applicant_id is not None:
                app_url = self._build_app_url(request, int(link.account_id), int(link.applicant_id))
            else:
                app_url = None

            # Всегда отдаём ссылку в формате с вакансией (vacancy/.../id/...)
            if app_url:
                app_url = self._normalize_huntflow_url_to_vacancy_format(app_url, user=request.user)[0]

            # Получаем название вакансии из ссылки или через applicant_id
            vacancy_name = None
            vacancy_id = None
            account_id = None
            status_name = None
            status_id = None
            
            # Сначала пробуем извлечь vacancy_id из target_url или app_url
            url_to_check = link.target_url or app_url
            if url_to_check:
                huntflow_ids = self._extract_huntflow_ids(url_to_check)
                if huntflow_ids.get('vacancy_id'):
                    vacancy_id = huntflow_ids['vacancy_id']
                    # Если есть account_name, получаем account_id
                    if huntflow_ids.get('account_name'):
                        try:
                            from apps.huntflow.services import HuntflowService
                            api = HuntflowService(user=request.user)
                            accounts_response = api.get_accounts()
                            if isinstance(accounts_response, dict) and 'items' in accounts_response:
                                accounts = accounts_response['items']
                            elif isinstance(accounts_response, list):
                                accounts = accounts_response
                            else:
                                accounts = []
                            
                            for a in accounts:
                                if (a.get('name', '').lower() == huntflow_ids['account_name'].lower() or 
                                    a.get('nick', '').lower() == huntflow_ids['account_name'].lower()):
                                    account_id = a.get('id')
                                    break
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Error getting account_id from account_name: {e}")
                    # Если account_id уже есть в link, используем его
                    elif link.account_id is not None:
                        account_id = int(link.account_id)
            
            # Если vacancy_id не найден в ссылке, но есть сохраненный vacancy_id в связи
            if not vacancy_id and link.vacancy_id is not None:
                vacancy_id = int(link.vacancy_id)
                account_id = int(link.account_id) if link.account_id is not None else account_id
                logger.info(f"Using saved vacancy_id from link: {vacancy_id}")
            
            # Если vacancy_id или status_id еще не найдены, но есть account_id и applicant_id, получаем через applicant_data
            if (not vacancy_id or not status_id) and link.account_id is not None and link.applicant_id is not None:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    from apps.huntflow.services import HuntflowService
                    from apps.google_oauth.cache_service import HuntflowAPICache
                    api = HuntflowService(user=request.user)
                    
                    account_id = int(link.account_id)
                    applicant_id = int(link.applicant_id)
                    
                    # Если требуется принудительное обновление, очищаем кэш кандидата
                    if force_refresh:
                        logger.info(f"Force refresh requested, clearing cache for applicant_id={applicant_id}")
                        HuntflowAPICache.clear_candidate(request.user.id, account_id, applicant_id)
                    
                    logger.info(f"Getting vacancy name for account_id={account_id}, applicant_id={applicant_id}")
                    
                    # Получаем данные кандидата
                    applicant_data = api.get_applicant(account_id, applicant_id)
                    if applicant_data:
                        # Вакансия с последней активностью (при нескольких — та, по которой была последняя активность)
                        vid, sid = self._get_vacancy_with_latest_activity(applicant_data)
                        if vid:
                            vacancy_id = vid
                            status_id = sid
                            logger.info(f"Vacancy with latest activity: {vacancy_id}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error getting vacancy_id from applicant: {e}", exc_info=True)

            if status_id is not None and isinstance(status_id, dict):
                status_id = status_id.get('id')

            last_comment_datetime = None
            if account_id is None and link.account_id is not None:
                account_id = int(link.account_id)
            if account_id is not None and link.applicant_id is not None:
                try:
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    logs_data = api.get_applicant_logs(account_id, int(link.applicant_id))
                    if logs_data and isinstance(logs_data.get('items'), list):
                        for log in reversed(logs_data['items']):
                            comment = (log.get('comment') or log.get('comment_text') or '').strip()
                            if not comment:
                                continue
                            if re.search(r'\d{1,2}\s+[а-я]+\s*⋅\s*\d{1,2}:\d{2}–\d{1,2}:\d{2}', comment, re.I):
                                last_comment_datetime = comment
                                break
                except Exception as e:
                    logger.debug("Error getting last comment: %s", e)
            
            # Если нашли vacancy_id, получаем название вакансии
            if vacancy_id and account_id:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    
                    logger.info(f"Getting vacancy name for vacancy_id={vacancy_id}, account_id={account_id}")
                    vacancy_data = api.get_vacancy(account_id, vacancy_id)
                    if vacancy_data:
                        vacancy_name = vacancy_data.get('position')
                        logger.info(f"Vacancy name: {vacancy_name}")
                    else:
                        logger.warning(f"Vacancy data not found for vacancy_id={vacancy_id}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error getting vacancy name: {e}", exc_info=True)
            
            # Если нашли status_id, получаем название статуса
            # Убеждаемся, что account_id определен (используем из link, если не был получен ранее)
            if status_id:
                # Если account_id еще не определен, но есть в link, используем его
                if not account_id and link.account_id is not None:
                    account_id = int(link.account_id)
                
                if account_id:
                    try:
                        import logging
                        logger = logging.getLogger(__name__)
                        from apps.huntflow.services import HuntflowService
                        api = HuntflowService(user=request.user)
                        
                        logger.info(f"Getting status name for status_id={status_id}, account_id={account_id}")
                        statuses_data = api.get_vacancy_statuses(account_id)
                        if statuses_data:
                            # Ищем статус по ID
                            statuses_list = statuses_data.get('items', [])
                            if isinstance(statuses_list, list):
                                for status_item in statuses_list:
                                    if status_item.get('id') == status_id:
                                        status_name = status_item.get('name')
                                        logger.info(f"Status name: {status_name}")
                                        break
                            else:
                                logger.warning(f"Statuses list is not a list: {type(statuses_list)}")
                        else:
                            logger.warning(f"Statuses data is None for account_id={account_id}")
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error getting status name: {e}", exc_info=True)
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Cannot get status name: status_id={status_id} but account_id is None")

            rejection_reason_id = None
            rejection_reason_name = None
            if account_id is not None and link.applicant_id is not None:
                try:
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    applicant_data = api.get_applicant(account_id, int(link.applicant_id))
                    if applicant_data:
                        links = applicant_data.get('links', []) or []
                        link_for_vacancy = next(
                            (l for l in links if (l.get('vacancy') or {}).get('id') == vacancy_id or l.get('vacancy') == vacancy_id),
                            links[0] if links else None,
                        )
                        if link_for_vacancy:
                            rr = link_for_vacancy.get('rejection_reason')
                            if rr is not None:
                                rejection_reason_id = int(rr.get('id', rr)) if isinstance(rr, dict) else int(rr)
                                rejection_reason_name = rr.get('name') if isinstance(rr, dict) else None
                except Exception as e:
                    logger.debug("Error getting rejection_reason: %s", e)

            return Response(
                {
                    "success": True,
                    "exists": True,
                    "linkedin_url": linkedin_url,
                    "account_id": int(link.account_id) if link.account_id is not None else None,
                    "applicant_id": int(link.applicant_id) if link.applicant_id is not None else None,
                    "app_url": app_url,
                    "vacancy_name": vacancy_name,
                    "status_name": status_name,
                    "status_id": int(status_id) if status_id is not None else None,
                    "rejection_reason_id": rejection_reason_id,
                    "rejection_reason_name": rejection_reason_name,
                    "last_comment_datetime": last_comment_datetime,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="status-multi")
    def status_multi(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/status-multi/?linkedin_url=... или ?huntflow_url=...
        Возвращает все вакансии кандидата (для поддержки множественных вакансий).
        """
        try:
            from datetime import datetime
            from apps.huntflow.services import HuntflowService
            from apps.google_oauth.cache_service import HuntflowAPICache

            force_refresh = request.query_params.get("force_refresh", "").lower() == "true"
            huntflow_url_param = (request.query_params.get("huntflow_url") or "").strip()

            def _vacancy_id(v):
                if v is None:
                    return None
                return v.get("id") if isinstance(v, dict) else (int(v) if v is not None else None)

            def _status_id(v):
                if v is None:
                    return None
                return v.get("id") if isinstance(v, dict) else (int(v) if v is not None else None)

            account_id = None
            applicant_id = None
            account_name = None
            linkedin_url = None

            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = int(resolved["account_id"])
                applicant_id = int(resolved["applicant_id"])
                ids = self._extract_huntflow_ids(huntflow_url_param)
                account_name = ids.get("account_name")
            else:
                raw_url = request.query_params.get("linkedin_url") or request.query_params.get("url") or ""
                linkedin_url = _normalize_linkedin_profile_url(raw_url)
                if not linkedin_url:
                    return Response(
                        {"success": False, "message": "Нужен корректный LinkedIn URL профиля (/in/<slug>/) или huntflow_url."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                link = self._get_link(request, linkedin_url)
                if not link or not link.account_id or not link.applicant_id:
                    return Response(
                        {"success": True, "applicant_id": None, "applicant_name": "", "default_vacancy_id": None, "items": []},
                        status=status.HTTP_200_OK,
                    )
                account_id = int(link.account_id)
                applicant_id = int(link.applicant_id)
                accounts_resp = HuntflowService(user=request.user).get_accounts()
                for acc in (accounts_resp.get("items") or []):
                    if acc.get("id") == account_id:
                        account_name = acc.get("nick") or acc.get("name")
                        break

            if not account_id or not applicant_id:
                return Response(
                    {"success": True, "applicant_id": None, "applicant_name": "", "default_vacancy_id": None, "items": []},
                    status=status.HTTP_200_OK,
                )

            if force_refresh:
                HuntflowAPICache.clear_candidate(request.user.id, account_id, applicant_id)

            api = HuntflowService(user=request.user)
            applicant_data = api.get_applicant(account_id, applicant_id)
            if not applicant_data:
                return Response(
                    {"success": False, "message": "Кандидат не найден в Huntflow."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            applicant_name = f"{applicant_data.get('first_name', '')} {applicant_data.get('last_name', '')}".strip()
            links = applicant_data.get("links", []) or []
            statuses_data = api.get_vacancy_statuses(account_id)
            statuses_map = {}
            if statuses_data and statuses_data.get("items"):
                for s in statuses_data["items"]:
                    statuses_map[s["id"]] = s

            rejection_reasons_data = api.get_rejection_reasons(account_id)
            rejection_reasons_map = {}
            if rejection_reasons_data:
                items_rr = (
                    rejection_reasons_data.get("items")
                    or rejection_reasons_data.get("rejection_reasons")
                    or (rejection_reasons_data if isinstance(rejection_reasons_data, list) else [])
                )
                for r in items_rr:
                    rid = r.get("id") if isinstance(r, dict) else r
                    if rid is not None:
                        try:
                            rid_int = int(rid)
                            name = r.get("name", "") if isinstance(r, dict) else ""
                            rejection_reasons_map[rid_int] = name
                        except (TypeError, ValueError):
                            pass

            if not account_name:
                accounts_resp = api.get_accounts()
                for acc in (accounts_resp.get("items") or []):
                    if acc.get("id") == account_id:
                        account_name = acc.get("nick") or acc.get("name", "")
                        break
            account_name = account_name or ""

            logs_data = api.get_applicant_logs(account_id, applicant_id)
            logs_items = (logs_data.get("items") or []) if logs_data else []

            items = []
            default_vacancy_id = None
            max_change_ts = None

            for link_item in links:
                vid = _vacancy_id(link_item.get("vacancy"))
                sid = _status_id(link_item.get("status"))
                if not vid:
                    continue

                vacancy_data = api.get_vacancy(account_id, vid)
                vacancy_name = vacancy_data.get("position", "N/A") if vacancy_data else "N/A"
                status_obj = statuses_map.get(sid, {}) if sid else {}
                status_name = status_obj.get("name", "N/A")
                status_type_raw = (status_obj.get("type") or "").lower()

                last_change_at = link_item.get("changed") or link_item.get("created") or ""
                last_comment_at = None

                status_type = "in_progress"
                if status_type_raw in ("reject", "trash"):
                    status_type = "rejected"
                elif status_type_raw == "hired":
                    status_type = "hired"
                elif vacancy_data and (vacancy_data.get("state") or "").upper() == "CLOSED":
                    status_type = "archived"

                is_hired = status_type_raw == "hired"
                is_archived = (vacancy_data or {}).get("state", "").upper() == "CLOSED"

                rr = link_item.get("rejection_reason")
                rejection_reason_id = rr.get("id") if isinstance(rr, dict) else (int(rr) if rr else None)
                rejection_reason_name = rr.get("name") if isinstance(rr, dict) else None
                if rejection_reason_id and not rejection_reason_name and rejection_reasons_map:
                    try:
                        rid_int = int(rejection_reason_id)
                        rejection_reason_name = rejection_reasons_map.get(rid_int) or None
                    except (TypeError, ValueError):
                        pass

                appurl = f"https://huntflow.ru/my/{account_name}#/vacancy/{vid}/filter/workon/id/{applicant_id}"
                link_id = link_item.get("id")
                if link_id:
                    appurl += f"#{link_id}"

                vacancy_comments = []
                for log in logs_items:
                    if _vacancy_id(log.get("vacancy")) != vid:
                        continue
                    comment_text = (log.get("comment") or log.get("comment_text") or "").strip()
                    log_type = log.get("type") or ""
                    # Для STATUS: если нет текста, формируем из статуса с датой
                    if log_type == "STATUS" and not comment_text:
                        sid_log = _status_id(log.get("status"))
                        status_obj_log = statuses_map.get(sid_log, {}) if sid_log else {}
                        status_name_log = status_obj_log.get("name", "N/A")
                        comment_text = f"Статус изменён на: {status_name_log}"
                    if not comment_text:
                        continue
                    if comment_text.startswith("Изменение статуса:"):
                        comment_text = comment_text.replace("Изменение статуса:", "").strip()
                    account_info = log.get("account_info") or {}
                    author = (account_info.get("name") or account_info.get("email") or "").strip() or None
                    vacancy_comments.append({
                        "text": comment_text,
                        "created": log.get("created") or "",
                        "author": author,
                    })
                vacancy_comments.sort(key=lambda c: c["created"] or "", reverse=True)
                vacancy_comments = vacancy_comments[:5]

                item = {
                    "vacancy_id": vid,
                    "vacancy_name": vacancy_name,
                    "status_id": sid,
                    "status_name": status_name,
                    "status_type": status_type,
                    "rejection_reason_id": rejection_reason_id,
                    "rejection_reason_name": rejection_reason_name,
                    "last_change_at": last_change_at,
                    "last_comment_at": last_comment_at,
                    "is_hired": is_hired,
                    "is_archived": is_archived,
                    "appurl": appurl,
                    "comments": vacancy_comments,
                }
                items.append(item)

                if not is_hired and not is_archived and status_type != "rejected":
                    try:
                        change_ts = datetime.fromisoformat(last_change_at.replace("Z", "+00:00")) if last_change_at else None
                        if change_ts and (max_change_ts is None or change_ts > max_change_ts):
                            max_change_ts = change_ts
                            default_vacancy_id = vid
                    except Exception:
                        if default_vacancy_id is None:
                            default_vacancy_id = vid

            if default_vacancy_id is None and items:
                default_vacancy_id = items[0]["vacancy_id"]

            return Response(
                {
                    "success": True,
                    "applicant_id": applicant_id,
                    "applicant_name": applicant_name,
                    "default_vacancy_id": default_vacancy_id,
                    "items": items,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error("Error in status_multi: %s", e, exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="available-vacancies")
    def available_vacancies(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/available-vacancies/?linkedin_url=... или ?huntflow_url=...
        Возвращает открытые вакансии, на которые кандидат ещё не добавлен.
        """
        try:
            from apps.huntflow.services import HuntflowService

            huntflow_url_param = (request.query_params.get("huntflow_url") or "").strip()
            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = int(resolved["account_id"])
                applicant_id = int(resolved["applicant_id"])
            else:
                raw_url = request.query_params.get("linkedin_url") or request.query_params.get("url") or ""
                linkedin_url = _normalize_linkedin_profile_url(raw_url)
                if not linkedin_url:
                    return Response(
                        {"success": False, "message": "Нужен linkedin_url или huntflow_url."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                link = self._get_link(request, linkedin_url)
                if not link or not link.account_id:
                    return Response(
                        {"success": False, "message": "Кандидат не найден или не привязан к организации."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                account_id = int(link.account_id)
                applicant_id = int(link.applicant_id) if link.applicant_id else None

            api = HuntflowService(user=request.user)
            existing_vacancy_ids = set()

            if applicant_id:
                applicant_data = api.get_applicant(account_id, applicant_id)
                if applicant_data:
                    for link_item in applicant_data.get("links", []) or []:
                        v = link_item.get("vacancy")
                        vid = v.get("id") if isinstance(v, dict) else (int(v) if v else None)
                        if vid:
                            existing_vacancy_ids.add(vid)

            vacancies_resp = api.get_vacancies(account_id, state="OPEN")
            all_vacancies = vacancies_resp.get("items", []) if isinstance(vacancies_resp, dict) else []
            if isinstance(vacancies_resp, list):
                all_vacancies = vacancies_resp

            available = [
                {"vacancy_id": v["id"], "vacancy_name": v.get("position", ""), "state": v.get("state", "OPEN")}
                for v in all_vacancies
                if isinstance(v, dict) and v.get("id") not in existing_vacancy_ids
            ]

            return Response({"success": True, "items": available}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("Error in available_vacancies: %s", e, exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="add-to-vacancy")
    def add_to_vacancy(self, request):
        """
        POST /api/v1/huntflow/linkedin-applicants/add-to-vacancy/
        Body: { "linkedin_url": "..." или "huntflow_url": "...", "vacancy_id": 123 }
        Добавляет кандидата на вакансию.
        """
        try:
            from apps.huntflow.services import HuntflowService
            from apps.google_oauth.cache_service import HuntflowAPICache

            data = request.data or {}
            huntflow_url_param = (data.get("huntflow_url") or "").strip()
            vacancy_id = data.get("vacancy_id")

            if not vacancy_id:
                return Response(
                    {"success": False, "message": "Нужен vacancy_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = int(resolved["account_id"])
                applicant_id = int(resolved["applicant_id"])
            else:
                raw_li = data.get("linkedin_url") or ""
                linkedin_url = _normalize_linkedin_profile_url(raw_li)
                if not linkedin_url:
                    return Response(
                        {"success": False, "message": "Нужен linkedin_url или huntflow_url."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                link = self._get_link(request, linkedin_url)
                if not link or not link.account_id or not link.applicant_id:
                    return Response(
                        {"success": False, "message": "Кандидат не найден или не привязан к организации."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                account_id = int(link.account_id)
                applicant_id = int(link.applicant_id)

            vacancy_id = int(vacancy_id)

            api = HuntflowService(user=request.user)
            ok = api.add_applicant_to_vacancy(account_id, applicant_id, vacancy_id)

            if ok:
                HuntflowAPICache.clear_candidate(request.user.id, account_id, applicant_id)
                return Response(
                    {"success": True, "vacancy_id": vacancy_id, "applicant_id": applicant_id},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"success": False, "message": "Не удалось добавить кандидата на вакансию."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            logger.error("Error in add_to_vacancy: %s", e, exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="set-link")
    def set_link(self, request):
        """
        POST /api/v1/huntflow/linkedin-applicants/set-link/
        Body: { "linkedin_url": "...", "target_url": "..." }
        Сохраняет связку LinkedIn -> URL кандидата в Huntflow/HRHelper в нашей БД.
        
        Поддерживаемые форматы target_url (Huntflow):
        - С вакансией: https://huntflow.ru/my/softnetix#/vacancy/3936534/filter/workon/id/80312638
        - Без вакансии: https://huntflow.ru/my/softnetix#/applicants/filter/all/80312638
          → бэкенд определяет вакансию по кандидату (последняя «в работе») и сохраняет/возвращает
            ссылку в формате с вакансией (vacancy/.../id/...).
        """
        try:
            raw_li = (request.data or {}).get("linkedin_url") or ""
            linkedin_url = _normalize_linkedin_profile_url(raw_li)
            if not linkedin_url:
                return Response(
                    {"success": False, "message": "Нужен корректный LinkedIn URL профиля (/in/<slug>/)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            raw_target = (request.data or {}).get("target_url") or (request.data or {}).get("huntflow_url") or ""
            # Фрагмент после # в HTTP не передаётся — расширение может прислать его отдельно
            raw_fragment = (request.data or {}).get("target_url_fragment") or (request.data or {}).get("target_url_hash") or ""
            if raw_fragment and "#" not in raw_target:
                raw_target = raw_target.rstrip("/") + "#/" + str(raw_fragment).strip().lstrip("#/")
            target_url = self._normalize_target_url(request, raw_target)
            if not target_url:
                return Response(
                    {"success": False, "message": "Нужна корректная ссылка на кандидата (полный URL или относительный /huntflow/... )."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Пытаемся извлечь данные из Huntflow URL
            huntflow_ids = self._extract_huntflow_ids(target_url)
            
            account_id = None
            applicant_id = None
            vacancy_id = None
            final_url = target_url
            
            # Если это Huntflow URL формата /applicants/filter/all/ID — приводим к формату с вакансией
            if huntflow_ids["applicant_id"]:
                applicant_id = huntflow_ids["applicant_id"]
                vacancy_id = huntflow_ids.get("vacancy_id")
                
                if huntflow_ids["account_name"] and not vacancy_id:
                    # Формат https://huntflow.ru/my/softnetix#/applicants/filter/all/80312638
                    # → определяем вакансию и приводим к https://huntflow.ru/my/softnetix#/vacancy/3936534/filter/workon/id/80312638
                    final_url, norm_account_id, norm_vacancy_id = self._normalize_huntflow_url_to_vacancy_format(
                        target_url, user=request.user
                    )
                    if norm_account_id is not None:
                        account_id = norm_account_id
                    if norm_vacancy_id is not None:
                        vacancy_id = norm_vacancy_id
                elif huntflow_ids["account_name"]:
                    # Если vacancy_id уже есть в URL, получаем account_id
                    try:
                        from apps.huntflow.services import HuntflowService
                        api = HuntflowService(user=request.user)
                        accounts_response = api.get_accounts()
                        if isinstance(accounts_response, dict) and 'items' in accounts_response:
                            accounts = accounts_response['items']
                        elif isinstance(accounts_response, list):
                            accounts = accounts_response
                        else:
                            accounts = []
                        
                        for a in accounts:
                            if (a.get('name', '').lower() == huntflow_ids['account_name'].lower() or 
                                a.get('nick', '').lower() == huntflow_ids['account_name'].lower()):
                                account_id = a.get('id')
                                break
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error getting account_id from account_name: {e}")
            else:
                # Извлекаем account/applicant из URL нашего веб-интерфейса (если это не Huntflow)
                m = re.search(r"/huntflow/accounts/(?P<acc>\d+)/applicants/(?P<app>\d+)/", target_url)
                if m:
                    account_id = int(m.group("acc"))
                    applicant_id = int(m.group("app"))

            # Если vacancy_id не определен, но есть account_id и applicant_id, пытаемся получить его
            if not vacancy_id and account_id and applicant_id:
                try:
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    applicant_data = api.get_applicant(account_id, applicant_id)
                    if applicant_data:
                        # Сначала пробуем получить vacancy_id из links (для новых вакансий)
                        links = applicant_data.get('links', [])
                        if links and len(links) > 0:
                            vacancy_id_from_links = links[0].get('vacancy')
                            if vacancy_id_from_links:
                                vacancy_id = vacancy_id_from_links
                        # Если не нашли в links, ищем в vacancy_statuses
                        if not vacancy_id:
                            vacancies = applicant_data.get('vacancy_statuses', [])
                            if vacancies:
                                vacancies_in_work = [
                                    v for v in vacancies 
                                    if v.get('status', {}).get('type') == 'workon'
                                ]
                                if vacancies_in_work:
                                    latest = sorted(
                                        vacancies_in_work, 
                                        key=lambda x: x.get('changed', ''),
                                        reverse=True
                                    )[0]
                                    vacancy_id = latest.get('vacancy')
                                else:
                                    latest = sorted(
                                        vacancies, 
                                        key=lambda x: x.get('changed', ''),
                                        reverse=True
                                    )[0]
                                    vacancy_id = latest.get('vacancy')
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error getting vacancy_id when saving link: {e}")
            
            # Формируем defaults для сохранения
            defaults = {
                "target_url": final_url,
                "account_id": account_id,
                "applicant_id": applicant_id,
            }
            # Добавляем vacancy_id только если он определен
            if vacancy_id is not None:
                defaults["vacancy_id"] = vacancy_id
            
            defaults["updated_by_id"] = request.user.id
            try:
                obj, created = LinkedInHuntflowLink.objects.update_or_create(
                    linkedin_url=linkedin_url,
                    defaults=defaults,
                )
                if created:
                    obj.created_by_id = request.user.id
                    obj.save(update_fields=["created_by_id"])
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error saving LinkedInHuntflowLink: {e}", exc_info=True)
                # Пробуем сохранить без vacancy_id, если была ошибка
                if "vacancy_id" in defaults:
                    del defaults["vacancy_id"]
                    obj, created = LinkedInHuntflowLink.objects.update_or_create(
                        linkedin_url=linkedin_url,
                        defaults=defaults,
                    )
                    if created:
                        obj.created_by_id = request.user.id
                        obj.save(update_fields=["created_by_id"])
                else:
                    raise

            # Получаем название вакансии для ответа
            vacancy_name = None
            status_name = None
            if obj.vacancy_id and obj.account_id:
                try:
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    vacancy_data = api.get_vacancy(int(obj.account_id), int(obj.vacancy_id))
                    if vacancy_data:
                        vacancy_name = vacancy_data.get('position')
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error getting vacancy name in set_link: {e}")
            
            # Получаем статус кандидата для ответа
            if obj.account_id and obj.applicant_id:
                try:
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    applicant_data = api.get_applicant(int(obj.account_id), int(obj.applicant_id))
                    if applicant_data:
                        # Получаем статус ID из links
                        links = applicant_data.get('links', [])
                        status_id = None
                        if links and len(links) > 0:
                            status_id = links[0].get('status')
                        
                        # Если не нашли в links, ищем в vacancy_statuses
                        if not status_id:
                            vacancies = applicant_data.get('vacancy_statuses', [])
                            if vacancies:
                                # Сортируем по дате изменения статуса (последняя = самая свежая)
                                vacancies_in_work = [
                                    v for v in vacancies 
                                    if v.get('status', {}).get('type') == 'workon'
                                ]
                                
                                if vacancies_in_work:
                                    latest = sorted(
                                        vacancies_in_work, 
                                        key=lambda x: x.get('changed', ''),
                                        reverse=True
                                    )[0]
                                    status_obj = latest.get('status', {})
                                    if isinstance(status_obj, dict):
                                        status_id = status_obj.get('id')
                                    elif status_obj:
                                        status_id = status_obj
                                else:
                                    latest = sorted(
                                        vacancies, 
                                        key=lambda x: x.get('changed', ''),
                                        reverse=True
                                    )[0]
                                    status_obj = latest.get('status', {})
                                    if isinstance(status_obj, dict):
                                        status_id = status_obj.get('id')
                                    elif status_obj:
                                        status_id = status_obj
                        
                        # Получаем название статуса
                        if status_id:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f"Getting status name for status_id={status_id}, account_id={obj.account_id}")
                            statuses_data = api.get_vacancy_statuses(int(obj.account_id))
                            if statuses_data:
                                statuses_list = statuses_data.get('items', [])
                                if isinstance(statuses_list, list):
                                    for status_item in statuses_list:
                                        if status_item.get('id') == status_id:
                                            status_name = status_item.get('name')
                                            logger.info(f"Status name found: {status_name}")
                                            break
                                    if not status_name:
                                        logger.warning(f"Status with id={status_id} not found in statuses list")
                                else:
                                    logger.warning(f"Statuses list is not a list: {type(statuses_list)}")
                            else:
                                logger.warning(f"Statuses data is None for account_id={obj.account_id}")
                        else:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Status ID is None, cannot get status name")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error getting status name in set_link: {e}", exc_info=True)
            
            app_url = obj.target_url or (
                self._build_app_url(request, int(obj.account_id), int(obj.applicant_id))
                if obj.account_id is not None and obj.applicant_id is not None
                else None
            )
            
            # Обновляем поле "Где ведется коммуникация", если оно пустое
            # Это работает и при первом сохранении, и при редактировании существующей ссылки
            # Используем account_id и applicant_id из обновленного объекта (могут быть из новой ссылки)
            final_account_id = obj.account_id
            final_applicant_id = obj.applicant_id
            
            # Если account_id и applicant_id не были сохранены в obj, но были извлечены из новой ссылки, используем их
            if not final_account_id and account_id:
                final_account_id = account_id
            if not final_applicant_id and applicant_id:
                final_applicant_id = applicant_id
            
            if final_account_id and final_applicant_id:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Checking communication field for account_id={final_account_id}, applicant_id={final_applicant_id}, linkedin_url={linkedin_url}")
                    from apps.huntflow.services import HuntflowService
                    api = HuntflowService(user=request.user)
                    _update_communication_field_if_empty(
                        api, 
                        int(final_account_id), 
                        int(final_applicant_id), 
                        linkedin_url
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error updating communication field in set_link: {e}", exc_info=True)
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Cannot update communication field: account_id={final_account_id}, applicant_id={final_applicant_id}")
            
            return Response(
                {
                    "success": True,
                    "exists": True,
                    "linkedin_url": linkedin_url,
                    "target_url": obj.target_url,
                    "account_id": obj.account_id,
                    "applicant_id": obj.applicant_id,
                    "vacancy_id": obj.vacancy_id,
                    "app_url": app_url,
                    "vacancy_name": vacancy_name,
                    "status_name": status_name,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="status-options")
    def status_options(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/status-options/?linkedin_url=... или ?huntflow_url=...
        Возвращает список доступных статусов и причин отказа для кандидата
        """
        try:
            link = None
            huntflow_url_param = (request.query_params.get("huntflow_url") or "").strip()
            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = int(resolved["account_id"])
            else:
                account_id = None

            if not account_id:
                raw_url = request.query_params.get("linkedin_url") or request.query_params.get("url") or ""
                linkedin_url = _normalize_linkedin_profile_url(raw_url)
                if not linkedin_url:
                    return Response(
                        {"success": False, "message": "Нужен корректный LinkedIn URL профиля (/in/<slug>/) или huntflow_url."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                link = self._get_link(request, linkedin_url)
                if not link or not link.account_id:
                    return Response(
                        {"success": False, "message": "Кандидат не найден или не привязан к организации."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                account_id = int(link.account_id)

            if account_id is None:
                return Response(
                    {"success": False, "message": "Кандидат не найден или не привязан к организации."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)

            # Получаем список статусов
            statuses_data = api.get_vacancy_statuses(account_id)
            statuses = []
            if statuses_data and 'items' in statuses_data:
                statuses = statuses_data['items']

            # Получаем список причин отказа
            rejection_reasons_data = api.get_rejection_reasons(account_id)
            rejection_reasons = []
            if rejection_reasons_data:
                if 'items' in rejection_reasons_data:
                    rejection_reasons = rejection_reasons_data['items']
                elif isinstance(rejection_reasons_data, list):
                    rejection_reasons = rejection_reasons_data
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Status options: {len(statuses)} statuses, {len(rejection_reasons)} rejection reasons")

            return Response(
                {
                    "success": True,
                    "statuses": statuses,
                    "rejection_reasons": rejection_reasons,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting status options: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="update-status")
    def update_status(self, request):
        """
        POST /api/v1/huntflow/linkedin-applicants/update-status/
        Body: { "linkedin_url": "..." или "huntflow_url": "...", "status_id": 123, "rejection_reason_id": 456 (опционально), "comment": "..." (опционально) }
        Обновляет статус кандидата
        """
        try:
            data = request.data or {}
            status_id = data.get("status_id")
            if not status_id:
                return Response(
                    {"success": False, "message": "Нужен status_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rejection_reason_id = data.get("rejection_reason_id")
            comment = data.get("comment", "")
            # vacancy_id из запроса — для множественных вакансий
            vacancy_id_from_request = data.get("vacancy_id")

            linkedin_url = None
            huntflow_url_param = (data.get("huntflow_url") or "").strip()
            if huntflow_url_param:
                resolved = self._resolve_huntflow_url_to_ids(request, huntflow_url_param)
                if not resolved:
                    return Response(
                        {"success": False, "message": "Некорректная ссылка Huntflow или организация не найдена."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                account_id = int(resolved["account_id"])
                applicant_id = int(resolved["applicant_id"])
                vacancy_id = int(vacancy_id_from_request) if vacancy_id_from_request else resolved.get("vacancy_id")
            else:
                raw_li = data.get("linkedin_url") or ""
                linkedin_url = _normalize_linkedin_profile_url(raw_li)
                if not linkedin_url:
                    return Response(
                        {"success": False, "message": "Нужен корректный LinkedIn URL профиля (/in/<slug>/) или huntflow_url."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                link = self._get_link(request, linkedin_url)
                if not link or not link.account_id or not link.applicant_id:
                    return Response(
                        {"success": False, "message": "Кандидат не найден или не привязан к организации."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                account_id = int(link.account_id)
                applicant_id = int(link.applicant_id)
                # vacancy_id: приоритет — из запроса, иначе из link
                vacancy_id = int(vacancy_id_from_request) if vacancy_id_from_request else (int(link.vacancy_id) if link.vacancy_id else None)

            from apps.huntflow.services import HuntflowService
            from apps.google_oauth.cache_service import HuntflowAPICache
            api = HuntflowService(user=request.user)
            final_comment = comment if comment else None

            result = api.update_applicant_status(
                account_id=account_id,
                applicant_id=applicant_id,
                status_id=int(status_id),
                comment=final_comment,
                vacancy_id=vacancy_id,
                rejection_reason_id=int(rejection_reason_id) if rejection_reason_id else None
            )

            if result:
                # Очищаем кэш кандидата
                HuntflowAPICache.clear_candidate(request.user.id, account_id, applicant_id)
                
                # Обновляем поле "Где ведется коммуникация" (только для LinkedIn)
                if linkedin_url:
                    try:
                        _update_communication_field_if_empty(
                            api, account_id, applicant_id, linkedin_url
                        )
                    except Exception as e:
                        logger.warning("Error updating communication field in update_status: %s", e)
                
                return Response(
                    {
                        "success": True,
                        "message": "Статус успешно обновлен",
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"success": False, "message": "Не удалось обновить статус"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating status: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="communication-link")
    def get_communication_link(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/communication-link/?huntflow_url=...
        
        Получает ссылку на Telegram или LinkedIn из поля "Где ведется коммуникация"
        для кандидата по ссылке на Huntflow.
        
        Параметры:
        - huntflow_url: URL на Huntflow в формате:
          https://huntflow.ru/my/softnetix#/vacancy/3936868/filter/workon/id/79149055
        
        Возвращает:
        {
            "success": true,
            "communication_link": "https://t.me/username" или "https://www.linkedin.com/in/username/",
            "link_type": "telegram" или "linkedin"
        }
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            huntflow_url = request.query_params.get("huntflow_url", "").strip()
            if not huntflow_url:
                return Response(
                    {"success": False, "message": "Нужен параметр huntflow_url"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Извлекаем данные из URL
            ids = self._extract_huntflow_ids(huntflow_url)
            if not ids.get("account_name") or not ids.get("applicant_id"):
                return Response(
                    {"success": False, "message": "Не удалось извлечь данные из URL Huntflow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            account_name = ids["account_name"]
            applicant_id = ids["applicant_id"]
            
            # Получаем account_id по account_name
            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)
            accounts = api.get_accounts()
            
            account_id = None
            if accounts and 'items' in accounts:
                account_name_lower = account_name.lower()
                for account in accounts['items']:
                    # Проверяем name, nick и id (без учета регистра)
                    account_name_field = (account.get('name') or '').lower()
                    account_nick_field = (account.get('nick') or '').lower()
                    account_id_str = str(account.get('id') or '')
                    
                    if (account_name_field == account_name_lower or 
                        account_nick_field == account_name_lower or
                        account_id_str == account_name):
                        account_id = account.get('id')
                        break
            
            if not account_id:
                logger.warning(f"Account '{account_name}' not found. Available accounts: {[a.get('name') for a in (accounts.get('items', []) if accounts else [])]}")
                return Response(
                    {"success": False, "message": f"Организация '{account_name}' не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Получаем значение поля "Где ведется коммуникация"
            communication_value = _get_communication_field_value(api, account_id, applicant_id)
            
            if not communication_value:
                return Response(
                    {"success": False, "message": "Поле 'Где ведется коммуникация' не заполнено"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Определяем тип ссылки (telegram, linkedin, whatsapp, viber)
            link_type = _detect_link_type_from_url(communication_value)
            if link_type == "communication":
                # Дополнительно по ключевым словам (если в поле текст "WhatsApp: +375..." без URL)
                communication_value_lower = communication_value.lower()
                if "whatsapp" in communication_value_lower or "wa.me" in communication_value_lower:
                    link_type = "whatsapp"
                elif "viber" in communication_value_lower or "viber.me" in communication_value_lower or "viber://" in communication_value_lower:
                    link_type = "viber"
                else:
                    link_type = "unknown"
            
            return Response(
                {
                    "success": True,
                    "communication_link": communication_value,
                    "link_type": link_type,
                },
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting communication link: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="by-meet")
    def get_by_meet(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/by-meet/?meet_url=... или ?meet_code=...

        Возвращает данные кандидата по ссылке/коду Google Meet для расширения на meet.google.com:
        scorecard_link, communication_link, huntflow_url, candidate_name, level и т.д.
        """
        try:
            meet_url = request.query_params.get("meet_url", "").strip()
            meet_code = request.query_params.get("meet_code", "").strip()
            if meet_url:
                match = re.search(r"meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})", meet_url, re.I)
                if match:
                    meet_code = match.group(1).lower()
            meet_code = meet_code.lower().strip() if meet_code else None
            if not meet_code:
                return Response(
                    {"success": False, "message": "Нужен параметр meet_url или meet_code"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            link = MeetHuntflowLink.objects.filter(meet_code=meet_code).first()
            if not link:
                return Response(
                    {"success": False, "message": "Связка для этой встречи не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            communication_link = None
            communication_label = "Контакт"
            if link.account_id and link.applicant_id:
                from apps.huntflow.services import HuntflowService
                api = HuntflowService(user=request.user)
                comm = _get_communication_field_value(api, link.account_id, link.applicant_id)
                if comm:
                    communication_link = comm
                    comm_lower = (comm or "").lower()
                    if "t.me" in comm_lower or "telegram" in comm_lower:
                        communication_label = "Telegram"
                    elif "linkedin" in comm_lower:
                        communication_label = "LinkedIn"
            return Response(
                {
                    "success": True,
                    "scorecard_link": link.scorecard_url or None,
                    "communication_link": communication_link,
                    "communication_label": communication_label,
                    "huntflow_url": link.huntflow_candidate_url or None,
                    "candidate_name": link.candidate_name or None,
                    "vacancy_title": link.vacancy_title or None,
                    "level": link.candidate_grade or None,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error get_by_meet: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="candidate-level")
    def get_candidate_level(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/candidate-level/?huntflow_url=...
        
        Получает уровень кандидата из поля "Уровень" для кандидата по ссылке на Huntflow.
        
        Параметры:
        - huntflow_url: URL на Huntflow в формате:
          https://huntflow.ru/my/softnetix#/vacancy/3936868/filter/workon/id/79149055
        
        Возвращает:
        {
            "success": true,
            "level": "Middle" или другое значение уровня
        }
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            huntflow_url = request.query_params.get("huntflow_url", "").strip()
            if not huntflow_url:
                return Response(
                    {"success": False, "message": "Нужен параметр huntflow_url"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Извлекаем данные из URL
            ids = self._extract_huntflow_ids(huntflow_url)
            if not ids.get("account_name") or not ids.get("applicant_id"):
                return Response(
                    {"success": False, "message": "Не удалось извлечь данные из URL Huntflow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            account_name = ids["account_name"]
            applicant_id = ids["applicant_id"]
            vacancy_id = ids.get("vacancy_id")
            
            # Получаем account_id по account_name
            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)
            accounts = api.get_accounts()
            
            account_id = None
            if accounts and 'items' in accounts:
                account_name_lower = account_name.lower()
                for account in accounts['items']:
                    account_name_field = (account.get('name') or '').lower()
                    account_nick_field = (account.get('nick') or '').lower()
                    account_id_str = str(account.get('id') or '')
                    if (account_name_field == account_name_lower or
                        account_nick_field == account_name_lower or
                        account_id_str == account_name):
                        account_id = account.get('id')
                        break
            
            if not account_id:
                logger.warning(f"Account '{account_name}' not found.")
                return Response(
                    {"success": False, "message": f"Организация '{account_name}' не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            if not vacancy_id:
                try:
                    _aid, vacancy_id = self._get_latest_vacancy_for_applicant(
                        account_name, applicant_id, user=request.user
                    )
                    if _aid is not None:
                        account_id = _aid
                except Exception as e:
                    logger.warning(f"Could not get vacancy for applicant {applicant_id}: {e}")
            
            # Получаем уровень кандидата
            level_value = _get_candidate_level(api, account_id, applicant_id)
            if not level_value:
                return Response(
                    {"success": False, "message": "Поле 'Уровень' не заполнено"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Вакансия: название из apps.vacancies (external_id) или Huntflow
            vacancy_name = None
            if vacancy_id:
                from apps.vacancies.models import Vacancy
                v = Vacancy.objects.filter(external_id=str(vacancy_id)).first()
                if v:
                    vacancy_name = v.name
                else:
                    vh = api.get_vacancy(account_id, vacancy_id)
                    if vh:
                        vacancy_name = (vh.get("position") or "").strip() or f"Вакансия {vacancy_id}"
            
            return Response(
                {
                    "success": True,
                    "level": level_value,
                    "vacancy_name": vacancy_name or "",
                },
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting candidate level: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    @action(detail=False, methods=["get"], url_path="scorecard-link")
    def get_scorecard_link(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/scorecard-link/?huntflow_url=...
        
        Получает ссылку на Scorecard из соответствующего поля в Huntflow
        для кандидата по ссылке на Huntflow.
        
        Параметры:
        - huntflow_url: URL на Huntflow в формате:
          https://huntflow.ru/my/softnetix#/vacancy/3936868/filter/workon/id/79149055
        
        Возвращает:
        {
            "success": true,
            "scorecard_link": "https://docs.google.com/spreadsheets/..."
        }
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            huntflow_url = request.query_params.get("huntflow_url", "").strip()
            if not huntflow_url:
                return Response(
                    {"success": False, "message": "Нужен параметр huntflow_url"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Извлекаем данные из URL
            ids = self._extract_huntflow_ids(huntflow_url)
            if not ids.get("account_name") or not ids.get("applicant_id"):
                return Response(
                    {"success": False, "message": "Не удалось извлечь данные из URL Huntflow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            account_name = ids["account_name"]
            applicant_id = ids["applicant_id"]
            
            # Получаем account_id по account_name
            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)
            accounts = api.get_accounts()
            
            account_id = None
            if accounts and 'items' in accounts:
                account_name_lower = account_name.lower()
                for account in accounts['items']:
                    account_name_field = (account.get('name') or '').lower()
                    account_nick_field = (account.get('nick') or '').lower()
                    account_id_str = str(account.get('id') or '')
                    
                    if (account_name_field == account_name_lower or 
                        account_nick_field == account_name_lower or
                        account_id_str == account_name):
                        account_id = account.get('id')
                        break
            
            if not account_id:
                logger.warning(f"Account '{account_name}' not found")
                return Response(
                    {"success": False, "message": f"Организация '{account_name}' не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Получаем значение поля "Scorecard"
            scorecard_value = _get_candidate_scorecard(api, account_id, applicant_id)
            
            if not scorecard_value:
                return Response(
                    {"success": False, "message": "Поле 'Scorecard' не заполнено"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            return Response(
                {
                    "success": True,
                    "scorecard_link": scorecard_value,
                },
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting scorecard link: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    @action(detail=False, methods=["get"], url_path="level-text")
    def get_level_text(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/level-text/?vacancy_name=...&level=...
        
        Получает сохраненный текст для пары (вакансия, уровень) из LevelText.
        Используется расширением на Google Meet для кнопки грейда.
        
        Параметры:
        - vacancy_name: Название вакансии (из apps.vacancies или Huntflow)
        - level: Грейд/уровень (например: "Junior", "Middle", "Senior")
        
        Возвращает: { "success": true, "text": "..." }
        """
        try:
            from .models import LevelText
            from urllib.parse import unquote
            
            vacancy_name = request.query_params.get("vacancy_name", "").strip()
            vacancy_name = unquote(vacancy_name) if vacancy_name else ""
            level = request.query_params.get("level", "").strip()
            if not level:
                return Response(
                    {"success": False, "message": "Нужен параметр level"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not vacancy_name:
                return Response(
                    {"success": True, "text": ""},
                    status=status.HTTP_200_OK,
                )
            
            try:
                lt = LevelText.objects.get(
                    vacancy_name=vacancy_name,
                    level=level,
                )
                return Response(
                    {"success": True, "text": lt.text or ""},
                    status=status.HTTP_200_OK,
                )
            except LevelText.DoesNotExist:
                return Response(
                    {"success": True, "text": ""},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            logger.error(f"Error getting level text: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="candidate-info")
    def get_candidate_info(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/candidate-info/?huntflow_url=...

        Возвращает данные кандидата по ссылке Huntflow для отображения на rabota.by / hh.ru:
        ФИО, Телефон, Email, Telegram, где ведется коммуникация, готовность к офису, уровень, статус.
        """
        try:
            huntflow_url = request.query_params.get("huntflow_url", "").strip()
            if not huntflow_url:
                return Response(
                    {"success": False, "message": "Нужен параметр huntflow_url"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ids = self._extract_huntflow_ids(huntflow_url)
            if not ids.get("account_name") or not ids.get("applicant_id"):
                return Response(
                    {"success": False, "message": "Не удалось извлечь данные из URL Huntflow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)
            accounts = api.get_accounts()
            account_id = None
            if accounts and "items" in accounts:
                aname = ids["account_name"].lower()
                for acc in accounts["items"]:
                    if (acc.get("name") or "").lower() == aname or (acc.get("nick") or "").lower() == aname:
                        account_id = acc.get("id")
                        break
            if not account_id:
                return Response(
                    {"success": False, "message": f"Организация '{ids['account_name']}' не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            applicant_id = ids["applicant_id"]
            applicant_data = api.get_applicant(account_id, applicant_id)
            if not applicant_data:
                return Response(
                    {"success": False, "message": "Кандидат не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            last_name = (applicant_data.get("last_name") or "").strip()
            first_name = (applicant_data.get("first_name") or "").strip()
            middle_name = (applicant_data.get("middle_name") or "").strip()
            full_name = " ".join(filter(None, [last_name, first_name, middle_name])).strip() or None
            phone = (applicant_data.get("phone") or "").strip() or None
            email = (applicant_data.get("email") or "").strip() or None
            level = _get_candidate_level(api, account_id, applicant_id)
            communication = _get_communication_field_value(api, account_id, applicant_id)
            telegram = _get_questionary_value_by_title_keywords(
                api, account_id, applicant_id, ["telegram", "телеграм"]
            )
            office_readiness = _get_questionary_value_by_title_keywords(
                api, account_id, applicant_id, ["офис", "готовность", "office"]
            )
            extra_fields = _build_extra_fields_from_questionary(api, account_id, applicant_id)
            # Метки: из ответа get_applicant приходит поле "tags" — массив вида [{"tag": id}, ...]
            # В ответе get_tags Huntflow возвращает color (часто hex без #, например "30b25b") — нормализуем в #hex для UI
            def _tag_color_to_hex(tag_obj):
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
                s = (raw or "").strip()
                if not s:
                    return None
                if s.startswith("#"):
                    return s if len(s) in (4, 7) else "#" + s[-6:].lower()
                if len(s) in (3, 6) and all(c in "0123456789aAbBcCdDeEfF" for c in s):
                    return "#" + s.lower()
                return s

            labels = []
            applicant_tags = applicant_data.get("tags") or []
            if applicant_tags:
                tags_data = api.get_tags(account_id)
                tags_by_id = {}
                if tags_data and tags_data.get("items"):
                    for t in tags_data["items"]:
                        tid = t.get("id")
                        if tid is not None:
                            name = (t.get("name") or "").strip() or f"Метка {tid}"
                            label_obj = {"id": tid, "name": name}
                            color = _tag_color_to_hex(t)
                            if color:
                                label_obj["color"] = color
                            tags_by_id[tid] = label_obj
                for tag_item in applicant_tags:
                    tag_id = tag_item.get("tag") if isinstance(tag_item, dict) else tag_item
                    if tag_id is not None:
                        labels.append(tags_by_id.get(tag_id) or {"id": tag_id, "name": f"Метка {tag_id}"})
            status_name = None
            vacancy_id_for_name, status_id = self._get_vacancy_with_latest_activity(applicant_data)
            if status_id is not None:
                statuses_data = api.get_vacancy_statuses(account_id)
                if statuses_data and statuses_data.get("items"):
                    for s in statuses_data["items"]:
                        if s.get("id") == status_id:
                            status_name = s.get("name")
                            break
            vacancy_name = None
            if vacancy_id_for_name:
                try:
                    v_data = api.get_vacancy(account_id, vacancy_id_for_name)
                    if v_data:
                        vacancy_name = v_data.get("position")
                except Exception:
                    pass
            return Response(
                {
                    "success": True,
                    "full_name": full_name,
                    "vacancy_name": vacancy_name,
                    "phone": phone,
                    "email": email,
                    "telegram": telegram,
                    "communication": communication,
                    "office_readiness": office_readiness,
                    "level": level,
                    "status_name": status_name,
                    "labels": labels,
                    "extra_fields": extra_fields,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("Error getting candidate info")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="candidate-links")
    def get_candidate_links(self, request):
        """
        GET /api/v1/huntflow/linkedin-applicants/candidate-links/?huntflow_url=...

        Возвращает все внешние ссылки кандидата для отображения кнопок на странице Huntflow:
        linkedin_url, resume_url, communication (Telegram и т.д.).
        """
        try:
            huntflow_url = (request.query_params.get("huntflow_url") or "").strip()
            if not huntflow_url:
                return Response(
                    {"success": False, "message": "Нужен параметр huntflow_url"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ids = self._extract_huntflow_ids(huntflow_url)
            if not ids.get("account_name") or not ids.get("applicant_id"):
                return Response(
                    {"success": False, "message": "Не удалось извлечь данные из URL Huntflow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            account_name = ids["account_name"]
            applicant_id = ids["applicant_id"]

            from apps.huntflow.services import HuntflowService
            api = HuntflowService(user=request.user)
            accounts = api.get_accounts()
            account_id = None
            if accounts and "items" in accounts:
                aname = account_name.lower()
                for acc in accounts["items"]:
                    if ((acc.get("name") or "").lower() == aname or
                            (acc.get("nick") or "").lower() == aname):
                        account_id = acc.get("id")
                        break
            if not account_id:
                return Response(
                    {"success": False, "message": f"Организация '{account_name}' не найдена"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Собираем все «другие» ссылки для сравнения (если ссылка из коммуникации совпадает — не показываем)
            other_urls = set()
            linkedin_url = None
            li_link = LinkedInHuntflowLink.objects.filter(
                account_id=account_id,
                applicant_id=applicant_id
            ).first()
            if li_link:
                linkedin_url = li_link.linkedin_url
                if linkedin_url:
                    other_urls.add(_normalize_url_for_compare(linkedin_url))

            resume_url = None
            resume_obj = ResumeHuntflowLink.objects.filter(
                huntflow_url__icontains=f"/id/{applicant_id}"
            ).first()
            if resume_obj:
                resume_url = resume_obj.resume_url
                if resume_url:
                    other_urls.add(_normalize_url_for_compare(resume_url))

            def _telegram_to_url(val: str) -> str:
                val = (val or "").strip()
                if not val:
                    return ""
                if re.search(r"^https?://", val, re.I):
                    return val
                if re.search(r"t\.me|telegram\.me", val, re.I):
                    return val if "://" in val else "https://" + val
                uname = val.lstrip("@")
                return f"https://t.me/{uname}"

            telegram = _get_questionary_value_by_title_keywords(
                api, account_id, applicant_id, ["telegram", "телеграм"]
            )
            if telegram and (telegram or "").strip():
                tg_url = _telegram_to_url(telegram)
                if tg_url:
                    other_urls.add(_normalize_url_for_compare(tg_url))

            links = []
            labels_map = {"telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "linkedin": "LinkedIn", "communication": "Контакт"}

            if telegram and (telegram or "").strip():
                tg_url = _telegram_to_url(telegram)
                if tg_url:
                    links.append({
                        "type": "telegram",
                        "label": "Telegram",
                        "url": tg_url,
                        "username": _extract_username_from_url(tg_url, "telegram") or None,
                        "source": "questionnaire",
                    })

            if linkedin_url:
                links.append({
                    "type": "linkedin",
                    "label": "LinkedIn",
                    "url": linkedin_url,
                    "username": _extract_username_from_url(linkedin_url, "linkedin") or None,
                    "source": "linkedin",
                })

            # Ссылки из поля «Где ведется коммуникация» (исключая дубли TG и LinkedIn)
            communication = _get_communication_field_value(api, account_id, applicant_id)
            if communication:
                # Разбиваем по переносам, запятым, | — поле может содержать несколько ссылок
                parts = re.split(r"[\n,|]+", str(communication))
                for part in parts:
                    comm = (part or "").strip()
                    if not comm:
                        continue
                    comm_norm = _normalize_url_for_compare(comm)
                    if comm_norm in other_urls:
                        continue
                    link_type = _detect_link_type_from_url(comm)
                    username = _extract_username_from_url(comm, link_type)
                    links.append({
                        "type": link_type,
                        "label": labels_map.get(link_type, "Контакт"),
                        "url": comm,
                        "username": username or None,
                        "source": "communication",
                    })

            tg_li = [l for l in links if l["type"] in ("telegram", "linkedin")]
            others = [l for l in links if l["type"] not in ("telegram", "linkedin")]
            tg_first = sorted(tg_li, key=lambda x: (0 if x["type"] == "telegram" else 1,))
            links = tg_first + others

            return Response(
                {"success": True, "links": links},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("Error getting candidate links")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LinkedInThreadMappingViewSet(viewsets.ViewSet):
    """
    API для маппинга LinkedIn thread_id → profile_url.
    
    Используется Chrome-расширением для работы на страницах /messaging/:
    - POST: сохранить маппинг thread_id → profile_url (автоматически при посещении профиля)
    - GET: получить profile_url по thread_id (на странице сообщений)
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request):
        """
        POST /api/v1/linkedin/thread-mapping/
        Body: { "thread_id": "2-ABC...", "profile_url": "https://linkedin.com/in/..." }
        """
        try:
            thread_id = (request.data or {}).get("thread_id", "").strip()
            raw_profile = (request.data or {}).get("profile_url", "").strip()
            
            if not thread_id:
                return Response(
                    {"success": False, "message": "Нужен thread_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            profile_url = _normalize_linkedin_profile_url(raw_profile)
            if not profile_url:
                return Response(
                    {"success": False, "message": "Нужен корректный LinkedIn profile URL"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            obj, created = LinkedInThreadProfile.objects.update_or_create(
                user=request.user,
                thread_id=thread_id,
                defaults={
                    "profile_url": profile_url,
                    "last_accessed_at": timezone.now(),
                },
            )
            
            return Response(
                {
                    "success": True,
                    "created": created,
                    "thread_id": obj.thread_id,
                    "profile_url": obj.profile_url,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        
        except Exception as e:
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def list(self, request):
        """
        GET /api/v1/linkedin/thread-mapping/?thread_id=...
        """
        try:
            thread_id = request.query_params.get("thread_id", "").strip()
            
            if not thread_id:
                return Response(
                    {"success": False, "message": "Нужен параметр thread_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            obj = LinkedInThreadProfile.objects.filter(
                user=request.user,
                thread_id=thread_id
            ).first()
            
            if not obj:
                return Response(
                    {"success": False, "message": "Маппинг не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Обновляем last_accessed_at
            obj.last_accessed_at = timezone.now()
            obj.save(update_fields=['last_accessed_at'])
            
            return Response(
                {
                    "success": True,
                    "thread_id": obj.thread_id,
                    "profile_url": obj.profile_url,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResumeHuntflowLinkViewSet(viewsets.ViewSet):
    """
    API для сохранения связей «страница резюме (hh.ru/rabota.by) → Huntflow».
    Расширение вызывает POST при нажатии «Применить» на странице резюме.
    GET ?resume_url=... — получить связь по URL резюме (для content script).
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """
        GET /api/v1/huntflow/resume-links/?resume_url=...
        Возвращает связь по resume_id (часть после /resume/ в URL).
        Один ID работает для всех доменов: hh.ru, rabota.by, gomel.rabota.by и т.д.
        """
        resume_url = (request.query_params.get("resume_url") or "").strip()
        if "?" in resume_url:
            resume_url = resume_url.split("?")[0].split("#")[0]
        if not resume_url:
            return Response(
                {"success": False, "message": "Нужен параметр resume_url."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resume_id = _extract_resume_id_from_url(resume_url)
            if not resume_id:
                return Response(
                    {"success": True, "found": False, "resume_url": resume_url},
                    status=status.HTTP_200_OK,
                )
            obj = ResumeHuntflowLink.objects.filter(resume_id=resume_id).first()
            if not obj:
                return Response(
                    {"success": True, "found": False, "resume_url": resume_url},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {
                    "success": True,
                    "found": True,
                    "resume_url": obj.resume_url or resume_url,
                    "huntflow_url": obj.huntflow_url,
                    "vacancy_name": obj.vacancy_name or "",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("ResumeHuntflowLink list")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request):
        """
        POST /api/v1/huntflow/resume-links/
        Body: { "resume_url": "...", "huntflow_url": "...", "vacancy_name": "..." (optional) }
        Сохраняет по resume_id (часть после /resume/) — один ID для всех доменов.
        """
        try:
            resume_url = (request.data or {}).get("resume_url") or ""
            resume_url = resume_url.strip()
            if "?" in resume_url:
                resume_url = resume_url.split("?")[0]
            resume_id = _extract_resume_id_from_url(resume_url)
            huntflow_url = (request.data or {}).get("huntflow_url") or ""
            huntflow_url = huntflow_url.strip()
            vacancy_name = (request.data or {}).get("vacancy_name") or ""
            vacancy_name = (vacancy_name or "").strip()[:255]

            if not resume_id:
                return Response(
                    {"success": False, "message": "Нужен resume_url с путём /resume/{id}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not huntflow_url or ("huntflow" not in huntflow_url.lower() and "huntflow" not in huntflow_url):
                return Response(
                    {"success": False, "message": "Нужна корректная ссылка Huntflow (huntflow_url)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Канонический URL для отображения (hh.ru или rabota.by)
            canonical_url = resume_url
            if ".rabota.by" in resume_url or "rabota.by" in resume_url:
                canonical_url = re.sub(r"https?://[^/]+", "https://rabota.by", resume_url)
            elif "hh.ru" in resume_url or "headhunter.ru" in resume_url:
                canonical_url = re.sub(r"https?://[^/]+", "https://hh.ru", resume_url)

            obj, created = ResumeHuntflowLink.objects.update_or_create(
                resume_id=resume_id,
                defaults={
                    "resume_url": canonical_url,
                    "huntflow_url": huntflow_url,
                    "vacancy_name": vacancy_name,
                    "updated_at": timezone.now(),
                    "updated_by_id": request.user.id,
                },
            )
            if created:
                obj.created_by_id = request.user.id
                obj.save(update_fields=["created_by_id"])
            return Response(
                {
                    "success": True,
                    "created": created,
                    "resume_url": obj.resume_url or resume_url,
                    "huntflow_url": obj.huntflow_url,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("ResumeHuntflowLink create")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
