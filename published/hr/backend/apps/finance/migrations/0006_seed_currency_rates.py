# Generated manually for initial currency rates

from django.db import migrations
from decimal import Decimal


def create_initial_currency_rates(apps, schema_editor):
    """Создает начальные курсы валют с fallback значениями"""
    CurrencyRate = apps.get_model('finance', 'CurrencyRate')
    
    # Создаем курсы валют с fallback значениями
    initial_rates = [
        {
            'code': 'BYN',
            'rate': Decimal('1.000000'),
            'scale': 1,
        },
        {
            'code': 'USD', 
            'rate': Decimal('2.850000'),  # Fallback курс USD
            'scale': 1,
        },
        {
            'code': 'PLN',
            'rate': Decimal('0.720000'),  # Fallback курс PLN
            'scale': 1,
        }
    ]
    
    for rate_data in initial_rates:
        CurrencyRate.objects.get_or_create(
            code=rate_data['code'],
            defaults={
                'rate': rate_data['rate'],
                'scale': rate_data['scale'],
            }
        )


def reverse_create_initial_currency_rates(apps, schema_editor):
    """Удаляет начальные курсы валют"""
    CurrencyRate = apps.get_model('finance', 'CurrencyRate')
    CurrencyRate.objects.filter(code__in=['BYN', 'USD', 'PLN']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_salaryrange'),
    ]

    operations = [
        migrations.RunPython(
            create_initial_currency_rates,
            reverse_create_initial_currency_rates,
        ),
    ]

