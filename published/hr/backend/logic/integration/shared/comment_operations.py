"""Базовые операции с комментариями для всех интеграций"""
from abc import ABC, abstractmethod
from logic.base.response_handler import UnifiedResponseHandler

class BaseCommentOperations(ABC):
    """
    Базовый класс для операций с комментариями
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные комментариев
    ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
    ОБРАБОТКА: Абстрактный базовый класс для операций с комментариями
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты операций с комментариями
    СВЯЗИ: UnifiedResponseHandler
    ФОРМАТ: Абстрактный класс с общими методами
    """
    
    @abstractmethod
    def add_comment(self, candidate_id, comment_data):
        """Добавление комментария - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def update_comment(self, comment_id, comment_data):
        """Обновление комментария - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def delete_comment(self, comment_id):
        """Удаление комментария - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def get_comments(self, candidate_id):
        """Получение комментариев - должен быть реализован в наследниках"""
        pass
    
    def bulk_add_comments(self, candidate_id, comments_data):
        """
        Массовое добавление комментариев - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), comments_data (список)
        ИСТОЧНИКИ ДАННЫЕ: ID кандидата и данные комментариев
        ОБРАБОТКА: Массовое добавление комментариев к кандидату
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат массового добавления
        СВЯЗИ: UnifiedResponseHandler, метод add_comment
        ФОРМАТ: Словарь с результатами операции
        """
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for comment_data in comments_data:
                result = self.add_comment(candidate_id, comment_data)
                results.append({
                    'comment_data': comment_data,
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
                        'total': len(comments_data),
                        'success': success_count,
                        'errors': error_count
                    }
                },
                f"Массовое добавление комментариев завершено: {success_count} успешно, {error_count} ошибок"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def search_comments(self, search_params):
        """Поиск комментариев - базовая реализация"""
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                [],
                "Поиск комментариев (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))