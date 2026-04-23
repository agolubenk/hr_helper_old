# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_user_linkedin_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='preferred_ai_model',
            field=models.CharField(
                choices=[
                    ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
                    ('gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite'),
                    ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
                    ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
                    ('gemini-1.0-pro', 'Gemini 1.0 Pro'),
                ],
                default='gemini-2.0-flash',
                help_text='Базовая модель Gemini для генерации ответов',
                max_length=64,
                verbose_name='Предпочтительная AI модель',
            ),
        ),
    ]
