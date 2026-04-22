from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('answer_library', '0003_prompttablerow'),
    ]

    operations = [
        migrations.AddField(
            model_name='prompttablerow',
            name='trigger_words',
            field=models.TextField(blank=True, help_text='Слова или фразы через запятую', verbose_name='Слова-триггеры'),
        ),
    ]
