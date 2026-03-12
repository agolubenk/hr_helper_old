from django import forms
from django.core.exceptions import ValidationError
from apps.vacancies.models import Vacancy


class CreateApplicantForm(forms.Form):
    """Форма для создания кандидата в Huntflow"""
    
    # Основная информация
    first_name = forms.CharField(
        max_length=100,
        required=True,
        label='Имя',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите имя кандидата'
        })
    )
    
    last_name = forms.CharField(
        max_length=100,
        required=True,
        label='Фамилия',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите фамилию кандидата'
        })
    )
    
    middle_name = forms.CharField(
        max_length=100,
        required=False,
        label='Отчество',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите отчество (необязательно)'
        })
    )
    
    # Контакты
    email = forms.EmailField(
        required=False,
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        label='Телефон',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        })
    )
    
    # Профессиональная информация
    position = forms.CharField(
        max_length=200,
        required=False,
        label='Должность',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Текущая или желаемая должность'
        })
    )
    
    company = forms.CharField(
        max_length=200,
        required=False,
        label='Компания',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Текущая или предыдущая компания'
        })
    )
    
    salary = forms.CharField(
        max_length=50,
        required=False,
        label='Зарплата',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ожидания по зарплате (например: 150000 руб)'
        })
    )
    
    # Файл резюме
    resume_file = forms.FileField(
        required=False,
        label='Файл резюме',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.txt',
            'id': 'resume_file_input'
        }),
        help_text='Загрузите файл резюме (PDF, DOC, DOCX, TXT). Файл будет автоматически обработан парсером Huntflow для заполнения данных.'
    )
    
    # Резюме
    resume_text = forms.CharField(
        required=False,
        label='Текст резюме',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Вставьте текст резюме или дополнительную информацию о кандидате',
            'id': 'resume_text_input'
        })
    )
    
    # Вакансия
    vacancy = forms.ModelChoiceField(
        queryset=Vacancy.objects.none(),
        required=True,
        label='Вакансия',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='Выберите вакансию, к которой будет привязан кандидат'
    )
    
    def __init__(self, *args, **kwargs):
        """Инициализация формы с активными вакансиями"""
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Получаем только активные вакансии
        if user:
            vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
            # Фильтруем по правам доступа пользователя, если нужно
            self.fields['vacancy'].queryset = vacancies
        else:
            self.fields['vacancy'].queryset = Vacancy.objects.filter(is_active=True).order_by('name')
    
    def clean(self):
        """Валидация формы"""
        cleaned_data = super().clean()
        
        # Проверяем, что указано хотя бы одно контактное средство
        email = cleaned_data.get('email')
        phone = cleaned_data.get('phone')
        
        if not email and not phone:
            raise ValidationError('Необходимо указать хотя бы email или телефон')
        
        return cleaned_data

