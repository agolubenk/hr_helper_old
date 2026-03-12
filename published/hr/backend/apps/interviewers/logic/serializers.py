from rest_framework import serializers
from ..models import Interviewer, InterviewRule
from apps.finance.models import Grade


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
        fields = ['id', 'full_name', 'email', 'is_active']
        read_only_fields = ['id', 'full_name']
    
    def get_full_name(self, obj):
        """Возвращает полное имя интервьюера"""
        return obj.get_full_name()


class InterviewRuleSerializer(serializers.ModelSerializer):
    """Сериализатор для правил привлечения интервьюеров"""
    min_grade_name = serializers.CharField(source='min_grade.name', read_only=True)
    max_grade_name = serializers.CharField(source='max_grade.name', read_only=True)
    grade_range = serializers.SerializerMethodField()
    
    class Meta:
        model = InterviewRule
        fields = [
            'id', 'name', 'description', 'daily_limit', 'weekly_limit',
            'min_grade', 'min_grade_name', 'max_grade', 'max_grade_name',
            'grade_range', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'min_grade_name', 'max_grade_name', 'grade_range']
    
    def get_grade_range(self, obj):
        """Возвращает диапазон грейдов"""
        return obj.get_grade_range()
    
    def validate(self, attrs):
        """Валидация правил"""
        daily_limit = attrs.get('daily_limit')
        weekly_limit = attrs.get('weekly_limit')
        
        if daily_limit and (daily_limit < 1 or daily_limit > 50):
            raise serializers.ValidationError("Лимит в день должен быть от 1 до 50")
        
        if weekly_limit and (weekly_limit < 1 or weekly_limit > 200):
            raise serializers.ValidationError("Лимит в неделю должен быть от 1 до 200")
        
        if daily_limit and weekly_limit and daily_limit > weekly_limit:
            raise serializers.ValidationError("Дневной лимит не может быть больше недельного")
        
        return attrs


class InterviewRuleCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания правил привлечения интервьюеров"""
    
    class Meta:
        model = InterviewRule
        fields = [
            'name', 'description', 'daily_limit', 'weekly_limit',
            'min_grade', 'max_grade', 'is_active'
        ]
    
    def validate(self, attrs):
        """Валидация правил"""
        daily_limit = attrs.get('daily_limit')
        weekly_limit = attrs.get('weekly_limit')
        
        if daily_limit and (daily_limit < 1 or daily_limit > 50):
            raise serializers.ValidationError("Лимит в день должен быть от 1 до 50")
        
        if weekly_limit and (weekly_limit < 1 or weekly_limit > 200):
            raise serializers.ValidationError("Лимит в неделю должен быть от 1 до 200")
        
        if daily_limit and weekly_limit and daily_limit > weekly_limit:
            raise serializers.ValidationError("Дневной лимит не может быть больше недельного")
        
        return attrs


class InterviewerStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики интервьюеров"""
    total_interviewers = serializers.IntegerField()
    active_interviewers = serializers.IntegerField()
    inactive_interviewers = serializers.IntegerField()
    interviewers_with_calendar = serializers.IntegerField()
    recent_interviewers = InterviewerListSerializer(many=True)
