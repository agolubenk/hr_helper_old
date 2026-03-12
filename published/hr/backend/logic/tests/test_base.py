"""Базовые тесты для всех logic модулей"""
import unittest
import sys
import os
from unittest.mock import Mock, patch

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class BaseTestCase(unittest.TestCase):
    """Базовый класс для всех тестов logic"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_api_key = "test_api_key_123"
        self.test_base_url = "https://api.test.com"
        self.test_timeout = 30
    
    def tearDown(self):
        """Очистка после каждого теста"""
        pass
    
    def create_mock_response(self, status_code=200, data=None, error=None):
        """Создание mock ответа"""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = data or {}
        mock_response.text = str(data) if data else ""
        mock_response.ok = status_code < 400
        return mock_response

def run_all_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == '__main__':
    unittest.main()

