"""
Модели для вики-системы
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinLengthValidator
from django.urls import reverse

User = get_user_model()


class WikiTag(models.Model):
    """Теги (метки) для страниц вики"""
    
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Название тега',
        help_text='Название тега (например: "настройка", "вакансии", "интеграции")'
    )
    
    color = models.CharField(
        max_length=7,
        default='#6c757d',
        verbose_name='Цвет тега',
        help_text='Цвет тега в формате HEX (например: #007bff)'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    class Meta:
        verbose_name = 'Тег вики'
        verbose_name_plural = 'Теги вики'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class WikiPage(models.Model):
    """Страница вики с описанием функциональности"""
    
    title = models.CharField(
        max_length=200,
        verbose_name='Название',
        help_text='Название страницы вики',
        validators=[MinLengthValidator(3)]
    )
    
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name='URL-адрес',
        help_text='Уникальный идентификатор для URL (например: "nastroyki-kompanii"). Используется для создания URL страницы'
    )
    
    content = models.TextField(
        verbose_name='Содержание',
        help_text='Основной текст страницы вики (HTML, редактируется через WYSIWYG Summernote)',
        validators=[MinLengthValidator(10)]
    )
    
    description = models.TextField(
        max_length=500,
        blank=True,
        verbose_name='Краткое описание',
        help_text='Краткое описание страницы для превью'
    )
    
    CATEGORY_CHOICES = [
        ('', 'Без категории'),
        ('Введение', 'Введение'),
        ('Архитектура', 'Архитектура'),
        ('Настройка', 'Настройка'),
        ('Использование', 'Использование'),
        ('Интеграции', 'Интеграции'),
    ]
    
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='',
        blank=True,
        verbose_name='Категория',
        help_text='Категория страницы'
    )
    
    tags = models.ManyToManyField(
        WikiTag,
        blank=True,
        related_name='pages',
        verbose_name='Теги',
        help_text='Теги (метки) для страницы'
    )
    
    RELATED_APP_CHOICES = [
        ('', 'Не привязано'),
        ('accounts', 'Пользователи'),
        ('company_settings', 'Настройки компании'),
        ('finance', 'Финансы'),
        ('vacancies', 'Вакансии'),
        ('hiring_plan', 'План найма'),
        ('google_oauth', 'Google Calendar'),
        ('gemini', 'AI-помощник'),
        ('interviewers', 'Интервьюеры'),
        ('clickup_int', 'ClickUp'),
        ('notion_int', 'Notion'),
        ('huntflow', 'Huntflow'),
    ]
    
    related_app = models.CharField(
        max_length=50,
        choices=RELATED_APP_CHOICES,
        default='',
        blank=True,
        verbose_name='Связанное приложение',
        help_text='Приложение, к которому относится страница'
    )
    
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок сортировки',
        help_text='Порядок отображения страницы в списке (меньше = выше)'
    )
    
    is_published = models.BooleanField(
        default=True,
        verbose_name='Опубликовано',
        help_text='Показывать ли страницу в списке'
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_pages',
        verbose_name='Автор',
        help_text='Пользователь, создавший страницу'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_wiki_pages',
        verbose_name='Последний редактор',
        help_text='Пользователь, последним отредактировавший страницу'
    )
    
    class Meta:
        verbose_name = 'Страница вики'
        verbose_name_plural = 'Страницы вики'
        ordering = ['order', 'title']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', 'is_published']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        """Возвращает URL страницы"""
        return reverse('wiki:page_detail', kwargs={'slug': self.slug})
    
    def get_edit_url(self):
        """Возвращает URL для редактирования страницы"""
        return reverse('wiki:page_edit', kwargs={'slug': self.slug})
    
    @classmethod
    def get_published_pages(cls, category=None):
        """Получает опубликованные страницы, опционально фильтруя по категории"""
        queryset = cls.objects.filter(is_published=True)
        if category:
            queryset = queryset.filter(category=category)
        return queryset


class WikiPageHistory(models.Model):
    """История изменений страниц вики"""
    
    page = models.ForeignKey(
        WikiPage,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Страница'
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name='Название'
    )
    
    content = models.TextField(
        verbose_name='Содержание'
    )
    
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_edits',
        verbose_name='Редактор'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата изменения'
    )
    
    change_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Примечание к изменению',
        help_text='Краткое описание внесенных изменений'
    )
    
    class Meta:
        verbose_name = 'История изменений страницы'
        verbose_name_plural = 'История изменений страниц'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.page.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
