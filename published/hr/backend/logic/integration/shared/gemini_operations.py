"""Базовые операции с Gemini AI для всех интеграций"""
from logic.base.response_handler import UnifiedResponseHandler
from logic.base.api_client import BaseAPIClient
import json

class BaseGeminiOperations(BaseAPIClient):
    """
    Базовый класс для операций с Gemini AI
    
    ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
    ИСТОЧНИКИ ДАННЫЕ: Google Gemini API
    ОБРАБОТКА: Базовый класс для операций с Gemini AI
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты анализа через Gemini AI
    СВЯЗИ: BaseAPIClient, UnifiedResponseHandler
    ФОРМАТ: Базовый класс с методами для работы с Gemini
    """
    
    def __init__(self, api_key="", base_url="https://generativelanguage.googleapis.com", timeout=30):
        """
        Инициализация базовых операций с Gemini AI
        
        ВХОДЯЩИЕ ДАННЫЕ: api_key (строка), base_url (строка), timeout (число)
        ИСТОЧНИКИ ДАННЫЕ: Параметры подключения к Gemini API
        ОБРАБОТКА: Настройка базовых параметров для работы с Gemini
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный клиент Gemini
        СВЯЗИ: BaseAPIClient
        ФОРМАТ: Экземпляр класса BaseGeminiOperations
        """
        super().__init__(api_key, base_url, timeout=timeout)
    
    def _setup_auth(self):
        """
        Настройка аутентификации для Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: self.api_key
        ОБРАБОТКА: Настройка заголовков авторизации для Gemini API
        ВЫХОДЯЩИЕ ДАННЫЕ: Настроенные заголовки
        СВЯЗИ: Нет
        ФОРМАТ: Обновление session.headers
        """
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
    
    def test_connection(self):
        """
        Тест подключения к Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет
        ИСТОЧНИКИ ДАННЫЕ: Gemini API
        ОБРАБОТКА: Проверка доступности Gemini API
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат тестирования подключения
        СВЯЗИ: Gemini API
        ФОРМАТ: Кортеж (bool, строка с сообщением)
        """
        try:
            # Простой тест подключения
            response = self.get("v1beta/models")
            return response.get('success', False), "Gemini API connection OK"
        except Exception as e:
            return False, f"Gemini API connection failed: {str(e)}"
    
    def direct_analysis(self, data):
        """
        Прямой анализ данных без промптов (как в оригинальном Gemini)
        
        ВХОДЯЩИЕ ДАННЫЕ: data (словарь или список)
        ИСТОЧНИКИ ДАННЫЕ: Переданные данные для анализа
        ОБРАБОТКА: Прямой анализ данных через Gemini API
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат анализа
        СВЯЗИ: Gemini API, UnifiedResponseHandler
        ФОРМАТ: Словарь с результатом анализа
        """
        try:
            # Формируем запрос для прямого анализа
            analysis_request = {
                'contents': [{
                    'parts': [{
                        'text': json.dumps(data, ensure_ascii=False)
                    }]
                }],
                'generationConfig': {
                    'temperature': 0.7,
                    'topK': 40,
                    'topP': 0.95,
                    'maxOutputTokens': 1024
                }
            }
            
            response = self.post("v1beta/models/gemini-pro:generateContent", json=analysis_request)
            
            if response.get('success'):
                # Извлекаем результат анализа
                candidates = response.get('data', {}).get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {}).get('parts', [])
                    if content:
                        analysis_text = content[0].get('text', '')
                        
                        return UnifiedResponseHandler.success_response(
                            {
                                'analysis': analysis_text,
                                'type': 'direct',
                                'raw_data': data
                            },
                            "Прямой анализ выполнен успешно"
                        )
                
                return UnifiedResponseHandler.error_response("Не удалось получить результат анализа")
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка прямого анализа: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def prompt_based_analysis(self, data, prompt_source='finance'):
        """Анализ с использованием промптов из Finance/Vacancies"""
        try:
            # Получаем промпт из соответствующего источника
            prompt_manager = GeminiPromptManager()
            prompt = prompt_manager.get_prompt(prompt_source, data.get('analysis_type', 'general'))
            
            if not prompt:
                return UnifiedResponseHandler.error_response(f"Промпт для {prompt_source} не найден")
            
            # Формируем запрос с промптом
            prompt_request = {
                'contents': [{
                    'parts': [{
                        'text': f"{prompt}\n\nДанные для анализа:\n{json.dumps(data, ensure_ascii=False)}"
                    }]
                }],
                'generationConfig': {
                    'temperature': 0.5,
                    'topK': 40,
                    'topP': 0.95,
                    'maxOutputTokens': 2048
                }
            }
            
            response = self.post("v1beta/models/gemini-pro:generateContent", json=prompt_request)
            
            if response.get('success'):
                # Извлекаем результат анализа
                candidates = response.get('data', {}).get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {}).get('parts', [])
                    if content:
                        analysis_text = content[0].get('text', '')
                        
                        return UnifiedResponseHandler.success_response(
                            {
                                'analysis': analysis_text,
                                'type': 'prompt_based',
                                'prompt_source': prompt_source,
                                'prompt': prompt,
                                'raw_data': data
                            },
                            "Prompt-based анализ выполнен успешно"
                        )
                
                return UnifiedResponseHandler.error_response("Не удалось получить результат анализа")
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка prompt-based анализа: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_prompt_from_source(self, source, analysis_type):
        """Получение промпта из источника"""
        try:
            prompt_manager = GeminiPromptManager()
            prompt = prompt_manager.get_prompt(source, analysis_type)
            
            if prompt:
                return UnifiedResponseHandler.success_response(
                    {'prompt': prompt, 'source': source, 'type': analysis_type},
                    "Промпт получен"
                )
            else:
                return UnifiedResponseHandler.error_response(f"Промпт для {source}/{analysis_type} не найден")
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def process_gemini_response(self, response_data):
        """Обработка ответа от Gemini"""
        try:
            if not response_data:
                return UnifiedResponseHandler.error_response("Пустой ответ от Gemini")
            
            # Извлекаем текст из ответа Gemini
            candidates = response_data.get('candidates', [])
            if not candidates:
                return UnifiedResponseHandler.error_response("Нет кандидатов в ответе Gemini")
            
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if not parts:
                return UnifiedResponseHandler.error_response("Нет частей в контенте Gemini")
            
            text = parts[0].get('text', '')
            if not text:
                return UnifiedResponseHandler.error_response("Пустой текст в ответе Gemini")
            
            # Обрабатываем текст (можно добавить дополнительную логику)
            processed_text = text.strip()
            
            return UnifiedResponseHandler.success_response(
                {
                    'original_text': text,
                    'processed_text': processed_text,
                    'length': len(processed_text)
                },
                "Ответ Gemini обработан"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def test_connection(self):
        """Тест подключения к Gemini"""
        try:
            # Простой тестовый запрос
            test_data = {'test': 'connection', 'timestamp': 'now'}
            result = self.direct_analysis(test_data)
            
            if result.get('success'):
                return UnifiedResponseHandler.success_response(
                    result.get('data'),
                    "Подключение к Gemini работает"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка подключения к Gemini: {result.get('message', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))

class GeminiPromptManager:
    """Менеджер промптов для Gemini"""
    
    def __init__(self):
        self._prompts = {
            'finance': {
                'salary_benchmark_analysis': """
Проанализируйте данные зарплатного бенчмарка и предоставьте детальный анализ:

1. Общая оценка уровня зарплат
2. Сравнение с рынком
3. Рекомендации по корректировке
4. Тренды и прогнозы
5. Выводы и рекомендации

Будьте конкретными и практичными в своих рекомендациях.
""",
                'finance_dashboard': """
Проанализируйте финансовые данные дашборда и предоставьте:

1. Ключевые показатели эффективности
2. Проблемные области
3. Возможности для улучшения
4. Рекомендации по оптимизации
5. Прогноз развития

Фокус на практических рекомендациях для HR-процессов.
""",
                'salary_trends': """
Проанализируйте тренды зарплат и предоставьте:

1. Основные тренды по позициям
2. Изменения по валютам
3. Сезонные колебания
4. Прогноз на будущее
5. Рекомендации по планированию зарплат

Используйте данные для обоснования рекомендаций.
"""
            },
            'vacancies': {
                'vacancy_analysis': """
Проанализируйте данные вакансии и предоставьте:

1. Оценка привлекательности вакансии
2. Конкурентоспособность зарплаты
3. Соответствие требованиям рынка
4. Рекомендации по улучшению
5. Стратегия поиска кандидатов

Будьте конкретными в рекомендациях.
""",
                'candidate_matching': """
Проанализируйте соответствие кандидата вакансии:

1. Соответствие навыков требованиям
2. Опыт работы
3. Образование
4. Зарплатные ожидания
5. Общая оценка кандидата

Предоставьте рекомендации по найму.
"""
            },
            'general': {
                'general_analysis': """
Проанализируйте предоставленные данные и дайте детальный анализ:

1. Основные выводы
2. Проблемы и возможности
3. Рекомендации
4. Следующие шаги

Будьте конкретными и практичными.
"""
            }
        }
    
    def get_prompt(self, source, analysis_type):
        """Получение промпта по источнику и типу анализа"""
        try:
            return self._prompts.get(source, {}).get(analysis_type, self._prompts.get('general', {}).get('general_analysis'))
        except Exception:
            return None
    
    def add_prompt(self, source, analysis_type, prompt_text):
        """Добавление нового промпта"""
        try:
            if source not in self._prompts:
                self._prompts[source] = {}
            
            self._prompts[source][analysis_type] = prompt_text
            return True
        except Exception:
            return False
    
    def get_all_prompts(self):
        """Получение всех промптов"""
        return self._prompts
    
    def get_prompts_by_source(self, source):
        """Получение промптов по источнику"""
        return self._prompts.get(source, {})
