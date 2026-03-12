# Generated manually for QuickButton model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_user_meeting_interval_minutes'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickButton',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Название быстрой кнопки', max_length=100, verbose_name='Название')),
                ('icon', models.CharField(default='fas fa-circle', help_text='Класс иконки Font Awesome (например: fas fa-link, fas fa-calendar)', max_length=50, verbose_name='Иконка')),
                ('button_type', models.CharField(choices=[('link', 'Ссылка'), ('text', 'Текст'), ('datetime', 'Дата и время')], default='link', help_text='Тип быстрой кнопки', max_length=20, verbose_name='Тип')),
                ('value', models.TextField(help_text='Значение в зависимости от типа: URL для ссылки, текст для текста, дата/время для datetime', verbose_name='Значение')),
                ('order', models.PositiveIntegerField(default=0, help_text='Порядок отображения (меньше = выше)', verbose_name='Порядок')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quick_buttons', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Быстрая кнопка',
                'verbose_name_plural': 'Быстрые кнопки',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='quickbutton',
            index=models.Index(fields=['user', 'order'], name='accounts_qu_user_id_order_idx'),
        ),
    ]
