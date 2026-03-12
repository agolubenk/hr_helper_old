import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_clickup_text(text):
    """
    Форматирует текст ClickUp с поддержкой ссылок и базового форматирования
    """
    if not text:
        return text
    
    # Сначала обрабатываем обычные URL (http/https), но не те, что уже в Markdown-ссылках
    text = re.sub(
        r'(?<!\]\()(https?://[^\s<>"{}|\\^`\[\]]+)(?!\))', 
        r'<a href="\1" target="_blank" class="text-decoration-none">\1</a>', 
        text
    )
    
    # Затем обрабатываем Markdown ссылки [текст](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)', 
        r'<a href="\2" target="_blank" class="text-decoration-none">\1</a>', 
        text
    )
    
    # Обрабатываем email-адреса
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
        r'<a href="mailto:\1" class="text-decoration-none">\1</a>', 
        text
    )
    
    # Обрабатываем жирный текст (**текст**)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Обрабатываем курсив (*текст*)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    
    # Обрабатываем подчеркивание (__текст__)
    text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
    
    # Обрабатываем зачеркивание (~~текст~~)
    text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
    
    # Обрабатываем переносы строк
    text = text.replace('\n', '<br>')
    
    return mark_safe(text)


@register.filter
def format_clickup_links(text):
    """
    Простая обработка только ссылок в тексте ClickUp
    """
    if not text:
        return text
    
    # Обрабатываем ссылки [текст](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)', 
        r'<a href="\2" target="_blank" class="text-decoration-none">\1</a>', 
        text
    )
    
    return mark_safe(text)