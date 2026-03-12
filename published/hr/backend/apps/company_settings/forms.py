from django import forms
from django.utils.translation import gettext_lazy as _
from datetime import time
from .models import CompanySettings, RejectionTemplate
from apps.finance.models import Grade


class CompanySettingsForm(forms.ModelForm):
    """Форма для редактирования настроек компании"""
    
    class Meta:
        model = CompanySettings
        fields = ['company_name', 'theme', 'main_calendar_id', 'ignore_non_accepted_meetings',
                  'work_start_time', 'work_end_time',
                  'org_structure', 'active_grades',
                  'office_address', 'office_map_link', 'office_directions', 'office_interview_instructions']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название компании'
            }),
            'theme': forms.Select(attrs={
                'class': 'form-select'
            }),
            'main_calendar_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID календаря Google Calendar'
            }),
            'ignore_non_accepted_meetings': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'work_start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': '09:00',
            }),
            'work_end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': '18:00',
            }),
            'org_structure': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': '{"departments": [], "employees": []}'
            }),
            'active_grades': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'office_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: г. Москва, ул. Ленина, д. 10, офис 205'
            }),
            'office_map_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yandex.ru/maps/... или https://www.google.com/maps/...'
            }),
            'office_directions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Опишите, как добраться до офиса: ориентиры, этаж, вход и т.д.'
            }),
            'office_interview_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Инструкции для кандидатов: что взять с собой, куда обратиться при входе, контактное лицо, телефон и т.д.'
            }),
        }
        labels = {
            'company_name': 'Название компании',
            'theme': 'Тема оформления',
            'main_calendar_id': 'ID главного календаря',
            'ignore_non_accepted_meetings': 'Игнорировать не принятые встречи',
            'work_start_time': 'Начало рабочего времени',
            'work_end_time': 'Конец рабочего времени',
            'org_structure': 'Оргструктура (JSON)',
            'active_grades': 'Активные грейды компании',
            'office_address': 'Адрес офиса',
            'office_map_link': 'Ссылка на карты',
            'office_directions': 'Как пройти',
            'office_interview_instructions': 'Инструкции для офисного интервью',
        }
        help_texts = {
            'company_name': 'Название вашей компании',
            'theme': 'Цветовая тема интерфейса приложения',
            'main_calendar_id': 'ID календаря Google Calendar для компании',
            'ignore_non_accepted_meetings': 'Если включено: при расчёте доступных слотов встречи без подтверждения (ожидают ответа, предварительно) не считаются занятыми — слот остаётся свободным. Если выключено: любая встреча, кроме отклонённой, занимает слот.',
            'work_start_time': 'Время начала рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.',
            'work_end_time': 'Время окончания рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.',
            'org_structure': 'Организационная структура в формате JSON',
            'active_grades': 'Выберите грейды, которые используются в вашей компании',
            'office_address': 'Полный адрес офиса компании',
            'office_map_link': 'Ссылка на Google Maps, Yandex Maps или другую карту',
            'office_directions': 'Подробное описание, как добраться до офиса (ориентиры, этаж, вход и т.д.)',
            'office_interview_instructions': 'Инструкции для кандидатов, которые приходят на офисное интервью (что взять с собой, куда обратиться, контакты и т.д.)',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('work_start_time')
        end_time = cleaned_data.get('work_end_time')
        if start_time is not None and end_time is not None:
            if start_time < time(7, 0) or start_time > time(21, 0):
                self.add_error('work_start_time', 'Время начала должно быть в диапазоне 07:00–21:00')
            if end_time < time(7, 0) or end_time > time(21, 0):
                self.add_error('work_end_time', 'Время окончания должно быть в диапазоне 07:00–21:00')
            if start_time >= end_time:
                self.add_error('work_end_time', 'Время окончания должно быть позже времени начала')
        elif start_time is not None or end_time is not None:
            self.add_error('work_start_time', 'Укажите оба времени или оставьте оба пустыми (будут использованы настройки из профиля пользователя).')
            self.add_error('work_end_time', 'Укажите оба времени или оставьте оба пустыми.')
        return cleaned_data
    
    def clean_org_structure(self):
        """Валидация JSON структуры оргструктуры"""
        import json
        org_structure = self.cleaned_data.get('org_structure')
        
        if isinstance(org_structure, str):
            try:
                org_structure = json.loads(org_structure)
            except json.JSONDecodeError:
                raise forms.ValidationError('Неверный формат JSON для оргструктуры')
        
        return org_structure


class RejectionTemplateForm(forms.ModelForm):
    """Форма для создания и редактирования шаблонов отказов"""
    
    class Meta:
        model = RejectionTemplate
        fields = ['rejection_type', 'grade', 'title', 'message', 'is_active']
        widgets = {
            'rejection_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_rejection_type'
            }),
            'grade': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_grade'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название шаблона'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Введите текст ответа для отказа'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'rejection_type': 'Тип отказа',
            'grade': 'Грейд',
            'title': 'Название шаблона',
            'message': 'Текст ответа',
            'is_active': 'Активен',
        }
        help_texts = {
            'rejection_type': 'Тип причины отказа',
            'grade': 'Грейд (заполняется только для типа "Грейд")',
            'title': 'Краткое название шаблона для идентификации',
            'message': 'Текст стандартного ответа для отказа',
            'is_active': 'Используется ли этот шаблон',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Фильтруем грейды только активными для компании
        from .models import CompanySettings
        settings = CompanySettings.get_settings()
        active_grades = settings.active_grades.all()
        
        self.fields['grade'].queryset = active_grades
        self.fields['grade'].required = False
        
        # Если редактируем существующий шаблон
        if self.instance and self.instance.pk:
            # Если тип не "grade", очищаем поле
            if self.instance.rejection_type != 'grade':
                self.fields['grade'].widget.attrs['disabled'] = True
        # При создании нового шаблона или если данные не переданы
        elif not self.data or self.data.get('rejection_type') != 'grade':
            # Поле будет скрыто через JavaScript
            pass
    
    def clean(self):
        cleaned_data = super().clean()
        rejection_type = cleaned_data.get('rejection_type')
        grade = cleaned_data.get('grade')
        
        # Для типа "grade" обязательно должно быть указано поле grade
        if rejection_type == 'grade' and not grade:
            raise forms.ValidationError({
                'grade': 'Для типа отказа "Грейд" обязательно укажите грейд'
            })
        
        # Для других типов grade должен быть пустым
        if rejection_type != 'grade' and grade:
            raise forms.ValidationError({
                'grade': 'Поле "Грейд" заполняется только для типа отказа "Грейд"'
            })
        
        return cleaned_data

