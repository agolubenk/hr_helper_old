# Generated manually for encrypted reminder phrase

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_quick_button_color'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserReminderPhrase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('encrypted_value', models.TextField(blank=True, default='', help_text='Фраза хранится в зашифрованном виде', verbose_name='Зашифрованное значение')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reminder_phrase', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Фраза-напоминание',
                'verbose_name_plural': 'Фразы-напоминания',
            },
        ),
    ]
