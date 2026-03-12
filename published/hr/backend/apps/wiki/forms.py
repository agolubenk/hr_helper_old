"""
Формы вики с WYSIWYG-редактором Summernote для поля «Содержание».
"""
from django import forms
from django_summernote.widgets import SummernoteWidget

from .models import WikiPage


class WikiPageEditForm(forms.Form):
    """Форма создания/редактирования страницы вики. Поле content — единый WYSIWYG (Summernote)."""
    title = forms.CharField(
        max_length=200,
        min_length=3,
        label='Название',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите название страницы',
        }),
    )
    slug = forms.SlugField(
        label='URL-адрес',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'nastroyki-kompanii',
            'pattern': '[a-z0-9-]+',
        }),
    )
    content = forms.CharField(
        min_length=10,
        label='Содержание',
        widget=SummernoteWidget(attrs={
            'placeholder': 'Введите содержание страницы. Можно форматировать текст, вставлять списки, таблицы и ссылки.',
        }),
    )
    description = forms.CharField(
        max_length=500,
        required=False,
        label='Краткое описание',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Краткое описание страницы для превью',
        }),
    )
    category = forms.ChoiceField(
        choices=WikiPage.CATEGORY_CHOICES,
        required=False,
        label='Категория',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    related_app = forms.ChoiceField(
        choices=WikiPage.RELATED_APP_CHOICES,
        required=False,
        label='Связанное приложение',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    order = forms.IntegerField(
        initial=0,
        min_value=0,
        required=False,
        label='Порядок сортировки',
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    is_published = forms.BooleanField(
        initial=True,
        required=False,
        label='Опубликовано',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    change_note = forms.CharField(
        max_length=200,
        required=False,
        label='Примечание к изменению',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Краткое описание внесенных изменений',
        }),
    )
