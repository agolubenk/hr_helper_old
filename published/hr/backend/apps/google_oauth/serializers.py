"""Сериализаторы для Google OAuth приложения"""
from rest_framework import serializers
from .models import (
    GoogleOAuthAccount, SyncSettings, ScorecardPathSettings, 
    SlotsSettings, Invite, HRScreening, QuestionTemplate
)


class GoogleOAuthAccountSerializer(serializers.ModelSerializer):
    """
    Сериализатор для Google OAuth аккаунта
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - google_id: ID аккаунта Google
    - email: email аккаунта
    - name: имя пользователя
    - picture_url: URL аватара
    - scopes: области доступа
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleOAuthAccount модель из apps.google_oauth.models
    
    ОБРАБОТКА:
    - Сериализация полей аккаунта Google
    - Вычисляемые поля: is_token_valid, needs_refresh, available_services
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными Google OAuth аккаунта
    
    СВЯЗИ:
    - Использует: GoogleOAuthAccount модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Google OAuth API viewsets
    """
    is_token_valid = serializers.SerializerMethodField()
    needs_refresh = serializers.SerializerMethodField()
    available_services = serializers.SerializerMethodField()
    
    class Meta:
        model = GoogleOAuthAccount
        fields = [
            'id', 'google_id', 'email', 'name', 'picture_url',
            'scopes', 'created_at', 'updated_at', 'last_sync_at',
            'is_token_valid', 'needs_refresh', 'available_services'
        ]
        read_only_fields = [
            'id', 'google_id', 'email', 'name', 'picture_url',
            'scopes', 'created_at', 'updated_at', 'last_sync_at'
        ]
    
    def get_is_token_valid(self, obj):
        """Проверяет, действителен ли токен"""
        return obj.is_token_valid()
    
    def get_needs_refresh(self, obj):
        """Проверяет, нужно ли обновить токен"""
        return obj.needs_refresh()
    
    def get_available_services(self, obj):
        """Получить доступные Google сервисы"""
        return obj.get_available_services()


class SyncSettingsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для настроек синхронизации
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - auto_sync: автоматическая синхронизация
    - sync_interval: интервал синхронизации
    - sync_calendar, sync_drive, sync_sheets: настройки синхронизации сервисов
    
    ИСТОЧНИКИ ДАННЫХ:
    - SyncSettings модель из apps.google_oauth.models
    
    ОБРАБОТКА:
    - Сериализация настроек синхронизации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с настройками синхронизации
    
    СВЯЗИ:
    - Использует: SyncSettings модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Google OAuth API viewsets
    """
    
    class Meta:
        model = SyncSettings
        fields = [
            'id', 'auto_sync', 'sync_interval', 'last_sync',
            'sync_calendar', 'sync_drive', 'sync_sheets',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ScorecardPathSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек путей scorecard"""
    
    class Meta:
        model = ScorecardPathSettings
        fields = [
            'id', 'scorecard_path', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SlotsSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек слотов"""
    
    class Meta:
        model = SlotsSettings
        fields = [
            'id',
            'current_week_prefix',
            'next_week_prefix',
            'all_slots_prefix',
            'separator_text',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InviteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для приглашений
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - candidate_email: email кандидата
    - candidate_name: имя кандидата
    - vacancy: ID вакансии
    - scheduled_time: время проведения
    - status: статус приглашения
    
    ИСТОЧНИКИ ДАННЫХ:
    - Invite модель из apps.google_oauth.models
    - Vacancy модель для связанных данных
    
    ОБРАБОТКА:
    - Сериализация полей приглашения
    - Вычисляемые поля: vacancy_name, formatted_time
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными приглашения
    
    СВЯЗИ:
    - Использует: Invite модель, Vacancy модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Google OAuth API viewsets
    """
    
    class Meta:
        model = Invite
        fields = [
            'id', 'candidate_name', 'candidate_email', 'interview_date',
            'interview_time', 'interview_type', 'interviewer_name',
            'meeting_link', 'calendar_event_id', 'calendar_event_url',
            'google_meet_url', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'calendar_event_id', 'calendar_event_url',
            'google_meet_url', 'created_at', 'updated_at'
        ]
    
    def validate_interview_date(self, value):
        """Валидация даты интервью"""
        from django.utils import timezone
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Дата интервью не может быть в прошлом")
        return value


class HRScreeningSerializer(serializers.ModelSerializer):
    """
    Сериализатор для HR-скринингов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - candidate_name: имя кандидата
    - candidate_email: email кандидата
    - vacancy: ID вакансии
    - screening_date: дата скрининга
    - notes: заметки по скринингу
    
    ИСТОЧНИКИ ДАННЫХ:
    - HRScreening модель из apps.google_oauth.models
    - Vacancy модель для связанных данных
    
    ОБРАБОТКА:
    - Сериализация полей HR-скрининга
    - Вычисляемые поля: vacancy_name, formatted_date
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными HR-скрининга
    
    СВЯЗИ:
    - Использует: HRScreening модель, Vacancy модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Google OAuth API viewsets
    """
    
    class Meta:
        model = HRScreening
        fields = [
            'id', 'candidate_name', 'candidate_email', 'interview_date',
            'interview_time', 'interviewer_name', 'meeting_link',
            'score', 'comments', 'recommendation', 'next_steps',
            'determined_grade', 'huntflow_grade_id', 'chatsession_id',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_score(self, value):
        """Валидация оценки"""
        if value is not None and (value < 0 or value > 10):
            raise serializers.ValidationError("Оценка должна быть от 0 до 10")
        return value


class QuestionTemplateSerializer(serializers.ModelSerializer):
    """Сериализатор для шаблонов вопросов"""
    
    class Meta:
        model = QuestionTemplate
        fields = [
            'id', 'name', 'category', 'questions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_questions(self, value):
        """Валидация списка вопросов"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Вопросы должны быть списком")
        
        if len(value) == 0:
            raise serializers.ValidationError("Список вопросов не может быть пустым")
        
        for question in value:
            if not isinstance(question, str) or not question.strip():
                raise serializers.ValidationError("Все вопросы должны быть непустыми строками")
        
        return value


class GoogleOAuthCallbackSerializer(serializers.Serializer):
    """Сериализатор для OAuth callback"""
    code = serializers.CharField(max_length=500)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    error = serializers.CharField(max_length=200, required=False, allow_blank=True)


class GoogleSyncRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса синхронизации"""
    sync_type = serializers.ChoiceField(
        choices=[
            ('all', 'Все данные'),
            ('calendar', 'Календарь'),
            ('drive', 'Drive'),
            ('sheets', 'Sheets')
        ],
        default='all'
    )


class GoogleCalendarEventSerializer(serializers.Serializer):
    """Сериализатор для событий Google Calendar"""
    id = serializers.CharField()
    summary = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    start = serializers.DictField()
    end = serializers.DictField()
    attendees = serializers.ListField(required=False)
    location = serializers.CharField(allow_blank=True)
    htmlLink = serializers.URLField(allow_blank=True)
    created = serializers.DateTimeField()
    updated = serializers.DateTimeField()


class GoogleDriveFileSerializer(serializers.Serializer):
    """Сериализатор для файлов Google Drive"""
    id = serializers.CharField()
    name = serializers.CharField()
    mimeType = serializers.CharField()
    size = serializers.CharField(allow_blank=True)
    createdTime = serializers.DateTimeField()
    modifiedTime = serializers.DateTimeField()
    webViewLink = serializers.URLField(allow_blank=True)
    webContentLink = serializers.URLField(allow_blank=True)


class GoogleSheetSerializer(serializers.Serializer):
    """Сериализатор для Google Sheets"""
    id = serializers.CharField()
    name = serializers.CharField()
    createdTime = serializers.DateTimeField()
    modifiedTime = serializers.DateTimeField()
    webViewLink = serializers.URLField(allow_blank=True)


class GoogleStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики Google сервисов"""
    calendar_events = serializers.IntegerField()
    drive_files = serializers.IntegerField()
    sheets = serializers.IntegerField()
    last_sync = serializers.DateTimeField(allow_null=True)
    connected_at = serializers.DateTimeField()
    scopes = serializers.ListField()


class GoogleAIAnalysisSerializer(serializers.Serializer):
    """Сериализатор для AI анализа Google данных"""
    text = serializers.CharField(max_length=10000)
    analysis_type = serializers.ChoiceField(
        choices=[
            ('hrscreening', 'HR скрининг'),
            ('interview_scheduling', 'Планирование интервью'),
            ('general', 'Общий анализ')
        ],
        default='hrscreening'
    )