from django import template

register = template.Library()


@register.filter
def format_duration_minutes(minutes):
    """
    Форматирует время в минутах в читаемый формат (часы и минуты)
    
    Примеры:
    - 90 -> "1 ч 30 мин"
    - 60 -> "1 ч"
    - 45 -> "45 мин"
    - 0 -> "0 мин"
    """
    if not minutes:
        return "0 мин"
    
    minutes = int(minutes)
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours > 0 and remaining_minutes > 0:
        return f"{hours} ч {remaining_minutes} мин"
    elif hours > 0:
        return f"{hours} ч"
    else:
        return f"{minutes} мин"

