# Generated manually for VacancyPrompt models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('company_settings', '0006_companysettings_office_interview_instructions'),
    ]

    operations = [
        migrations.CreateModel(
            name='VacancyPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt', models.TextField(default='Проанализируй вакансию и предоставь детальную информацию о требованиях, зарплате и условиях работы.', help_text='Промпт для анализа вакансий с помощью AI', verbose_name='Текст промпта')),
                ('is_active', models.BooleanField(default=True, help_text='Используется ли этот промпт для анализа вакансий', verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
            ],
            options={
                'verbose_name': 'Промпт для вакансий',
                'verbose_name_plural': 'Промпты для вакансий',
            },
        ),
        migrations.CreateModel(
            name='VacancyPromptHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt_text', models.TextField(help_text='Текст промпта на момент сохранения', verbose_name='Текст промпта')),
                ('is_active', models.BooleanField(default=True, help_text='Был ли промпт активен на момент сохранения', verbose_name='Активен')),
                ('updated_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата обновления')),
                ('prompt', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='history', to='company_settings.vacancyprompt', verbose_name='Промпт')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Обновил', help_text='Пользователь, который внес изменения')),
            ],
            options={
                'verbose_name': 'История промпта',
                'verbose_name_plural': 'История промптов',
                'ordering': ['-updated_at'],
            },
        ),
    ]
