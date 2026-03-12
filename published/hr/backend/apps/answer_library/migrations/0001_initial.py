# Generated manually for answer_library

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TriggerTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название темы')),
                ('trigger_words', models.TextField(help_text='Слова или фразы через запятую, при наличии которых в вопросе подтягивается эта тема', verbose_name='Слова-триггеры')),
                ('example_answer', models.TextField(blank=True, help_text='Шаблонный или примерный ответ по этой теме', verbose_name='Пример ответа')),
                ('extra_data', models.TextField(blank=True, help_text='Дополнительная информация для формирования ответа (даты, факты и т.п.)', verbose_name='Доп. данные для ответа')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Тема (триггеры + пример ответа)',
                'verbose_name_plural': 'Справочник: темы и примеры ответов',
                'ordering': ['order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='AnswerLibrarySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='', max_length=200, verbose_name='Название')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_library_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Сессия библиотеки ответов',
                'verbose_name_plural': 'Сессии библиотеки ответов',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='AnswerLibraryMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'Пользователь'), ('assistant', 'ИИ')], max_length=20, verbose_name='Роль')),
                ('content', models.TextField(verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='answer_library.answerlibrarysession', verbose_name='Сессия')),
            ],
            options={
                'verbose_name': 'Сообщение',
                'verbose_name_plural': 'Сообщения',
                'ordering': ['created_at'],
            },
        ),
    ]
