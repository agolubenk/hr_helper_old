from django import forms
from .models import Interviewer, InterviewRule


class InterviewerForm(forms.ModelForm):
    """
    Форма для создания и редактирования интервьюера
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - first_name: имя интервьюера (обязательно)
    - last_name: фамилия интервьюера (обязательно)
    - middle_name: отчество интервьюера (опционально)
    - email: email адрес интервьюера (обязательно)
    - calendar_link: ссылка на календарь (опционально)
    - is_active: статус активности интервьюера
    
    ИСТОЧНИКИ ДАННЫХ:
    - Interviewer модель из apps.interviewers.models
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Настройка виджетов для UI
    - Настройка лейблов и подсказок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для создания/редактирования интервьюера
    
    СВЯЗИ:
    - Использует: Interviewer модель
    - Передает: Django форма
    - Может вызываться из: Interviewer views
    """
    
    class Meta:
        model = Interviewer
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'calendar_link', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите фамилию'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите отчество (необязательно)'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@company.com'
            }),
            'calendar_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://calendly.com/username'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'middle_name': 'Отчество',
            'email': 'Email',
            'calendar_link': 'Ссылка на календарь',
            'is_active': 'Активен'
        }
        help_texts = {
            'first_name': 'Имя интервьюера',
            'last_name': 'Фамилия интервьюера',
            'middle_name': 'Отчество интервьюера (необязательно)',
            'email': 'Email адрес интервьюера',
            'calendar_link': 'Публичная ссылка на календарь (например, Calendly)',
            'is_active': 'Активен ли интервьюер для проведения интервью'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Делаем поля обязательными
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        
        # Добавляем валидацию
        self.fields['email'].widget.attrs['required'] = True
        self.fields['first_name'].widget.attrs['required'] = True
        self.fields['last_name'].widget.attrs['required'] = True


class InterviewerSearchForm(forms.Form):
    """
    Форма поиска интервьюеров
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - search: поисковый запрос (опционально)
    - is_active: фильтр по активности (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - GET параметры запроса
    
    ОБРАБОТКА:
    - Валидация параметров поиска
    - Настройка виджетов для UI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для поиска интервьюеров
    
    СВЯЗИ:
    - Использует: GET параметры
    - Передает: Django форма
    - Может вызываться из: Interviewer views
    """
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по имени, фамилии или email...'
        }),
        label='Поиск'
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


class InterviewRuleForm(forms.ModelForm):
    """
    Форма для создания и редактирования правил интервью
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - name: название правила (обязательно)
    - description: описание правила (опционально)
    - duration_minutes: длительность в минутах (обязательно)
    - is_active: статус активности правила
    
    ИСТОЧНИКИ ДАННЫХ:
    - InterviewRule модель из apps.interviewers.models
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Настройка виджетов для UI
    - Настройка лейблов и подсказок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для создания/редактирования правил интервью
    
    СВЯЗИ:
    - Использует: InterviewRule модель
    - Передает: Django форма
    - Может вызываться из: InterviewRule views
    """
    
    class Meta:
        model = InterviewRule
        fields = ['name', 'description', 'daily_limit', 'weekly_limit', 'min_grade', 'max_grade', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название правила'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание правила (необязательно)'
            }),
            'daily_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 50
            }),
            'weekly_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 200
            }),
            'min_grade': forms.Select(attrs={
                'class': 'form-select'
            }),
            'max_grade': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'name': 'Название правила',
            'description': 'Описание',
            'daily_limit': 'Лимит в день',
            'weekly_limit': 'Лимит в неделю',
            'min_grade': 'Минимальный грейд',
            'max_grade': 'Максимальный грейд',
            'is_active': 'Активно'
        }
        help_texts = {
            'name': 'Краткое название правила привлечения',
            'description': 'Подробное описание правила',
            'daily_limit': 'Максимальное количество интервью в день для одного интервьюера',
            'weekly_limit': 'Максимальное количество интервью в неделю для одного интервьюера',
            'min_grade': 'Минимальный грейд для привлечения интервьюера',
            'max_grade': 'Максимальный грейд для привлечения интервьюера',
            'is_active': 'Активно ли правило для применения'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Загружаем только активные грейды компании
        from apps.company_settings.utils import get_active_grades_queryset
        active_grades = get_active_grades_queryset()
        self.fields['min_grade'].queryset = active_grades.order_by('name')
        self.fields['max_grade'].queryset = active_grades.order_by('name')
        
        # Делаем поля обязательными
        self.fields['name'].required = True
        self.fields['daily_limit'].required = True
        self.fields['weekly_limit'].required = True
        self.fields['min_grade'].required = True
        self.fields['max_grade'].required = True


class InterviewRuleSearchForm(forms.Form):
    """
    Форма поиска правил интервью
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - search: поисковый запрос (опционально)
    - is_active: фильтр по активности (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - GET параметры запроса
    
    ОБРАБОТКА:
    - Валидация параметров поиска
    - Настройка виджетов для UI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для поиска правил интервью
    
    СВЯЗИ:
    - Использует: GET параметры
    - Передает: Django форма
    - Может вызываться из: InterviewRule views
    """
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию или описанию...'
        }),
        label='Поиск'
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
    
    min_grade = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Все грейды",
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Минимальный грейд'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.company_settings.utils import get_active_grades_queryset
        active_grades = get_active_grades_queryset()
        self.fields['min_grade'].queryset = active_grades.order_by('name')
