"""Сериализаторы для Gemini приложения"""
from rest_framework import serializers
from .models import ChatSession, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Сериализатор для сообщений чата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - role: роль отправителя (user, assistant, system)
    - content: содержимое сообщения
    - session: ID сессии чата
    
    ИСТОЧНИКИ ДАННЫХ:
    - ChatMessage модель из apps.gemini.models
    
    ОБРАБОТКА:
    - Сериализация полей сообщения чата
    - Автоматическое заполнение timestamp и session
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями сообщения чата
    
    СВЯЗИ:
    - Использует: ChatMessage модель
    - Передает данные в: DRF API responses
    - Может вызываться из: ChatMessage API viewsets
    """
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp', 'session']
        read_only_fields = ['id', 'timestamp', 'session']


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания сообщений чата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - content: содержимое сообщения (обязательно)
    
    ИСТОЧНИКИ ДАННЫХ:
    - ChatMessage модель из apps.gemini.models
    
    ОБРАБОТКА:
    - Сериализация полей для создания сообщения
    - Валидация содержимого сообщения
    - Проверка на пустое содержимое
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными созданного сообщения
    
    СВЯЗИ:
    - Использует: ChatMessage модель
    - Передает данные в: DRF API responses
    - Может вызываться из: ChatMessage API viewsets (create action)
    """
    
    class Meta:
        model = ChatMessage
        fields = ['content']
    
    def validate_content(self, value):
        """Валидация содержимого сообщения"""
        if not value or not value.strip():
            raise serializers.ValidationError("Содержимое сообщения не может быть пустым")
        return value.strip()


class ChatSessionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для сессий чата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - title: название сессии чата
    - is_active: статус активности сессии
    
    ИСТОЧНИКИ ДАННЫХ:
    - ChatSession модель из apps.gemini.models
    
    ОБРАБОТКА:
    - Сериализация полей сессии чата
    - Вычисляемые поля: message_count, last_message
    - Автоматическое заполнение created_at, updated_at
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями сессии чата
    
    СВЯЗИ:
    - Использует: ChatSession модель
    - Передает данные в: DRF API responses
    - Может вызываться из: ChatSession API viewsets
    """
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'is_active', 
                  'message_count', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_message_count(self, obj):
        """Получить количество сообщений в сессии"""
        return obj.messages.count()
    
    def get_last_message(self, obj):
        """Получить последнее сообщение в сессии"""
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return {
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'timestamp': last_msg.timestamp,
                'role': last_msg.role
            }
        return None


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детального просмотра сессии чата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - ChatSession объект для детального просмотра
    
    ИСТОЧНИКИ ДАННЫХ:
    - ChatSession модель из apps.gemini.models
    - ChatMessageSerializer: для сообщений в сессии
    
    ОБРАБОТКА:
    - Сериализация полей сессии чата
    - Включение всех сообщений в сессии
    - Вычисляемые поля: message_count, last_message
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с детальными данными сессии чата
    
    СВЯЗИ:
    - Использует: ChatSession модель, ChatMessageSerializer
    - Передает данные в: DRF API responses
    - Может вызываться из: ChatSession API viewsets (retrieve action)
    """
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'is_active', 
                  'messages', 'message_count']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_message_count(self, obj):
        """Получить количество сообщений в сессии"""
        return obj.messages.count()


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания сессии чата
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - title: название сессии чата (опционально)
    - is_active: статус активности сессии (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - ChatSession модель из apps.gemini.models
    
    ОБРАБОТКА:
    - Сериализация полей для создания сессии
    - Валидация данных
    - Автоматическое заполнение created_at, updated_at
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными созданной сессии чата
    
    СВЯЗИ:
    - Использует: ChatSession модель
    - Передает данные в: DRF API responses
    - Может вызываться из: ChatSession API viewsets (create action)
    """
    
    class Meta:
        model = ChatSession
        fields = ['title']
    
    def validate_title(self, value):
        """Валидация названия сессии"""
        if not value or not value.strip():
            raise serializers.ValidationError("Название сессии не может быть пустым")
        return value.strip()


class GeminiApiRequestSerializer(serializers.Serializer):
    """
    Сериализатор для запросов к Gemini API
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - prompt: промпт для отправки в Gemini API
    - session_id: ID сессии чата (опционально)
    - model: модель Gemini для использования (опционально)
    
    ИСТОЧНИКИ ДАННЫЕ:
    - request.data: данные запроса к Gemini API
    
    ОБРАБОТКА:
    - Сериализация данных для запроса к Gemini API
    - Валидация промпта
    - Проверка обязательных полей
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными запроса к Gemini API
    
    СВЯЗИ:
    - Использует: request.data
    - Передает данные в: Gemini API
    - Может вызываться из: Gemini API viewsets
    """
    text = serializers.CharField(max_length=10000)
    context = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    max_tokens = serializers.IntegerField(default=1000, min_value=1, max_value=4000)
    analysis_type = serializers.ChoiceField(
        choices=[
            ('general', 'Общий анализ'),
            ('sentiment', 'Анализ настроения'),
            ('summary', 'Краткое изложение'),
            ('keywords', 'Ключевые слова'),
            ('structure', 'Анализ структуры')
        ],
        default='general',
        required=False
    )
    
    def validate_text(self, value):
        """Валидация текста для анализа"""
        if not value or not value.strip():
            raise serializers.ValidationError("Текст для анализа не может быть пустым")
        return value.strip()


class GeminiStatsSerializer(serializers.Serializer):
    """
    Сериализатор для статистики Gemini
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - total_sessions: общее количество сессий
    - active_sessions: количество активных сессий
    - total_messages: общее количество сообщений
    - recent_sessions: последние сессии
    - api_usage: статистика использования API
    
    ИСТОЧНИКИ ДАННЫЕ:
    - ChatSession.objects: агрегированные данные сессий
    - ChatMessage.objects: агрегированные данные сообщений
    - ChatSessionSerializer: для последних сессий
    
    ОБРАБОТКА:
    - Сериализация статистических данных
    - Агрегация данных по различным критериям
    - Формирование структурированной статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект со статистикой Gemini
    
    СВЯЗИ:
    - Использует: ChatSessionSerializer
    - Передает данные в: DRF API responses
    - Может вызываться из: Gemini API viewsets (stats action)
    """
    total_sessions = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    total_messages = serializers.IntegerField()
    user_messages = serializers.IntegerField()
    assistant_messages = serializers.IntegerField()
    recent_messages_30d = serializers.IntegerField()
    has_api_key = serializers.BooleanField()
    last_activity = serializers.DateTimeField(allow_null=True)
