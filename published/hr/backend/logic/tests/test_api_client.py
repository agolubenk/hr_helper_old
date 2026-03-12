"""Тесты для BaseAPIClient"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from logic.tests.test_base import BaseTestCase
from logic.base.api_client import BaseAPIClient, APIResponse

class TestAPIClient(BaseTestCase):
    """Тесты для BaseAPIClient"""
    
    def setUp(self):
        super().setUp()
        # Создаем тестовый класс, наследующий от BaseAPIClient
        class TestAPIClient(BaseAPIClient):
            def _setup_auth(self):
                """Тестовая настройка аутентификации"""
                self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})
            
            def test_connection(self):
                """Тестовый метод проверки подключения"""
                try:
                    response = self.get("test")
                    return response.get('success', False), "Test connection OK"
                except Exception as e:
                    return False, f"Test connection failed: {str(e)}"
        
        self.client = TestAPIClient(self.test_api_key, self.test_base_url, timeout=self.test_timeout)
    
    def test_init(self):
        """Тест инициализации клиента"""
        self.assertEqual(self.client.api_key, self.test_api_key)
        self.assertEqual(self.client.base_url, self.test_base_url)
        self.assertEqual(self.client.timeout, self.test_timeout)
        self.assertIsNotNone(self.client.session)
    
    def test_setup_auth(self):
        """Тест настройки аутентификации"""
        self.client._setup_auth()
        self.assertIn('Authorization', self.client.session.headers)
        self.assertEqual(self.client.session.headers['Authorization'], f'Bearer {self.test_api_key}')
    
    @patch('requests.Session.get')
    def test_get_request_success(self, mock_get):
        """Тест успешного GET запроса"""
        # Настраиваем mock
        mock_response = self.create_mock_response(200, {'success': True, 'data': 'test'})
        mock_get.return_value = mock_response
        
        # Выполняем запрос
        response = self.client.get("test")
        
        # Проверяем результат
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], 'test')
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_get_request_failure(self, mock_get):
        """Тест неудачного GET запроса"""
        # Настраиваем mock для ошибки
        mock_response = self.create_mock_response(500, {'error': 'Server error'})
        mock_get.return_value = mock_response
        
        # Выполняем запрос
        response = self.client.get("test")
        
        # Проверяем результат
        self.assertFalse(response['success'])
        self.assertIn('error', response)
        mock_get.assert_called_once()
    
    @patch('requests.Session.post')
    def test_post_request_success(self, mock_post):
        """Тест успешного POST запроса"""
        # Настраиваем mock
        mock_response = self.create_mock_response(201, {'success': True, 'id': 123})
        mock_post.return_value = mock_response
        
        # Выполняем запрос
        data = {'name': 'test', 'value': 42}
        response = self.client.post("test", data=data)
        
        # Проверяем результат
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['id'], 123)
        mock_post.assert_called_once()
    
    @patch('requests.Session.put')
    def test_put_request_success(self, mock_put):
        """Тест успешного PUT запроса"""
        # Настраиваем mock
        mock_response = self.create_mock_response(200, {'success': True, 'updated': True})
        mock_put.return_value = mock_response
        
        # Выполняем запрос
        data = {'name': 'updated'}
        response = self.client.put("test/1", data=data)
        
        # Проверяем результат
        self.assertTrue(response['success'])
        self.assertTrue(response['data']['updated'])
        mock_put.assert_called_once()
    
    @patch('requests.Session.delete')
    def test_delete_request_success(self, mock_delete):
        """Тест успешного DELETE запроса"""
        # Настраиваем mock
        mock_response = self.create_mock_response(204, {})
        mock_delete.return_value = mock_response
        
        # Выполняем запрос
        response = self.client.delete("test/1")
        
        # Проверяем результат
        self.assertTrue(response['success'])
        mock_delete.assert_called_once()
    
    def test_test_connection(self):
        """Тест проверки подключения"""
        with patch.object(self.client, 'get') as mock_get:
            mock_get.return_value = {'success': True}
            
            success, message = self.client.test_connection()
            
            self.assertTrue(success)
            self.assertEqual(message, "Test connection OK")
    
    def test_test_connection_failure(self):
        """Тест неудачной проверки подключения"""
        with patch.object(self.client, 'get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            success, message = self.client.test_connection()
            
            self.assertFalse(success)
            self.assertIn("Connection failed", message)
    
    @patch('requests.Session.get')
    def test_retry_mechanism(self, mock_get):
        """Тест механизма повторных попыток"""
        # Настраиваем mock для первых двух неудачных попыток, затем успех
        mock_responses = [
            self.create_mock_response(500, {'error': 'Server error'}),
            self.create_mock_response(500, {'error': 'Server error'}),
            self.create_mock_response(200, {'success': True})
        ]
        mock_get.side_effect = mock_responses
        
        # Выполняем запрос
        response = self.client.get("test")
        
        # Проверяем что было 3 попытки
        self.assertEqual(mock_get.call_count, 3)
        self.assertTrue(response['success'])
    
    def test_api_response_dataclass(self):
        """Тест dataclass APIResponse"""
        # Тест успешного ответа
        response = APIResponse(
            success=True,
            data={'test': 'data'},
            status_code=200
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data, {'test': 'data'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.error)
        
        # Тест ответа с ошибкой
        error_response = APIResponse(
            success=False,
            error="Test error",
            status_code=400
        )
        
        self.assertFalse(error_response.success)
        self.assertEqual(error_response.error, "Test error")
        self.assertEqual(error_response.status_code, 400)
        self.assertIsNone(error_response.data)

if __name__ == '__main__':
    unittest.main()
