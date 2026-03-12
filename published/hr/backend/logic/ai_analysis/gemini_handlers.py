"""Обработчики для Gemini AI"""
import json
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.gemini.models import ChatSession, ChatMessage
from logic.ai_analysis.gemini_services import GeminiService

User = get_user_model()
logger = logging.getLogger(__name__)


class MessageApiHandler:
    """
    Обработчик для работы с сообщениями в API
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные сообщений, HTTP запросы
    ИСТОЧНИКИ ДАННЫХ: База данных (ChatSession, ChatMessage), Gemini API
    ОБРАБОТКА: Отправка сообщений, создание ответов, управление сессиями
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты обработки сообщений
    СВЯЗИ: apps.gemini.models, logic.ai_analysis.gemini_services.GeminiService
    ФОРМАТ: Словари с результатами операций
    """
    
    @staticmethod
    def send_message_api_handler(data, request):
        """
        Обработчик отправки сообщения через API
        
        ВХОДЯЩИЕ ДАННЫЕ: data (session_id, content), request.user
        ИСТОЧНИКИ ДАННЫХ: База данных (ChatSession, ChatMessage), Gemini API
        ОБРАБОТКА: Валидация данных, создание сообщения, отправка в Gemini AI
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом операции и ID сообщений
        СВЯЗИ: apps.gemini.models, logic.ai_analysis.gemini_services.GeminiService
        ФОРМАТ: Словарь с ключами success, user_message_id, assistant_message_id
        """
        try:
            session_id = data.get('session_id')
            content = data.get('content', '').strip()
            
            if not session_id or not content:
                return {
                    'success': False,
                    'error': 'ID сессии и содержимое сообщения обязательны'
                }
            
            # Получаем сессию
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                return {
                    'success': False,
                    'error': 'Сессия не найдена'
                }
            
            # Проверяем API ключ
            if not request.user.gemini_api_key:
                return {
                    'success': False,
                    'error': 'API ключ Gemini не настроен'
                }
            
            # Создаем сообщение пользователя
            user_message = ChatMessage.objects.create(
                session=session,
                role='user',
                content=content,
                timestamp=timezone.now()
            )
            
            # Получаем историю сообщений
            messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
            messages_data = []
            
            for msg in messages:
                messages_data.append({
                    'role': msg.role,
                    'content': msg.content
                })
            
            # Отправляем запрос к Gemini
            gemini_service = GeminiService(request.user.gemini_api_key)
            result = gemini_service.chat_completion(messages_data)
            
            if result['success']:
                # Создаем ответное сообщение
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=result['response'],
                    timestamp=timezone.now()
                )
                
                # Обновляем время последнего обновления сессии
                session.updated_at = timezone.now()
                session.save()
                
                return {
                    'success': True,
                    'user_message_id': user_message.id,
                    'assistant_message_id': assistant_message.id,
                    'response': result['response']
                }
            else:
                # Создаем сообщение об ошибке
                error_message = ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=f"Ошибка: {result['error']}",
                    timestamp=timezone.now()
                )
                
                return {
                    'success': False,
                    'error': result['error'],
                    'error_message_id': error_message.id
                }
                
        except Exception as e:
            logger.error(f"Ошибка в send_message_api_handler: {str(e)}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}'
            }
    
    @staticmethod
    def send_message_viewset_handler(session, content, user):
        """
        Обработчик отправки сообщения для ViewSet
        
        ВХОДЯЩИЕ ДАННЫЕ: session (ChatSession), content (текст), user (пользователь)
        ИСТОЧНИКИ ДАННЫХ: База данных (ChatMessage), Gemini API
        ОБРАБОТКА: Создание сообщения пользователя, отправка в Gemini AI, создание ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом операции и ID сообщений
        СВЯЗИ: apps.gemini.models.ChatMessage, logic.ai_analysis.gemini_services.GeminiService
        ФОРМАТ: Словарь с ключами success, user_message_id, assistant_message_id
        """
        try:
            # Создаем сообщение пользователя
            user_message = ChatMessage.objects.create(
                session=session,
                role='user',
                content=content,
                timestamp=timezone.now()
            )
            
            # Получаем историю сообщений
            messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
            messages_data = []
            
            for msg in messages:
                messages_data.append({
                    'role': msg.role,
                    'content': msg.content
                })
            
            # Отправляем запрос к Gemini
            gemini_service = GeminiService(user.gemini_api_key)
            result = gemini_service.chat_completion(messages_data)
            
            if result['success']:
                # Создаем ответное сообщение
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=result['response'],
                    timestamp=timezone.now()
                )
                
                # Обновляем время последнего обновления сессии
                session.updated_at = timezone.now()
                session.save()
                
                return {
                    'success': True,
                    'user_message_id': user_message.id,
                    'assistant_message_id': assistant_message.id,
                    'response': result['response']
                }
            else:
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            logger.error(f"Ошибка в send_message_viewset_handler: {str(e)}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}'
            }


