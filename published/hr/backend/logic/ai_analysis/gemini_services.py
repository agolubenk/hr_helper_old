"""Сервисы для работы с Gemini AI"""
import requests
import json
import time
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError
from logic.base.api_client import BaseAPIClient


class GeminiService(BaseAPIClient):
    """
    Сервис для работы с Google Gemini API
    Наследуется от BaseAPIClient для унифицированной работы с API
    
    ВХОДЯЩИЕ ДАННЫЕ: API ключи, текстовые данные, сообщения
    ИСТОЧНИКИ ДАННЫХ: Google Gemini API
    ОБРАБОТКА: Отправка запросов к Gemini API, генерация ответов, анализ текста
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты генерации и анализа от Gemini AI
    СВЯЗИ: logic.base.api_client.BaseAPIClient, Google Gemini API
    ФОРМАТ: Словари с результатами операций
    """
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-2.0-flash"
    
    def __init__(self, api_key: str):
        """
        Инициализация сервиса с API ключом
        
        ВХОДЯЩИЕ ДАННЫЕ: api_key (строка с API ключом)
        ИСТОЧНИКИ ДАННЫХ: Переданный API ключ
        ОБРАБОТКА: Валидация ключа, настройка HTTP сессии
        ВЫХОДЯЩИЕ ДАННЫЕ: Инициализированный сервис
        СВЯЗИ: logic.base.api_client.BaseAPIClient
        ФОРМАТ: Экземпляр класса GeminiService
        """
        if not api_key:
            raise ValidationError("API ключ не может быть пустым")
        
        # Инициализируем базовый класс с правильными параметрами
        super().__init__(api_key, self.BASE_URL)
    
    def _setup_auth(self):
        """
        Настройка аутентификации для Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (использует self.api_key)
        ИСТОЧНИКИ ДАННЫХ: self.api_key
        ОБРАБОТКА: Настройка аутентификации через API ключ в URL
        ВЫХОДЯЩИЕ ДАННЫЕ: Настроенная аутентификация
        СВЯЗИ: requests.Session
        ФОРМАТ: Нет (настройка заголовков сессии)
        """
        # Для Gemini API аутентификация происходит через API ключ в URL
        # Дополнительные заголовки не нужны
        pass
    
    def _make_request(self, endpoint: str, data: Dict, max_retries: int = 2) -> Tuple[bool, Dict, Optional[str]]:
        """
        Выполняет запрос к Gemini API с повторными попытками
        
        ВХОДЯЩИЕ ДАННЫЕ: endpoint (строка), data (словарь), max_retries (число)
        ИСТОЧНИКИ ДАННЫХ: Google Gemini API
        ОБРАБОТКА: Отправка HTTP запроса, обработка ошибок, повторные попытки
        ВЫХОДЯЩИЕ ДАННЫЕ: Кортеж (успех, ответ, ошибка)
        СВЯЗИ: Google Gemini API
        ФОРМАТ: Tuple[bool, Dict, Optional[str]]
        """
        url = f"{self.BASE_URL}/{endpoint}?key={self.api_key}"
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                response = self.session.post(url, json=data, timeout=30)
                request_time = time.time() - start_time
                
                if response.status_code == 200:
                    response_data = response.json()
                    return True, response_data, None
                
                elif response.status_code == 429:
                    # Rate limit - ждем и повторяем
                    if attempt < max_retries:
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                    else:
                        return False, {}, "Превышен лимит запросов к API"
                
                elif response.status_code == 400:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Ошибка API')
                    return False, {}, f"Ошибка API: {error_message}"
                
                else:
                    return False, {}, f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    continue
                return False, {}, "Таймаут запроса к API"
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return False, {}, f"Ошибка сети: {str(e)}"
                
            except Exception as e:
                return False, {}, f"Неожиданная ошибка: {str(e)}"
        
        return False, {}, "Не удалось выполнить запрос после всех попыток"
    
    def test_connection(self):
        """
        Тестирование подключения к Gemini API
        
        ВХОДЯЩИЕ ДАННЫЕ: Нет (использует self.api_key)
        ИСТОЧНИКИ ДАННЫХ: Google Gemini API
        ОБРАБОТКА: Отправка тестового запроса для проверки подключения
        ВЫХОДЯЩИЕ ДАННЫЕ: APIResponse с результатом тестирования
        СВЯЗИ: Google Gemini API
        ФОРМАТ: APIResponse
        """
        from logic.base.api_client import APIResponse
        
        try:
            # Простой тестовый запрос
            test_data = {
                "contents": [{
                    "parts": [{"text": "Привет! Это тест подключения."}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 10
                }
            }
            
            success, response, error = self._make_request(
                f"models/{self.MODEL}:generateContent", 
                test_data
            )
            
            if success:
                return APIResponse(
                    success=True,
                    data={"message": "Подключение к Gemini API успешно"}
                )
            else:
                return APIResponse(
                    success=False,
                    data={"error": error or "Неизвестная ошибка подключения"}
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                data={"error": f"Ошибка тестирования: {str(e)}"}
            )
    
    def generate_response(self, prompt: str, context: str = "", max_tokens: int = 1000) -> Dict:
        """
        Генерация ответа на основе промпта
        
        ВХОДЯЩИЕ ДАННЫЕ: prompt (строка), context (строка), max_tokens (число)
        ИСТОЧНИКИ ДАННЫХ: Google Gemini API
        ОБРАБОТКА: Формирование запроса, отправка в Gemini API, извлечение ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом генерации
        СВЯЗИ: Google Gemini API
        ФОРМАТ: Словарь с ключами success, response, usage, raw_response
        """
        try:
            # Формируем содержимое для запроса
            content_text = prompt
            if context:
                content_text = f"Контекст: {context}\n\nЗапрос: {prompt}"
            
            request_data = {
                "contents": [{
                    "parts": [{"text": content_text}]
                }],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.7,
                    "topP": 0.8,
                    "topK": 40
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH", 
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }
            
            success, response, error = self._make_request(
                f"models/{self.MODEL}:generateContent", 
                request_data
            )
            
            if success:
                # Извлекаем текст ответа
                candidates = response.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        generated_text = parts[0].get('text', '')
                        
                        return {
                            'success': True,
                            'response': generated_text,
                            'usage': response.get('usageMetadata', {}),
                            'raw_response': response
                        }
                
                return {
                    'success': False,
                    'error': 'Не удалось получить ответ от модели'
                }
            else:
                return {
                    'success': False,
                    'error': error or 'Неизвестная ошибка генерации'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка генерации: {str(e)}'
            }
    
    def analyze_text(self, text: str, analysis_type: str = "general", max_tokens: int = 1000) -> Dict:
        """
        Анализ текста с помощью Gemini
        
        ВХОДЯЩИЕ ДАННЫЕ: text (строка), analysis_type (строка), max_tokens (число)
        ИСТОЧНИКИ ДАННЫХ: Google Gemini API
        ОБРАБОТКА: Формирование промпта для анализа, отправка в Gemini API
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом анализа
        СВЯЗИ: Google Gemini API, self.generate_response()
        ФОРМАТ: Словарь с результатом анализа
        """
        try:
            # Формируем промпт в зависимости от типа анализа
            prompts = {
                "general": "Проанализируй следующий текст и дай краткую характеристику:",
                "sentiment": "Определи эмоциональную окраску следующего текста:",
                "summary": "Создай краткое изложение следующего текста:",
                "keywords": "Выдели ключевые слова и фразы из следующего текста:",
                "structure": "Проанализируй структуру следующего текста:"
            }
            
            prompt = prompts.get(analysis_type, prompts["general"])
            full_prompt = f"{prompt}\n\n{text}"
            
            return self.generate_response(full_prompt, max_tokens=max_tokens)
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка анализа: {str(e)}'
            }
    
    def chat_completion(self, messages: List[Dict], max_tokens: int = 1000) -> Dict:
        """
        Завершение чата на основе истории сообщений
        
        ВХОДЯЩИЕ ДАННЫЕ: messages (список словарей), max_tokens (число)
        ИСТОЧНИКИ ДАННЫХ: Google Gemini API
        ОБРАБОТКА: Преобразование сообщений в формат Gemini, отправка запроса
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом завершения чата
        СВЯЗИ: Google Gemini API
        ФОРМАТ: Словарь с ключами success, response, usage, raw_response
        """
        try:
            # Преобразуем сообщения в формат Gemini
            contents = []
            for message in messages:
                role = message.get('role', 'user')
                content = message.get('content', '')
                
                if role == 'user':
                    contents.append({
                        "parts": [{"text": content}],
                        "role": "user"
                    })
                elif role == 'assistant':
                    contents.append({
                        "parts": [{"text": content}],
                        "role": "model"
                    })
            
            request_data = {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.7,
                    "topP": 0.8,
                    "topK": 40
                }
            }
            
            success, response, error = self._make_request(
                f"models/{self.MODEL}:generateContent", 
                request_data
            )
            
            if success:
                candidates = response.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        generated_text = parts[0].get('text', '')
                        
                        return {
                            'success': True,
                            'response': generated_text,
                            'usage': response.get('usageMetadata', {}),
                            'raw_response': response
                        }
                
                return {
                    'success': False,
                    'error': 'Не удалось получить ответ от модели'
                }
            else:
                return {
                    'success': False,
                    'error': error or 'Неизвестная ошибка завершения чата'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка завершения чата: {str(e)}'
            }
