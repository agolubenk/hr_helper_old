"""Сервис для работы с кандидатами Huntflow с использованием shared модулей"""
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from logic.integration.shared.candidate_operations import BaseCandidateOperations
from logic.integration.shared.comment_operations import BaseCommentOperations
from logic.integration.shared.field_operations import BaseFieldOperations
from logic.integration.shared.status_operations import BaseStatusOperations
from apps.huntflow.services import HuntflowService


class HuntflowCandidateService(BaseAPIClient, BaseCandidateOperations, BaseCommentOperations, BaseFieldOperations, BaseStatusOperations):
    """
    Сервис для работы с кандидатами Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ: user (пользователь)
    ИСТОЧНИКИ ДАННЫЕ: HuntflowService, Huntflow API
    ОБРАБОТКА: Наследует функциональность от shared модулей для переиспользования логики
    ВЫХОДЯЩИЕ ДАННЫЕ: Операции с кандидатами в Huntflow
    СВЯЗИ: BaseAPIClient, BaseCandidateOperations, BaseCommentOperations, BaseFieldOperations, BaseStatusOperations
    ФОРМАТ: Класс сервиса для работы с кандидатами
    """
    
    def __init__(self, user):
        """
        Инициализация сервиса кандидатов Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: user (пользователь)
        ИСТОЧНИКИ ДАННЫЕ: Пользовательские данные
        ОБРАБОТКА: Настройка подключения к Huntflow API
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный сервис
        СВЯЗИ: BaseAPIClient, HuntflowService
        ФОРМАТ: Экземпляр HuntflowCandidateService
        """
        super().__init__("", "https://api.huntflow.ru/v2", timeout=30)
        self.user = user
        self.huntflow_service = HuntflowService(user)
        self._setup_auth()
    
    def _setup_auth(self):
        """
        Настройка аутентификации для Huntflow API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: self.user.active_system, HuntflowService для получения заголовков
        ОБРАБОТКА: Настройка заголовков авторизации в зависимости от системы через HuntflowService
        ВЫХОДЯЩИЕ ДАННЫЕ: Настроенные заголовки
        СВЯЗИ: HuntflowService
        ФОРМАТ: Обновление self.headers
        """
        # Используем HuntflowService для получения правильных заголовков с поддержкой токенов
        headers = self.huntflow_service._get_headers()
        self.headers.update(headers)
    
    # ==================== КАНДИДАТЫ ====================
    
    def create_candidate(self, candidate_data, account_id):
        """
        Создание кандидата в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_data (словарь), account_id (строка)
        ИСТОЧНИКИ ДАННЫЕ: Данные кандидата
        ОБРАБОТКА: Создание кандидата в Huntflow через API
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат создания кандидата
        СВЯЗИ: UnifiedResponseHandler, Huntflow API
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            # Подготавливаем данные для Huntflow API
            huntflow_candidate_data = self._prepare_huntflow_candidate_data(candidate_data)
            
            # Отправляем запрос к Huntflow API
            response = self.post(f"/accounts/{account_id}/applicants", huntflow_candidate_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно создан в Huntflow"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка создания кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def update_candidate(self, candidate_id, candidate_data, account_id):
        """
        Обновление кандидата в Huntflow
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), candidate_data (словарь), account_id (строка)
        ИСТОЧНИКИ ДАННЫЕ: Данные кандидата для обновления
        ОБРАБОТКА: Обновление кандидата в Huntflow через API
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат обновления кандидата
        СВЯЗИ: UnifiedResponseHandler, Huntflow API
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            # Подготавливаем данные для Huntflow API
            huntflow_candidate_data = self._prepare_huntflow_candidate_data(candidate_data)
            
            # Отправляем запрос к Huntflow API
            response = self.patch(f"/accounts/{account_id}/applicants/{candidate_id}", huntflow_candidate_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат успешно обновлен в Huntflow"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка обновления кандидата'),
                    response.get('status_code', 400)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_candidate(self, candidate_id, account_id):
        """
        Получение кандидата из Huntflow
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            response = self.get(f"/accounts/{account_id}/applicants/{candidate_id}")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
                    "Кандидат получен из Huntflow"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    response.get('message', 'Ошибка получения кандидата'),
                    response.get('status_code', 404)
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def link_candidate_to_vacancy(self, candidate_id, vacancy_id, account_id, status_id=None):
        """
        Привязка кандидата к вакансии
        Переопределяем метод из BaseCandidateOperations
        """
        try:
            link_data = {
                'applicant_id': candidate_id,
                'vacancy_id': vacancy_id
            }
            
            if status_id:
                link_data['status_id'] = status_id
            
            response = self.post(f"/accounts/{account_id}/applicants/{candidate_id}/vacancy", link_data)
            
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
    
    def add_comment(self, candidate_id, comment_text, account_id, comment_type='comment'):
        """
        Добавление комментария к кандидату
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), comment_text (строка), account_id (строка), comment_type (строка)
        ИСТОЧНИКИ ДАННЫЕ: Текст комментария
        ОБРАБОТКА: Добавление комментария к кандидату в Huntflow
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат добавления комментария
        СВЯЗИ: UnifiedResponseHandler, Huntflow API
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            comment_data = {
                'body': comment_text,
                'type': comment_type
            }
            
            response = self.post(f"/accounts/{account_id}/applicants/{candidate_id}/comments", comment_data)
            
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
    
    def get_comments(self, candidate_id, account_id):
        """
        Получение комментариев кандидата
        Переопределяем метод из BaseCommentOperations
        """
        try:
            response = self.get(f"/accounts/{account_id}/applicants/{candidate_id}/comments")
            
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
    
    def update_custom_fields(self, candidate_id, custom_fields, account_id):
        """
        Обновление дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            # Подготавливаем данные для Huntflow API
            huntflow_fields_data = self._prepare_huntflow_fields_data(custom_fields)
            
            response = self.patch(f"/accounts/{account_id}/applicants/{candidate_id}", huntflow_fields_data)
            
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
    
    def get_custom_fields(self, candidate_id, account_id):
        """
        Получение дополнительных полей кандидата
        Переопределяем метод из BaseFieldOperations
        """
        try:
            response = self.get(f"/accounts/{account_id}/applicants/{candidate_id}")
            
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
    
    def update_candidate_status(self, candidate_id, status_id, account_id, comment=None):
        """
        Обновление статуса кандидата
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), status_id (строка), account_id (строка), comment (строка)
        ИСТОЧНИКИ ДАННЫЕ: ID статуса и опциональный комментарий
        ОБРАБОТКА: Обновление статуса кандидата в Huntflow
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат обновления статуса
        СВЯЗИ: UnifiedResponseHandler, Huntflow API
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            status_data = {
                'status_id': status_id
            }
            
            if comment:
                status_data['comment'] = comment
            
            response = self.post(f"/accounts/{account_id}/applicants/{candidate_id}/status", status_data)
            
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
    
    def get_candidate_status_history(self, candidate_id, account_id):
        """
        Получение истории статусов кандидата
        Переопределяем метод из BaseStatusOperations
        """
        try:
            response = self.get(f"/accounts/{account_id}/applicants/{candidate_id}/status")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response['data'],
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
    
    def add_tags(self, candidate_id, tags, account_id):
        """
        Добавление меток к кандидату
        """
        try:
            tags_data = {
                'tags': tags
            }
            
            response = self.post(f"/accounts/{account_id}/applicants/{candidate_id}/tags", tags_data)
            
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
    
    def remove_tags(self, candidate_id, tags, account_id):
        """
        Удаление меток кандидата
        """
        try:
            tags_data = {
                'tags': tags
            }
            
            response = self.delete(f"/accounts/{account_id}/applicants/{candidate_id}/tags", tags_data)
            
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
    
    def _prepare_huntflow_candidate_data(self, candidate_data):
        """Подготовка данных кандидата для Huntflow API"""
        return {
            'first_name': candidate_data.get('first_name', ''),
            'last_name': candidate_data.get('last_name', ''),
            'middle_name': candidate_data.get('middle_name', ''),
            'email': candidate_data.get('email', ''),
            'phone': candidate_data.get('phone', ''),
            'position': candidate_data.get('position', ''),
            'company': candidate_data.get('company', ''),
            'money': candidate_data.get('money', ''),
            'photo': candidate_data.get('photo', ''),
            'externals': candidate_data.get('externals', [])
        }
    
    def _prepare_huntflow_fields_data(self, custom_fields):
        """Подготовка дополнительных полей для Huntflow API"""
        fields_data = {}
        
        for field_key, field_value in custom_fields.items():
            # Преобразуем ключи полей в формат Huntflow
            huntflow_key = f"field_{field_key}"
            fields_data[huntflow_key] = field_value
        
        return fields_data
    
    def _extract_custom_fields(self, candidate_data):
        """Извлечение дополнительных полей из ответа Huntflow"""
        custom_fields = {}
        
        for key, value in candidate_data.items():
            if key.startswith('field_'):
                # Преобразуем ключи обратно в исходный формат
                original_key = key.replace('field_', '')
                custom_fields[original_key] = value
        
        return custom_fields
    
    def test_connection(self):
        """
        Тестирование подключения к Huntflow API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Huntflow API
        ОБРАБОТКА: Тестирование подключения к Huntflow API
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат тестирования подключения
        СВЯЗИ: Huntflow API
        ФОРМАТ: Boolean
        """
        try:
            response = self.get("/accounts")
            return response.get('success', False)
        except Exception:
            return False
