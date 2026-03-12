# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0005_companysettings_office_address_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='office_interview_instructions',
            field=models.TextField(blank=True, help_text='Инструкции для кандидатов, которые приходят на офисное интервью (что взять с собой, куда обратиться, контакты и т.д.)', verbose_name='Инструкции для офисного интервью'),
        ),
    ]

