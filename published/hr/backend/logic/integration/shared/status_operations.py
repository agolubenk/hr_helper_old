"""Базовые операции со статусами для всех интеграций"""
from abc import ABC, abstractmethod
from logic.base.response_handler import UnifiedResponseHandler

class BaseStatusOperations(ABC):
    """
    Базовый класс для операций со статусами
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные статусов кандидатов
    ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
    ОБРАБОТКА: Абстрактный базовый класс для операций со статусами
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты операций со статусами
    СВЯЗИ: UnifiedResponseHandler
    ФОРМАТ: Абстрактный класс с общими методами
    """
    
    @abstractmethod
    def change_status(self, candidate_id, new_status):
        """Изменение статуса - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def get_status_history(self, candidate_id):
        """Получение истории статусов - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def get_available_statuses(self):
        """Получение доступных статусов - должен быть реализован в наследниках"""
        pass
    
    def get_current_status(self, candidate_id):
        """
        Получение текущего статуса - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка)
        ИСТОЧНИКИ ДАННЫЕ: ID кандидата
        ОБРАБОТКА: Получение текущего статуса кандидата
        ВЫХОДЯЩИЕ ДАННЫЕ: Текущий статус кандидата
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с текущим статусом
        """
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                {'status': 'unknown', 'candidate_id': candidate_id},
                "Текущий статус получен (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def bulk_change_status(self, candidate_ids, new_status):
        """
        Массовое изменение статуса - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_ids (список), new_status (строка)
        ИСТОЧНИКИ ДАННЫЕ: Список ID кандидатов и новый статус
        ОБРАБОТКА: Массовое изменение статуса для списка кандидатов
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат массового изменения статуса
        СВЯЗИ: UnifiedResponseHandler, метод change_status
        ФОРМАТ: Словарь с результатами операции
        """
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for candidate_id in candidate_ids:
                result = self.change_status(candidate_id, new_status)
                results.append({
                    'candidate_id': candidate_id,
                    'success': result.get('success'),
                    'message': result.get('message')
                })
                
                if result.get('success'):
                    success_count += 1
                else:
                    error_count += 1
            
            return UnifiedResponseHandler.success_response(
                {
                    'results': results,
                    'summary': {
                        'total': len(candidate_ids),
                        'success': success_count,
                        'errors': error_count
                    }
                },
                f"Массовое изменение статуса завершено: {success_count} успешно, {error_count} ошибок"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def validate_status_transition(self, current_status, new_status):
        """Валидация перехода статуса - базовая реализация"""
        try:
            # Базовые правила переходов (должны быть переопределены в конкретных реализациях)
            allowed_transitions = {
                'new': ['in_progress', 'rejected'],
                'in_progress': ['completed', 'rejected', 'on_hold'],
                'on_hold': ['in_progress', 'rejected'],
                'completed': [],
                'rejected': ['new']
            }
            
            allowed = allowed_transitions.get(current_status, [])
            is_valid = new_status in allowed
            
            return UnifiedResponseHandler.success_response(
                {
                    'is_valid': is_valid,
                    'current_status': current_status,
                    'new_status': new_status,
                    'allowed_transitions': allowed
                },
                f"Переход статуса {'валиден' if is_valid else 'невалиден'}"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))