from django import forms
from django.contrib.auth import get_user_model
from .models import VacancySLA, HiringRequest
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade

User = get_user_model()


class HiringPlanFilterForm(forms.Form):
    """Форма фильтрации списка планов найма (для шаблона plan_list.html)."""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Поиск'}),
        label='Поиск'
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Все'), ('active', 'Активные'), ('completed', 'Завершённые')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Статус'
    )
    responsible_recruiter = forms.ChoiceField(
        required=False,
        choices=[],  # задаётся в __init__
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Владелец'
    )
    start_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Дата с'
    )
    start_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Дата по'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import HiringPlan
        owners = User.objects.filter(
            id__in=HiringPlan.objects.values_list('owner_id', flat=True).distinct()
        ).order_by('first_name', 'last_name')
        self.fields['responsible_recruiter'].choices = [('', 'Все')] + [
            (str(u.id), u.get_full_name() or u.username) for u in owners
        ]


class DateInput(forms.DateInput):
    """Кастомный виджет для правильного формата даты в HTML5"""
    input_type = 'date'
    
    def format_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)


class HiringRequestForm(forms.ModelForm):
    class Meta:
        model = HiringRequest
        fields = [
            'vacancy', 'grade', 'project', 'priority',
            'opening_reason', 'opening_date', 'recruiter', 'clickup_task_id', 'notes'
        ]
        widgets = {
            'vacancy': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.TextInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'opening_reason': forms.Select(attrs={'class': 'form-select'}),
            'opening_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'recruiter': forms.Select(attrs={'class': 'form-select'}),
            'clickup_task_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 86c7y88xk'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'vacancy': 'Вакансия',
            'grade': 'Грейд',
            'project': 'Проект',
            'priority': 'Приоритет',
            'opening_reason': 'Причина открытия',
            'opening_date': 'Дата открытия вакансии',
            'recruiter': 'Рекрутер',
            'clickup_task_id': 'ID задачи в ClickUp',
            'notes': 'Заметки',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Фильтруем только активных пользователей для выбора рекрутера
        self.fields['recruiter'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        self.fields['recruiter'].empty_label = "Выберите рекрутера..."
        
        # Ограничиваем выбор только активными грейдами компании
        from apps.company_settings.utils import get_active_grades_queryset
        self.fields['grade'].queryset = get_active_grades_queryset().order_by('name')
        self.fields['clickup_task_id'].required = False
        if 'clickup_task_id' in self.fields:
            self.fields['clickup_task_id'].help_text = 'Связь с задачей в плане найма ClickUp (из карточки задачи или URL).'
    
    def clean_grade(self):
        """Валидация грейда - проверяем, что он является активным для компании"""
        grade = self.cleaned_data.get('grade')
        if grade:
            from apps.company_settings.utils import get_active_grades_queryset
            active_grades = get_active_grades_queryset()
            if grade not in active_grades:
                raise forms.ValidationError(
                    f'Грейд "{grade.name}" не является активным для компании.'
                )
        return grade

    def clean_clickup_task_id(self):
        value = self.cleaned_data.get('clickup_task_id')
        if value is not None and isinstance(value, str):
            value = value.strip() or ''
        else:
            value = value or ''
        if value:
            if HiringRequest.objects.filter(clickup_task_id=value).exists():
                raise forms.ValidationError(
                    'Эта задача ClickUp уже привязана к другой заявке плана найма.'
                )
        return value


class HiringRequestUpdateForm(forms.ModelForm):
    class Meta:
        model = HiringRequest
        fields = [
            'opening_date', 'candidate_id', 'candidate_name', 'closed_date', 'hire_date',
            'recruiter', 'grade', 'project', 'clickup_task_id', 'notes'
        ]
        widgets = {
            'opening_date': DateInput(attrs={'class': 'form-control'}),
            'candidate_id': forms.TextInput(attrs={'class': 'form-control'}),
            'candidate_name': forms.TextInput(attrs={'class': 'form-control'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.TextInput(attrs={'class': 'form-control'}),
            'closed_date': DateInput(attrs={'class': 'form-control'}),
            'hire_date': DateInput(attrs={'class': 'form-control'}),
            'recruiter': forms.Select(attrs={'class': 'form-select'}),
            'clickup_task_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 86c7y88xk'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'opening_date': 'Дата открытия',
            'candidate_id': 'ID кандидата',
            'candidate_name': 'Имя кандидата',
            'closed_date': 'Дата закрытия',
            'hire_date': 'Дата выхода специалиста',
            'recruiter': 'Рекрутер',
            'grade': 'Грейд',
            'project': 'Проект',
            'clickup_task_id': 'ID задачи в ClickUp',
            'notes': 'Заметки',
        }
        help_texts = {
            'clickup_task_id': 'Связь с задачей в плане найма ClickUp (из карточки задачи или URL).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Фильтруем только активных пользователей для выбора рекрутера
        self.fields['recruiter'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        self.fields['recruiter'].empty_label = "Выберите рекрутера..."

        # Грейд — только активные грейды компании
        from apps.company_settings.utils import get_active_grades_queryset
        self.fields['grade'].queryset = get_active_grades_queryset().order_by('name')

        # Показываем поле opening_date только для планируемых заявок
        if self.instance and self.instance.status != 'planned':
            # Для незапланированных заявок делаем поле только для чтения
            self.fields['opening_date'].widget = forms.DateInput(attrs={'class': 'form-control', 'readonly': True})
            self.fields['opening_date'].required = False
            # Устанавливаем текущее значение
            if self.instance.opening_date:
                self.fields['opening_date'].initial = self.instance.opening_date
                # Также устанавливаем значение в data для POST запроса
                if 'opening_date' not in self.data:
                    self.data = self.data.copy()
                    self.data['opening_date'] = self.instance.opening_date
        
        # Поле candidate_name только для чтения - заполняется автоматически из Huntflow
        self.fields['candidate_name'].widget = forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
        self.fields['candidate_name'].required = False
        self.fields['candidate_name'].help_text = "Заполняется автоматически из Huntflow по ID кандидата"

    def clean_clickup_task_id(self):
        value = self.cleaned_data.get('clickup_task_id')
        if value is not None and isinstance(value, str):
            value = value.strip() or ''
        else:
            value = value or ''
        if value:
            other = HiringRequest.objects.filter(clickup_task_id=value).exclude(pk=self.instance.pk)
            if other.exists():
                raise forms.ValidationError(
                    'Эта задача ClickUp уже привязана к другой заявке плана найма.'
                )
        return value


class VacancySLAForm(forms.ModelForm):
    class Meta:
        model = VacancySLA
        fields = ['vacancy', 'grade', 'time_to_offer', 'time_to_hire', 'is_active']
        widgets = {
            'vacancy': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'time_to_offer': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'time_to_hire': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'vacancy': 'Вакансия',
            'grade': 'Грейд',
            'time_to_offer': 'Time-to-Offer (дни)',
            'time_to_hire': 'Time-to-Hire (дни)',
            'is_active': 'Активен',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Получаем активные грейды компании
        from apps.company_settings.utils import get_active_grades_queryset
        all_grades = get_active_grades_queryset()
        
        # Получаем все вакансии
        from apps.vacancies.models import Vacancy
        all_vacancies = Vacancy.objects.filter(is_active=True)
        
        # Для создания нового SLA
        if not self.instance.pk:
            # Исключаем вакансии, для которых уже созданы SLA для всех грейдов
            available_vacancies = []
            for vacancy in all_vacancies:
                existing_grades = VacancySLA.objects.filter(vacancy=vacancy).values_list('grade', flat=True)
                if len(existing_grades) < all_grades.count():
                    available_vacancies.append(vacancy)
            
            self.fields['vacancy'].queryset = Vacancy.objects.filter(
                id__in=[v.id for v in available_vacancies]
            )
        else:
            # Для редактирования - показываем все активные вакансии + текущую вакансию
            current_vacancy = self.instance.vacancy
            available_vacancies = list(all_vacancies)
            if current_vacancy not in available_vacancies:
                available_vacancies.append(current_vacancy)
            
            self.fields['vacancy'].queryset = Vacancy.objects.filter(
                id__in=[v.id for v in available_vacancies]
            )
        
        # Настройка грейдов в зависимости от режима
        if not self.instance.pk:
            # Для создания - исключаем грейды, для которых уже есть SLA
            # (логика будет в JavaScript)
            self.fields['grade'].queryset = all_grades
        else:
            # Для редактирования - показываем только текущий грейд
            current_grade = self.instance.grade
            self.fields['grade'].queryset = Grade.objects.filter(id=current_grade.id)
    
    def clean(self):
        cleaned_data = super().clean()
        vacancy = cleaned_data.get('vacancy')
        grade = cleaned_data.get('grade')
        
        # Проверяем, что выбранный грейд является активным для компании
        if grade:
            from apps.company_settings.utils import get_active_grades_queryset
            active_grades = get_active_grades_queryset()
            if grade not in active_grades:
                raise forms.ValidationError(
                    f'Грейд "{grade.name}" не является активным для компании.'
                )
        
        if vacancy and grade:
            # Проверяем, не существует ли уже SLA для этой пары
            existing_sla = VacancySLA.objects.filter(
                vacancy=vacancy, 
                grade=grade
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            if existing_sla.exists():
                raise forms.ValidationError(
                    f'SLA для вакансии "{vacancy.name}" и грейда "{grade.name}" уже существует.'
                )
        
        return cleaned_data