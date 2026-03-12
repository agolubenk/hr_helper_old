from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import User, SystemChoice
from datetime import time


class ProfileEditForm(UserChangeForm):
    """
    Форма редактирования профиля пользователя
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - first_name: имя пользователя
    - last_name: фамилия пользователя
    - email: электронная почта
    - telegram_username: имя пользователя в Telegram
    - telegram_username: имя пользователя в Telegram
    
    ИСТОЧНИКИ ДАННЫЕ:
    - User модель из apps.accounts.models
    
    ОБРАБОТКА:
    - Настройка полей для редактирования профиля
    - Удаление поля пароля из формы
    - Настройка виджетов для UI
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для редактирования профиля
    
    СВЯЗИ:
    - Использует: User модель
    - Передает: Django форма
    - Может вызываться из: Account views
    """
    
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'email', 
            'telegram_username',
            'interview_start_time',
            'interview_end_time',
            'meeting_interval_minutes'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Фамилия'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email'
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '@username'
            }),
            'interview_start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': '09:00'
            }),
            'interview_end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': '18:00'
            }),
            'meeting_interval_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '60',
                'step': '5',
                'placeholder': '15'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убираем поле пароля из формы
        if 'password' in self.fields:
            del self.fields['password']
    
    def clean_telegram_username(self):
        """Очищаем telegram username от префиксов @ и https://t.me/"""
        telegram_username = self.cleaned_data.get('telegram_username', '').strip()
        
        if telegram_username:
            # Убираем @ в начале
            if telegram_username.startswith('@'):
                telegram_username = telegram_username[1:]
            
            # Убираем https://t.me/ в начале
            if telegram_username.startswith('https://t.me/'):
                telegram_username = telegram_username[13:]
            
            # Убираем t.me/ в начале
            if telegram_username.startswith('t.me/'):
                telegram_username = telegram_username[5:]
        
        return telegram_username
    

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('interview_start_time')
        end_time = cleaned_data.get('interview_end_time')
        meeting_interval = cleaned_data.get('meeting_interval_minutes')
        
        if start_time and end_time:
            # Проверяем, что время находится в диапазоне 07:00 - 21:00
            
            if start_time < time(7, 0) or start_time > time(21, 0):
                raise forms.ValidationError("Время начала должно быть в диапазоне 07:00 - 21:00")
            
            if end_time < time(7, 0) or end_time > time(21, 0):
                raise forms.ValidationError("Время окончания должно быть в диапазоне 07:00 - 21:00")
            
            # Проверяем, что время начала раньше времени окончания
            if start_time >= end_time:
                raise forms.ValidationError("Время начала должно быть раньше времени окончания")
        
        # Валидация времени между встречами
        if meeting_interval is not None:
            if meeting_interval < 0 or meeting_interval > 60:
                raise forms.ValidationError("Время между встречами должно быть от 0 до 60 минут")
            if meeting_interval % 5 != 0:
                raise forms.ValidationError("Время между встречами должно быть кратно 5 минутам")
        
        return cleaned_data


class ApiKeysForm(forms.ModelForm):
    """Форма для управления API ключами"""
    
    class Meta:
        model = User
        fields = [
            'gemini_api_key',
            'clickup_api_key',
            'notion_integration_token',
            'huntflow_sandbox_api_key',
            'huntflow_sandbox_url',
            'huntflow_prod_url',
            'active_system'
        ]
        widgets = {
            'gemini_api_key': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите API ключ Gemini'
            }),
            'clickup_api_key': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите API ключ ClickUp'
            }),
            'notion_integration_token': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите Integration Token Notion'
            }),
            'huntflow_sandbox_api_key': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите API ключ Huntflow (песочница)'
            }),
            'huntflow_sandbox_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://sandbox-api.huntflow.dev'
            }),
            'huntflow_prod_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://api.huntflow.ru'
            }),
            'active_system': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
