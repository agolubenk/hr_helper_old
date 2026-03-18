from django import forms
from django.contrib.auth import get_user_model
from .models import Vacancy
from apps.finance.models import SalaryRange
from apps.interviewers.models import Interviewer

User = get_user_model()


def get_huntflow_statuses_choices(user=None):
    """
    Получает список статусов вакансий из Huntflow для использования в формах
    
    Returns:
        List of tuples: [(status_id, status_name), ...]
    """
    try:
        from apps.huntflow.services import HuntflowService
        
        if not user:
            return []
            
        # Создаем сервис Huntflow
        huntflow_service = HuntflowService(user)
        
        # Получаем список аккаунтов
        accounts = huntflow_service.get_accounts()
        if not accounts or not accounts.get('items'):
            return []
            
        # Берем первый доступный аккаунт
        account_id = accounts['items'][0]['id']
        
        # Получаем статусы вакансий
        statuses_data = huntflow_service.get_vacancy_statuses(account_id)
        if not statuses_data or not statuses_data.get('items'):
            return []
            
        # Формируем список кортежей для ChoiceField
        choices = []
        for status in statuses_data['items']:
            status_id = status.get('id')
            status_name = status.get('name', f'Статус {status_id}')
            choices.append((status_id, status_name))
            
        return choices
        
    except Exception as e:
        print(f"❌ Ошибка получения статусов Huntflow: {e}")
        return []


