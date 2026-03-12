"""
Модуль для парсинга даты и времени из естественного языка
Поддерживает русский язык, опечатки, сокращения и относительные даты
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import pytz


class DateTimeParser:
    """Парсер для извлечения даты и времени из текста на русском языке"""

    def __init__(self, timezone_name: str = 'Europe/Minsk'):
        self.timezone = pytz.timezone(timezone_name)

        # Регулярные выражения для различных форматов даты
        self.date_patterns = [
            # DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY
            r'(?P<day>\d{1,2})[.\-/](?P<month>\d{1,2})[.\-/](?P<year>\d{4})',
            # DD.MM.YY, DD-MM-YY
            r'(?P<day>\d{1,2})[.\-/](?P<month>\d{1,2})[.\-/](?P<year>\d{2})',
            # YYYY-MM-DD (ISO format)
            r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})',
            # DD MM YYYY (с пробелами)
            r'(?P<day>\d{1,2})\s+(?P<month>\d{1,2})\s+(?P<year>\d{4})',
        ]

        # Регулярные выражения для времени
        self.time_patterns = [
            # HH:MM, HH.MM
            r'(?P<hour>\d{1,2})[:\.](?P<minute>\d{2})',
            # HHMM
            r'(?P<hour>\d{1,2})(?P<minute>\d{2})(?=\s|$|[^\d])',
            # HH (только часы)
            r'(?P<hour>\d{1,2})(?=\s*(?:ч|час|утра|дня|вечера|ночи|$))',
        ]

        # Словари для русских названий
        self.months_ru = {
            'январ': 1, 'февр': 2, 'март': 3, 'апрел': 4, 'май': 5, 'мая': 5,
            'июн': 6, 'июл': 7, 'август': 8, 'сентябр': 9, 'октябр': 10, 
            'ноябр': 11, 'декабр': 12,
            # Сокращения с опечатками
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'июня': 6, 'июля': 7,
            'авг': 8, 'сен': 9, 'сент': 9, 'окт': 10, 'нояб': 11, 'дек': 12
        }

        self.weekdays_ru = {
            'понедельник': 0, 'пн': 0, 'пон': 0,
            'вторник': 1, 'вт': 1, 'втор': 1,
            'среда': 2, 'ср': 2, 'сред': 2,
            'четверг': 3, 'чт': 3, 'четв': 3,
            'пятница': 4, 'пт': 4, 'пятн': 4,
            'суббота': 5, 'сб': 5, 'субб': 5,
            'воскресенье': 6, 'вс': 6, 'воскр': 6,
        }

        # Относительные даты
        self.relative_dates = {
            'сегодня': 0, 'сёдня': 0, 'сейчас': 0,
            'завтра': 1, 'завт': 1, 'зафтра': 1,
            'послезавтра': 2, 'послезафтра': 2,
            'вчера': -1, 'вчира': -1,
            'позавчера': -2, 'позавчира': -2,
        }

        # Время суток
        self.time_periods = {
            'утром': 9, 'утра': 9, 'с утра': 9,
            'днем': 14, 'днём': 14, 'в обед': 13, 'обед': 13,
            'вечером': 18, 'вечера': 18,
            'ночью': 22, 'ночи': 22,
        }

    def clean_text(self, text: str) -> str:
        """Очистка и нормализация текста"""
        if not text:
            return ""

        # Удаление URL
        text = re.sub(r'https?://\S+', '', text)

        # Нормализация пробелов
        text = re.sub(r'\s+', ' ', text.strip())

        return text.lower()

    def extract_date(self, text: str) -> Optional[datetime]:
        """Извлечение даты из текста"""
        clean_text = self.clean_text(text)

        # 1. Поиск конкретных дат
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, clean_text)
            for match in matches:
                try:
                    day = int(match.group('day'))
                    month = int(match.group('month'))
                    year = int(match.group('year'))

                    # Преобразование 2-значного года
                    if year < 100:
                        if year < 30:  # 00-29 -> 2000-2029
                            year += 2000
                        else:  # 30-99 -> 1930-1999
                            year += 1900

                    # Проверка валидности даты
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
                except (ValueError, AttributeError):
                    continue

        # 2. Поиск дат с русскими названиями месяцев
        month_pattern = '|'.join(self.months_ru.keys())
        date_with_month = re.search(
            rf'(?P<day>\d{{1,2}})\s*(?P<month>{month_pattern})\w*\s*(?P<year>\d{{4}})?',
            clean_text
        )

        if date_with_month:
            try:
                day = int(date_with_month.group('day'))
                month_name = date_with_month.group('month')
                year = int(date_with_month.group('year')) if date_with_month.group('year') else datetime.now().year

                # Поиск месяца по названию
                month = None
                for month_key, month_num in self.months_ru.items():
                    if month_name.startswith(month_key):
                        month = month_num
                        break

                if month and 1 <= day <= 31:
                    return datetime(year, month, day)
            except (ValueError, AttributeError):
                pass

        # 3. Поиск относительных дат
        for relative_word, days_offset in self.relative_dates.items():
            if relative_word in clean_text:
                return datetime.now() + timedelta(days=days_offset)

        # 4. Поиск дней недели
        for weekday_name, weekday_num in self.weekdays_ru.items():
            if weekday_name in clean_text:
                current_date = datetime.now()
                current_weekday = current_date.weekday()
                days_ahead = (weekday_num - current_weekday) % 7
                if days_ahead == 0:  # Если сегодня этот день, берем следующую неделю
                    days_ahead = 7
                return current_date + timedelta(days=days_ahead)

        return None

    def extract_time(self, text: str, default_hour: int = 9) -> Optional[datetime]:
        """Извлечение времени из текста"""
        clean_text = self.clean_text(text)

        # 1. Поиск конкретного времени
        for pattern in self.time_patterns:
            matches = re.finditer(pattern, clean_text)
            for match in matches:
                try:
                    hour = int(match.group('hour'))
                    minute = int(match.group('minute')) if 'minute' in match.groupdict() and match.group('minute') else 0

                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                        return today
                except (ValueError, AttributeError):
                    continue

        # 2. Поиск времени суток
        for period_name, hour in self.time_periods.items():
            if period_name in clean_text:
                today = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
                return today

        return None

    def parse_datetime(self, text: str) -> Tuple[Optional[datetime], str]:
        """
        Основной метод парсинга даты и времени
        Возвращает кортеж (datetime_object, error_message)
        """
        if not text or not text.strip():
            return None, "Пустая строка"

        clean_text = self.clean_text(text)

        # Извлечение даты
        extracted_date = self.extract_date(clean_text)

        # Извлечение времени
        extracted_time = self.extract_time(clean_text)

        # Комбинирование даты и времени
        result_datetime = None

        if extracted_date and extracted_time:
            # Есть и дата, и время
            result_datetime = extracted_date.replace(
                hour=extracted_time.hour,
                minute=extracted_time.minute,
                second=0,
                microsecond=0
            )
        elif extracted_date:
            # Есть только дата, используем время по умолчанию
            result_datetime = extracted_date.replace(hour=9, minute=0, second=0, microsecond=0)
        elif extracted_time:
            # Есть только время, используем сегодняшнюю дату
            today = datetime.now().date()
            result_datetime = datetime.combine(today, extracted_time.time())

        if result_datetime:
            # Локализация временной зоны
            if result_datetime.tzinfo is None:
                result_datetime = self.timezone.localize(result_datetime)

            return result_datetime, "Успешно"
        else:
            return None, "Не удалось определить дату и время из текста"

    def format_result(self, dt: datetime) -> str:
        """Форматирование результата в строку DD.MM.YYYY HH:MM"""
        if dt:
            return dt.strftime("%d.%m.%Y %H:%M")
        return ""


# Функции для удобства использования
def parse_datetime_from_text(text: str, timezone_name: str = 'Europe/Minsk') -> Tuple[Optional[datetime], str]:
    """
    Простая функция для парсинга даты и времени из текста

    Args:
        text: Текст для анализа
        timezone_name: Название временной зоны

    Returns:
        Кортеж (datetime_object, error_message)
    """
    parser = DateTimeParser(timezone_name)
    return parser.parse_datetime(text)


def format_datetime_result(dt: Optional[datetime]) -> str:
    """
    Форматирование результата в строку DD.MM.YYYY HH:MM

    Args:
        dt: Объект datetime или None

    Returns:
        Отформатированная строка или пустая строка
    """
    if dt:
        return dt.strftime("%d.%m.%Y %H:%M")
    return ""


# Пример использования и тестирование
if __name__ == "__main__":
    parser = DateTimeParser()

    test_cases = [
        "завтра в 14:30",
        "послезавтра утром", 
        "25.09.2025 в 15:00",
        "понедельник в 18:00",
        "15 октября 2025 года в 10 утра",
        "сегодня вечером",
        "во вторник днем",
        "28/10/2025 20:15",
    ]

    print("🧪 Тестирование парсера:")
    for test_text in test_cases:
        result_dt, message = parser.parse_datetime(test_text)
        formatted_result = format_datetime_result(result_dt)
        print(f"  '{test_text}' -> {formatted_result if formatted_result else message}")
