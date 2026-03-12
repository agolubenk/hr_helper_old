"""Интеграционные тесты для logic модулей"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from unittest.mock import Mock, patch, MagicMock
from logic.tests.test_base import BaseTestCase
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.exceptions import LogicBaseException, APIClientException
from logic.integration.shared.candidate_operations import BaseCandidateOperations
from logic.integration.shared.gemini_operations import BaseGeminiOperations, GeminiPromptManager

class TestAPIClient(BaseAPIClient):
    """Тестовый API клиент для интеграционных тестов"""
    
    def _setup_auth(self):
        """Настройка аутентификации"""
        self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})
    
    def test_connection(self):
        """Тест подключения"""
        try:
            response = self.get("test")
            return response.get('success', False), "Connection OK"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

class TestCandidateService(BaseCandidateOperations):
    """Тестовый сервис кандидатов для интеграционных тестов"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def create_candidate(self, candidate_data):
        response = self.api_client.post("candidates", data=candidate_data)
        if response.get('success'):
            return UnifiedResponseHandler.success_response(
                response['data'], "Candidate created"
            )
        else:
            return UnifiedResponseHandler.error_response(
                response.get('error', 'Unknown error')
            )
    
    def update_candidate(self, candidate_id, candidate_data):
        response = self.api_client.put(f"candidates/{candidate_id}", data=candidate_data)
        if response.get('success'):
            return UnifiedResponseHandler.success_response(
                response['data'], "Candidate updated"
            )
        else:
            return UnifiedResponseHandler.error_response(
                response.get('error', 'Unknown error')
            )
    
    def get_candidate(self, candidate_id):
        response = self.api_client.get(f"candidates/{candidate_id}")
        if response.get('success'):
            return UnifiedResponseHandler.success_response(
                response['data'], "Candidate retrieved"
            )
        else:
            return UnifiedResponseHandler.error_response(
                response.get('error', 'Unknown error')
            )
    
    def delete_candidate(self, candidate_id):
        response = self.api_client.delete(f"candidates/{candidate_id}")
        if response.get('success'):
            return UnifiedResponseHandler.success_response(
                response['data'], "Candidate deleted"
            )
        else:
            return UnifiedResponseHandler.error_response(
                response.get('error', 'Unknown error')
            )

