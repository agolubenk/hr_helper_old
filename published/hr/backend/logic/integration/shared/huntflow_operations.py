"""Общие операции для работы с Huntflow API - устраняет дублирование"""

import logging
from typing import Dict, List, Optional, Any
from apps.huntflow.services import HuntflowService

logger = logging.getLogger(__name__)


class HuntflowOperations:
    """Универсальный класс для всех операций с Huntflow API"""
    
    def __init__(self, user):
        """
        Инициализация общих операций Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: user (объект пользователя)
        ИСТОЧНИКИ ДАННЫХ: HuntflowService
        ОБРАБОТКА: Создание экземпляра основного сервиса Huntflow
        ВЫХОДЯЩИЕ ДАННЫЕ: Настроенный объект HuntflowOperations
        СВЯЗИ: HuntflowService
        ФОРМАТ: Объект класса HuntflowOperations
        """
        self.user = user
        self.huntflow_service = HuntflowService(user)
    
    # ==================== СОЗДАНИЕ КАНДИДАТОВ ====================
    
    def create_candidate_from_task_data(self, task_data: Dict[str, Any], 
                                       account_id: int, vacancy_id: int = None,
                                       source_type: str = 'unknown') -> Optional[Dict[str, Any]]:
        """
        Универсальный метод создания кандидата из данных задачи (ClickUp/Notion)
        
        ВХОДЯЩИЕ ДАННЫЕ: 
        - task_data: словарь с данными задачи
        - account_id: ID организации в Huntflow
        - vacancy_id: ID вакансии (опционально)
        - source_type: тип источника ('clickup', 'notion', 'other')
        
        ИСТОЧНИКИ ДАННЫХ: task_data, HuntflowService
        ОБРАБОТКА: 
        - Анализ типа данных (PDF, LinkedIn, rabota.by)
        - Извлечение и обработка данных кандидата
        - Создание кандидата через HuntflowService
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат создания кандидата или None при ошибке
        СВЯЗИ: HuntflowService, методы обработки файлов и ссылок
        ФОРМАТ: Dict с данными созданного кандидата
        """
        try:
            logger.info(f"Создание кандидата из {source_type}: {task_data.get('name', 'unknown')}")
            
            # Извлекаем данные в зависимости от источника
            if source_type == 'clickup':
                parsed_data = self._process_clickup_task(task_data, account_id)
            elif source_type == 'notion':
                parsed_data = self._process_notion_page(task_data, account_id)
            else:
                parsed_data = self._process_generic_data(task_data, account_id)
            
            if not parsed_data:
                logger.error(f"Не удалось обработать данные из {source_type}")
                return None
            
            # Создаем кандидата
            applicant = self.huntflow_service.create_applicant_from_parsed_data(
                account_id=account_id,
                parsed_data=parsed_data,
                vacancy_id=vacancy_id,
                task_name=task_data.get('name', task_data.get('title', '')),
                task_description=task_data.get('description', task_data.get('content', '')),
                task_comments=task_data.get('comments', []),
                assignees=task_data.get('assignees', []),
                task_status=task_data.get('status', ''),
                notion_data=task_data if source_type == 'notion' else None,
                task_data=task_data  # Передаем полные данные задачи для извлечения custom fields
            )
            
            return applicant
            
        except Exception as e:
            logger.error(f"Ошибка создания кандидата из {source_type}: {e}")
            return None
    
    def _process_clickup_task(self, task_data: Dict[str, Any], account_id: int) -> Optional[Dict[str, Any]]:
        """Обработка данных задачи ClickUp"""
        attachments = task_data.get('attachments', [])
        
        # Проверяем PDF файлы по имени или URL
        pdf_attachments = []
        for att in attachments:
            name = att.get('name', '').lower()
            url = att.get('url', '').lower()
            if name.endswith('.pdf') or url.endswith('.pdf'):
                pdf_attachments.append(att)
        
        if pdf_attachments:
            return self._process_pdf_attachment(pdf_attachments[0], account_id)
        
        # Проверяем LinkedIn/rabota.by в custom fields
        custom_fields = task_data.get('custom_fields', {})
        
        for field_data in custom_fields.values():
            field_name = field_data.get('name', '').lower()
            field_value = field_data.get('value', '')
            
            if field_name in ['linkedin', 'linkedin profile', 'linkedin url'] and field_value:
                return self._process_linkedin_profile(field_value, task_data)
            
            if ('rabota' in field_name or 'резюме' in field_name or 'rabota.by' in field_value.lower()) and field_value:
                return self._process_rabota_profile(field_value, task_data)
        
        # Проверяем LinkedIn ссылки в описании задачи
        description = task_data.get('description', '')
        if description:
            import re
            linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[^\s<>"{}\|\\^`\[\]]+', description)
            if linkedin_match:
                return self._process_linkedin_profile(linkedin_match.group(0), task_data)
        
        return None
    
    def _process_notion_page(self, page_data: Dict[str, Any], account_id: int) -> Optional[Dict[str, Any]]:
        """Обработка данных страницы Notion"""
        attachments = page_data.get('attachments', [])
        
        # Проверяем PDF файлы
        pdf_attachments = [att for att in attachments if att.get('name', '').lower().endswith('.pdf')]
        
        if pdf_attachments:
            return self._process_pdf_attachment(pdf_attachments[0], account_id)
        
        # Проверяем ссылки в содержимом страницы
        content = page_data.get('content', '')
        
        if content:
            import re
            
            # Ищем LinkedIn ссылки
            linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[^\s<>"{}\|\\^`\[\]]+', content)
            if linkedin_match:
                return self._process_linkedin_profile(linkedin_match.group(0), page_data)
            
            # Ищем rabota.by ссылки
            rabota_match = re.search(r'https?://(?:www\.)?rabota\.by/[^\s<>"{}\|\\^`\[\]]+', content)
            if rabota_match:
                return self._process_rabota_profile(rabota_match.group(0), page_data)
        
        return None
    
    def _process_generic_data(self, data: Dict[str, Any], account_id: int) -> Optional[Dict[str, Any]]:
        """Обработка общих данных (fallback)"""
        # Простая обработка для неспецифичных источников
        return {
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'position': data.get('position', ''),
        }
    
    # ==================== ОБРАБОТКА ФАЙЛОВ И ССЫЛОК ====================
    
    def _process_pdf_attachment(self, attachment: Dict[str, Any], account_id: int) -> Optional[Dict[str, Any]]:
        """Общая обработка PDF вложения"""
        try:
            import requests
            
            # Скачиваем файл
            file_response = requests.get(attachment['url'], timeout=30)
            if file_response.status_code != 200:
                logger.error("Не удалось скачать PDF файл")
                return None
            
            # Загружаем в Huntflow с парсингом
            file_name = attachment.get('name', attachment.get('title', 'resume.pdf'))
            if not file_name or file_name == '':
                # Если имя файла пустое, извлекаем из URL
                url = attachment.get('url', '')
                if url:
                    import os
                    file_name = os.path.basename(url.split('?')[0])  # Убираем query параметры
                if not file_name:
                    file_name = 'resume.pdf'
            
            parsed_data = self.huntflow_service.upload_file(
                account_id=account_id,
                file_data=file_response.content,
                file_name=file_name,
                parse_file=True
            )
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Ошибка обработки PDF: {e}")
            return None
    
    def _process_linkedin_profile(self, linkedin_url: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Общая обработка LinkedIn профиля"""
        try:
            logger.info(f"Обрабатываем LinkedIn: {linkedin_url}")
            
            return self.huntflow_service.create_linkedin_profile_data(
                linkedin_url=linkedin_url,
                task_name=task_data.get('name', task_data.get('title', '')),
                task_description=task_data.get('description', task_data.get('content', ''))
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки LinkedIn: {e}")
            return None
    
    def _process_rabota_profile(self, rabota_url: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Общая обработка rabota.by профиля"""
        try:
            logger.info(f"Обрабатываем rabota.by: {rabota_url}")
            
            return self.huntflow_service.create_rabota_by_profile_data(
                rabota_url=rabota_url,
                task_name=task_data.get('name', task_data.get('title', '')),
                task_description=task_data.get('description', task_data.get('content', ''))
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки rabota.by: {e}")
            return None
    
    # ==================== КОММЕНТАРИИ ====================
    
    def add_comment_to_candidate(self, account_id: int, applicant_id: int, 
                                comment_text: str, vacancy_id: int = None) -> bool:
        """
        Универсальное добавление комментария к кандидату
        
        ВХОДЯЩИЕ ДАННЫЕ: 
        - account_id: ID организации
        - applicant_id: ID кандидата
        - comment_text: текст комментария
        - vacancy_id: ID вакансии (опционально)
        
        ИСТОЧНИКИ ДАННЫХ: параметры метода
        ОБРАБОТКА: Добавление комментария через HuntflowService
        ВЫХОДЯЩИЕ ДАННЫЕ: True при успехе, False при ошибке
        СВЯЗИ: HuntflowService
        ФОРМАТ: Boolean
        """
        try:
            result = self.huntflow_service.add_applicant_comment(
                account_id=account_id,
                applicant_id=applicant_id,
                comment=comment_text,
                vacancy_id=vacancy_id
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Ошибка добавления комментария: {e}")
            return False
    
    # ==================== СТАТУСЫ ====================
    
    def update_candidate_status(self, account_id: int, applicant_id: int, 
                               status_id: int, comment: str = None, 
                               vacancy_id: int = None) -> bool:
        """
        Универсальное обновление статуса кандидата
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - account_id: ID организации
        - applicant_id: ID кандидата  
        - status_id: ID нового статуса
        - comment: комментарий к смене статуса (опционально)
        - vacancy_id: ID вакансии (опционально)
        
        ИСТОЧНИКИ ДАННЫХ: параметры метода
        ОБРАБОТКА: Обновление статуса через HuntflowService
        ВЫХОДЯЩИЕ ДАННЫЕ: True при успехе, False при ошибке
        СВЯЗИ: HuntflowService
        ФОРМАТ: Boolean
        """
        try:
            result = self.huntflow_service.update_applicant_status(
                account_id=account_id,
                applicant_id=applicant_id,
                status_id=status_id,
                comment=comment,
                vacancy_id=vacancy_id
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def get_accounts(self) -> Optional[List[Dict[str, Any]]]:
        """Получение списка организаций"""
        try:
            accounts_data = self.huntflow_service.get_accounts()
            if accounts_data and 'items' in accounts_data:
                return accounts_data['items']
            return []
        except Exception as e:
            logger.error(f"Ошибка получения организаций: {e}")
            return []
    
    def get_vacancies(self, account_id: int) -> Optional[List[Dict[str, Any]]]:
        """Получение списка вакансий для организации"""
        try:
            vacancies_data = self.huntflow_service.get_vacancies(account_id)
            if vacancies_data and 'items' in vacancies_data:
                return vacancies_data['items']
            return []
        except Exception as e:
            logger.error(f"Ошибка получения вакансий: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Тестирование подключения к Huntflow API"""
        try:
            return self.huntflow_service.test_connection()
        except Exception as e:
            logger.error(f"Ошибка тестирования подключения: {e}")
            return False
    
    def get_and_import_hh_responses(
        self,
        account_id: int,
        vacancy_id: int,
        hh_vacancy_id: str,
        filters: Dict = None
    ) -> Dict:
        """
        Получает отклики из HH.ru, фильтрует их и импортирует в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - account_id: ID организации в Huntflow
        - vacancy_id: ID вакансии в Huntflow
        - hh_vacancy_id: ID вакансии на HH.ru
        - filters: словарь с критериями фильтрации
        
        ИСТОЧНИКИ ДАННЫХ: HH.ru API, параметры метода
        
        ОБРАБОТКА:
        1. Инициализация HHResponsesHandler
        2. Получение откликов из HH.ru
        3. Фильтрация откликов по заданным критериям
        4. Импорт прошедших фильтр кандидатов в Huntflow
        5. Логирование всех операций
        
        ВЫХОДЯЩИЕ ДАННЫЕ: Результаты импорта откликов
        
        СВЯЗИ: HHResponsesHandler, HH.ru API, Huntflow API
        
        ФОРМАТ: Dict с результатами импорта
        """
        
        try:
            from apps.huntflow.hh_integration import HHResponsesHandler
            
            handler = HHResponsesHandler(self.user)
            
            # Получаем отклики из HH.ru
            hh_responses = handler.get_responses_from_hh(hh_vacancy_id)
            
            if not hh_responses['success']:
                return hh_responses
            
            # Фильтруем и импортируем отклики
            result = handler.filter_and_import_responses(
                hh_responses['items'],
                account_id,
                vacancy_id,
                filters,
                hh_vacancy_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении откликов из HH.ru: {e}")
            return {
                'success': False,
                'message': f"Ошибка: {str(e)}"
            }

