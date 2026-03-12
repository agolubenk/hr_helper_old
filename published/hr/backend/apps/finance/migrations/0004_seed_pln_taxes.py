from django.db import migrations


def seed_pln_taxes(apps, schema_editor):
    PLNTax = apps.get_model('finance', 'PLNTax')
    
    # Примеры налогов для Польши
    taxes_data = [
        {
            'name': 'Подоходный налог (PIT)',
            'rate': 17.0,
            'is_active': True
        },
        {
            'name': 'Социальные взносы (ZUS)',
            'rate': 19.48,
            'is_active': True
        },
        {
            'name': 'Медицинское страхование',
            'rate': 9.0,
            'is_active': True
        },
        {
            'name': 'Дополнительные взносы',
            'rate': 2.45,
            'is_active': False  # Неактивный по умолчанию
        }
    ]
    
    for tax_data in taxes_data:
        PLNTax.objects.get_or_create(
            name=tax_data['name'],
            defaults={
                'rate': tax_data['rate'],
                'is_active': tax_data['is_active']
            }
        )


def unseed_pln_taxes(apps, schema_editor):
    PLNTax = apps.get_model('finance', 'PLNTax')
    PLNTax.objects.filter(
        name__in=[
            'Подоходный налог (PIT)',
            'Социальные взносы (ZUS)',
            'Медицинское страхование',
            'Дополнительные взносы'
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0003_plntax'),
    ]

    operations = [
        migrations.RunPython(seed_pln_taxes, reverse_code=unseed_pln_taxes),
    ]

