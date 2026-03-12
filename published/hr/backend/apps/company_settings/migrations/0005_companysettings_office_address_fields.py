# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0004_alter_rejectiontemplate_rejection_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='office_address',
            field=models.CharField(blank=True, help_text='Полный адрес офиса компании', max_length=500, verbose_name='Адрес офиса'),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='office_map_link',
            field=models.URLField(blank=True, help_text='Ссылка на Google Maps, Yandex Maps или другую карту', max_length=1000, verbose_name='Ссылка на карты'),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='office_directions',
            field=models.TextField(blank=True, help_text='Подробное описание, как добраться до офиса (ориентиры, этаж, вход и т.д.)', verbose_name='Как пройти'),
        ),
    ]

