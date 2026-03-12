# Generated manually for hiring plan folder

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clickup_int', '0010_clickupsettings_huntflow_filter'),
    ]

    operations = [
        migrations.AddField(
            model_name='clickupsettings',
            name='hiring_plan_folder_id',
            field=models.CharField(blank=True, help_text='Папка в ClickUp, из которой вытягиваются списки и задачи для плана найма', max_length=100, null=True, verbose_name='ID папки для плана найма'),
        ),
        migrations.AddField(
            model_name='clickupsettings',
            name='hiring_plan_space_id',
            field=models.CharField(blank=True, help_text='Пространство, в котором находится папка плана найма (для UI)', max_length=100, null=True, verbose_name='ID пространства папки плана найма'),
        ),
    ]
