"""
Обработчики для работы с API ключами
Содержит общую логику для тестирования API ключей
"""
from typing import Dict, Any, Tuple
from django.core.exceptions import ValidationError

from .services import GeminiService


class ApiKeyHandler:
    """Обработчик для работы с API ключами"""
    
    @staticmethod
    def validate_api_key_input(api_key: str) -> Tuple[bool, str]:
        """
        Валидация входного API ключа
        
        Args:
            api_key: API ключ для проверки
            
        Returns:
            Tuple[bool, str]: (валидность, сообщение об ошибке)
        """
        if not api_key:
            return False, 'API ключ не может быть пустым'
        
        if not api_key.strip():
            return False, 'API ключ не может быть пустым'
        
        return True, ''
    
    @staticmethod
    def test_api_key_connection(api_key: str) -> Tuple[bool, str]:
        """
        Тестирование подключения к Gemini API
        
        Args:
            api_key: API ключ для тестирования
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            gemini_service = GeminiService(api_key)
            success, message = gemini_service.test_connection()
            return success, message
        except ValidationError as e:
            return False, f'Ошибка валидации API ключа: {str(e)}'
        except Exception as e:
            return False, f'Ошибка при тестировании API ключа: {str(e)}'
    
    @staticmethod
    def test_api_key(api_key: str) -> Dict[str, Any]:
        """
        Общая логика тестирования API ключа
        
        Args:
            api_key: API ключ для тестирования
            
        Returns:
            Dict[str, Any]: Результат тестирования
        """
        # Валидация входных данных
        is_valid, error = ApiKeyHandler.validate_api_key_input(api_key)
        if not is_valid:
            return {
                'success': False,
                'error': error
            }
        
        # Тестирование подключения
        success, message = ApiKeyHandler.test_api_key_connection(api_key)
        
        return {
            'success': success,
            'message': message
        }


class ApiKeyApiHandler:
    """Обработчик для API endpoints тестирования ключей"""
    
    @staticmethod
    def test_api_key_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для тестирования API ключа
        
        Args:
            data: Данные запроса
            request: HTTP запрос (не используется, но нужен для совместимости)
            
        Returns:
            Dict[str, Any]: Результат тестирования
        """
        api_key = data.get('api_key', '').strip()
        return ApiKeyHandler.test_api_key(api_key)
    
    @staticmethod
    def test_connection_viewset_handler(api_key: str) -> Dict[str, Any]:
        """
        Обработчик для ViewSet тестирования подключения
        
        Args:
            api_key: API ключ для тестирования
            
        Returns:
            Dict[str, Any]: Результат тестирования
        """
        return ApiKeyHandler.test_api_key(api_key)
