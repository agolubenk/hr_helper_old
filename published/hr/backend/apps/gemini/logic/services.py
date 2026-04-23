import requests
import json
import time
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError


class GeminiService:
    """
    Сервис для работы с Google Gemini API
    """
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-flash-latest"
    FALLBACK_MODELS = []

    def __init__(self, api_key: str, model: str = None):
        """
        Инициализация сервиса с API ключом и опциональным выбором модели.

        Args:
            api_key: API ключ для доступа к Gemini API
            model: Название модели (если None, используется DEFAULT_MODEL)
        """
        if not api_key:
            raise ValidationError("API ключ не может быть пустым")

        self.api_key = api_key.strip()
        self.MODEL = model if model else self.DEFAULT_MODEL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key,
        })

        api_key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else "***"
        print(f"🔑 GEMINI_SERVICE: Инициализация с ключом: {api_key_preview} (длина: {len(self.api_key)}), модель: {self.MODEL}")
    
    def _make_request(self, endpoint: str, data: Dict, max_retries: int = 2) -> Tuple[bool, Dict, Optional[str]]:
        """
        Выполняет запрос к Gemini API с повторными попытками
        
        Args:
            endpoint: Конечная точка API
            data: Данные для отправки
            max_retries: Максимальное количество повторных попыток
            
        Returns:
            Tuple[bool, Dict, Optional[str]]: (успех, ответ, ошибка)
        """
        url = f"{self.BASE_URL}/{endpoint}"

        api_key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else "***"
        print(f"🌐 GEMINI_API: Запрос к {endpoint}")
        print(f"🌐 GEMINI_API: Используется ключ: {api_key_preview} (длина: {len(self.api_key)})")
        print(f"🌐 GEMINI_API: URL: {url}")
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                print(f"📤 GEMINI_API: Отправка запроса (попытка {attempt + 1}/{max_retries + 1})...")
                response = self.session.post(url, json=data, timeout=30)
                response_time = time.time() - start_time
                print(f"📥 GEMINI_API: Получен ответ за {response_time:.2f}с, статус: {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    return True, response_data, None
                else:
                    # Обработка специфических ошибок
                    try:
                        error_data = response.json()
                        if response.status_code == 503:
                            if attempt < max_retries:
                                # Ждем перед повторной попыткой
                                wait_time = (attempt + 1) * 2  # 2, 4 секунды
                                time.sleep(wait_time)
                                continue
                            else:
                                return False, {}, "Модель Gemini перегружена. Пожалуйста, попробуйте позже."
                        elif response.status_code == 429:
                            # Логируем информацию об ошибке 429
                            api_key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else "***"
                            print(f"⚠️ GEMINI_API: Ошибка 429 (превышен лимит) для ключа: {api_key_preview}")
                            print(f"⚠️ GEMINI_API: Попытка {attempt + 1}/{max_retries + 1}")
                            
                            # Извлекаем детали ошибки
                            error_details = error_data.get('error', {})
                            error_message = error_details.get('message', 'Превышен лимит запросов')
                            
                            # Проверяем, есть ли информация о времени ожидания
                            if 'retryAfter' in error_data or 'retry_after' in error_data:
                                retry_after = error_data.get('retryAfter') or error_data.get('retry_after', 60)
                                print(f"⏳ GEMINI_API: Рекомендуемое время ожидания: {retry_after} секунд")
                            
                            if attempt < max_retries:
                                # Экспоненциальная задержка: 5, 15, 45 секунд
                                wait_time = 5 * (3 ** attempt)
                                print(f"⏳ GEMINI_API: Ожидание {wait_time} секунд перед повторной попыткой...")
                                time.sleep(wait_time)
                                continue
                            else:
                                # Извлекаем полный текст ошибки для анализа
                                error_text = response.text if hasattr(response, 'text') else str(error_data)
                                
                                print(f"❌ GEMINI_API: Все попытки исчерпаны. Ошибка: {error_message}")
                                
                                # Проверяем, не установлен ли лимит в 0 (ключ не активирован)
                                if "limit: 0" in error_text:
                                    print(f"❌ GEMINI_API: ВАЖНО: Обнаружен лимит 0 - API ключ не имеет доступа к квоте!")
                                    detailed_error = f"Квота API ключа не активирована или исчерпана.\n\n{error_message}"
                                    detailed_error += "\n\n⚠️ ПРОБЛЕМА: Обнаружен 'limit: 0' - это означает отсутствие доступа к квоте."
                                    detailed_error += "\n\nВОЗМОЖНЫЕ ПРИЧИНЫ:"
                                    detailed_error += "\n1. API ключ не активирован в Google Cloud Console"
                                    detailed_error += "\n2. Gemini API не включен для проекта"
                                    detailed_error += "\n3. Квота Free tier не доступна для этого ключа"
                                    detailed_error += "\n\nРЕШЕНИЯ:"
                                    detailed_error += "\n1. Проверьте статус API ключа: https://makersuite.google.com/app/apikey"
                                    detailed_error += "\n2. Убедитесь, что Gemini API включен в Google Cloud Console"
                                    detailed_error += "\n3. Создайте новый API ключ в Google AI Studio"
                                    detailed_error += "\n4. Проверьте использование: https://ai.dev/usage?tab=rate-limit"
                                else:
                                    detailed_error = f"Превышен лимит запросов к Gemini API.\n\n{error_message}"
                                    detailed_error += "\n\nРекомендации:"
                                    detailed_error += "\n1. Подождите несколько минут (лимиты сбрасываются)"
                                    detailed_error += "\n2. Проверьте квоты в Google AI Studio: https://makersuite.google.com/app/apikey"
                                
                                return False, {}, detailed_error
                        elif response.status_code == 404:
                            # Модель не найдена - это нормально, если модель недоступна в этой версии API
                            error_message = error_data.get('error', {}).get('message', 'Модель не найдена')
                            print(f"⚠️ GEMINI_API: Ошибка 404 (модель не найдена): {error_message}")
                            return False, {}, f"Модель не найдена: {error_message}"
                        elif response.status_code == 400:
                            error_message = error_data.get('error', {}).get('message', 'Неверный запрос')
                            error_details = error_data.get('error', {})
                            print(f"❌ GEMINI_API: Ошибка 400: {error_message}")
                            print(f"❌ GEMINI_API: Детали ошибки: {json.dumps(error_details, indent=2, ensure_ascii=False)}")
                            return False, {}, f"Ошибка запроса: {error_message}"
                        else:
                            error_message = error_data.get('error', {}).get('message', response.text)
                            print(f"❌ GEMINI_API: Ошибка {response.status_code}: {error_message}")
                            print(f"❌ GEMINI_API: Полный ответ: {response.text[:500]}")
                            return False, {}, f"Ошибка API ({response.status_code}): {error_message}"
                    except json.JSONDecodeError:
                        error_msg = f"Ошибка API: {response.status_code} - {response.text}"
                        return False, {}, error_msg
                        
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return False, {}, "Превышено время ожидания запроса"
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return False, {}, "Ошибка подключения к API"
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return False, {}, f"Ошибка запроса: {str(e)}"
            except json.JSONDecodeError:
                return False, {}, "Ошибка декодирования JSON ответа"
        
        # Если все попытки исчерпаны
        return False, {}, "Превышено максимальное количество попыток"
    
    def generate_content(self, prompt: str, history: List[Dict] = None, model: str = None, max_tokens: int = 8192) -> Tuple[bool, str, Dict]:
        """
        Генерирует контент с помощью Gemini API
        
        Args:
            prompt: Текст запроса пользователя
            history: История предыдущих сообщений
            model: Модель для использования (если None, используется self.MODEL)
            
        Returns:
            Tuple[bool, str, Dict]: (успех, ответ, метаданные)
        """
        if not prompt.strip():
            return False, "Запрос не может быть пустым", {}
        
        # Используем указанную модель или модель по умолчанию
        current_model = model or self.MODEL
        
        # Формируем содержимое для API
        contents = []
        
        # Добавляем историю сообщений
        if history:
            for msg in history:
                if msg.get('role') in ['user', 'assistant']:
                    contents.append({
                        "role": msg['role'],
                        "parts": [{"text": msg['content']}]
                    })
        
        # Добавляем текущий запрос
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Данные для API
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": max_tokens,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        # Используем только указанную модель (fallback модели не поддерживаются в v1beta)
        print(f"🤖 GEMINI_API: Используется модель: {current_model}")
        
        # Выполняем запрос
        success, response_data, error = self._make_request(
            f"models/{current_model}:generateContent", 
            data
        )
        
        if not success:
            return False, error, {}
        
        # Извлекаем ответ
        try:
            if 'candidates' in response_data and response_data['candidates']:
                candidate = response_data['candidates'][0]
                
                # Проверяем блокировку безопасности
                finish_reason = candidate.get('finishReason', '')
                if finish_reason == 'SAFETY':
                    safety_ratings = candidate.get('safetyRatings', [])
                    blocked_categories = []
                    for rating in safety_ratings:
                        if rating.get('probability') in ['HIGH', 'MEDIUM']:
                            category = rating.get('category', 'UNKNOWN')
                            blocked_categories.append(category)
                    
                    error_msg = "Ответ заблокирован настройками безопасности"
                    if blocked_categories:
                        error_msg += f" (категории: {', '.join(blocked_categories)})"
                    return False, error_msg, {}
                
                if 'content' in candidate and 'parts' in candidate['content']:
                    response_text = candidate['content']['parts'][0]['text']
                    
                    # Метаданные
                    metadata = {
                        'response_time': response_data.get('response_time', 0),
                        'usage_metadata': response_data.get('usageMetadata', {}),
                        'finish_reason': finish_reason,
                        'safety_ratings': candidate.get('safetyRatings', [])
                    }
                    
                    return True, response_text, metadata
                else:
                    # Проверяем, есть ли информация о причине отсутствия контента
                    if finish_reason:
                        return False, f"Не удалось извлечь ответ из API (причина: {finish_reason})", {}
                    return False, "Не удалось извлечь ответ из API", {}
            else:
                # Проверяем наличие информации об ошибке в ответе
                if 'promptFeedback' in response_data:
                    feedback = response_data['promptFeedback']
                    if 'blockReason' in feedback:
                        return False, f"Запрос заблокирован: {feedback['blockReason']}", {}
                return False, "API не вернул кандидатов", {}
                
        except (KeyError, IndexError, TypeError) as e:
            return False, f"Ошибка обработки ответа: {str(e)}", {}
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Тестирует подключение к Gemini API
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        test_prompt = "Привет! Это тестовое сообщение. Ответь коротко."
        
        success, response, metadata = self.generate_content(test_prompt)
        
        if success:
            return True, "Подключение к Gemini API успешно установлено"
        else:
            return False, f"Ошибка подключения: {response}"
    
    def get_available_models(self) -> Tuple[bool, List[str], Optional[str]]:
        """
        Получает список доступных моделей
        
        Returns:
            Tuple[bool, List[str], Optional[str]]: (успех, модели, ошибка)
        """
        success, response_data, error = self._make_request("models", {})
        
        if not success:
            return False, [], error
        
        try:
            models = []
            if 'models' in response_data:
                for model in response_data['models']:
                    if 'name' in model:
                        models.append(model['name'])
            return True, models, None
        except (KeyError, TypeError) as e:
            return False, [], f"Ошибка обработки списка моделей: {str(e)}"
