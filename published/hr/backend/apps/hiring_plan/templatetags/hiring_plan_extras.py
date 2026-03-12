from django import template

register = template.Library()

@register.filter
def enumerate_list(value):
    """Возвращает enumerate для списка"""
    return enumerate(value)

@register.filter
def get_item(dictionary, key):
    """Получить элемент из словаря по ключу"""
    return dictionary.get(key, {})

@register.filter
def grade_short(grade_name):
    """Сократить название грейда до первой буквы + знак"""
    if not grade_name:
        return ""
    
    # Убираем пробелы и берем первую букву
    first_letter = grade_name.strip()[0].upper()
    
    # Ищем знаки в конце (+, -, *, # и т.д.)
    import re
    match = re.search(r'([A-Za-z]+)([+\-*#]+)$', grade_name.strip())
    if match:
        return first_letter + match.group(2)
    
    return first_letter

@register.filter
def recruiter_short(user):
    """Сократить имя рекрутера до Фамилия И."""
    if not user:
        return ""
    
    # Получаем полное имя
    full_name = user.get_full_name()
    if not full_name:
        return user.username
    
    # Разделяем на части
    name_parts = full_name.strip().split()
    if len(name_parts) >= 2:
        # Фамилия + первая буква имени
        first_name = name_parts[0]
        last_name = name_parts[-1]
        return f"{last_name} {first_name[0].upper()}."
    elif len(name_parts) == 1:
        # Если только одно имя, возвращаем как есть
        return name_parts[0]
    else:
        return user.username
