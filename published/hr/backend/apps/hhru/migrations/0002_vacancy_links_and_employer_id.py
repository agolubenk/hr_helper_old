# Migration: employer_id on account, HHruVacancyLink model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hhru', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='hhruoauthaccount',
            name='employer_id',
            field=models.CharField(blank=True, max_length=64, verbose_name='ID работодателя на HH.ru'),
        ),
        migrations.CreateModel(
            name='HHruVacancyLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hh_vacancy_id', models.CharField(db_index=True, max_length=64, verbose_name='ID вакансии на HH.ru')),
                ('huntflow_id', models.CharField(blank=True, max_length=100, verbose_name='Huntflow ID')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vacancy_links', to='hhru.hhruoauthaccount', verbose_name='Аккаунт HH.ru')),
            ],
            options={
                'verbose_name': 'Связь вакансии HH.ru',
                'verbose_name_plural': 'Связи вакансий HH.ru',
                'ordering': ['-updated_at'],
                'unique_together': {('account', 'hh_vacancy_id')},
            },
        ),
    ]
