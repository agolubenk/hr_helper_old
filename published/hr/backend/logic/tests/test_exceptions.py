"""Тесты для кастомных исключений"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logic.tests.test_base import BaseTestCase
from logic.base.exceptions import (
    LogicBaseException,
    APIClientException,
    ValidationException,
    SyncException,
    AnalysisException
)

class TestExceptions(BaseTestCase):
    """Тесты для кастомных исключений"""
    
    def test_logic_base_exception(self):
        """Тест базового исключения Logic"""
        message = "Test base exception"
        
        with self.assertRaises(LogicBaseException) as context:
            raise LogicBaseException(message)
        
        self.assertEqual(str(context.exception), message)
        self.assertIsInstance(context.exception, Exception)
    
    def test_api_client_exception(self):
        """Тест исключения APIClientException"""
        message = "API request failed"
        
        with self.assertRaises(APIClientException) as context:
            raise APIClientException(message)
        
        self.assertEqual(str(context.exception), message)
        self.assertIsInstance(context.exception, LogicBaseException)
    
    def test_validation_exception(self):
        """Тест исключения ValidationException"""
        message = "Validation failed"
        
        with self.assertRaises(ValidationException) as context:
            raise ValidationException(message)
        
        self.assertEqual(str(context.exception), message)
        self.assertIsInstance(context.exception, LogicBaseException)
    
    def test_sync_exception(self):
        """Тест исключения SyncException"""
        message = "Sync failed"
        
        with self.assertRaises(SyncException) as context:
            raise SyncException(message)
        
        self.assertEqual(str(context.exception), message)
        self.assertIsInstance(context.exception, LogicBaseException)
    
    def test_analysis_exception(self):
        """Тест исключения AnalysisException"""
        message = "Analysis failed"
        
        with self.assertRaises(AnalysisException) as context:
            raise AnalysisException(message)
        
        self.assertEqual(str(context.exception), message)
        self.assertIsInstance(context.exception, LogicBaseException)
    
    def test_exception_inheritance(self):
        """Тест наследования исключений"""
        # Все кастомные исключения должны наследоваться от LogicBaseException
        exceptions = [
            APIClientException,
            ValidationException,
            SyncException,
            AnalysisException
        ]
        
        for exception_class in exceptions:
            with self.subTest(exception=exception_class):
                self.assertTrue(issubclass(exception_class, LogicBaseException))
                self.assertTrue(issubclass(exception_class, Exception))
    
    def test_exception_with_context(self):
        """Тест исключений с контекстной информацией"""
        # ValidationException с контекстом
        with self.assertRaises(ValidationException) as context:
            raise ValidationException("Invalid user data")
        
        self.assertEqual(str(context.exception), "Invalid user data")
    
    def test_exception_serialization(self):
        """Тест сериализации исключений"""
        import json
        
        try:
            raise ValidationException("Test validation error")
        except ValidationException as e:
            # Проверяем что исключение можно преобразовать в словарь
            error_dict = {
                'type': e.__class__.__name__,
                'message': str(e)
            }
            
            # Проверяем сериализацию в JSON
            json_str = json.dumps(error_dict)
            self.assertIsInstance(json_str, str)
    
    def test_multiple_exceptions_handling(self):
        """Тест обработки множественных исключений"""
        exceptions_to_test = [
            (APIClientException("API failed"), "API failed"),
            (ValidationException("Validation failed"), "Validation failed"),
            (SyncException("Sync failed"), "Sync failed"),
            (AnalysisException("Analysis failed"), "Analysis failed")
        ]
        
        for exception, expected_message in exceptions_to_test:
            with self.subTest(exception=type(exception).__name__):
                with self.assertRaises(type(exception)) as context:
                    raise exception
                
                self.assertEqual(str(context.exception), expected_message)
                self.assertIsInstance(context.exception, LogicBaseException)
    
    def test_exception_with_unicode(self):
        """Тест исключений с Unicode символами"""
        unicode_message = "Ошибка валидации: тест 🚀"
        
        with self.assertRaises(ValidationException) as context:
            raise ValidationException(unicode_message)
        
        self.assertEqual(str(context.exception), unicode_message)
    
    def test_exception_chaining(self):
        """Тест цепочки исключений"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise APIClientException("API call failed") from e
        except APIClientException as api_error:
            self.assertEqual(str(api_error), "API call failed")
            self.assertIsNotNone(api_error.__cause__)
            self.assertIsInstance(api_error.__cause__, ValueError)

if __name__ == '__main__':
    unittest.main()
