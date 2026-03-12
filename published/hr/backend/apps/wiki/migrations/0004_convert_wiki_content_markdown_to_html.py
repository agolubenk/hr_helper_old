# Миграция данных: конвертация существующего Markdown-содержимого вики в HTML
# для перехода на единое поле Summernote (WYSIWYG). Все текущие записи остаются
# читаемыми и отображаются как раньше, но в формате HTML.

from django.db import migrations
import markdown


def _looks_like_html(text):
    """Считаем контент уже HTML, если начинается с тега или содержит типичные блоки."""
    if not text or not text.strip():
        return True  # пустой не трогаем
    s = text.strip()
    if s.startswith('<') and '>' in s[:50]:
        return True
    if s.startswith('<!') or s.startswith('<?'):
        return True
    return False


def _markdown_to_html(text):
    if not text:
        return text
    return markdown.markdown(text, output_format='html5')


def convert_markdown_to_html(apps, schema_editor):
    WikiPage = apps.get_model('wiki', 'WikiPage')
    WikiPageHistory = apps.get_model('wiki', 'WikiPageHistory')
    for page in WikiPage.objects.all():
        if not _looks_like_html(page.content):
            page.content = _markdown_to_html(page.content)
            page.save(update_fields=['content'])
    for entry in WikiPageHistory.objects.all():
        if not _looks_like_html(entry.content):
            entry.content = _markdown_to_html(entry.content)
            entry.save(update_fields=['content'])


def noop_reverse(apps, schema_editor):
    """Обратная миграция не восстанавливает Markdown из HTML (потеря информации)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0003_alter_wikipage_category'),
    ]

    operations = [
        migrations.RunPython(convert_markdown_to_html, noop_reverse),
    ]
