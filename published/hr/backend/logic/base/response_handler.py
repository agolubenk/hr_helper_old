from typing import Dict, Any, Optional
from django.http import JsonResponse
from rest_framework.response import Response

class UnifiedResponseHandler:
    """
    Унифицированный обработчик ответов для всех приложений
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные ответа, сообщения, коды статуса
    ИСТОЧНИКИ ДАННЫЕ: Django views, API endpoints
    ОБРАБОТКА: Стандартизация ответов API и HTTP запросов
    ВЫХОДЯЩИЕ ДАННЫЕ: Унифицированные ответы в JSON формате
    СВЯЗИ: Django JsonResponse, DRF Response
    ФОРМАТ: Dict[str, Any] или Response объекты
    """
    
    @staticmethod
    def success_response(
        data: Any = None, 
        message: Optional[str] = None,
        status_code: int = 200
    ) -> Dict[str, Any]:
        """
        Успешный ответ
        
        ВХОДЯЩИЕ ДАННЫЕ: data (любые данные), message (строка), status_code (int)
        ИСТОЧНИКИ ДАННЫЕ: Успешные операции приложений
        ОБРАБОТКА: Формирование стандартизированного успешного ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с success=True и данными
        СВЯЗИ: Нет
        ФОРМАТ: Dict[str, Any] с полями success, data, message
        """
        response_data = {'success': True}
        
        if data is not None:
            response_data['data'] = data
        
        if message:
            response_data['message'] = message
        
        return response_data
    
    @staticmethod
    def error_response(
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict] = None,
        status_code: int = 400
    ) -> Dict[str, Any]:
        """
        Ответ с ошибкой
        
        ВХОДЯЩИЕ ДАННЫЕ: message (строка), error_code (строка), details (словарь), status_code (int)
        ИСТОЧНИКИ ДАННЫЕ: Ошибки приложений и API
        ОБРАБОТКА: Формирование стандартизированного ответа с ошибкой
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с success=False и деталями ошибки
        СВЯЗИ: Нет
        ФОРМАТ: Dict[str, Any] с полями success, error, error_code, details
        """
        response_data = {
            'success': False,
            'error': message
        }
        
        if error_code:
            response_data['error_code'] = error_code
        
        if details:
            response_data['details'] = details
        
        return response_data
    
    @staticmethod
    def validation_error_response(errors: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ответ с ошибками валидации
        
        ВХОДЯЩИЕ ДАННЫЕ: errors (словарь с ошибками валидации)
        ИСТОЧНИКИ ДАННЫЕ: Django serializers, формы валидации
        ОБРАБОТКА: Формирование стандартизированного ответа с ошибками валидации
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с success=False и validation_errors
        СВЯЗИ: Нет
        ФОРМАТ: Dict[str, Any] с полями success, error, validation_errors
        """
        return {
            'success': False,
            'error': 'Validation failed',
            'validation_errors': errors
        }
    
    @staticmethod
    def api_response(data: Dict[str, Any], status_code: int = 200) -> Response:
        """
        DRF Response
        
        ВХОДЯЩИЕ ДАННЫЕ: data (словарь данных), status_code (int)
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework
        ОБРАБОТКА: Создание DRF Response объекта
        ВЫХОДЯЩИЕ ДАННЫЕ: DRF Response объект
        СВЯЗИ: rest_framework.response.Response
        ФОРМАТ: Response объект
        """
        return Response(data, status=status_code)
    
    @staticmethod
    def json_response(data: Dict[str, Any], status_code: int = 200) -> JsonResponse:
        """
        JSON Response для Django views
        
        ВХОДЯЩИЕ ДАННЫЕ: data (словарь данных), status_code (int)
        ИСТОЧНИКИ ДАННЫЕ: Django HTTP
        ОБРАБОТКА: Создание Django JsonResponse объекта
        ВЫХОДЯЩИЕ ДАННЫЕ: Django JsonResponse объект
        СВЯЗИ: django.http.JsonResponse
        ФОРМАТ: JsonResponse объект
        """
        return JsonResponse(data, status=status_code)
