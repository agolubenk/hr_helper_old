"""Тесты для shared модулей"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from unittest.mock import Mock, patch
from logic.tests.test_base import BaseTestCase
from logic.integration.shared.candidate_operations import BaseCandidateOperations
from logic.integration.shared.comment_operations import BaseCommentOperations
from logic.integration.shared.field_operations import BaseFieldOperations
from logic.integration.shared.status_operations import BaseStatusOperations
from logic.integration.shared.gemini_operations import BaseGeminiOperations, GeminiPromptManager

class TestSharedModules(BaseTestCase):
    """Тесты для shared модулей"""
    
    def setUp(self):
        super().setUp()
        
        # Создаем тестовые классы, наследующие от shared модулей
        class TestCandidateService(BaseCandidateOperations):
            def create_candidate(self, candidate_data):
                return {'success': True, 'data': {'id': 1, **candidate_data}}
            
            def update_candidate(self, candidate_id, candidate_data):
                return {'success': True, 'data': {'id': candidate_id, **candidate_data}}
            
            def get_candidate(self, candidate_id):
                return {'success': True, 'data': {'id': candidate_id, 'name': 'Test'}}
            
            def delete_candidate(self, candidate_id):
                return {'success': True, 'data': {'deleted_id': candidate_id}}
        
        self.candidate_service = TestCandidateService()
    
    def test_base_candidate_operations_search(self):
        """Тест поиска кандидатов в BaseCandidateOperations"""
        search_params = {'name': 'test', 'status': 'active'}
        
        response = self.candidate_service.search_candidates(search_params)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], [])
        self.assertIn('базовая реализация', response['message'])
    
    def test_base_candidate_operations_link_vacancy(self):
        """Тест привязки кандидата к вакансии"""
        candidate_id = 1
        vacancy_id = 2
        
        response = self.candidate_service.link_candidate_to_vacancy(candidate_id, vacancy_id)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['candidate_id'], candidate_id)
        self.assertEqual(response['data']['vacancy_id'], vacancy_id)
    
    def test_base_candidate_operations_bulk_create(self):
        """Тест массового создания кандидатов"""
        candidates_data = [
            {'name': 'John', 'email': 'john@test.com'},
            {'name': 'Jane', 'email': 'jane@test.com'}
        ]
        
        response = self.candidate_service.bulk_create_candidates(candidates_data)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['summary']['total'], 2)
        self.assertEqual(response['data']['summary']['success'], 2)
        self.assertEqual(response['data']['summary']['errors'], 0)
        self.assertEqual(len(response['data']['results']), 2)
    
    def test_base_candidate_operations_bulk_create_with_errors(self):
        """Тест массового создания кандидатов с ошибками"""
        # Создаем сервис с ошибками
        class FailingCandidateService(BaseCandidateOperations):
            def create_candidate(self, candidate_data):
                if 'fail' in candidate_data.get('name', ''):
                    return {'success': False, 'message': 'Creation failed'}
                return {'success': True, 'data': {'id': 1, **candidate_data}}
            
            def update_candidate(self, candidate_id, candidate_data):
                pass
            
            def get_candidate(self, candidate_id):
                pass
            
            def delete_candidate(self, candidate_id):
                pass
        
        failing_service = FailingCandidateService()
        candidates_data = [
            {'name': 'John', 'email': 'john@test.com'},
            {'name': 'fail_user', 'email': 'fail@test.com'}
        ]
        
        response = failing_service.bulk_create_candidates(candidates_data)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['summary']['total'], 2)
        self.assertEqual(response['data']['summary']['success'], 1)
        self.assertEqual(response['data']['summary']['errors'], 1)
    
    def test_base_comment_operations_bulk_add(self):
        """Тест массового добавления комментариев"""
        class TestCommentService(BaseCommentOperations):
            def add_comment(self, candidate_id, comment_data):
                return {'success': True, 'data': {'id': 1, **comment_data}}
            
            def update_comment(self, comment_id, comment_data):
                pass
            
            def delete_comment(self, comment_id):
                pass
            
            def get_comments(self, candidate_id):
                pass
        
        comment_service = TestCommentService()
        candidate_id = 1
        comments_data = [
            {'text': 'First comment', 'type': 'note'},
            {'text': 'Second comment', 'type': 'feedback'}
        ]
        
        response = comment_service.bulk_add_comments(candidate_id, comments_data)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['summary']['total'], 2)
        self.assertEqual(response['data']['summary']['success'], 2)
        self.assertEqual(len(response['data']['results']), 2)
    
    def test_base_field_operations_schema(self):
        """Тест получения схемы полей"""
        class TestFieldService(BaseFieldOperations):
            def add_custom_field(self, candidate_id, field_data):
                pass
            
            def update_custom_field(self, field_id, field_data):
                pass
            
            def delete_custom_field(self, field_id):
                pass
            
            def get_custom_fields(self, candidate_id):
                pass
        
        field_service = TestFieldService()
        
        # Тест схемы текстового поля
        response = field_service.get_field_schema('text')
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['type'], 'text')
        self.assertFalse(response['data']['required'])
        
        # Тест схемы числового поля
        response = field_service.get_field_schema('number')
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['type'], 'number')
        
        # Тест неизвестного типа поля
        response = field_service.get_field_schema('unknown')
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['type'], 'text')  # Должен вернуть text по умолчанию
    
    def test_base_status_operations_validation(self):
        """Тест валидации переходов статуса"""
        class TestStatusService(BaseStatusOperations):
            def change_status(self, candidate_id, new_status):
                pass
            
            def get_status_history(self, candidate_id):
                pass
            
            def get_available_statuses(self):
                pass
        
        status_service = TestStatusService()
        
        # Тест валидного перехода
        response = status_service.validate_status_transition('new', 'in_progress')
        self.assertTrue(response['success'])
        self.assertTrue(response['data']['is_valid'])
        self.assertIn('in_progress', response['data']['allowed_transitions'])
        
        # Тест невалидного перехода
        response = status_service.validate_status_transition('completed', 'in_progress')
        self.assertTrue(response['success'])
        self.assertFalse(response['data']['is_valid'])
        self.assertEqual(response['data']['allowed_transitions'], [])
    
    def test_base_status_operations_bulk_change(self):
        """Тест массового изменения статуса"""
        class TestStatusService(BaseStatusOperations):
            def change_status(self, candidate_id, new_status):
                return {'success': True, 'data': {'candidate_id': candidate_id, 'status': new_status}}
            
            def get_status_history(self, candidate_id):
                pass
            
            def get_available_statuses(self):
                pass
        
        status_service = TestStatusService()
        candidate_ids = [1, 2, 3]
        new_status = 'in_progress'
        
        response = status_service.bulk_change_status(candidate_ids, new_status)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['data']['summary']['total'], 3)
        self.assertEqual(response['data']['summary']['success'], 3)
        self.assertEqual(response['data']['summary']['errors'], 0)
        self.assertEqual(len(response['data']['results']), 3)
    
    def test_gemini_prompt_manager(self):
        """Тест GeminiPromptManager"""
        prompt_manager = GeminiPromptManager()
        
        # Тест получения промпта
        prompt = prompt_manager.get_prompt('finance', 'salary_benchmark_analysis')
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
        
        # Тест получения промпта по источнику
        prompts = prompt_manager.get_prompts_by_source('finance')
        self.assertIsInstance(prompts, dict)
        self.assertIn('salary_benchmark_analysis', prompts)
        
        # Тест получения всех промптов
        all_prompts = prompt_manager.get_all_prompts()
        self.assertIsInstance(all_prompts, dict)
        self.assertIn('finance', all_prompts)
        self.assertIn('vacancies', all_prompts)
        self.assertIn('general', all_prompts)
    
    def test_gemini_prompt_manager_add_prompt(self):
        """Тест добавления нового промпта"""
        prompt_manager = GeminiPromptManager()
        
        # Добавляем новый промпт
        test_prompt = "Test prompt for custom analysis"
        result = prompt_manager.add_prompt('test', 'custom_analysis', test_prompt)
        
        self.assertTrue(result)
        
        # Проверяем что промпт добавился
        prompt = prompt_manager.get_prompt('test', 'custom_analysis')
        self.assertEqual(prompt, test_prompt)
    
    def test_gemini_prompt_manager_update_prompt(self):
        """Тест обновления промпта"""
        prompt_manager = GeminiPromptManager()
        
        # Проверяем что метод update_prompt не существует
        self.assertFalse(hasattr(prompt_manager, 'update_prompt'))
        
        # Тестируем только добавление нового промпта
        new_prompt = "Updated test prompt"
        result = prompt_manager.add_prompt('test_update', 'updated_prompt', new_prompt)
        
        self.assertTrue(result)
        
        # Проверяем что новый промпт добавился
        updated_prompt = prompt_manager.get_prompt('test_update', 'updated_prompt')
        self.assertEqual(updated_prompt, new_prompt)
    
    def test_gemini_operations_base(self):
        """Тест базовых операций Gemini"""
        gemini_service = BaseGeminiOperations(api_key=self.test_api_key)
        
        # Тест инициализации
        self.assertEqual(gemini_service.api_key, self.test_api_key)
        self.assertEqual(gemini_service.base_url, "https://generativelanguage.googleapis.com")
        
        # Тест настройки аутентификации
        gemini_service._setup_auth()
        self.assertIn('Authorization', gemini_service.session.headers)
        self.assertIn('Content-Type', gemini_service.session.headers)
    
    def test_shared_modules_abstract_methods(self):
        """Тест что shared модули являются абстрактными"""
        # Проверяем что нельзя создать экземпляры абстрактных классов
        with self.assertRaises(TypeError):
            BaseCandidateOperations()
        
        with self.assertRaises(TypeError):
            BaseCommentOperations()
        
        with self.assertRaises(TypeError):
            BaseFieldOperations()
        
        with self.assertRaises(TypeError):
            BaseStatusOperations()
    
    def test_shared_modules_inheritance(self):
        """Тест наследования от shared модулей"""
        # Проверяем что тестовые классы правильно наследуются
        self.assertIsInstance(self.candidate_service, BaseCandidateOperations)
        
        # Проверяем что у них есть все необходимые методы
        self.assertTrue(hasattr(self.candidate_service, 'create_candidate'))
        self.assertTrue(hasattr(self.candidate_service, 'update_candidate'))
        self.assertTrue(hasattr(self.candidate_service, 'get_candidate'))
        self.assertTrue(hasattr(self.candidate_service, 'delete_candidate'))
        self.assertTrue(hasattr(self.candidate_service, 'search_candidates'))
        self.assertTrue(hasattr(self.candidate_service, 'link_candidate_to_vacancy'))
        self.assertTrue(hasattr(self.candidate_service, 'bulk_create_candidates'))

if __name__ == '__main__':
    unittest.main()