class ApiKeyApiHandler:
    """
    Обработчик для работы с API ключами
    
    ВХОДЯЩИЕ ДАННЫЕ: API ключи, HTTP запросы
    ИСТОЧНИКИ ДАННЫХ: Gemini API, база данных (User)
    ОБРАБОТКА: Тестирование API ключей, сохранение в профиле пользователя
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты тестирования и сохранения ключей
    СВЯЗИ: logic.ai_analysis.gemini_services.GeminiService, User модель
    ФОРМАТ: Словари с результатами операций
    """
    
    @staticmethod
    def test_api_key_handler(data, request):
        """
        Обработчик тестирования API ключа
        
        ВХОДЯЩИЕ ДАННЫЕ: data (api_key), request.user
        ИСТОЧНИКИ ДАННЫХ: Gemini API, база данных (User)
        ОБРАБОТКА: Валидация ключа, тестирование подключения, сохранение в профиле
        ВЫХОДЯЩИЕ ДАННЫЕ: Словарь с результатом тестирования
        СВЯЗИ: logic.ai_analysis.gemini_services.GeminiService, User модель
        ФОРМАТ: Словарь с ключами success, message/error
        """
        try:
            api_key = data.get('api_key', '').strip()
            
            if not api_key:
                return {
                    'success': False,
                    'error': 'API ключ не указан'
                }
            
            # Тестируем API ключ
            gemini_service = GeminiService(api_key)
            success, message = gemini_service.test_connection()
            
            if success:
                # Сохраняем API ключ в профиль пользователя
                request.user.gemini_api_key = api_key
                request.user.save()
                
                return {
                    'success': True,
                    'message': 'API ключ успешно сохранен и протестирован'
                }
            else:
                return {
                    'success': False,
                    'error': message
                }
                
        except Exception as e:
            logger.error(f"Ошибка в test_api_key_handler: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка тестирования API ключа: {str(e)}'
            }


class StatsApiHandler:
    """
    Обработчик для получения статистики
    
    ВХОДЯЩИЕ ДАННЫЕ: HTTP запросы, данные пользователя
    ИСТОЧНИКИ ДАННЫХ: База данных (ChatSession, ChatMessage)
    ОБРАБОТКА: Агрегация статистики по сессиям и сообщениям
    ВЫХОДЯЩИЕ ДАННЫЕ: Статистические данные и контекст для дашборда
    СВЯЗИ: apps.gemini.models (ChatSession, ChatMessage)
    ФОРМАТ: Словари со статистическими данными
    """
    
    @staticmethod
    def get_dashboard_handler(data, request):
        """
        Обработчик получения данных для дашборда
        
        ВХОДЯЩИЕ ДАННЫЕ: data, request.user
        ИСТОЧНИКИ ДАННЫХ: База данных (ChatSession, ChatMessage)
        ОБРАБОТКА: Получение статистики сессий и сообщений, последние записи
        ВЫХОДЯЩИЕ ДАННЫЕ: Контекст для отображения дашборда
        СВЯЗИ: apps.gemini.models (ChatSession, ChatMessage)
        ФОРМАТ: Словарь с контекстом дашборда
        """
        try:
            user = request.user
            
            # Получаем статистику сессий
            total_sessions = ChatSession.objects.filter(user=user, is_active=True).count()
            recent_sessions = ChatSession.objects.filter(
                user=user, 
                is_active=True
            ).order_by('-updated_at')[:5]
            
            # Получаем статистику сообщений
            total_messages = ChatMessage.objects.filter(session__user=user).count()
            recent_messages = ChatMessage.objects.filter(
                session__user=user
            ).order_by('-timestamp')[:10]
            
            # Проверяем наличие API ключа
            has_api_key = bool(user.gemini_api_key)
            
            context = {
                'title': 'Gemini AI Dashboard',
                'has_api_key': has_api_key,
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'recent_sessions': recent_sessions,
                'recent_messages': recent_messages,
                'user': user,
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Ошибка в get_dashboard_handler: {str(e)}")
            return {
                'error': f'Ошибка получения данных дашборда: {str(e)}'
            }
    
    @staticmethod
    def get_stats_handler(data, request):
        """
        Обработчик получения общей статистики
        
        ВХОДЯЩИЕ ДАННЫЕ: data, request.user
        ИСТОЧНИКИ ДАННЫХ: База данных (ChatSession, ChatMessage)
        ОБРАБОТКА: Агрегация статистики по сессиям, сообщениям, активности
        ВЫХОДЯЩИЕ ДАННЫЕ: Подробная статистика использования
        СВЯЗИ: apps.gemini.models (ChatSession, ChatMessage)
        ФОРМАТ: Словарь со статистическими данными
        """
        try:
            user = request.user
            
            # Статистика сессий
            total_sessions = ChatSession.objects.filter(user=user, is_active=True).count()
            active_sessions = ChatSession.objects.filter(
                user=user, 
                is_active=True,
                updated_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
            
            # Статистика сообщений
            total_messages = ChatMessage.objects.filter(session__user=user).count()
            user_messages = ChatMessage.objects.filter(
                session__user=user, 
                role='user'
            ).count()
            assistant_messages = ChatMessage.objects.filter(
                session__user=user, 
                role='assistant'
            ).count()
            
            # Статистика за последние 30 дней
            from django.db.models import Count
            from django.utils import timezone
            from datetime import timedelta
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_messages = ChatMessage.objects.filter(
                session__user=user,
                timestamp__gte=thirty_days_ago
            ).count()
            
            stats_data = {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'user_messages': user_messages,
                'assistant_messages': assistant_messages,
                'recent_messages_30d': recent_messages,
                'has_api_key': bool(user.gemini_api_key),
                'last_activity': None
            }
            
            # Последняя активность
            last_message = ChatMessage.objects.filter(
                session__user=user
            ).order_by('-timestamp').first()
            
            if last_message:
                stats_data['last_activity'] = last_message.timestamp.isoformat()
            
            return stats_data
            
        except Exception as e:
            logger.error(f"Ошибка в get_stats_handler: {str(e)}")
            return {
                'error': f'Ошибка получения статистики: {str(e)}'
            }
