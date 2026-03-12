"""
Интеграция с HH.ru API для получения откликов

ВХОДЯЩИЕ ДАННЫЕ: user (пользователь), vacancy_id (ID вакансии на HH.ru)
ИСТОЧНИКИ ДАННЫХ: HH.ru API, HuntflowService
ОБРАБОТКА: Получение откликов из HH.ru, фильтрация, импорт в Huntflow
ВЫХОДЯЩИЕ ДАННЫЕ: Список импортированных кандидатов
СВЯЗИ: HuntflowService, HHResponsesFilter
ФОРМАТ: Класс HHResponsesHandler
"""

import logging
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from django.utils import timezone

from apps.huntflow.models import HuntflowLog
from apps.huntflow.services import HuntflowService
# from logic.integration.huntflow.huntflow_candidates import HuntflowCandidateService  # Не используется, т.к. требует реализации абстрактных методов
from logic.base.response_handler import UnifiedResponseHandler

logger = logging.getLogger(__name__)


class HHResponsesHandler:
    """
    Обработчик откликов из HH.ru с фильтрацией и импортом в Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: user (пользователь)
    ИСТОЧНИКИ ДАННЫХ: HH.ru API, Huntflow API
    ОБРАБОТКА: Получение, фильтрация и импорт откликов
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты импорта откликов
    СВЯЗИ: HuntflowService, HHResponsesFilter
    ФОРМАТ: Класс с методами для работы с откликами
    """
    
    HH_API_BASE = "https://api.hh.ru"
    
    def __init__(self, user):
        """
        Инициализация обработчика откликов HH.ru
        
        ВХОДЯЩИЕ ДАННЫЕ: user (пользователь)
        ИСТОЧНИКИ ДАННЫХ: Пользовательские данные
        ОБРАБОТКА: Настройка сервисов для работы с API
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный обработчик
        СВЯЗИ: HuntflowService
        ФОРМАТ: Экземпляр HHResponsesHandler
        """
        self.user = user
        self.huntflow_service = HuntflowService(user)
        # self.huntflow_candidate_service = HuntflowCandidateService(user)  # Не используется, т.к. требует реализации абстрактных методов
        self.hh_responses_filter = HHResponsesFilter()
        self.session = requests.Session()
        
        # Настройка заголовков для HH.ru API
        # Для HH.ru API нужен OAuth токен доступа
        # Если у пользователя есть токен для HH.ru, используем его
        # Иначе используем токен из Huntflow (если вакансия опубликована через Huntflow)
        # TODO: Добавить отдельное поле для токена HH.ru в модель User
        hh_token = getattr(user, 'hh_access_token', None)
        if hh_token:
            self.session.headers.update({
                'Authorization': f'Bearer {hh_token}',
                'User-Agent': 'Huntflow-HH-Integration/1.0'
            })
        else:
            # Используем User-Agent для идентификации
            self.session.headers.update({
                'User-Agent': 'Huntflow-HH-Integration/1.0'
            })
    
    def get_responses_from_hh(
        self,
        vacancy_id: str,
        page: int = 0,
        per_page: int = 100
    ) -> Dict:
        """
        Получает список откликов из HH.ru для вакансии
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - vacancy_id: ID вакансии на HH.ru
        - page: номер страницы (по умолчанию 0)
        - per_page: количество результатов на странице (по умолчанию 100)
        
        ИСТОЧНИКИ ДАННЫХ: HH.ru API
        
        ОБРАБОТКА:
        1. Формирование URL запроса к HH.ru API
        2. Отправка GET запроса
        3. Обработка ответа и ошибок
        4. Логирование операции
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с откликами и метаинформацией
        
        СВЯЗИ: HH.ru API, logger
        
        ФОРМАТ: Dict с полями:
        {
            'success': bool,
            'items': List[Dict],  # Список откликов
            'total': int,  # Общее количество откликов
            'pages': int,  # Количество страниц
            'page': int,  # Текущая страница
            'message': str
        }
        """
        try:
            # Используем правильный endpoint для получения откликов
            url = f"{self.HH_API_BASE}/vacancies/{vacancy_id}/negotiations"
            
            params = {
                'page': page,
                'per_page': min(per_page, 50),  # Максимум 50 на страницу
            }
            
            logger.info(f"Получение откликов из HH.ru для вакансии {vacancy_id}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            self.log_operation(
                operation_type='HH_GET_RESPONSES',
                status='success',
                details={
                    'vacancy_id': vacancy_id,
                    'responses_count': len(data.get('items', [])),
                    'total': data.get('found', 0)
                }
            )
            
            return {
                'success': True,
                'items': data.get('items', []),
                'total': data.get('found', 0),
                'pages': data.get('pages', 0),
                'page': data.get('page', 0),
                'message': f"Получено {len(data.get('items', []))} откликов"
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении откликов из HH.ru: {e}")
            self.log_operation(
                operation_type='HH_GET_RESPONSES',
                status='error',
                details={'error': str(e)}
            )
            return {
                'success': False,
                'items': [],
                'total': 0,
                'pages': 0,
                'page': 0,
                'message': f"Ошибка при получении откликов: {str(e)}"
            }
    
    def filter_and_import_responses(
        self,
        responses: List[Dict],
        account_id: int,
        vacancy_id: int,
        filters: Dict = None,
        hh_vacancy_id: str = None
    ) -> Dict:
        """
        Фильтрует отклики по заданным критериям и импортирует в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - responses: список откликов из HH.ru
        - account_id: ID организации в Huntflow
        - vacancy_id: ID вакансии в Huntflow
        - filters: словарь с критериями фильтрации
        
        ИСТОЧНИКИ ДАННЫХ: responses, filters
        
        ОБРАБОТКА:
        1. Инициализация фильтров (если не указаны, используются по умолчанию)
        2. Фильтрация кандидатов
        3. Импорт прошедших фильтр кандидатов в Huntflow
        4. Логирование результатов
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результаты импорта
        
        СВЯЗИ: HHResponsesFilter, HuntflowService
        
        ФОРМАТ: Dict с результатами:
        {
            'success': bool,
            'imported': int,  # Количество импортированных кандидатов
            'filtered_out': int,  # Количество отфильтрованных кандидатов
            'errors': int,  # Количество ошибок при импорте
            'imported_candidates': List[Dict],
            'filter_results': Dict,  # Подробные результаты фильтрации
            'message': str
        }
        """
        
        if filters is None:
            filters = self._get_default_filters()
        
        # Фильтруем кандидатов
        filtered, rejected = self.hh_responses_filter.filter_responses(
            responses, filters, self.user
        )
        
        logger.info(f"Фильтрация завершена: прошло {len(filtered)}, отклонено {len(responses) - len(filtered)}")
        
        # Импортируем прошедших фильтр кандидатов
        imported_candidates = []
        errors = 0
        
        for response in filtered:
            try:
                candidate = self._import_candidate_to_huntflow(
                    response, account_id, vacancy_id, hh_vacancy_id
                )
                if candidate:
                    imported_candidates.append(candidate)
            except Exception as e:
                logger.error(f"Ошибка импорта кандидата: {e}")
                errors += 1
        
        self.log_operation(
            operation_type='HH_IMPORT_RESPONSES',
            status='success',
            details={
                'imported': len(imported_candidates),
                'errors': errors,
                'filtered_out': len(responses) - len(filtered)
            }
        )
        
        return {
            'success': True,
            'imported': len(imported_candidates),
            'filtered_out': len(responses) - len(filtered),
            'errors': errors,
            'imported_candidates': imported_candidates,
            'filter_results': {
                'total_responses': len(responses),
                'passed_filter': len(filtered),
                'rejected': rejected
            },
            'message': f"Импортировано {len(imported_candidates)} кандидатов, отклонено {len(responses) - len(filtered)}"
        }
    
    def _import_candidate_to_huntflow(
        self,
        hh_response: Dict,
        account_id: int,
        vacancy_id: int,
        hh_vacancy_id: str = None
    ) -> Optional[Dict]:
        """
        Импортирует одного кандидата из HH.ru в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - hh_response: данные отклика из HH.ru
        - account_id: ID организации в Huntflow
        - vacancy_id: ID вакансии в Huntflow
        
        ИСТОЧНИКИ ДАННЫХ: hh_response
        
        ОБРАБОТКА:
        1. Извлечение данных кандидата из HH.ru response
        2. Преобразование данных в формат Huntflow
        3. Создание кандидата в Huntflow
        4. Привязка кандидата к вакансии
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Данные импортированного кандидата
        
        СВЯЗИ: HuntflowService, Huntflow API
        
        ФОРМАТ: Dict с данными кандидата или None при ошибке
        """
        
        try:
            resume = hh_response.get('resume', {})
            
            # Извлекаем данные кандидата для формата HuntflowService.create_applicant_manual
            candidate_data = {
                'first_name': resume.get('first_name', ''),
                'last_name': resume.get('last_name', ''),
                'middle_name': resume.get('middle_name', ''),
                'email': self._extract_email(resume),
                'phone': self._extract_phone(resume),
                'position': self._get_last_position(resume),
                'company': self._get_last_company(resume),
                'resume_text': self._extract_resume_text(resume)
            }
            
            # Создаем кандидата в Huntflow используя HuntflowService
            # Метод create_applicant_manual автоматически привязывает к вакансии, если указан vacancy_id
            created = self.huntflow_service.create_applicant_manual(
                account_id=account_id,
                candidate_data=candidate_data,
                vacancy_id=vacancy_id
            )
            
            if created:
                # Получаем ID созданного кандидата
                applicant_id = created.get('id')
                
                if applicant_id:
                    # Добавляем информацию о HH.ru источнике
                    self._add_hh_source_comment(
                        account_id, applicant_id, hh_response, vacancy_id
                    )
                    
                    # Сохраняем отклик в БД с привязкой к кандидату
                    # Если hh_vacancy_id не передан, пытаемся извлечь из данных
                    if not hh_vacancy_id:
                        vacancy_data = hh_response.get('vacancy', {})
                        hh_vacancy_id = vacancy_data.get('id', '') if vacancy_data else ''
                    
                    self._save_hh_response_to_db(
                        hh_response, account_id, vacancy_id, applicant_id, hh_vacancy_id
                    )
                    
                    return created
            
        except Exception as e:
            logger.error(f"Ошибка при импорте кандидата: {e}")
        
        return None
    
    def _extract_email(self, resume: Dict) -> str:
        """Извлекает email из резюме HH.ru"""
        contacts = resume.get('contacts', [])
        for contact in contacts:
            if contact.get('type', {}).get('id') == 'email':
                return contact.get('value', '')
        return ''
    
    def _extract_phone(self, resume: Dict) -> str:
        """Извлекает телефон из резюме HH.ru"""
        contacts = resume.get('contacts', [])
        for contact in contacts:
            if contact.get('type', {}).get('id') == 'phone':
                return contact.get('value', '')
        return ''
    
    def _extract_resume_text(self, resume: Dict) -> str:
        """Извлекает текстовое представление резюме из HH.ru"""
        text_parts = []
        
        # Заголовок
        if resume.get('title'):
            text_parts.append(f"Должность: {resume['title']}")
        
        # Опыт работы
        experience = resume.get('experience', [])
        if experience:
            text_parts.append("\nОпыт работы:")
            for exp in experience:
                text_parts.append(
                    f"- {exp.get('position', '')} в {exp.get('company', '')} "
                    f"({exp.get('start', '')} - {exp.get('end', 'наст. время')})"
                )
        
        # Навыки (если доступны)
        if resume.get('skills'):
            text_parts.append("\nНавыки:")
            for skill in resume.get('skills', []):
                text_parts.append(f"- {skill.get('name', '')}")
        
        return '\n'.join(text_parts)
    
    def _get_hh_source_id(self) -> int:
        """Получает ID источника HH.ru в Huntflow (обычно 2)"""
        # В Huntflow HH.ru обычно имеет ID 2
        return 2
    
    def _get_last_position(self, resume: Dict) -> str:
        """Получает последнюю должность кандидата"""
        experience = resume.get('experience', [])
        if experience:
            return experience[0].get('position', '')
        return ''
    
    def _get_last_company(self, resume: Dict) -> str:
        """Получает последнюю компанию, где работал кандидат"""
        experience = resume.get('experience', [])
        if experience:
            return experience[0].get('company', '')
        return ''
    
    def _add_hh_source_comment(
        self,
        account_id: int,
        applicant_id: int,
        hh_response: Dict,
        vacancy_id: int = None
    ) -> None:
        """Добавляет комментарий о источнике из HH.ru"""
        
        resume = hh_response.get('resume', {})
        hh_url = resume.get('url', '')
        created_at = hh_response.get('created_at', '')
        
        comment = f"Автоматически импортировано из HH.ru\n"
        comment += f"Дата отклика: {created_at}\n"
        comment += f"Ссылка на резюме: {hh_url}\n"
        comment += f"ID на HH.ru: {resume.get('id')}"
        
        # Используем HuntflowService для добавления комментария
        self.huntflow_service.add_applicant_comment(
            account_id=account_id,
            applicant_id=applicant_id,
            comment=comment,
            vacancy_id=vacancy_id
        )
    
    def _save_hh_response_to_db(
        self,
        hh_response: Dict,
        account_id: int,
        vacancy_id: int,
        applicant_id: int,
        hh_vacancy_id: str = None
    ) -> None:
        """Сохраняет отклик из HH.ru в БД"""
        try:
            from apps.huntflow.models import HHResponse
            from datetime import datetime
            
            resume = hh_response.get('resume', {})
            hh_response_id = hh_response.get('id', '')
            
            # Если hh_vacancy_id не передан, пытаемся извлечь из данных
            if not hh_vacancy_id:
                vacancy_data = hh_response.get('vacancy', {})
                hh_vacancy_id = vacancy_data.get('id', '') if vacancy_data else ''
            
            # Проверяем, не существует ли уже такой отклик
            existing = HHResponse.objects.filter(
                hh_response_id=hh_response_id
            ).first()
            
            if existing:
                # Обновляем существующий
                existing.applicant_id = applicant_id
                existing.account_id = account_id
                existing.vacancy_id = vacancy_id
                existing.import_status = 'imported'
                existing.save()
                return
            
            # Парсим даты
            created_at_str = hh_response.get('created_at', '')
            updated_at_str = hh_response.get('updated_at', created_at_str)
            
            try:
                if 'T' in created_at_str:
                    hh_created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    hh_created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
            except:
                hh_created_at = timezone.now()
            
            try:
                if 'T' in updated_at_str:
                    hh_updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                else:
                    hh_updated_at = datetime.strptime(updated_at_str, '%Y-%m-%d')
            except:
                hh_updated_at = timezone.now()
            
            # Парсим дату рождения
            birth_date = None
            birth_date_str = resume.get('birth_date')
            if birth_date_str:
                try:
                    if 'T' in birth_date_str:
                        birth_date = datetime.fromisoformat(birth_date_str.replace('Z', '+00:00')).date()
                    else:
                        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                except:
                    pass
            
            # Извлекаем локацию
            area = resume.get('area', {})
            location = area.get('name', '')
            location_id = str(area.get('id', ''))
            
            # Создаем запись
            HHResponse.objects.create(
                hh_response_id=hh_response_id,
                hh_vacancy_id=hh_vacancy_id or '',
                first_name=resume.get('first_name', ''),
                last_name=resume.get('last_name', ''),
                middle_name=resume.get('middle_name', ''),
                email=self._extract_email(resume),
                phone=self._extract_phone(resume),
                birth_date=birth_date,
                gender=resume.get('gender', {}).get('id', ''),
                location=location,
                location_id=location_id,
                experience_json=resume.get('experience', []),
                skills_json=resume.get('skills', []),
                resume_text=self._extract_resume_text(resume),
                hh_resume_url=resume.get('url', ''),
                response_state=hh_response.get('state', 'applied'),
                import_status='imported',
                account_id=account_id,
                vacancy_id=vacancy_id,
                applicant_id=applicant_id,
                imported_by=self.user,
                raw_data=hh_response,
                hh_created_at=hh_created_at,
                hh_updated_at=hh_updated_at
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения HHResponse в БД: {e}")
    
    def _get_default_filters(self) -> Dict:
        """Получает фильтры по умолчанию"""
        return {
            'allowed_locations': ['1', '2', '3'],  # Москва, СПб, Екатеринбург
            'allowed_genders': ['male', 'female', 'any'],
            'min_age': 18,
            'max_age': 65,
            'check_existing': True,
            'min_experience_years': 1,
            'max_experience_years': 50
        }
    
    def reject_response(
        self,
        negotiation_id: str,
        vacancy_id: str,
        message: str = None
    ) -> Dict:
        """
        Отклоняет отклик в HH.ru
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - negotiation_id: ID переговоров (отклика) в HH.ru
        - vacancy_id: ID вакансии на HH.ru
        - message: сообщение об отказе (опционально)
        
        ИСТОЧНИКИ ДАННЫХ: HH.ru API
        
        ОБРАБОТКА:
        1. Отправка запроса на отклонение отклика
        2. Логирование операции
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат операции
        """
        try:
            url = f"{self.HH_API_BASE}/negotiations/{negotiation_id}/reject"
            
            data = {}
            if message:
                data['message'] = message
            
            response = self.session.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Отклик {negotiation_id} отклонен в HH.ru")
            
            self.log_operation(
                operation_type='HH_REJECT_RESPONSE',
                status='success',
                details={
                    'negotiation_id': negotiation_id,
                    'vacancy_id': vacancy_id,
                    'message': message
                }
            )
            
            return {
                'success': True,
                'message': 'Отклик отклонен'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при отклонении отклика: {e}")
            self.log_operation(
                operation_type='HH_REJECT_RESPONSE',
                status='error',
                details={'error': str(e)}
            )
            return {
                'success': False,
                'message': f"Ошибка: {str(e)}"
            }
    
    def archive_response(
        self,
        negotiation_id: str
    ) -> Dict:
        """
        Архивирует отклик в HH.ru
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - negotiation_id: ID переговоров (отклика) в HH.ru
        
        ИСТОЧНИКИ ДАННЫХ: HH.ru API
        
        ОБРАБОТКА:
        1. Отправка запроса на архивирование отклика
        2. Логирование операции
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат операции
        """
        try:
            url = f"{self.HH_API_BASE}/negotiations/{negotiation_id}/archive"
            
            response = self.session.post(url, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Отклик {negotiation_id} архивирован в HH.ru")
            
            self.log_operation(
                operation_type='HH_ARCHIVE_RESPONSE',
                status='success',
                details={'negotiation_id': negotiation_id}
            )
            
            return {
                'success': True,
                'message': 'Отклик архивирован'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при архивировании отклика: {e}")
            self.log_operation(
                operation_type='HH_ARCHIVE_RESPONSE',
                status='error',
                details={'error': str(e)}
            )
            return {
                'success': False,
                'message': f"Ошибка: {str(e)}"
            }
    
    def mark_as_viewed(
        self,
        negotiation_id: str
    ) -> Dict:
        """
        Отмечает отклик как просмотренный в HH.ru
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - negotiation_id: ID переговоров (отклика) в HH.ru
        
        ИСТОЧНИКИ ДАННЫХ: HH.ru API
        
        ОБРАБОТКА:
        1. Отправка запроса на отметку как просмотренный
        2. Логирование операции
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат операции
        """
        try:
            url = f"{self.HH_API_BASE}/negotiations/{negotiation_id}/viewed"
            
            response = self.session.post(url, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Отклик {negotiation_id} отмечен как просмотренный")
            
            self.log_operation(
                operation_type='HH_MARK_VIEWED',
                status='success',
                details={'negotiation_id': negotiation_id}
            )
            
            return {
                'success': True,
                'message': 'Отклик отмечен как просмотренный'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при отметке отклика: {e}")
            self.log_operation(
                operation_type='HH_MARK_VIEWED',
                status='error',
                details={'error': str(e)}
            )
            return {
                'success': False,
                'message': f"Ошибка: {str(e)}"
            }
    
    def log_operation(
        self,
        operation_type: str,
        status: str,
        details: Dict = None
    ) -> None:
        """
        Логирует операцию интеграции с HH.ru
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - operation_type: тип операции (HH_GET_RESPONSES, HH_IMPORT_RESPONSES)
        - status: статус (success, error)
        - details: дополнительные детали
        
        ИСТОЧНИКИ ДАННЫХ: параметры метода
        
        ОБРАБОТКА: Создание записи лога в базе данных
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Запись в HuntflowLog
        
        СВЯЗИ: HuntflowLog модель
        
        ФОРМАТ: Нет возвращаемого значения
        """
        
        try:
            HuntflowLog.objects.create(
                log_type='GET' if 'GET' in operation_type else 'POST',
                endpoint=f'/hh/{operation_type}',
                method='GET' if 'GET' in operation_type else 'POST',
                status_code=200 if status == 'success' else 400,
                request_data={'operation_type': operation_type},
                response_data=details or {},
                user=self.user
            )
        except Exception as e:
            logger.error(f"Ошибка логирования операции: {e}")


class HHResponsesFilter:
    """
    Фильтр для откликов из HH.ru
    
    ВХОДЯЩИЕ ДАННЫЕ: responses (список откликов), filters (критерии фильтрации)
    ИСТОЧНИКИ ДАННЫХ: HH.ru API response, фильтры
    ОБРАБОТКА: Фильтрация откликов по различным критериям
    ВЫХОДЯЩИЕ ДАННЫЕ: Отфильтрованные отклики и отклоненные
    СВЯЗИ: Нет внешних зависимостей
    ФОРМАТ: Класс с методами фильтрации
    """
    
    def filter_responses(
        self,
        responses: List[Dict],
        filters: Dict,
        user
    ) -> Tuple[List[Dict], Dict]:
        """
        Фильтрует список откликов по заданным критериям
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - responses: список откликов из HH.ru
        - filters: словарь с критериями фильтрации
        - user: пользователь для проверки дубликатов
        
        ИСТОЧНИКИ ДАННЫХ: responses, filters
        
        ОБРАБОТКА:
        1. Для каждого отклика проверяются все критерии фильтрации
        2. Если отклик соответствует всем критериям - он добавляется в filtered
        3. Если не соответствует - он добавляется в rejected с указанием причины
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - filtered: список прошедших фильтр откликов
        - rejected: словарь с отклоненными откликами (причина: список)
        
        СВЯЗИ: методы фильтрации (_check_*)
        
        ФОРМАТ: Кортеж (List[Dict], Dict)
        """
        
        filtered = []
        rejected = {
            'location_mismatch': [],
            'gender_mismatch': [],
            'age_mismatch': [],
            'experience_mismatch': [],
            'already_in_db': [],
            'other': []
        }
        
        for response in responses:
            result = self._check_response(response, filters, user)
            if result['valid']:
                filtered.append(response)
            else:
                rejected[result['reason']].append(response)
        
        return filtered, rejected
    
    def _check_response(self, response: Dict, filters: Dict, user) -> Dict:
        """Проверяет один отклик по всем критериям"""
        
        resume = response.get('resume', {})
        
        # 1. Проверка локации
        if not self._check_location(resume, filters):
            return {'valid': False, 'reason': 'location_mismatch'}
        
        # 2. Проверка пола
        if not self._check_gender(resume, filters):
            return {'valid': False, 'reason': 'gender_mismatch'}
        
        # 3. Проверка возраста
        if not self._check_age(resume, filters):
            return {'valid': False, 'reason': 'age_mismatch'}
        
        # 4. Проверка опыта работы
        if not self._check_experience(resume, filters):
            return {'valid': False, 'reason': 'experience_mismatch'}
        
        # 5. Проверка наличия в базе
        if filters.get('check_existing', False):
            if self._check_already_in_db(resume, self._extract_email(resume), user):
                return {'valid': False, 'reason': 'already_in_db'}
        
        return {'valid': True, 'reason': None}
    
    def _check_location(self, resume: Dict, filters: Dict) -> bool:
        """Проверяет соответствие локации"""
        if 'allowed_locations' not in filters or not filters['allowed_locations']:
            return True  # Локация не проверяется
        
        area = resume.get('area', {})
        location_id = str(area.get('id', ''))
        allowed = [str(l) for l in filters.get('allowed_locations', [])]
        
        # Если None в списке разрешенных, пропускаем проверку
        if None in allowed or 'None' in allowed:
            return True
        
        return location_id in allowed
    
    def _check_gender(self, resume: Dict, filters: Dict) -> bool:
        """Проверяет соответствие полу"""
        if 'allowed_genders' not in filters or not filters['allowed_genders']:
            return True  # Пол не проверяется
        
        gender = resume.get('gender', {}).get('id', 'any')
        allowed = filters.get('allowed_genders', ['any'])
        
        # Если 'any' в списке разрешенных, пропускаем проверку
        if 'any' in allowed:
            return True
        
        return gender in allowed
    
    def _check_age(self, resume: Dict, filters: Dict) -> bool:
        """Проверяет соответствие возрасту"""
        birth_date_str = resume.get('birth_date')
        if not birth_date_str:
            return True  # Если возраста нет, не отклоняем
        
        try:
            # Парсим дату рождения
            if 'T' in birth_date_str:
                birth_date = datetime.fromisoformat(birth_date_str.replace('Z', '+00:00')).date()
            else:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            
            today = date.today()
            age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
            
            min_age = filters.get('min_age', 18)
            max_age = filters.get('max_age', 65)
            
            return min_age <= age <= max_age
        except (ValueError, TypeError):
            return True  # Если дата в неправильном формате, не отклоняем
    
    def _check_experience(self, resume: Dict, filters: Dict) -> bool:
        """Проверяет соответствие опыту работы"""
        experience_list = resume.get('experience', [])
        if not experience_list:
            return filters.get('min_experience_years', 0) == 0
        
        total_days = 0
        today = date.today()
        
        for exp in experience_list:
            start_str = exp.get('start')
            end_str = exp.get('end')
            
            if not start_str:
                continue
            
            try:
                if 'T' in start_str:
                    start = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
                else:
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                
                if end_str:
                    if 'T' in end_str:
                        end = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
                    else:
                        end = datetime.strptime(end_str, '%Y-%m-%d').date()
                else:
                    end = today
                
                total_days += (end - start).days
            except (ValueError, TypeError):
                continue
        
        experience_years = total_days / 365.25
        min_exp = filters.get('min_experience_years', 1)
        max_exp = filters.get('max_experience_years', 50)
        
        return min_exp <= experience_years <= max_exp
    
    def _check_already_in_db(self, resume: Dict, email: str, user) -> bool:
        """
        Проверяет, есть ли кандидат уже в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: resume из HH.ru, email кандидата, user
        ИСТОЧНИКИ ДАННЫЕ: Django БД (Huntflow кандидаты)
        ОБРАБОТКА: Поиск кандидата по email или ФИ
        ВЫХОДЯЩИЕ ДАННЫЕ: True если кандидат уже в БД, False если новый
        СВЯЗИ: HuntflowApplicant модель (если существует)
        ФОРМАТ: Метод с return True/False
        """
        
        email = email or ''
        first_name = resume.get('first_name', '').strip()
        last_name = resume.get('last_name', '').strip()
        
        # Проверка по email (самый надежный способ)
        if email:
            # Проверяем в таблице HH откликов (если модель существует)
            try:
                from apps.huntflow.models import HHResponse
                if HHResponse.objects.filter(
                    imported_by=user,
                    email__iexact=email
                ).exists():
                    return True
            except:
                pass
        
        # Проверка по ФИ (менее надежно)
        if first_name and last_name:
            # Можно добавить проверку в других моделях если нужно
            pass
        
        return False
    
    def _extract_email(self, resume: Dict) -> str:
        """Извлекает email из резюме"""
        contacts = resume.get('contacts', [])
        for contact in contacts:
            if contact.get('type', {}).get('id') == 'email':
                return contact.get('value', '')
        return ''

