# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('huntflow', '0006_add_vacancy_id_to_linkedin_huntflow_link'),
    ]

    operations = [
        migrations.CreateModel(
            name='LevelText',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(help_text="Название уровня из Huntflow (например: Junior, Middle, Senior)", max_length=100, verbose_name='Уровень')),
                ('text', models.TextField(blank=True, help_text='Многострочный текст для этого уровня', verbose_name='Текст')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='level_texts', to='accounts.user', verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Текст для уровня',
                'verbose_name_plural': 'Тексты для уровней',
            },
        ),
        migrations.AddIndex(
            model_name='leveltext',
            index=models.Index(fields=['user', 'level'], name='huntflow_le_user_id_level_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='leveltext',
            unique_together={('user', 'level')},
        ),
    ]
