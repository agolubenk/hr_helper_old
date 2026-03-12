from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    """
    Модель для хранения сессий чата с Gemini
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='gemini_chat_sessions',
        verbose_name='Пользователь'
    )
    title = models.CharField(
        max_length=200, 
        verbose_name='Название сессии',
        help_text='Название чат-сессии'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name='Создана'
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name='Обновлена'
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name='Активна'
    )

    class Meta:
        verbose_name = 'Сессия чата'
        verbose_name_plural = 'Сессии чата'
        db_table = 'gemini_chat_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} - {self.user.username}'


class ChatMessage(models.Model):
    """
    Модель для хранения сообщений в чате
    """
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'Ассистент'),
        ('system', 'Система'),
    ]

    session = models.ForeignKey(
        ChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages',
        verbose_name='Сессия'
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        verbose_name='Роль'
    )
    content = models.TextField(
        verbose_name='Содержание сообщения'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, 
        verbose_name='Время отправки'
    )
    tokens_used = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name='Использовано токенов'
    )
    response_time = models.FloatField(
        null=True, 
        blank=True, 
        verbose_name='Время ответа (сек)'
    )

    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        db_table = 'gemini_chat_messages'
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}...'
