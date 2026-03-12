"""Тесты для UnifiedResponseHandler"""
import unittest
from logic.tests.test_base import BaseTestCase
from logic.base.response_handler import UnifiedResponseHandler

class TestUnifiedResponseHandler(BaseTestCase):
    """Тесты для UnifiedResponseHandler"""
    
    def test_success_response_basic(self):
        """Тест базового успешного ответа"""
        data = {'test': 'data', 'id': 123}
        message = "Test successful"
        
        response = UnifiedResponseHandler.success_response(data, message)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], data)
        self.assertEqual(response['message'], message)
        self.assertNotIn('error', response)
    
    def test_success_response_with_metadata(self):
        """Тест успешного ответа с метаданными"""
        data = {'users': [{'id': 1, 'name': 'test'}], 'metadata': {'count': 1, 'page': 1}}
        message = "Users retrieved"
        
        response = UnifiedResponseHandler.success_response(data, message)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], data)
        self.assertEqual(response['message'], message)
    
    def test_error_response_basic(self):
        """Тест базового ответа с ошибкой"""
        error_message = "Test error occurred"
        
        response = UnifiedResponseHandler.error_response(error_message)
        
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], error_message)
        self.assertNotIn('data', response)
        self.assertNotIn('message', response)
    
    def test_error_response_with_code(self):
        """Тест ответа с ошибкой и кодом"""
        error_message = "Validation failed"
        error_code = "VALIDATION_ERROR"
        status_code = 400
        
        response = UnifiedResponseHandler.error_response(
            error_message, 
            error_code=error_code, 
            status_code=status_code
        )
        
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], error_message)
        self.assertEqual(response['error_code'], error_code)
    
    def test_error_response_with_details(self):
        """Тест ответа с ошибкой и деталями"""
        error_message = "Multiple errors found"
        details = [
            {'field': 'email', 'message': 'Invalid email format'},
            {'field': 'password', 'message': 'Password too short'}
        ]
        
        response = UnifiedResponseHandler.error_response(
            error_message,
            error_code="VALIDATION_ERROR",
            details=details
        )
        
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], error_message)
        self.assertEqual(response['details'], details)
    
    def test_pagination_response(self):
        """Тест ответа с пагинацией"""
        data = {
            'items': [{'id': i, 'name': f'item_{i}'} for i in range(1, 11)],
            'pagination': {
                'page': 1,
                'per_page': 10,
                'total': 25,
                'total_pages': 3
            }
        }
        message = "Items retrieved"
        
        response = UnifiedResponseHandler.success_response(data, message)
        
        self.assertTrue(response['success'])
        self.assertEqual(len(response['data']['items']), 10)
        self.assertEqual(response['data']['pagination']['total'], 25)
    
    def test_empty_data_response(self):
        """Тест ответа с пустыми данными"""
        response = UnifiedResponseHandler.success_response([], "No data found")
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], [])
        self.assertEqual(response['message'], "No data found")
    
    def test_none_data_response(self):
        """Тест ответа с None данными"""
        response = UnifiedResponseHandler.success_response(None, "Operation completed")
        
        self.assertTrue(response['success'])
        self.assertEqual(response['message'], "Operation completed")
        # None данные не включаются в ответ
        self.assertNotIn('data', response)
    
    def test_complex_data_response(self):
        """Тест ответа со сложными данными"""
        complex_data = {
            'user': {
                'id': 1,
                'name': 'John Doe',
                'email': 'john@example.com',
                'permissions': ['read', 'write'],
                'profile': {
                    'avatar': 'avatar.jpg',
                    'settings': {
                        'theme': 'dark',
                        'notifications': True
                    }
                }
            },
            'stats': {
                'total_actions': 150,
                'last_login': '2024-01-01T12:00:00Z'
            }
        }
        
        response = UnifiedResponseHandler.success_response(
            complex_data, 
            "User profile retrieved"
        )
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], complex_data)
        self.assertEqual(response['data']['user']['name'], 'John Doe')
        self.assertEqual(len(response['data']['user']['permissions']), 2)
    
    def test_error_response_types(self):
        """Тест различных типов ошибок"""
        # Validation error
        validation_response = UnifiedResponseHandler.error_response(
            "Invalid input", 
            error_code="VALIDATION_ERROR",
            status_code=400
        )
        self.assertFalse(validation_response['success'])
        self.assertEqual(validation_response['error_code'], "VALIDATION_ERROR")
        
        # Authentication error
        auth_response = UnifiedResponseHandler.error_response(
            "Unauthorized", 
            error_code="AUTH_ERROR",
            status_code=401
        )
        self.assertFalse(auth_response['success'])
        self.assertEqual(auth_response['error_code'], "AUTH_ERROR")
        
        # Server error
        server_response = UnifiedResponseHandler.error_response(
            "Internal server error", 
            error_code="SERVER_ERROR",
            status_code=500
        )
        self.assertFalse(server_response['success'])
        self.assertEqual(server_response['error_code'], "SERVER_ERROR")
    
    def test_response_consistency(self):
        """Тест консистентности формата ответов"""
        # Успешный ответ
        success_response = UnifiedResponseHandler.success_response({'test': 'data'}, "Success")
        
        # Проверяем наличие обязательных полей
        self.assertIn('success', success_response)
        self.assertIn('data', success_response)
        self.assertIn('message', success_response)
        
        # Проверяем отсутствие полей ошибок
        self.assertNotIn('error', success_response)
        self.assertNotIn('error_code', success_response)
        
        # Ответ с ошибкой
        error_response = UnifiedResponseHandler.error_response("Error occurred")
        
        # Проверяем наличие обязательных полей
        self.assertIn('success', error_response)
        self.assertIn('error', error_response)
        
        # Проверяем отсутствие полей успеха
        self.assertNotIn('data', error_response)
        self.assertNotIn('message', error_response)
    
    def test_response_serialization(self):
        """Тест сериализации ответов в JSON"""
        import json
        
        response = UnifiedResponseHandler.success_response(
            {'test': 'data', 'metadata': {'version': '1.0'}}, 
            "Test message"
        )
        
        # Проверяем что ответ можно сериализовать в JSON
        json_str = json.dumps(response)
        self.assertIsInstance(json_str, str)
        
        # Проверяем что можно десериализовать обратно
        deserialized = json.loads(json_str)
        self.assertEqual(deserialized, response)
    
    def test_edge_cases(self):
        """Тест граничных случаев"""
        # Очень длинное сообщение
        long_message = "A" * 1000
        response = UnifiedResponseHandler.success_response({}, long_message)
        self.assertEqual(response['message'], long_message)
        
        # Специальные символы в данных
        special_data = {
            'unicode': 'тест 🚀',
            'quotes': '"test" \'test\'',
            'newlines': 'line1\nline2',
            'tabs': 'col1\tcol2'
        }
        response = UnifiedResponseHandler.success_response(special_data, "Special chars")
        self.assertEqual(response['data'], special_data)
        
        # Пустая строка ошибки
        response = UnifiedResponseHandler.error_response("")
        self.assertEqual(response['error'], "")

if __name__ == '__main__':
    unittest.main()
