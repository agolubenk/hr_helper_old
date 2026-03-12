# Generated manually for use_common_prompt field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0020_remove_salaryrange_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='use_common_prompt',
            field=models.BooleanField(default=False, help_text='Если включено, используется единый промпт из настроек компании. Если выключено, используется индивидуальный промпт.', verbose_name='Использовать общий промпт'),
        ),
    ]
