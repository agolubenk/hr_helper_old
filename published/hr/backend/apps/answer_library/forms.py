from django import forms
from .models import TriggerTopic


class TriggerTopicForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.vacancies.models import Vacancy
        self.fields['vacancy'].queryset = Vacancy.objects.filter(is_active=True).order_by('name')
        self.fields['vacancy'].required = False
        self.fields['vacancy'].empty_label = 'Все вакансии'

    class Meta:
        model = TriggerTopic
        fields = ('title', 'vacancy', 'trigger_words', 'example_answer', 'extra_data', 'order', 'is_active')
        widgets = {
            'vacancy': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: График работы'}),
            'trigger_words': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Слова или фразы через запятую: график, отпуск, зарплата, удалёнка',
            }),
            'example_answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Пример ответа кандидату'}),
            'extra_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Доп. данные для ответа (даты, цифры и т.п.)'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