class VacancyForm(forms.ModelForm):
    """
    Форма для создания и редактирования вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название вакансии (обязательно)
    - external_id: внешний ID вакансии (обязательно)
    - recruiter: ответственный рекрутер (обязательно)
    - invite_title: заголовок приглашений (обязательно)
    - invite_text: текст приглашений (обязательно)
    - scorecard_title: заголовок скоркарда (обязательно)
    - scorecard_link: ссылка на скоркард
    - questions_belarus, questions_poland: вопросы для интервью
    - vacancy_link_belarus, vacancy_link_poland: ссылки на вакансии
    - candidate_update_prompt: промпт для AI
    - hr_screening_stage, tech_screening_stage, tech_interview_stage: этапы для перевода кандидатов (из Huntflow)
    - screening_duration: длительность скринингов
    - available_grades: доступные грейды
    - interviewers: интервьюеры
    - is_active: статус активности
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy модель из apps.vacancies.models
    - User.objects: рекрутеры из группы 'Рекрутер'
    - Grade.objects: все грейды
    - Interviewer.objects: активные интервьюеры
    - Huntflow API: статусы вакансий для этапов
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Настройка виджетов для UI
    - Ограничение выбора рекрутеров и интервьюеров
    - Динамическая загрузка статусов из Huntflow
    - Настройка лейблов и подсказок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для создания/редактирования вакансий
    
    СВЯЗИ:
    - Использует: Vacancy модель, User.objects, Grade.objects, Interviewer.objects, HuntflowService
    - Передает: Django форма
    - Может вызываться из: Vacancy views
    """
    
    # Переопределяем поля этапов как ChoiceField
    hr_screening_stage = forms.ChoiceField(
        choices=[],
        required=False,
        label='Этап после HR-скрининга',
        help_text='Этап в Huntflow, на который переводить кандидата после HR-скрининга',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tech_screening_stage = forms.ChoiceField(
        choices=[],
        required=False,
        label='Этап после Tech-скрининга',
        help_text='Этап в Huntflow, на который переводить кандидата после Tech-скрининга',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tech_interview_stage = forms.ChoiceField(
        choices=[],
        required=False,
        label='Этап после Tech-интервью',
        help_text='Этап в Huntflow, на который переводить кандидата после Tech-интервью',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        # Извлекаем user из kwargs, если он передан
        user = kwargs.pop('user', None)
        super(VacancyForm, self).__init__(*args, **kwargs)
        
        # Загружаем статусы из Huntflow
        huntflow_choices = get_huntflow_statuses_choices(user)
        
        # Добавляем пустой выбор в начало
        empty_choice = [('', 'Не выбран')]
        all_choices = empty_choice + huntflow_choices
        
        # Устанавливаем choices для полей этапов
        self.fields['hr_screening_stage'].choices = all_choices
        self.fields['tech_screening_stage'].choices = all_choices
        self.fields['tech_interview_stage'].choices = all_choices
        
        # Ограничиваем выбор рекрутеров только группой "Рекрутер"
        recruiters_qs = User.objects.filter(groups__name='Рекрутер').order_by('first_name', 'last_name')
        self.fields['recruiter'].queryset = recruiters_qs
        self.fields['additional_recruiters'].queryset = recruiters_qs
        self.fields['additional_recruiters'].required = False
        # При редактировании основной рекрутер не должен быть в списке дополнительных
        if self.instance and self.instance.pk and self.instance.recruiter_id:
            self.fields['additional_recruiters'].queryset = self.fields['additional_recruiters'].queryset.exclude(pk=self.instance.recruiter_id)
        
        # Ограничиваем выбор только активными интервьюерами для обязательных участников
        self.fields['mandatory_tech_interviewers'].queryset = Interviewer.objects.filter(is_active=True)
        
        # Ограничиваем выбор только активными грейдами компании
        from apps.company_settings.utils import get_active_grades_queryset
        self.fields['available_grades'].queryset = get_active_grades_queryset()
        
        # Ограничиваем выбор только активными интервьюерами
        self.fields['interviewers'].queryset = Interviewer.objects.filter(is_active=True)
        
        # Делаем обязательные поля
        self.fields['name'].required = True
        self.fields['external_id'].required = True
        self.fields['recruiter'].required = True
        self.fields['invite_title'].required = True
        self.fields['invite_text'].required = True
        self.fields['scorecard_title'].required = True
    
    class Meta:
        model = Vacancy
        fields = [
            'name', 'external_id', 'recruiter', 'additional_recruiters', 'technologies', 'tech_interview_duration', 'mandatory_tech_interviewers',
            'invite_title', 'invite_text', 'tech_invite_title', 'tech_invite_text', 'scorecard_title', 'scorecard_link', 
            'questions_belarus', 'questions_poland', 'vacancy_link_belarus', 'vacancy_link_poland',
            'candidate_update_prompt', 'use_common_prompt', 'screening_duration',
            'hr_screening_stage', 'tech_screening_stage', 'tech_interview_stage',
            'available_grades', 'interviewers', 'is_active', 'review_period_months'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название вакансии'
            }),
            'external_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите ID для связи'
            }),
            'recruiter': forms.Select(attrs={
                'class': 'form-select'
            }),
            'additional_recruiters': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '6'
            }),
            'technologies': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Python, Django, PostgreSQL, Redis'
            }),
            'tech_interview_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '60',
                'min': '1',
                'max': '480'
            }),
            'mandatory_tech_interviewers': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'invite_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Заголовок для приглашений'
            }),
            'invite_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Сопровождающий текст для приглашений'
            }),
            'tech_invite_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Заголовок для приглашений на тех. интервью'
            }),
            'tech_invite_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Сопровождающий текст для приглашений на тех. интервью'
            }),
            'scorecard_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Заголовок Scorecard'
            }),
            'scorecard_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/scorecard'
            }),
            'questions_belarus': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Вопросы для интервью в Беларуси'
            }),
            'questions_poland': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Вопросы для интервью в Польше'
            }),
            'vacancy_link_belarus': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://rabota.by/vacancy/123'
            }),
            'vacancy_link_poland': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://pracuj.pl/job/456'
            }),
            'candidate_update_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Промпт для обновления информации о кандидате',
                'id': 'id_candidate_update_prompt'
            }),
            'use_common_prompt': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_use_common_prompt'
            }),
            'screening_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '480',
                'placeholder': 'Длительность в минутах'
            }),
            'available_grades': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'interviewers': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'review_period_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Месяцы'
            })
        }
        labels = {
            'name': 'Название вакансии',
            'external_id': 'ID для связи',
            'technologies': 'Технологии',
            'tech_interview_duration': 'Длительность тех. интервью (минуты)',
            'mandatory_tech_interviewers': 'Обязательные участники тех. интервью',
            'recruiter': 'Ответственный рекрутер',
            'additional_recruiters': 'Дополнительные рекрутеры',
            'invite_title': 'Заголовок инвайтов',
            'invite_text': 'Сопровождающий текст для инвайтов',
            'tech_invite_title': 'Заголовок инвайтов на тех. интервью',
            'tech_invite_text': 'Сопровождающий текст для инвайтов на тех. интервью',
            'scorecard_title': 'Заголовок Scorecard',
            'scorecard_link': 'Ссылка на Scorecard',
            'questions_belarus': 'Вопросы Беларусь',
            'questions_poland': 'Вопросы Польша',
            'vacancy_link_belarus': 'Ссылка на вакансию (Беларусь)',
            'vacancy_link_poland': 'Ссылка на вакансию (Польша)',
            'candidate_update_prompt': 'Промпт для обновления кандидата',
            'use_common_prompt': 'Использовать общий промпт',
            'screening_duration': 'Длительность скринингов',
            'available_grades': 'Доступные грейды',
            'interviewers': 'Интервьюеры',
            'is_active': 'Активна',
            'review_period_months': 'Срок пересмотра (месяцы)'
        }
        help_texts = {
            'name': 'Название вакансии',
            'external_id': 'Внешний идентификатор для связи с внешними системами',
            'recruiter': 'Рекрутер, ответственный за вакансию',
            'additional_recruiters': 'Опционально: один или несколько дополнительных рекрутеров по вакансии',
            'invite_title': 'Заголовок для приглашений кандидатов',
            'invite_text': 'Текст сопроводительного письма для приглашений',
            'scorecard_title': 'Заголовок для Scorecard',
            'scorecard_link': 'Ссылка на Scorecard для оценки кандидатов',
            'questions_belarus': 'Вопросы для интервью в Беларуси',
            'questions_poland': 'Вопросы для интервью в Польше',
            'vacancy_link_belarus': 'Ссылка на вакансию в Беларуси (например, rabota.by, jobs.tut.by)',
            'vacancy_link_poland': 'Ссылка на вакансию в Польше (например, pracuj.pl, nofluffjobs.com)',
            'candidate_update_prompt': 'Промпт для обновления информации о кандидате',
            'use_common_prompt': 'Если включено, используется единый промпт из настроек компании. Если выключено, используется индивидуальный промпт.',
            'screening_duration': 'Длительность скринингов в минутах (по умолчанию 45 минут)',
            'available_grades': 'Грейды, доступные для данной вакансии',
            'interviewers': 'Интервьюеры, привязанные к вакансии',
            'is_active': 'Активна ли вакансия',
            'review_period_months': 'Срок пересмотра вакансии в месяцах (целое число)'
        }

    def clean(self):
        cleaned = super().clean()
        recruiter = cleaned.get('recruiter')
        additional_recruiters = cleaned.get('additional_recruiters') or []
        if recruiter and additional_recruiters:
            if recruiter in additional_recruiters:
                self.add_error('additional_recruiters', 'Дополнительные рекрутеры не должны включать основного рекрутера.')
        return cleaned

    
