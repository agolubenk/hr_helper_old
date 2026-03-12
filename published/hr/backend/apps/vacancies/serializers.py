from rest_framework import serializers
from .models import Vacancy
from apps.finance.models import Grade


class VacancySerializer(serializers.ModelSerializer):
    """
    Сериализатор для вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название вакансии
    - external_id: внешний ID вакансии
    - recruiter: ID рекрутера
    - invite_title, invite_text: данные приглашения
    - scorecard_title, scorecard_text: данные скоркарда
    - available_grades: список доступных грейдов
    - is_active: статус активности
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy модель из apps.vacancies.models
    - Grade модель из apps.finance.models
    
    ОБРАБОТКА:
    - Сериализация полей вакансии
    - Вычисляемые поля: recruiter_name, recruiter_username, available_grades_names
    - Валидация уникальности external_id
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с полями вакансии
    
    СВЯЗИ:
    - Использует: Vacancy модель, Grade модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Vacancy API viewsets
    """
    recruiter_name = serializers.CharField(source='recruiter.get_full_name', read_only=True)
    recruiter_username = serializers.CharField(source='recruiter.username', read_only=True)
    available_grades_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Vacancy
        fields = [
            'id', 'name', 'external_id', 'recruiter', 'recruiter_name', 'recruiter_username',
            'invite_title', 'invite_text', 'scorecard_title', 'scorecard_text',
            'vacancy_link_belarus', 'vacancy_link_poland', 'questions_belarus', 'questions_poland',
            'available_grades', 'available_grades_names', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'recruiter_name', 'recruiter_username', 'available_grades_names']
    
    def get_available_grades_names(self, obj):
        """Возвращает список названий доступных грейдов"""
        return [grade.name for grade in obj.available_grades.all()]
    
    def validate_external_id(self, value):
        """Валидация уникальности external_id"""
        if Vacancy.objects.filter(external_id=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Вакансия с таким внешним ID уже существует")
        return value


class VacancyCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания вакансии
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название вакансии (обязательно)
    - external_id: внешний ID вакансии
    - recruiter: ID рекрутера
    - invite_title, invite_text: данные приглашения
    - scorecard_title, scorecard_text: данные скоркарда
    - available_grades: список доступных грейдов
    - is_active: статус активности
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy модель из apps.vacancies.models
    
    ОБРАБОТКА:
    - Сериализация полей для создания вакансии
    - Валидация уникальности external_id
    - Проверка обязательных полей
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с данными созданной вакансии
    
    СВЯЗИ:
    - Использует: Vacancy модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Vacancy API viewsets (create action)
    """
    
    class Meta:
        model = Vacancy
        fields = [
            'name', 'external_id', 'recruiter', 'invite_title', 'invite_text',
            'scorecard_title', 'scorecard_text', 'available_grades', 'is_active'
        ]
    
    def validate_external_id(self, value):
        """Валидация уникальности external_id"""
        if Vacancy.objects.filter(external_id=value).exists():
            raise serializers.ValidationError("Вакансия с таким внешним ID уже существует")
        return value


class VacancyListSerializer(serializers.ModelSerializer):
    """
    Упрощенный сериализатор для списка вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - Vacancy объекты для сериализации
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy модель из apps.vacancies.models
    
    ОБРАБОТКА:
    - Сериализация основных полей для отображения в списке
    - Вычисляемые поля: recruiter_name, available_grades_count
    - Оптимизированная версия для списков
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект с основными полями вакансии
    
    СВЯЗИ:
    - Использует: Vacancy модель
    - Передает данные в: DRF API responses
    - Может вызываться из: Vacancy API viewsets (list action)
    """
    recruiter_name = serializers.CharField(source='recruiter.get_full_name', read_only=True)
    available_grades_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Vacancy
        fields = [
            'id', 'name', 'external_id', 'recruiter_name',
            'available_grades_count', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_available_grades_count(self, obj):
        """Возвращает количество доступных грейдов"""
        return obj.available_grades.count()


class VacancyStatsSerializer(serializers.Serializer):
    """
    Сериализатор для статистики вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - total_vacancies: общее количество вакансий
    - active_vacancies: количество активных вакансий
    - inactive_vacancies: количество неактивных вакансий
    - vacancies_by_recruiter: статистика по рекрутерам
    - vacancies_by_grade: статистика по грейдам
    - recent_vacancies: последние вакансии
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy.objects: агрегированные данные вакансий
    - VacancyListSerializer: для последних вакансий
    
    ОБРАБОТКА:
    - Сериализация статистических данных
    - Агрегация данных по различным критериям
    - Формирование структурированной статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON объект со статистикой вакансий
    
    СВЯЗИ:
    - Использует: VacancyListSerializer
    - Передает данные в: DRF API responses
    - Может вызываться из: Vacancy API viewsets (stats action)
    """
    total_vacancies = serializers.IntegerField()
    active_vacancies = serializers.IntegerField()
    inactive_vacancies = serializers.IntegerField()
    vacancies_by_recruiter = serializers.DictField()
    vacancies_by_grade = serializers.DictField()
    recent_vacancies = VacancyListSerializer(many=True)
