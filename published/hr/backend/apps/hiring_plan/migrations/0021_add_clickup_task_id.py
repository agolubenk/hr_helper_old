# Generated manually for ClickUp integration with hiring plan

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_plan', '0020_alter_hiringrequest_opening_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='hiringrequest',
            name='clickup_task_id',
            field=models.CharField(
                blank=True,
                help_text='ID задачи в ClickUp для связи заявки с планом найма (например, из папки плана найма)',
                max_length=100,
                verbose_name='ID задачи в ClickUp'
            ),
        ),
    ]