class IntegrationTestCase(BaseTestCase):
    """Интеграционные тесты"""
    
    def setUp(self):
        super().setUp()
        self.api_client = TestAPIClient(self.test_api_key, self.test_base_url)
        self.candidate_service = TestCandidateService(self.api_client)
    
    @patch('requests.Session.get')
    def test_full_candidate_workflow(self, mock_get):
        """Тестируем полный рабочий процесс с кандидатами"""
        # 1. Тестируем подключение
        mock_response = self.create_mock_response(200, {'success': True})
        mock_get.return_value = mock_response
        
        response = self.api_client.test_connection()
        self.assertTrue(response[0])
        self.assertEqual(response[1], "Connection OK")
        
        # 2. Создаем кандидата
        with patch('requests.Session.post') as mock_post:
            mock_post.return_value = self.create_mock_response(
                201, {'success': True, 'data': {'id': 1, 'name': 'John Doe'}}
            )
            
            candidate_data = {'name': 'John Doe', 'email': 'john@example.com'}
            response = self.candidate_service.create_candidate(candidate_data)
            
            self.assertTrue(response['success'])
            self.assertEqual(response['data']['name'], 'John Doe')
            self.assertEqual(response['message'], 'Candidate created')
        
        # 3. Получаем кандидата
        mock_get.return_value = self.create_mock_response(
            200, {'success': True, 'data': {'id': 1, 'name': 'John Doe'}}
        )
        
        response = self.candidate_service.get_candidate(1)
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['name'], 'John Doe')
        
        # 4. Обновляем кандидата
        with patch('requests.Session.put') as mock_put:
            mock_put.return_value = self.create_mock_response(
                200, {'success': True, 'data': {'id': 1, 'name': 'John Updated'}}
            )
            
            update_data = {'name': 'John Updated'}
            response = self.candidate_service.update_candidate(1, update_data)
            
            self.assertTrue(response['success'])
            self.assertEqual(response['data']['name'], 'John Updated')
        
        # 5. Удаляем кандидата
        with patch('requests.Session.delete') as mock_delete:
            mock_delete.return_value = self.create_mock_response(
                204, {'success': True, 'data': {'deleted': True}}
            )
            
            response = self.candidate_service.delete_candidate(1)
            self.assertTrue(response['success'])
            self.assertEqual(response['message'], 'Candidate deleted')
    
    def test_error_handling_workflow(self):
        """Тестируем обработку ошибок в полном workflow"""
        # 1. Тестируем ошибку подключения
        with patch('requests.Session.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            success, message = self.api_client.test_connection()
            self.assertFalse(success)
            self.assertIn("Connection failed", message)
        
        # 2. Тестируем ошибку создания кандидата
        with patch('requests.Session.post') as mock_post:
            mock_post.return_value = self.create_mock_response(
                400, {'success': False, 'error': 'Validation failed'}
            )
            
            candidate_data = {'name': ''}  # Невалидные данные
            response = self.candidate_service.create_candidate(candidate_data)
            
            self.assertFalse(response['success'])
            self.assertIn('Validation failed', response['error'])
        
        # 3. Тестируем ошибку получения несуществующего кандидата
        with patch('requests.Session.get') as mock_get:
            mock_get.return_value = self.create_mock_response(
                404, {'success': False, 'error': 'Not found'}
            )
            
            response = self.candidate_service.get_candidate(999)
            self.assertFalse(response['success'])
            self.assertIn('Not found', response['error'])
    
    def test_unified_response_integration(self):
        """Тестируем интеграцию UnifiedResponseHandler"""
        # Тестируем успешный ответ
        success_response = UnifiedResponseHandler.success_response(
            {'test': 'data'}, "Test successful"
        )
        
        self.assertTrue(success_response['success'])
        self.assertEqual(success_response['data'], {'test': 'data'})
        self.assertEqual(success_response['message'], "Test successful")
        
        # Тестируем ответ с ошибкой
        error_response = UnifiedResponseHandler.error_response(
            "Test error", error_code="TEST_ERROR"
        )
        
        self.assertFalse(error_response['success'])
        self.assertEqual(error_response['error'], "Test error")
        self.assertEqual(error_response['error_code'], "TEST_ERROR")
    
    def test_exception_handling_integration(self):
        """Тестируем интеграцию обработки исключений"""
        # Тестируем LogicBaseException
        try:
            raise LogicBaseException("Test logic exception")
        except LogicBaseException as e:
            error_response = UnifiedResponseHandler.error_response(
                str(e), error_code="LOGIC_ERROR"
            )
            self.assertFalse(error_response['success'])
            self.assertEqual(error_response['error_code'], "LOGIC_ERROR")
        
        # Тестируем APIClientException
        try:
            raise APIClientException("API request failed")
        except APIClientException as e:
            error_response = UnifiedResponseHandler.error_response(
                str(e), error_code="API_ERROR"
            )
            self.assertFalse(error_response['success'])
            self.assertEqual(error_response['error_code'], "API_ERROR")
    
    def test_gemini_integration(self):
        """Тестируем интеграцию с Gemini"""
        # Тестируем GeminiPromptManager
        prompt_manager = GeminiPromptManager()
        
        # Получаем промпт
        prompt = prompt_manager.get_prompt('finance', 'salary_benchmark_analysis')
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)
        
        # Добавляем новый промпт
        test_prompt = "Test prompt for integration"
        result = prompt_manager.add_prompt('test', 'integration_test', test_prompt)
        self.assertTrue(result)
        
        # Проверяем что промпт добавился
        retrieved_prompt = prompt_manager.get_prompt('test', 'integration_test')
        self.assertEqual(retrieved_prompt, test_prompt)
        
        # Тестируем BaseGeminiOperations
        gemini_service = BaseGeminiOperations(api_key=self.test_api_key)
        
        # Проверяем инициализацию
        self.assertEqual(gemini_service.api_key, self.test_api_key)
        self.assertIsNotNone(gemini_service.session)
        
        # Проверяем настройку аутентификации
        gemini_service._setup_auth()
        self.assertIn('Authorization', gemini_service.session.headers)
    
    def test_bulk_operations_integration(self):
        """Тестируем интеграцию массовых операций"""
        # Тестируем массовое создание кандидатов
        candidates_data = [
            {'name': 'John', 'email': 'john@test.com'},
            {'name': 'Jane', 'email': 'jane@test.com'},
            {'name': 'Bob', 'email': 'bob@test.com'}
        ]
        
        # Мокаем успешные создания
        with patch.object(self.candidate_service, 'create_candidate') as mock_create:
            mock_create.side_effect = [
                {'success': True, 'data': {'id': 1, 'name': 'John'}},
                {'success': True, 'data': {'id': 2, 'name': 'Jane'}},
                {'success': True, 'data': {'id': 3, 'name': 'Bob'}}
            ]
            
            response = self.candidate_service.bulk_create_candidates(candidates_data)
            
            self.assertTrue(response['success'])
            self.assertEqual(response['data']['summary']['total'], 3)
            self.assertEqual(response['data']['summary']['success'], 3)
            self.assertEqual(response['data']['summary']['errors'], 0)
    
    def test_performance_integration(self):
        """Тестируем производительность интеграции"""
        import time
        
        # Тестируем производительность UnifiedResponseHandler
        start_time = time.time()
        
        for i in range(1000):
            UnifiedResponseHandler.success_response(
                {'iteration': i}, f"Test {i}"
            )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Проверяем что 1000 операций выполняются быстро
        self.assertLess(execution_time, 1.0)  # Менее 1 секунды
        
        # Тестируем производительность GeminiPromptManager
        prompt_manager = GeminiPromptManager()
        
        start_time = time.time()
        
        for i in range(100):
            prompt_manager.get_prompt('finance', 'salary_benchmark_analysis')
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Проверяем что 100 операций выполняются быстро
        self.assertLess(execution_time, 0.1)  # Менее 0.1 секунды
    
    def test_data_consistency_integration(self):
        """Тестируем консистентность данных в интеграции"""
        # Создаем тестовые данные
        test_data = {
            'user': {
                'id': 1,
                'name': 'Test User',
                'email': 'test@example.com',
                'permissions': ['read', 'write']
            },
            'metadata': {
                'created_at': '2024-01-01T00:00:00Z',
                'version': '1.0'
            }
        }
        
        # Тестируем что данные сохраняются консистентно
        response = UnifiedResponseHandler.success_response(test_data, "Data consistency test")
        
        self.assertEqual(response['data'], test_data)
        self.assertEqual(response['data']['user']['id'], 1)
        self.assertEqual(response['data']['user']['name'], 'Test User')
        self.assertEqual(len(response['data']['user']['permissions']), 2)
        self.assertEqual(response['data']['metadata']['version'], '1.0')
        
        # Тестируем сериализацию/десериализацию
        import json
        
        json_str = json.dumps(response)
        deserialized = json.loads(json_str)
        
        self.assertEqual(deserialized, response)
        self.assertEqual(deserialized['data']['user']['name'], 'Test User')
    
    def test_error_propagation_integration(self):
        """Тестируем распространение ошибок в интеграции"""
        # Тестируем цепочку ошибок
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise APIError("API call failed", 500) from e
        except APIError as api_error:
            # Проверяем что ошибка правильно обрабатывается
            error_response = UnifiedResponseHandler.error_response(
                str(api_error),
                error_code="API_ERROR",
                status_code=api_error.status_code
            )
            
            self.assertFalse(error_response['success'])
            self.assertEqual(error_response['error'], "API call failed")
            self.assertEqual(error_response['error_code'], "API_ERROR")
            self.assertEqual(error_response['status_code'], 500)
    
    def test_mock_integration(self):
        """Тестируем интеграцию с mock объектами"""
        # Создаем mock API клиент
        mock_client = Mock(spec=BaseAPIClient)
        mock_client.api_key = "mock_key"
        mock_client.base_url = "https://mock.api.com"
        
        # Настраиваем mock методы
        mock_client.get.return_value = {'success': True, 'data': {'test': 'data'}}
        mock_client.post.return_value = {'success': True, 'data': {'id': 1}}
        
        # Тестируем интеграцию с mock клиентом
        mock_candidate_service = TestCandidateService(mock_client)
        
        # Тестируем создание кандидата
        response = mock_candidate_service.create_candidate({'name': 'Mock User'})
        self.assertTrue(response['success'])
        
        # Проверяем что mock методы были вызваны
        mock_client.post.assert_called_once()
        
        # Тестируем получение кандидата
        response = mock_candidate_service.get_candidate(1)
        self.assertTrue(response['success'])
        
        # Проверяем что mock методы были вызваны
        mock_client.get.assert_called_with("candidates/1")

if __name__ == '__main__':
    unittest.main()
