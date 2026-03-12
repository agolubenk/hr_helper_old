"""Сервис для работы с кандидатами ClickUp с использованием shared модулей"""
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from logic.integration.shared.candidate_operations import BaseCandidateOperations
from logic.integration.shared.comment_operations import BaseCommentOperations
from logic.integration.shared.field_operations import BaseFieldOperations
from logic.integration.shared.status_operations import BaseStatusOperations
from apps.clickup_int.services import ClickUpService


class ClickUpCandidateService(BaseAPIClient, BaseCandidateOperations, BaseCommentOperations, BaseFieldOperations, BaseStatusOperations):
    """
    Сервис для работы с кандидатами ClickUp
    Наследует функциональность от shared модулей для переиспользования логики
    """
    
    def __init__(self, user):
        super().__init__("", "https://api.clickup.com/api/v2", timeout=30)
        self.user = user
        self.clickup_service = ClickUpService(user.clickup_api_key)
        self._setup_auth()
    
    def _setup_auth(self):
        """Настройка аутентификации для ClickUp API"""
        self.headers.update({
            'Authorization': self.user.clickup_api_key,
            'Content-Type': 'application/json'
        })
    
    # ==================== КАНДИДАТЫ ====================
    
    def create_candidate(self, candidate_data, team_id, space_id, list_id):
        """
        Создание кандидата в ClickUp как задачи
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # Подготавливаем данные для ClickUp API
            clickup_task_data = self._prepare_clickup_candidate_data(candidate_data)
            
            # Отправляем запрос к ClickUp API
            response = self.post(f"/list/{list_id}/task", clickup_task_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно создан в ClickUp"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка создания кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def update_candidate(self, candidate_id, candidate_data, team_id=None, space_id=None, list_id=None):
        """
        Обновление кандидата в ClickUp
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # Подготавливаем данные для ClickUp API
            clickup_task_data = self._prepare_clickup_candidate_data(candidate_data)
            
            # Отправляем запрос к ClickUp API
            response = self.put(f"/task/{candidate_id}", clickup_task_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно обновлен в ClickUp"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка обновления кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_candidate(self, candidate_id, team_id=None, space_id=None, list_id=None):
        """
        Получение кандидата из ClickUp
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            response = self.get(f"/task/{candidate_id}")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат получен из ClickUp"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения кандидата'),
                    response.get('status_code', 404)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def link_candidate_to_vacancy(self, candidate_id, vacancy_id, team_id, space_id, list_id):
        """
        Привязка кандидата к вакансии через метки
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            # В ClickUp привязка к вакансии осуществляется через метки
            tags = [f"vacancy_{vacancy_id}"]
            
            tag_data = {
                'tags': tags
            }
            
            response = self.post(f"/task/{candidate_id}/tag", tag_data)
            
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
    
    def add_comment(self, candidate_id, comment_text, team_id=None, space_id=None, list_id=None, comment_type='comment'):
        """
        Добавление комментария к кандидату
        Переопределяем метод из BaseCommentOperations
        """
        try:
            comment_data = {
                'comment_text': comment_text,
                'notify_all': False
            }
            
            response = self.post(f"/task/{candidate_id}/comment", comment_data)
            
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
    
    def get_comments(self, candidate_id, team_id=None, space_id=None, list_id=None):
        """
        Получение комментариев кандидата
        Переопределяем метод из BaseCommentOperations
        """
        try:
            response = self.get(f"/task/{candidate_id}/comment")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
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
    
    def update_custom_fields(self, candidate_id, custom_fields, team_id=None, space_id=None, list_id=None):
        """
        Обновление дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            # В ClickUp дополнительные поля обновляются через custom_fields
            clickup_fields_data = self._prepare_clickup_fields_data(custom_fields)
            
            update_data = {
                'custom_fields': clickup_fields_data
            }
            
            response = self.put(f"/task/{candidate_id}", update_data)
            
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
    
    def get_custom_fields(self, candidate_id, team_id=None, space_id=None, list_id=None):
        """
        Получение дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            response = self.get(f"/task/{candidate_id}")
            
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
    
    def update_candidate_status(self, candidate_id, status_id, team_id=None, space_id=None, list_id=None, comment=None):
        """
        Обновление статуса кандидата
        Переопределяем метод из BaseStatusOperations
        """
        try:
            status_data = {
                'status': status_id
            }
            
            if comment:
                status_data['comment'] = comment
            
            response = self.put(f"/task/{candidate_id}", status_data)
            
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
    
    def get_candidate_status_history(self, candidate_id, team_id=None, space_id=None, list_id=None):
        """
        Получение истории статусов кандидата
        Переопределяем метод из BaseStatusOperations
        """
        try:
            response = self.get(f"/task/{candidate_id}/history")
            
            if response.get('success'):
                # Фильтруем только изменения статусов
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
    
    def add_tags(self, candidate_id, tags, team_id=None, space_id=None, list_id=None):
        """
        Добавление меток к кандидату
        """
        try:
            tag_data = {
                'tags': tags
            }
            
            response = self.post(f"/task/{candidate_id}/tag", tag_data)
            
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
    
    def remove_tags(self, candidate_id, tags, team_id=None, space_id=None, list_id=None):
        """
        Удаление меток кандидата
        """
        try:
            for tag in tags:
                response = self.delete(f"/task/{candidate_id}/tag/{tag}")
                
                if not response.get('success'):
                    return UnifiedResponseHandler.error_response(
                        f"Ошибка удаления метки {tag}",
                        response.get('status_code', 400)
                    )
            
            return UnifiedResponseHandler.success_response(
                {'removed_tags': tags},
                "Метки успешно удалены"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _prepare_clickup_candidate_data(self, candidate_data):
        """Подготовка данных кандидата для ClickUp API"""
        return {
            'name': f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip(),
            'description': candidate_data.get('description', ''),
            'status': candidate_data.get('status', 'open'),
            'priority': candidate_data.get('priority', 3),
            'assignees': candidate_data.get('assignees', []),
            'tags': candidate_data.get('tags', []),
            'custom_fields': candidate_data.get('custom_fields', [])
        }
    
    def _prepare_clickup_fields_data(self, custom_fields):
        """Подготовка дополнительных полей для ClickUp API"""
        fields_data = []
        
        for field_key, field_value in custom_fields.items():
            fields_data.append({
                'id': field_key,
                'value': field_value
            })
        
        return fields_data
    
    def _extract_custom_fields(self, task_data):
        """Извлечение дополнительных полей из ответа ClickUp"""
        custom_fields = {}
        
        if 'custom_fields' in task_data:
            for field in task_data['custom_fields']:
                custom_fields[field['id']] = field.get('value', '')
        
        return custom_fields
    
    def _extract_status_history(self, history_data):
        """Извлечение истории статусов из ответа ClickUp"""
        status_history = []
        
        if 'history' in history_data:
            for item in history_data['history']:
                if item.get('field') == 'status':
                    status_history.append({
                        'old_status': item.get('before', ''),
                        'new_status': item.get('after', ''),
                        'date': item.get('date', ''),
                        'user': item.get('user', {})
                    })
        
        return status_history
    
    def test_connection(self):
        """Тестирование подключения к ClickUp API"""
        try:
            response = self.get("/user")
            return response.get('success', False)
        except Exception:
            return False

