from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('answer_library', '0002_vacancy_binding'),
    ]

    operations = [
        migrations.CreateModel(
            name='PromptTableRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic', models.CharField(max_length=255, verbose_name='Тема')),
                ('clarification_points', models.TextField(blank=True, verbose_name='Примеры вопросов/моментов для уточнения')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
            ],
            options={
                'verbose_name': 'Строка таблицы для промпта',
                'verbose_name_plural': 'Таблица для промпта',
                'ordering': ['order', 'id'],
            },
        ),
    ]
