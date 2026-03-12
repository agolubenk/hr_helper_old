from rest_framework import serializers
from .models import Interviewer, InterviewRule


class InterviewerSerializer(serializers.ModelSerializer):
    """Сериализатор для интервьюеров"""
    full_name = serializers.SerializerMethodField()
    short_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Interviewer
        fields = [
            'id', 'first_name', 'last_name', 'middle_name', 'email',
            'calendar_link', 'is_active', 'full_name', 'short_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'full_name', 'short_name']
    
    def get_full_name(self, obj):
        """Возвращает полное имя интервьюера"""
        return obj.get_full_name()
    
    def get_short_name(self, obj):
        """Возвращает краткое имя интервьюера"""
        return obj.get_short_name()
    
    def validate_email(self, value):
        """Валидация уникальности email"""
        if Interviewer.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Интервьюер с таким email уже существует")
        return value


class InterviewerCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания интервьюера"""
    
    class Meta:
        model = Interviewer
        fields = [
            'first_name', 'last_name', 'middle_name', 'email',
            'calendar_link', 'is_active'
        ]
    
    def validate_email(self, value):
        """Валидация уникальности email"""
        if Interviewer.objects.filter(email=value).exists():
            raise serializers.ValidationError("Интервьюер с таким email уже существует")
        return value


class InterviewerListSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор для списка интервьюеров"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Interviewer
        fields = [
            'id', 'first_name', 'last_name', 'email', 'full_name',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_full_name(self, obj):
        """Возвращает полное имя интервьюера"""
        return obj.get_full_name()


class InterviewerStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики интервьюеров"""
    total_interviewers = serializers.IntegerField()
    active_interviewers = serializers.IntegerField()
    inactive_interviewers = serializers.IntegerField()
    by_first_letter = serializers.DictField()
    recent_interviewers = InterviewerListSerializer(many=True)


class InterviewRuleSerializer(serializers.ModelSerializer):
    """Сериализатор для правил интервью"""
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = InterviewRule
        fields = [
            'id', 'name', 'description', 'duration_minutes', 'duration_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'duration_display']
    
    def get_duration_display(self, obj):
        """Возвращает отформатированное отображение длительности"""
        hours = obj.duration_minutes // 60
        minutes = obj.duration_minutes % 60
        
        if hours > 0:
            if minutes > 0:
                return f"{hours}ч {minutes}м"
            else:
                return f"{hours}ч"
        else:
            return f"{minutes}м"


class InterviewRuleCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания правила интервью"""
    
    class Meta:
        model = InterviewRule
        fields = [
            'name', 'description', 'duration_minutes'
        ]
    
    def validate_duration_minutes(self, value):
        """Валидация длительности"""
        if value <= 0:
            raise serializers.ValidationError("Длительность должна быть больше 0 минут")
        if value > 480:  # 8 часов
            raise serializers.ValidationError("Длительность не может превышать 8 часов")
        return value