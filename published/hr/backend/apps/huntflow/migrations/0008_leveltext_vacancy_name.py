# Generated manually: уровни привязываем к вакансии; текущие в БД → Frontend

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('huntflow', '0007_leveltext'),
    ]

    operations = [
        migrations.AddField(
            model_name='leveltext',
            name='vacancy_name',
            field=models.CharField(
                default='Frontend',
                help_text='Название вакансии из Huntflow (например: Frontend, Backend)',
                max_length=255,
                verbose_name='Вакансия',
            ),
            preserve_default=False,
        ),
        migrations.RemoveIndex(
            model_name='leveltext',
            name='huntflow_le_user_id_level_idx',
        ),
        migrations.AlterUniqueTogether(
            name='leveltext',
            unique_together={('user', 'vacancy_name', 'level')},
        ),
        migrations.AddIndex(
            model_name='leveltext',
            index=models.Index(fields=['user', 'vacancy_name', 'level'], name='huntflow_le_user_id_vacancy_level_idx'),
        ),
    ]
