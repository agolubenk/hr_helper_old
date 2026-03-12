"""Базовые операции с дополнительными полями для всех интеграций"""
from abc import ABC, abstractmethod
from logic.base.response_handler import UnifiedResponseHandler

class BaseFieldOperations(ABC):
    """
    Базовый класс для операций с дополнительными полями
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные дополнительных полей
    ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
    ОБРАБОТКА: Абстрактный базовый класс для операций с дополнительными полями
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты операций с дополнительными полями
    СВЯЗИ: UnifiedResponseHandler
    ФОРМАТ: Абстрактный класс с общими методами
    """
    
    @abstractmethod
    def add_custom_field(self, candidate_id, field_data):
        """Добавление кастомного поля - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def update_custom_field(self, field_id, field_data):
        """Обновление кастомного поля - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def delete_custom_field(self, field_id):
        """Удаление кастомного поля - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def get_custom_fields(self, candidate_id):
        """Получение кастомных полей - должен быть реализован в наследниках"""
        pass
    
    def bulk_add_custom_fields(self, candidate_id, fields_data):
        """
        Массовое добавление кастомных полей - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), fields_data (список)
        ИСТОЧНИКИ ДАННЫЕ: ID кандидата и данные дополнительных полей
        ОБРАБОТКА: Массовое добавление дополнительных полей к кандидату
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат массового добавления
        СВЯЗИ: UnifiedResponseHandler, метод add_custom_field
        ФОРМАТ: Словарь с результатами операции
        """
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for field_data in fields_data:
                result = self.add_custom_field(candidate_id, field_data)
                results.append({
                    'field_data': field_data,
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
                        'total': len(fields_data),
                        'success': success_count,
                        'errors': error_count
                    }
                },
                f"Массовое добавление полей завершено: {success_count} успешно, {error_count} ошибок"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_field_schema(self, field_type):
        """Получение схемы поля - базовая реализация"""
        try:
            # Базовые схемы полей
            schemas = {
                'text': {
                    'type': 'text',
                    'required': False,
                    'max_length': 255
                },
                'number': {
                    'type': 'number',
                    'required': False,
                    'min_value': 0
                },
                'date': {
                    'type': 'date',
                    'required': False,
                    'format': 'YYYY-MM-DD'
                },
                'boolean': {
                    'type': 'boolean',
                    'required': False,
                    'default': False
                }
            }
            
            schema = schemas.get(field_type, schemas['text'])
            
            return UnifiedResponseHandler.success_response(
                schema,
                f"Схема поля {field_type} получена"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))