class VacancySearchForm(forms.Form):
    """
    Форма для поиска вакансий
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - search: поисковый запрос (опционально)
    - recruiter: фильтр по рекрутеру (опционально)
    - is_active: фильтр по статусу активности (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - User.objects: рекрутеры из группы 'Рекрутер'
    
    ОБРАБОТКА:
    - Настройка полей поиска и фильтрации
    - Ограничение выбора рекрутеров
    - Настройка виджетов для UI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для поиска вакансий
    
    СВЯЗИ:
    - Использует: User.objects
    - Передает: Django форма
    - Может вызываться из: Vacancy views
    """
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию или ID...'
        }),
        label='Поиск'
    )
    
    recruiter = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Все рекрутеры",
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Рекрутер'
    )
    
    is_active = forms.ChoiceField(
        choices=[
            ('', 'Все'),
            ('true', 'Активные'),
            ('false', 'Неактивные')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Статус'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recruiter'].queryset = User.objects.filter(groups__name='Рекрутер')


class SalaryRangeForm(forms.ModelForm):
    """
    Форма для создания и редактирования зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - vacancy: вакансия (обязательно)
    - grade: грейд (обязательно)
    - salary_min_usd: минимальная зарплата в USD (обязательно)
    - salary_max_usd: максимальная зарплата в USD (обязательно)
    - is_active: статус активности
    
    ИСТОЧНИКИ ДАННЫХ:
    - SalaryRange модель из apps.vacancies.models
    - Vacancy.objects: активные вакансии
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Проверка корректности зарплатной вилки (min <= max)
    - Настройка виджетов для UI
    - Ограничение выбора активными вакансиями
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для создания/редактирования зарплатных вилок
    
    СВЯЗИ:
    - Использует: SalaryRange модель, Vacancy.objects
    - Передает: Django форма
    - Может вызываться из: SalaryRange views
    """
    
    class Meta:
        model = SalaryRange
        fields = ['vacancy', 'grade', 'salary_min_usd', 'salary_max_usd', 'is_active']
        widgets = {
            'vacancy': forms.Select(attrs={
                'class': 'form-select'
            }),
            'grade': forms.Select(attrs={
                'class': 'form-select'
            }),
            'salary_min_usd': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Минимальная зарплата в USD'
            }),
            'salary_max_usd': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Максимальная зарплата в USD'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'vacancy': 'Вакансия',
            'grade': 'Грейд',
            'salary_min_usd': 'Минимальная зарплата (USD)',
            'salary_max_usd': 'Максимальная зарплата (USD)',
            'is_active': 'Активна'
        }
        help_texts = {
            'vacancy': 'Выберите вакансию для которой устанавливается зарплатная вилка',
            'grade': 'Выберите грейд для которого устанавливается зарплатная вилка',
            'salary_min_usd': 'Минимальная зарплата в долларах США',
            'salary_max_usd': 'Максимальная зарплата в долларах США',
            'is_active': 'Активна ли зарплатная вилка'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор только активными вакансиями
        self.fields['vacancy'].queryset = Vacancy.objects.filter(is_active=True)
        
        # Ограничиваем выбор только активными грейдами компании
        from apps.company_settings.utils import get_active_grades_queryset
        self.fields['grade'].queryset = get_active_grades_queryset().order_by('name')
        
        # Делаем обязательные поля
        self.fields['vacancy'].required = True  # Поле vacancy теперь обязательное
        self.fields['grade'].required = True
        self.fields['salary_min_usd'].required = True
        self.fields['salary_max_usd'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min_usd')
        salary_max = cleaned_data.get('salary_max_usd')
        
        if salary_min and salary_max and salary_min > salary_max:
            raise forms.ValidationError(
                'Минимальная зарплата не может быть больше максимальной'
            )
        
        return cleaned_data


class SalaryRangeSearchForm(forms.Form):
    """
    Форма для поиска зарплатных вилок
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - search: поисковый запрос (опционально)
    - vacancy: фильтр по вакансии (опционально)
    - grade: фильтр по грейду (опционально)
    - is_active: фильтр по статусу активности (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - Vacancy.objects: активные вакансии
    - Grade.objects: все грейды
    
    ОБРАБОТКА:
    - Настройка полей поиска и фильтрации
    - Ограничение выбора активными вакансиями
    - Настройка виджетов для UI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для поиска зарплатных вилок
    
    СВЯЗИ:
    - Использует: Vacancy.objects, Grade.objects
    - Передает: Django форма
    - Может вызываться из: SalaryRange views
    """
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по вакансии или грейду...'
        }),
        label='Поиск'
    )
    
    vacancy = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Все вакансии",
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Вакансия'
    )
    
    grade = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Все грейды",
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Грейд'
    )
    
    is_active = forms.ChoiceField(
        choices=[
            ('', 'Все'),
            ('true', 'Активные'),
            ('false', 'Неактивные')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Статус'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.company_settings.utils import get_active_grades_queryset
        
        # Ограничиваем выбор только активными вакансиями
        self.fields['vacancy'].queryset = Vacancy.objects.filter(is_active=True).order_by('name')
        self.fields['grade'].queryset = get_active_grades_queryset().order_by('name')

