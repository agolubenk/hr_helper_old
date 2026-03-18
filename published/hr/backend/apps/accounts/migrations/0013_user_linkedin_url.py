# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_user_reminder_phrase'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='linkedin_url',
            field=models.URLField(
                blank=True,
                help_text='Ссылка на профиль LinkedIn (например: https://www.linkedin.com/in/username/)',
                max_length=500,
                verbose_name='LinkedIn профиль',
            ),
        ),
    ]
