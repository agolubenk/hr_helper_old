from django import template
from django.utils.safestring import mark_safe
from urllib.parse import urlparse, parse_qs, unquote
import re

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
def get_contrast_color(hex_color):
    """
    Определяет контрастный цвет текста (белый или черный) для заданного hex цвета
    """
    if not hex_color:
        return '#000000'
    
    # Убираем # если есть
    hex_color = hex_color.lstrip('#')
    
    # Проверяем, что это валидный hex цвет
    if len(hex_color) != 6:
        return '#000000'
    
    try:
        # Конвертируем hex в RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Вычисляем яркость по формуле W3C
        # https://www.w3.org/WAI/ER/WD-AERT/#color-contrast
        brightness = ((r * 299) + (g * 587) + (b * 114)) / 1000
        
        # Если яркость больше 128, используем черный текст, иначе белый
        return '#000000' if brightness > 128 else '#ffffff'
        
    except (ValueError, IndexError):
        return '#000000'


@register.filter
def get_country(location):
    """Извлекает название страны из локации (последняя часть после запятой)"""
    if not location:
        return ""
    
    # Разделяем по запятой и берем последнюю часть
    parts = location.split(',')
    if len(parts) > 1:
        return parts[-1].strip()
    return location.strip()


@register.filter
def viber_phone(url):
    """
    Извлекает номер телефона из ссылки viber://chat?number=...
    Например: viber://chat?number=%2B375336169890 -> +375336169890
    """
    if not url or not isinstance(url, str) or 'viber' not in url.lower():
        return ''
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != 'viber':
            return ''
        qs = parse_qs(parsed.query)
        numbers = qs.get('number', [])
        if numbers:
            return unquote(str(numbers[0]).strip())
    except Exception:
        pass
    return ''