"""
Библиотека ответов: справочник тем с триггерами и примерами ответов,
чат с ИИ для генерации ответов на вопросы кандидатов.
"""
from django.db import models
from django.conf import settings


class TriggerTopic(models.Model):
    """
    Тема/блок для подбора по словам-триггерам.
    Слова-триггеры (через запятую или с новой строки) при вхождении в текст вопроса
    кандидата подтягивают этот блок в контекст для Gemini.
    Если задана вакансия — тема применяется только к этой вакансии; иначе ко всем.
    """
    title = models.CharField('Название темы', max_length=255)
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='answer_library_topics',
        verbose_name='Вакансия',
        help_text='Если не указана — тема применяется ко всем вакансиям',
    )
    trigger_words = models.TextField(
        'Слова-триггеры',
        help_text='Слова или фразы через запятую, при наличии которых в вопросе подтягивается эта тема',
    )
    example_answer = models.TextField(
        'Пример ответа',
        blank=True,
        help_text='Шаблонный или примерный ответ по этой теме',
    )
    extra_data = models.TextField(
        'Доп. данные для ответа',
        blank=True,
        help_text='Дополнительная информация для формирования ответа (даты, факты и т.п.)',
    )
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Тема (триггеры + пример ответа)'
        verbose_name_plural = 'Справочник: темы и примеры ответов'
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def get_trigger_list(self):
        """Нормализованный список триггеров (фразы и слова через запятую/новую строку)."""
        if not self.trigger_words:
            return []
        parts = []
        for line in self.trigger_words.replace(',', '\n').splitlines():
            w = line.strip().lower()
            if w:
                parts.append(w)
        return list(dict.fromkeys(parts))


class AnswerLibrarySession(models.Model):
    """Сессия чата библиотеки ответов (вопросы кандидата + ответы ИИ)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='answer_library_sessions',
        verbose_name='Пользователь',
    )
    vacancy = models.ForeignKey(
        'vacancies.Vacancy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='answer_library_sessions',
        verbose_name='Вакансия',
        help_text='Выбранная вакансия для ответов (подтягиваются только темы для неё и общие)',
    )
    title = models.CharField('Название', max_length=200, default='')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Сессия библиотеки ответов'
        verbose_name_plural = 'Сессии библиотеки ответов'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title or "Сессия"} ({self.user.username})'


class AnswerLibraryMessage(models.Model):
    """Сообщение в чате библиотеки ответов."""
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, 'Пользователь'),
        (ROLE_ASSISTANT, 'ИИ'),
    ]

    session = models.ForeignKey(
        AnswerLibrarySession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Сессия',
    )
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES)
    content = models.TextField('Текст')
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_role_display()}: {self.content[:50]}...'
