"""Сервис для работы с кандидатами Notion с использованием shared модулей"""
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from logic.integration.shared.candidate_operations import BaseCandidateOperations
from logic.integration.shared.comment_operations import BaseCommentOperations
from logic.integration.shared.field_operations import BaseFieldOperations
from logic.integration.shared.status_operations import BaseStatusOperations
from apps.notion_int.services import NotionService


class NotionCandidateService(BaseAPIClient, BaseCandidateOperations, BaseCommentOperations, BaseFieldOperations, BaseStatusOperations):
    """
    Сервис для работы с кандидатами Notion
    Наследует функциональность от shared модулей для переиспользования логики
    """
    
    def __init__(self, user):
        super().__init__("", "https://api.notion.com/v1", timeout=30)
        self.user = user
        self.notion_service = NotionService(user.notion_integration_token)
        self._setup_auth()
    
    def _setup_auth(self):
        """Настройка аутентификации для Notion API"""
        self.headers.update({
            'Authorization': f'Bearer {self.user.notion_integration_token}',
            'Content-Type': 'application/json',
            'Notion-Version': '2022-06-28'
        })
    
    # ==================== КАНДИДАТЫ ====================
    
    def create_candidate(self, candidate_data, database_id):
        """
        Создание кандидата в Notion как страницы базы данных
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # Подготавливаем данные для Notion API
            notion_page_data = self._prepare_notion_candidate_data(candidate_data)
            
            # Отправляем запрос к Notion API
            response = self.post(f"/pages", notion_page_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно создан в Notion"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка создания кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def update_candidate(self, candidate_id, candidate_data, database_id=None):
        """
        Обновление кандидата в Notion
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # Подготавливаем данные для Notion API
            notion_page_data = self._prepare_notion_candidate_data(candidate_data)
            
            # Отправляем запрос к Notion API
            response = self.patch(f"/pages/{candidate_id}", notion_page_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно обновлен в Notion"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка обновления кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_candidate(self, candidate_id, database_id=None):
        """
        Получение кандидата из Notion
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            response = self.get(f"/pages/{candidate_id}")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат получен из Notion"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения кандидата'),
                    response.get('status_code', 404)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def link_candidate_to_vacancy(self, candidate_id, vacancy_id, database_id):
        """
        Привязка кандидата к вакансии через свойства страницы
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # В Notion привязка к вакансии осуществляется через свойства страницы
            update_data = {
                'properties': {
                    'Вакансия': {
                        'relation': [{'id': vacancy_id}]
                    }
                }
            }
            
            response = self.patch(f"/pages/{candidate_id}", update_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно привязан к вакансии"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка привязки к вакансии'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== КОММЕНТАРИИ ====================
    
    def add_comment(self, candidate_id, comment_text, database_id=None, comment_type='comment'):
        """
        Добавление комментария к кандидату
        Переопределяем метод из BaseCommentOperations
        """
        try:
            # В Notion комментарии добавляются через blocks
            comment_data = {
                'children': [
                    {
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [
                                {
                                    'type': 'text',
                                    'text': {
                                        'content': comment_text
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
            
            response = self.patch(f"/blocks/{candidate_id}/children", comment_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Комментарий успешно добавлен"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка добавления комментария'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_comments(self, candidate_id, database_id=None):
        """
        Получение комментариев кандидата
        Переопределяем метод из BaseCommentOperations
        """
        try:
            response = self.get(f"/blocks/{candidate_id}/children")
            
            if response.get('success'):
                # Фильтруем только комментарии
                comments = self._extract_comments(response['data'])
                
                return UnifiedResponseHandler.success_response(
                    comments,
                    "Комментарии получены"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения комментариев'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ ====================
    
    def update_custom_fields(self, candidate_id, custom_fields, database_id=None):
        """
        Обновление дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            # В Notion дополнительные поля обновляются через properties
            notion_properties = self._prepare_notion_properties(custom_fields)
            
            update_data = {
                'properties': notion_properties
            }
            
            response = self.patch(f"/pages/{candidate_id}", update_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Дополнительные поля успешно обновлены"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка обновления полей'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_custom_fields(self, candidate_id, database_id=None):
        """
        Получение дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            response = self.get(f"/pages/{candidate_id}")
            
            if response.get('success'):
                # Извлекаем дополнительные поля из ответа
                custom_fields = self._extract_custom_fields(response['data'])
                
                return UnifiedResponseHandler.success_response(
                    custom_fields,
                    "Дополнительные поля получены"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения полей'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== СТАТУСЫ ====================
    
    def update_candidate_status(self, candidate_id, status_id, database_id=None, comment=None):
        """
        Обновление статуса кандидата
        Переопределяем метод из BaseStatusOperations
        """
        try:
            status_data = {
                'properties': {
                    'Статус': {
                        'select': {'name': status_id}
                    }
                }
            }
            
            if comment:
                # Добавляем комментарий о смене статуса
                comment_result = self.add_comment(candidate_id, f"Статус изменен на: {status_id}", database_id)
                if not comment_result.get('success'):
                    return comment_result
            
            response = self.patch(f"/pages/{candidate_id}", status_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Статус кандидата успешно обновлен"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка обновления статуса'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_candidate_status_history(self, candidate_id, database_id=None):
        """
        Получение истории статусов кандидата
        Переопределяем метод из BaseStatusOperations
        """
        try:
            # В Notion история статусов хранится в комментариях
            response = self.get(f"/blocks/{candidate_id}/children")
            
            if response.get('success'):
                # Извлекаем комментарии о смене статусов
                status_history = self._extract_status_history(response['data'])
                
                return UnifiedResponseHandler.success_response(
                    status_history,
                    "История статусов получена"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения истории статусов'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== МЕТКИ ====================
    
    def add_tags(self, candidate_id, tags, database_id=None):
        """
        Добавление меток к кандидату
        """
        try:
            tags_data = {
                'properties': {
                    'Теги': {
                        'multi_select': [{'name': tag} for tag in tags]
                    }
                }
            }
            
            response = self.patch(f"/pages/{candidate_id}", tags_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Метки успешно добавлены"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка добавления меток'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def remove_tags(self, candidate_id, tags, database_id=None):
        """
        Удаление меток кандидата
        """
        try:
            # Получаем текущие метки
            current_response = self.get(f"/pages/{candidate_id}")
            if not current_response.get('success'):
                return UnifiedResponseHandler.error_response(
                    "Ошибка получения текущих меток",
                    400
                )
            
            current_tags = current_response['data'].get('properties', {}).get('Теги', {}).get('multi_select', [])
            
            # Удаляем указанные метки
            updated_tags = [tag for tag in current_tags if tag['name'] not in tags]
            
            tags_data = {
                'properties': {
                    'Теги': {
                        'multi_select': updated_tags
                    }
                }
            }
            
            response = self.patch(f"/pages/{candidate_id}", tags_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Метки успешно удалены"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка удаления меток'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _prepare_notion_candidate_data(self, candidate_data):
        """Подготовка данных кандидата для Notion API"""
        return {
            'parent': {'database_id': candidate_data.get('database_id', '')},
            'properties': {
                'Имя': {
                    'title': [
                        {
                            'text': {
                                'content': f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip()
                            }
                        }
                    ]
                },
                'Email': {
                    'email': candidate_data.get('email', '')
                },
                'Телефон': {
                    'phone_number': candidate_data.get('phone', '')
                },
                'Статус': {
                    'select': {'name': candidate_data.get('status', 'Новый')}
                }
            }
        }
    
    def _prepare_notion_properties(self, custom_fields):
        """Подготовка дополнительных полей для Notion API"""
        properties = {}
        
        for field_key, field_value in custom_fields.items():
            if isinstance(field_value, str):
                properties[field_key] = {
                    'rich_text': [
                        {
                            'text': {
                                'content': field_value
                            }
                        }
                    ]
                }
            elif isinstance(field_value, (int, float)):
                properties[field_key] = {
                    'number': field_value
                }
            elif isinstance(field_value, bool):
                properties[field_key] = {
                    'checkbox': field_value
                }
        
        return properties
    
    def _extract_custom_fields(self, page_data):
        """Извлечение дополнительных полей из ответа Notion"""
        custom_fields = {}
        
        if 'properties' in page_data:
            for field_key, field_data in page_data['properties'].items():
                if field_key not in ['Имя', 'Email', 'Телефон', 'Статус']:
                    # Извлекаем значение в зависимости от типа поля
                    if field_data.get('type') == 'rich_text':
                        custom_fields[field_key] = field_data.get('rich_text', [{}])[0].get('text', {}).get('content', '')
                    elif field_data.get('type') == 'number':
                        custom_fields[field_key] = field_data.get('number')
                    elif field_data.get('type') == 'checkbox':
                        custom_fields[field_key] = field_data.get('checkbox')
        
        return custom_fields
    
    def _extract_comments(self, blocks_data):
        """Извлечение комментариев из блоков Notion"""
        comments = []
        
        if 'results' in blocks_data:
            for block in blocks_data['results']:
                if block.get('type') == 'paragraph':
                    paragraph = block.get('paragraph', {})
                    rich_text = paragraph.get('rich_text', [])
                    if rich_text:
                        comment_text = ''.join([text.get('text', {}).get('content', '') for text in rich_text])
                        if comment_text:
                            comments.append({
                                'id': block.get('id'),
                                'text': comment_text,
                                'created_time': block.get('created_time')
                            })
        
        return comments
    
    def _extract_status_history(self, blocks_data):
        """Извлечение истории статусов из блоков Notion"""
        status_history = []
        
        if 'results' in blocks_data:
            for block in blocks_data['results']:
                if block.get('type') == 'paragraph':
                    paragraph = block.get('paragraph', {})
                    rich_text = paragraph.get('rich_text', [])
                    if rich_text:
                        comment_text = ''.join([text.get('text', {}).get('content', '') for text in rich_text])
                        if 'Статус изменен на:' in comment_text:
                            status_history.append({
                                'id': block.get('id'),
                                'comment': comment_text,
                                'created_time': block.get('created_time')
                            })
        
        return status_history
    
    def test_connection(self):
        """Тестирование подключения к Notion API"""
        try:
            response = self.get("/users/me")
            return response.get('success', False)
        except Exception:
            return False

