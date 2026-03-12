from rest_framework import serializers
from ..models import ChatSession, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    """Сериализатор для сообщений чата"""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'session', 'role', 'content', 'timestamp',
            'tokens_used', 'response_time'
        ]
        read_only_fields = ['id', 'timestamp']


class ChatSessionSerializer(serializers.ModelSerializer):
    """Сериализатор для сессий чата"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    messages_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'user', 'user_username', 'title', 'is_active',
            'messages_count', 'last_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'messages_count', 'last_message']
    
    def get_messages_count(self, obj):
        """Возвращает количество сообщений в сессии"""
        return obj.messages.count()
    
    def get_last_message(self, obj):
        """Возвращает последнее сообщение"""
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'id': last_msg.id,
                'role': last_msg.role,
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'timestamp': last_msg.timestamp
            }
        return None


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор для сессий чата с сообщениями"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'user', 'user_username', 'title', 'is_active',
            'messages', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания сообщений чата"""
    
    class Meta:
        model = ChatMessage
        fields = ['session', 'role', 'content']
    
    def validate_role(self, value):
        """Валидация роли сообщения"""
        if value not in ['user', 'assistant', 'system']:
            raise serializers.ValidationError("Неверная роль сообщения")
        return value


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания сессий чата"""
    
    class Meta:
        model = ChatSession
        fields = ['title']
    
    def create(self, validated_data):
        """Создание сессии чата"""
        user = self.context['request'].user
        validated_data['user'] = user
        return ChatSession.objects.create(**validated_data)


class GeminiApiRequestSerializer(serializers.Serializer):
    """Сериализатор для запросов к Gemini API"""
    prompt = serializers.CharField(max_length=4000)
    session_id = serializers.IntegerField(required=False)
    max_tokens = serializers.IntegerField(default=1000, min_value=1, max_value=4000)
    temperature = serializers.FloatField(default=0.7, min_value=0.0, max_value=1.0)
    save_to_session = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Валидация параметров запроса"""
        if attrs['max_tokens'] < 1:
            raise serializers.ValidationError("Максимальное количество токенов должно быть не менее 1")
        
        if attrs['temperature'] < 0.0 or attrs['temperature'] > 1.0:
            raise serializers.ValidationError("Температура должна быть от 0.0 до 1.0")
        
        return attrs


class GeminiStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики Gemini"""
    total_sessions = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    total_messages = serializers.IntegerField()
    total_tokens_used = serializers.IntegerField()
    average_response_time = serializers.FloatField()
    sessions_by_user = serializers.DictField()
    recent_sessions = ChatSessionSerializer(many=True)
    top_prompts = serializers.ListField(child=serializers.DictField())
