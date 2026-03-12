# Generated manually for QuickButton color field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_add_quick_buttons'),
    ]

    operations = [
        migrations.AddField(
            model_name='quickbutton',
            name='color',
            field=models.CharField(default='#007bff', help_text='Цвет фона кнопки в формате HEX (например: #007bff)', max_length=7, verbose_name='Цвет фона'),
        ),
    ]
