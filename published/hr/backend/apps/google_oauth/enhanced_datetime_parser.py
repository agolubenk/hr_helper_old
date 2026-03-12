"""
Документация по проблемным импортам (линтер):
- pytz, dateutil, dateutil.parser — расширенный парсинг дат/времени и таймзоны

Влияние: улучшенный парсер даты/времени (для сообщений/инвайтов) будет работать ограниченно
или не работать вовсе без этих библиотек: распознавание форматов, таймзоны и нормализация дат
станут некорректными.
"""
"""
Расширенный парсер даты и времени с поддержкой всех форматов из библиотеки
Поддерживает: русский/английский, опечатки, неправильную раскладку, относительные даты
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from decimal import Decimal
import pytz


class EnhancedDateTimeParser:
    """
    Расширенный парсер для извлечения даты и времени из естественного языка
    с поддержкой всех форматов из библиотеки date-time-formats.md
    """

    def __init__(self, user=None, timezone_name: str = 'Europe/Minsk'):
        self.user = user
        self.timezone = pytz.timezone(timezone_name)
        
        # Бизнес-часы из настроек пользователя
        self.BUSINESS_HOURS = self._get_user_business_hours()
        # Валидные минуты: кратно 5 (00, 05, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)
        self.TIME_SLOTS = list(range(0, 60, 5))
        
        # Импорт словарей из библиотеки
        self._load_dictionaries()
    
    def _get_user_business_hours(self):
        """
        Получает эффективные рабочие часы (компания -> пользователь -> по умолчанию).
        
        Returns:
            dict: Словарь с ключами 'start' и 'end' (часы)
        """
        company_settings = None
        try:
            from apps.company_settings.models import CompanySettings
            company_settings = CompanySettings.get_settings()
        except Exception:
            pass
        from logic.working_hours_service import get_effective_working_hours
        hours = get_effective_working_hours(self.user, company_settings)
        return {
            'start': hours['work_start_hour'],
            'end': hours['work_end_hour'],
        }
    
    def _load_dictionaries(self):
        """Загрузка всех словарей из библиотеки форматов"""
        
        # Импорт полных словарей из библиотеки
        try:
            from .weekdays_full import WEEKDAYS as WEEKDAYS_FULL
            from .months_full import MONTHS as MONTHS_FULL
            
            self.WEEKDAYS = WEEKDAYS_FULL
            self.MONTHS = MONTHS_FULL
            print(f"✅ [PARSER_INIT] Загружены полные словари: {len(self.WEEKDAYS)} дней недели, {len(self.MONTHS)} месяцев")
        except ImportError as e:
            print(f"⚠️ [PARSER_INIT] Не удалось загрузить полные словари, используем базовые: {e}")
            
            # Базовые словари (fallback)
            self.WEEKDAYS = {
                'понедельник': 0, 'пн': 0, 'пон': 0, 'понед': 0,
                'gy': 0, 'gj': 0, 'monday': 0, 'mon': 0,
                'вторник': 1, 'вт': 1, 'втор': 1,
                'ds': 1, 'cu': 1, 'tuesday': 1, 'tue': 1,
                'среда': 2, 'ср': 2, 'сред': 2,
                'ch': 2, 'cc': 2, 'wednesday': 2, 'wed': 2,
                'четверг': 3, 'чт': 3, 'четв': 3,
                'xn': 3, 'db': 3, 'thursday': 3, 'thu': 3,
                'пятница': 4, 'пт': 4, 'пятн': 4,
                'gn': 4, 'friday': 4, 'fri': 4,
                'суббота': 5, 'сб': 5, 'субб': 5,
                'saturday': 5, 'sat': 5,
                'воскресенье': 6, 'вс': 6, 'воскр': 6,
                'sunday': 6, 'sun': 6,
            }
            
            self.MONTHS = {
                'январь': 1, 'янв': 1, 'january': 1, 'jan': 1, 'zydfhm': 1,
                'февраль': 2, 'фев': 2, 'february': 2, 'feb': 2, 'atdhfkm': 2,
                'март': 3, 'мар': 3, 'march': 3, 'mar': 3, 'vfhn': 3,
                'апрель': 4, 'апр': 4, 'april': 4, 'apr': 4, 'fghtkm': 4,
                'май': 5, 'may': 5, 'vfq': 5,
                'июнь': 6, 'июн': 6, 'june': 6, 'jun': 6, 'bym': 6,
                'июль': 7, 'июл': 7, 'july': 7, 'jul': 7, 'bkm': 7,
                'август': 8, 'авг': 8, 'august': 8, 'aug': 8, 'fduecn': 8,
                'сентябрь': 9, 'сен': 9, 'сент': 9, 'september': 9, 'sep': 9, 'ctynzhm': 9,
                'октябрь': 10, 'окт': 10, 'october': 10, 'oct': 10, 'jrnzhm': 10,
                'ноябрь': 11, 'ноя': 11, 'нояб': 11, 'november': 11, 'nov': 11, 'yjzhm': 11,
                'декабрь': 12, 'дек': 12, 'december': 12, 'dec': 12, 'ltrfhm': 12,
            }
        
        # Неправильная раскладка клавиатуры
        self.KEYBOARD_MAPPING = {
            # Английские буквы → Русские (QWERTY → ЙЦУКЕН)
            'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н',
            'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
            'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р',
            'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
            'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т',
            'm': 'ь', ',': 'б', '.': 'ю', '/': '.',
            
            # Русские буквы → Английские (ЙЦУКЕН → QWERTY)
            'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y',
            'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
            'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h',
            'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
            'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n',
            'ь': 'm', 'б': ',', 'ю': '.', '.': '/'
        }
        
        # Частые ошибки раскладки
        self.COMMON_KEYBOARD_ERRORS = {
            'GY': 'ПН', 'ds': 'вт', 'ch': 'ср', 'xn': 'чт', 'gn': 'пт',
            'c,': 'сб', 'dc': 'вс',
            'pfdnhf': 'завтра', 'ctuljyz': 'сегодня', 'gjcrfx': 'после',
            'jrn': 'окт', 'yjz': 'ноя', 'ltrf,hm': 'декабрь'
        }
        
        # Расширенные относительные даты
        self.RELATIVE_DATES = {
            # Сегодня
            'сегодня': 0, 'сёдня': 0, 'седня': 0, 'седн': 0, 'сед': 0,
            'today': 0, 'tod': 0, 'ctuljyz': 0, 'ctulj': 0, 'ctul': 0,
            'сейчас': 0, 'сейч': 0, 'сей': 0,
            'now': 0, 'nw': 0,
            
            # Завтра
            'завтра': 1, 'завтро': 1, 'завр': 1, 'зав': 1, 'завт': 1,
            'tomorrow': 1, 'tom': 1, 'pfdnhf': 1, 'pfdn': 1, 'pfd': 1,
            'завтрашний день': 1, 'завтрашний': 1,
            
            # Послезавтра
            'послезавтра': 2, 'послезавтро': 2, 'послезавт': 2, 'послезав': 2,
            'day after tomorrow': 2, 'day after': 2,
            'через день': 1, 'через 1 день': 1, 'через один день': 1,
            
            # Через несколько дней
            'через два дня': 2, 'через 2 дня': 2, 'через два': 2,
            'через три дня': 3, 'через 3 дня': 3, 'через три': 3,
            'через четыре дня': 4, 'через 4 дня': 4, 'через четыре': 4,
            'через пять дней': 5, 'через 5 дней': 5, 'через пять': 5,
            'через шесть дней': 6, 'через 6 дней': 6, 'через шесть': 6,
            
            # Недели
            'через неделю': 7, 'через 1 неделю': 7, 'через одну неделю': 7,
            'через две недели': 14, 'через 2 недели': 14, 'через две': 14,
            'через три недели': 21, 'через 3 недели': 21, 'через три': 21,
            
            # Следующая неделя
            'на следующей неделе': 'next_week', 'следующая неделя': 'next_week',
            'след неделе': 'next_week', 'следующей неделе': 'next_week',
            'next week': 'next_week', 'next wk': 'next_week',
            'в следующую неделю': 'next_week', 'на след неделе': 'next_week',
            
            # Месяцы
            'через месяц': 30, 'через 1 месяц': 30, 'через один месяц': 30,
            'через два месяца': 60, 'через 2 месяца': 60, 'через два': 60,
            'через три месяца': 90, 'через 3 месяца': 90, 'через три': 90,
            
            # Следующий месяц
            'в следующем месяце': 'next_month', 'следующий месяц': 'next_month',
            'next month': 'next_month', 'next mon': 'next_month',
            
            # Годы
            'через год': 365, 'через 1 год': 365, 'через один год': 365,
            'через два года': 730, 'через 2 года': 730, 'через два': 730,
            
            # Следующий год
            'в следующем году': 'next_year', 'следующий год': 'next_year',
            'next year': 'next_year', 'next yr': 'next_year',
            
            # Временные периоды
            'через полчаса': 0.5, 'через 30 минут': 0.5, 'через пол часа': 0.5,
            'через час': 1, 'через 1 час': 1, 'через один час': 1,
            'через два часа': 2, 'через 2 часа': 2, 'через два': 2,
            'через три часа': 3, 'через 3 часа': 3, 'через три': 3,
            
            # Английские варианты
            'in an hour': 1, 'in 1 hour': 1, 'in one hour': 1,
            'in two hours': 2, 'in 2 hours': 2, 'in two': 2,
            'in a day': 1, 'in 1 day': 1, 'in one day': 1,
            'in two days': 2, 'in 2 days': 2, 'in two': 2,
            'in a week': 7, 'in 1 week': 7, 'in one week': 7,
            'in two weeks': 14, 'in 2 weeks': 14, 'in two': 14,
            'in a month': 30, 'in 1 month': 30, 'in one month': 30,
            'in two months': 60, 'in 2 months': 60, 'in two': 60,
        }
        
        # Регулярные выражения для парсинга
        self.DATE_PATTERNS = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})',      # DD.MM.YYYY
            r'(\d{1,2})\.(\d{1,2})',                 # DD.MM
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',       # DD/MM/YYYY
            r'(\d{1,2})/(\d{1,2})',                  # DD/MM
            r'(\d{1,2})-(\d{1,2})-(\d{2,4})',       # DD-MM-YYYY
            r'(\d{1,2})-(\d{1,2})',                  # DD-MM
            r'(\d{4})-(\d{1,2})-(\d{1,2})',         # YYYY-MM-DD (ISO)
        ]
        
        self.TIME_PATTERNS = [
            r'(\d{1,2})[:\.\-](\d{2})',             # HH:MM, HH.MM, HH-MM
            r'(\d{1,2})\s*(?:ч|час|h|час\.|h\.)',   # HH час
            r'(?:^|\s)(\d{1,2})(?:\s|$)',           # просто число (час)
        ]
    
    def fix_keyboard_layout(self, text: str) -> Tuple[str, List[Dict]]:
        """Исправление неправильной раскладки клавиатуры"""
        corrections = []
        original_text = text.lower()
        
        # Исправление частых ошибок раскладки
        for wrong, correct in self.COMMON_KEYBOARD_ERRORS.items():
            if wrong.lower() in original_text:
                text = text.replace(wrong.lower(), correct.lower())
                corrections.append({
                    'type': 'keyboard_layout',
                    'original': wrong,
                    'corrected': correct,
                    'reason': 'исправление неправильной раскладки'
                })
        
        # Посимвольное исправление только для слов, которых нет в словарях
        words = text.split()
        corrected_words = []
        
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            # Проверяем, есть ли это слово уже в наших словарях
            if clean_word in self.WEEKDAYS or clean_word in self.MONTHS or clean_word in self.RELATIVE_DATES:
                # Слово уже правильное, не трогаем
                corrected_words.append(word)
                continue
            
            # Пробуем посимвольное исправление раскладки
            corrected_word = ''
            for char in word:
                if char.lower() in self.KEYBOARD_MAPPING:
                    corrected_char = self.KEYBOARD_MAPPING[char.lower()]
                    if char.isupper():
                        corrected_char = corrected_char.upper()
                    corrected_word += corrected_char
                else:
                    corrected_word += char
            
            # Проверяем, стало ли слово правильным после исправления
            corrected_clean = re.sub(r'[^\w]', '', corrected_word.lower())
            if corrected_word != word and (
                corrected_clean in self.WEEKDAYS or 
                corrected_clean in self.MONTHS or 
                corrected_clean in self.RELATIVE_DATES
            ):
                corrections.append({
                    'type': 'keyboard_layout',
                    'original': word,
                    'corrected': corrected_word,
                    'reason': 'посимвольное исправление раскладки'
                })
                corrected_words.append(corrected_word)
            else:
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        return corrected_text, corrections
    
    def normalize_text(self, text: str) -> Tuple[str, List[Dict]]:
        """Нормализация и очистка текста"""
        if not text:
            return "", []
        
        # Удаление URL
        text = re.sub(r'https?://\S+', '', text)
        
        # Нормализация пробелов
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Приведение к нижнему регистру
        text = text.lower()
        
        # Исправление раскладки клавиатуры
        text, corrections = self.fix_keyboard_layout(text)
        
        return text, corrections
    
    def extract_weekday(self, text: str) -> Optional[int]:
        """Извлечение дня недели из текста"""
        text_lower = text.lower()
        
        # Сначала ищем точное совпадение слова (без исправления раскладки)
        words = text_lower.split()
        for word in words:
            # Убираем знаки препинания
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.WEEKDAYS:
                return self.WEEKDAYS[clean_word]
        
        # Затем ищем вхождение в строке
        for weekday_name, weekday_num in self.WEEKDAYS.items():
            if weekday_name in text_lower:
                return weekday_num
        
        # Если не найдено, пробуем без исправления раскладки в исходном тексте
        # (потому что fix_keyboard_layout может испортить правильные русские слова)
        return None
    
    def extract_month(self, text: str) -> Optional[int]:
        """Извлечение месяца из текста"""
        text_lower = text.lower()
        
        # Сначала ищем точное совпадение слова
        words = text_lower.split()
        for word in words:
            # Убираем знаки препинания
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.MONTHS:
                return self.MONTHS[clean_word]
        
        # Затем ищем вхождение в строке
        for month_name, month_num in self.MONTHS.items():
            if month_name in text_lower:
                return month_num
        
        return None
    
    def extract_relative_date(self, text: str) -> Optional[datetime]:
        """Извлечение относительной даты из текста"""
        text_lower = text.lower()
        minsk_tz = pytz.timezone('Europe/Minsk')
        current_date = datetime.now(minsk_tz)
        
        for relative_word, days_offset in self.RELATIVE_DATES.items():
            if relative_word in text_lower:
                if days_offset == 'next_week':
                    # Следующая неделя - понедельник
                    days_to_next_monday = (7 - current_date.weekday()) % 7
                    if days_to_next_monday == 0:
                        days_to_next_monday = 7
                    return current_date + timedelta(days=days_to_next_monday)
                elif days_offset == 'next_month':
                    # Следующий месяц - первое число
                    if current_date.month == 12:
                        next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
                    else:
                        next_month = current_date.replace(month=current_date.month + 1, day=1)
                    return next_month
                elif days_offset == 'next_year':
                    # Следующий год - первое января
                    next_year = current_date.replace(year=current_date.year + 1, month=1, day=1)
                    return next_year
                elif isinstance(days_offset, (int, float)):
                    # Обычное смещение в днях
                    if days_offset < 1:
                        # Для временных периодов меньше дня (например, полчаса)
                        # Возвращаем текущую дату, время будет обработано отдельно
                        return current_date
                    else:
                        return current_date + timedelta(days=days_offset)
        
        return None
    
    def extract_date_from_patterns(self, text: str) -> Optional[datetime]:
        """Извлечение даты из числовых паттернов"""
        for pattern in self.DATE_PATTERNS:
            matches = list(re.finditer(pattern, text))
            for match in matches:
                try:
                    groups = match.groups()
                    
                    # Определяем формат (DD.MM.YYYY vs YYYY-MM-DD)
                    if len(groups) == 3:
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:  # DD.MM.YYYY
                            day, month = int(groups[0]), int(groups[1])
                            year = int(groups[2]) if groups[2] else datetime.now().year
                            
                            # Преобразование 2-значного года
                            if year < 100:
                                year += 2000 if year < 30 else 1900
                    elif len(groups) == 2:  # DD.MM (без года)
                        day, month = int(groups[0]), int(groups[1])
                        year = datetime.now().year
                    else:
                        continue
                    
                    # Валидация даты
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
                except (ValueError, AttributeError):
                    continue
        
        return None
    
    def extract_date_with_month_name(self, text: str) -> Optional[datetime]:
        """Извлечение даты с текстовым месяцем"""
        # Паттерн: DD месяц [YYYY]
        for month_name, month_num in self.MONTHS.items():
            pattern = rf'(\d{{1,2}})\s*{month_name}\w*\s*(\d{{4}})?'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                try:
                    day = int(match.group(1))
                    year = int(match.group(2)) if match.group(2) else datetime.now().year
                    
                    if 1 <= day <= 31:
                        return datetime(year, month_num, day)
                except (ValueError, AttributeError):
                    continue
        
        return None
    
    def extract_time(self, text: str) -> Optional[Tuple[int, int]]:
        """Извлечение времени из текста"""
        # Сначала ищем время с разделителем : (двоеточие - это точно время)
        time_pattern_colon = r'(\d{1,2}):(\d{2})'
        matches = list(re.finditer(time_pattern_colon, text))
        
        for match in matches:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2))
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return hour, minute
            except (ValueError, AttributeError, IndexError):
                continue
        
        # Ищем время с точкой или тире, НО проверяем контекст более тщательно
        time_pattern_dot_dash = r'(\d{1,2})[\.\-](\d{2})'
        matches = list(re.finditer(time_pattern_dot_dash, text))
        
        for match in matches:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2))
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    # Проверяем контекст - это дата или время?
                    context_before = text[max(0, match.start()-5):match.start()]
                    context_after = text[match.end():min(len(text), match.end()+10)]
                    
                    # Если оба числа <= 12, это может быть дата DD.MM
                    if hour <= 31 and minute <= 12:
                        # Это скорее дата, чем время - пропускаем
                        # Исключение: если есть явные временные маркеры
                        if not re.search(r'(?:в|к|время|час|ч|time|at)', context_before + context_after, re.IGNORECASE):
                            continue
                    
                    # Если минута > 31, это точно не дата
                    if minute > 31:
                        return hour, minute
                    
                    # Если час > 12, это скорее время
                    if hour > 12:
                        return hour, minute
                    
            except (ValueError, AttributeError, IndexError):
                continue
        
        # Ищем время с ключевыми словами (час, ч, h)
        time_pattern_with_keyword = r'(\d{1,2})\s*(?:ч|час|h|час\.|h\.)'
        matches = list(re.finditer(time_pattern_with_keyword, text))
        for match in matches:
            try:
                hour = int(match.group(1))
                if 0 <= hour <= 23:
                    return hour, 0
            except (ValueError, AttributeError):
                continue
        
        # Ищем просто число (час) после дня недели или предлога "в"
        # Паттерн 1: день недели + число
        weekday_hour_pattern = r'(?:пн|вт|ср|чт|пт|сб|вс|понедельник|вторник|среда|четверг|пятница|суббота|воскресенье|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun|gy|ds|ch|xn|gn)\s+(?:в\s+)?(\d{1,2})(?:\s|$)'
        matches = list(re.finditer(weekday_hour_pattern, text, re.IGNORECASE))
        for match in matches:
            try:
                hour = int(match.group(1))
                if 8 <= hour <= 23:  # Разумный диапазон часов
                    return hour, 0
            except (ValueError, AttributeError):
                continue
        
        # Паттерн 2: просто "в ЧЧ" или "к ЧЧ" (также учитываем "d" после исправления раскладки)
        preposition_hour_pattern = r'(?:в|к|после|до|около|примерно|d)\s+(\d{1,2})(?:\s|$)'
        matches = list(re.finditer(preposition_hour_pattern, text, re.IGNORECASE))
        for match in matches:
            try:
                hour = int(match.group(1))
                if 8 <= hour <= 23:
                    return hour, 0
            except (ValueError, AttributeError):
                continue
        
        # Паттерн 3: просто число в конце строки (если нет других чисел)
        end_number_pattern = r'\s(\d{1,2})$'
        match = re.search(end_number_pattern, text)
        if match:
            try:
                hour = int(match.group(1))
                if 8 <= hour <= 23:
                    return hour, 0
            except (ValueError, AttributeError):
                pass
        
        return None
    
    def extract_time_periods(self, text: str) -> Optional[Tuple[int, int]]:
        """Извлечение времени из относительных временных периодов"""
        text_lower = text.lower()
        minsk_tz = pytz.timezone('Europe/Minsk')
        current_time = datetime.now(minsk_tz)
        
        # Словарь временных периодов
        time_periods = {
            # Полчаса
            'через полчаса': 30, 'через 30 минут': 30, 'через пол часа': 30,
            'через пол часа': 30, 'через пол-часа': 30, 'через полчаса': 30,
            'in 30 minutes': 30, 'in half an hour': 30, 'in 30 min': 30,
            
            # Час
            'через час': 60, 'через 1 час': 60, 'через один час': 60,
            'через 60 минут': 60, 'через час': 60,
            'in an hour': 60, 'in 1 hour': 60, 'in one hour': 60,
            'in 60 minutes': 60, 'in 1h': 60,
            
            # Два часа
            'через два часа': 120, 'через 2 часа': 120, 'через два': 120,
            'через 120 минут': 120, 'через 2ч': 120,
            'in two hours': 120, 'in 2 hours': 120, 'in two': 120,
            'in 120 minutes': 120, 'in 2h': 120,
            
            # Три часа
            'через три часа': 180, 'через 3 часа': 180, 'через три': 180,
            'через 180 минут': 180, 'через 3ч': 180,
            'in three hours': 180, 'in 3 hours': 180, 'in three': 180,
            'in 180 minutes': 180, 'in 3h': 180,
        }
        
        for period_text, minutes_offset in time_periods.items():
            if period_text in text_lower:
                # Вычисляем время через указанный период
                future_time = current_time + timedelta(minutes=minutes_offset)
                return future_time.hour, future_time.minute
        
        return None
    
    def round_to_valid_slot(self, hour: int, minute: int) -> Tuple[int, int, List[Dict]]:
        """Округление времени до валидного слота (кратно 5 минутам: 00, 05, 10, ..., 55)."""
        corrections = []
        original_time = f"{hour:02d}:{minute:02d}"
        
        # Если минуты уже кратны 5 — используем время как есть
        if minute % 5 == 0:
            rounded_minute = minute
        else:
            # Округление до ближайшего кратного 5
            rounded_minute = round(minute / 5) * 5
            if rounded_minute >= 60:
                rounded_minute = 0
                hour += 1
            if minute != rounded_minute:
                corrections.append({
                    'type': 'time_rounding',
                    'original': original_time,
                    'corrected': f"{hour:02d}:{rounded_minute:02d}",
                    'reason': 'округление до валидного слота (кратно 5 мин: 00, 05, 10, …, 55)'
                })
        
        # Проверка бизнес-часов: начало дня
        if hour < self.BUSINESS_HOURS['start']:
            corrections.append({
                'type': 'business_hours_adjustment',
                'original': f"{hour:02d}:{rounded_minute:02d}",
                'corrected': f"{self.BUSINESS_HOURS['start']:02d}:00",
                'reason': 'перенос в начало рабочего дня'
            })
            hour = self.BUSINESS_HOURS['start']
            rounded_minute = 0
        # Конец дня: последний слот — 17:55 (кратно 5, до 18:00)
        elif hour > self.BUSINESS_HOURS['end'] - 1 or (hour == self.BUSINESS_HOURS['end'] - 1 and rounded_minute > 55):
            last_slot = f"{self.BUSINESS_HOURS['end'] - 1:02d}:55"
            corrections.append({
                'type': 'business_hours_adjustment',
                'original': f"{hour:02d}:{rounded_minute:02d}",
                'corrected': last_slot,
                'reason': 'перенос на последний слот рабочего дня'
            })
            hour = self.BUSINESS_HOURS['end'] - 1
            rounded_minute = 55
        
        return hour, rounded_minute, corrections
    
    def find_next_weekday(self, target_weekday: int, skip_today: bool = True) -> datetime:
        """Поиск ближайшего дня недели"""
        minsk_tz = pytz.timezone('Europe/Minsk')
        current_date = datetime.now(minsk_tz)
        current_weekday = current_date.weekday()
        
        # Вычисляем дней до целевого дня недели
        days_ahead = (target_weekday - current_weekday) % 7
        
        # Если это сегодня и skip_today = True, берем следующую неделю
        if days_ahead == 0 and skip_today:
            days_ahead = 7
        
        target_date = current_date + timedelta(days=days_ahead)
        return target_date
    
    def _check_slot_availability(self, dt: datetime, existing_bookings: List) -> Dict:
        """
        Проверка доступности слота в календаре
        Возвращает информацию о занимающем событии или None, если слот свободен
        """
        try:
            # Формируем диапазон времени для слота (45 минут)
            slot_start = dt
            slot_end = dt + timedelta(minutes=45)
            
            for booking in existing_bookings:
                try:
                    # Получаем время начала и конца события
                    event_start_str = booking.get('start', {}).get('dateTime') or booking.get('start', {}).get('date')
                    event_end_str = booking.get('end', {}).get('dateTime') or booking.get('end', {}).get('date')
                    
                    if not event_start_str or not event_end_str:
                        continue
                    
                    # Парсим даты событий
                    from dateutil import parser as date_parser
                    event_start = date_parser.parse(event_start_str)
                    event_end = date_parser.parse(event_end_str)
                    
                    # Проверяем пересечение
                    # Слот занят, если:
                    # 1. Начало слота находится внутри события
                    # 2. Конец слота находится внутри события
                    # 3. Слот полностью перекрывает событие
                    if (event_start <= slot_start < event_end) or \
                       (event_start < slot_end <= event_end) or \
                       (slot_start <= event_start and slot_end >= event_end):
                        print(f"⚠️ [SLOT_CHECK] Слот {dt.strftime('%d.%m %H:%M')} занят событием: {booking.get('summary', 'Без названия')}")
                        return {
                            'summary': booking.get('summary', 'Без названия'),
                            'start': event_start.strftime('%d.%m %H:%M'),
                            'end': event_end.strftime('%d.%m %H:%M')
                        }
                
                except Exception as e:
                    print(f"⚠️ [SLOT_CHECK] Ошибка проверки события: {e}")
                    continue
            
            print(f"✅ [SLOT_CHECK] Слот {dt.strftime('%d.%m %H:%M')} свободен")
            return None
            
        except Exception as e:
            print(f"❌ [SLOT_CHECK] Ошибка проверки доступности: {e}")
            return None
    
    def validate_datetime(self, dt: datetime, existing_bookings: List = None) -> Dict:
        """Многоуровневая валидация даты и времени"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        minsk_tz = pytz.timezone('Europe/Minsk')
        current_date = datetime.now(minsk_tz)
        
        # Проверка: не прошедшая дата
        if dt < current_date:
            validation_result['is_valid'] = False
            validation_result['errors'].append({
                'type': 'past_date',
                'description': 'Дата в прошлом',
                'severity': 'high'
            })
        
        # Проверка: не сегодняшний день
        if dt.date() == current_date.date():
            validation_result['warnings'].append({
                'type': 'same_day',
                'description': 'Встреча в тот же день',
                'severity': 'medium'
            })
        
        # Проверка: бизнес-часы
        if dt.hour < self.BUSINESS_HOURS['start'] or dt.hour >= self.BUSINESS_HOURS['end']:
            validation_result['is_valid'] = False
            validation_result['errors'].append({
                'type': 'outside_business_hours',
                'description': f'Время вне рабочих часов ({self.BUSINESS_HOURS["start"]}:00-{self.BUSINESS_HOURS["end"]-1}:55)',
                'severity': 'high'
            })
        
        # Проверка: минуты кратны 5 (00, 05, 10, …, 55)
        if dt.minute not in self.TIME_SLOTS:
            validation_result['is_valid'] = False
            validation_result['errors'].append({
                'type': 'invalid_minutes',
                'description': 'Минуты должны быть кратны 5 (00, 05, 10, 15, …, 55)',
                'severity': 'medium'
            })
        
        # Проверка: не слишком далеко в будущем (90 дней)
        if (dt - current_date).days > 90:
            validation_result['warnings'].append({
                'type': 'far_future',
                'description': 'Встреча запланирована более чем на 90 дней вперед',
                'severity': 'low'
            })
        
        # Проверка: занятость слота в календаре
        if existing_bookings:
            # Проверяем, есть ли события в это время
            slot_occupied = self._check_slot_availability(dt, existing_bookings)
            if slot_occupied:
                validation_result['is_valid'] = False
                validation_result['errors'].append({
                    'type': 'slot_occupied',
                    'description': f'Слот {dt.strftime("%d.%m %H:%M")} уже занят',
                    'severity': 'high',
                    'occupied_event': slot_occupied
                })
        
        return validation_result
    
    def parse_datetime(self, text: str, existing_bookings: List = None, vacancy_prompt: str = None, skip_time_adjustment: bool = False) -> Dict:
        """
        Основной метод парсинга даты и времени с полной валидацией и коррекцией
        
        Args:
            text: Текст для анализа
            existing_bookings: Список существующих бронирований
            vacancy_prompt: Промпт из вакансии
            skip_time_adjustment: Если True, не переносит время при конфликтах (для технических интервью)
        
        Возвращает словарь с результатами анализа:
        {
            "parsed_datetime": "DD.MM.YYYY HH:MM",
            "confidence": 0.95,
            "alternatives": [...],
            "corrections": [...],
            "validation": {...},
            "metadata": {...}
        }
        """
        if not text or not text.strip():
            return {
                'success': False,
                'error': 'Пустая строка',
                'parsed_datetime': None
            }
        
        # Нормализация текста
        normalized_text, normalization_corrections = self.normalize_text(text)
        all_corrections = normalization_corrections.copy()
        
        print(f"[ENHANCED_PARSER] Исходный текст: {text}")
        print(f"[ENHANCED_PARSER] Нормализованный текст: {normalized_text}")
        
        # Извлечение компонентов
        extracted_date = None
        extracted_time = None
        confidence = 1.0
        metadata = {
            'original_text': text,
            'normalized_text': normalized_text,
            'detected_language': 'mixed',
            'keyboard_layout': 'correct' if not normalization_corrections else 'corrected',
            'has_typos': len(normalization_corrections) > 0,
            'parsing_method': 'regex',
            'components_found': {}
        }
        
        # 1. Пробуем извлечь относительную дату
        relative_date = self.extract_relative_date(normalized_text)
        if relative_date:
            extracted_date = relative_date
            metadata['components_found']['relative_date'] = True
            confidence = 0.95
            print(f"[ENHANCED_PARSER] Найдена относительная дата: {extracted_date}")
        
        # 2. Пробуем извлечь день недели
        if not extracted_date:
            weekday_num = self.extract_weekday(normalized_text)
            if weekday_num is not None:
                extracted_date = self.find_next_weekday(weekday_num)
                metadata['components_found']['weekday'] = True
                confidence = 0.90
                print(f"[ENHANCED_PARSER] Найден день недели: {weekday_num} -> {extracted_date}")
        
        # 3. Пробуем извлечь конкретную дату
        if not extracted_date:
            date_from_pattern = self.extract_date_from_patterns(normalized_text)
            if date_from_pattern:
                extracted_date = date_from_pattern
                metadata['components_found']['date'] = True
                confidence = 1.0
                print(f"[ENHANCED_PARSER] Найдена дата из паттерна: {extracted_date}")
        
        # 4. Пробуем извлечь дату с текстовым месяцем
        if not extracted_date:
            date_with_month = self.extract_date_with_month_name(normalized_text)
            if date_with_month:
                extracted_date = date_with_month
                metadata['components_found']['date'] = True
                confidence = 0.95
                print(f"[ENHANCED_PARSER] Найдена дата с текстовым месяцем: {extracted_date}")
        
        # 5. Извлечение времени
        time_tuple = self.extract_time(normalized_text)
        if time_tuple:
            extracted_time = time_tuple
            metadata['components_found']['time'] = True
            print(f"[ENHANCED_PARSER] Найдено время: {time_tuple}")
        else:
            # Пробуем извлечь время из временных периодов
            time_period_tuple = self.extract_time_periods(normalized_text)
            if time_period_tuple:
                extracted_time = time_period_tuple
                metadata['components_found']['time_period'] = True
                print(f"[ENHANCED_PARSER] Найдено время из периода: {time_period_tuple}")
        
        # Если не найдена дата, используем завтра по умолчанию
        if not extracted_date:
            minsk_tz = pytz.timezone('Europe/Minsk')
            extracted_date = datetime.now(minsk_tz) + timedelta(days=1)
            metadata['components_found']['date'] = False
            confidence *= 0.8
            print(f"[ENHANCED_PARSER] Дата не найдена, используем завтра: {extracted_date}")
        
        # Если не найдено время, используем 15:00 по умолчанию
        if not extracted_time:
            extracted_time = (15, 0)
            metadata['components_found']['time'] = False
            confidence *= 0.9
            print(f"[ENHANCED_PARSER] Время не найдено, используем 15:00 по умолчанию")
        
        # Округление времени до валидного слота
        hour, minute, time_corrections = self.round_to_valid_slot(extracted_time[0], extracted_time[1])
        all_corrections.extend(time_corrections)
        
        # Комбинирование даты и времени
        if isinstance(extracted_date, datetime):
            result_datetime = extracted_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            result_datetime = datetime.combine(extracted_date, datetime.min.time())
            result_datetime = result_datetime.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Локализация временной зоны
        if result_datetime.tzinfo is None:
            result_datetime = self.timezone.localize(result_datetime)
        
        # Валидация результата
        validation_result = self.validate_datetime(result_datetime, existing_bookings)
        
        # Если слот занят, пытаемся найти следующий доступный слот в тот же день недели
        # НО: для технических интервью (skip_time_adjustment=True) НЕ переносим время
        if not validation_result['is_valid'] and not skip_time_adjustment:
            # Проверяем, занят ли слот
            slot_occupied_error = next((err for err in validation_result['errors'] if err['type'] == 'slot_occupied'), None)
            
            if slot_occupied_error:
                print(f"⚠️ [ENHANCED_PARSER] Слот {result_datetime.strftime('%d.%m %H:%M')} занят, ищем альтернативу...")
                
                # Ищем следующий свободный слот в тот же день недели
                original_weekday = result_datetime.weekday()
                original_time = (result_datetime.hour, result_datetime.minute)
                original_datetime_str = result_datetime.strftime('%d.%m %H:%M')
                
                # Пробуем следующую неделю с тем же днем недели и временем
                for week_offset in range(1, 5):  # Пробуем до 4 недель вперед
                    alternative_date = result_datetime + timedelta(weeks=week_offset)
                    alternative_validation = self.validate_datetime(alternative_date, existing_bookings)
                    
                    if alternative_validation['is_valid']:
                        print(f"✅ [ENHANCED_PARSER] Найден свободный слот: {alternative_date.strftime('%d.%m %H:%M')}")
                        
                        # Добавляем информацию об исправлении
                        all_corrections.append({
                            'type': 'slot_occupied_correction',
                            'original': original_datetime_str,
                            'corrected': alternative_date.strftime('%d.%m %H:%M'),
                            'reason': f'исходный слот занят, перенесено на {week_offset} недел{"ю" if week_offset == 1 else "и"} вперед'
                        })
                        
                        result_datetime = alternative_date
                        validation_result = alternative_validation
                        confidence *= 0.85  # Снижаем уверенность из-за переноса
                        break
                else:
                    # Если не нашли свободный слот за 4 недели, оставляем как есть
                    print(f"⚠️ [ENHANCED_PARSER] Не удалось найти свободный слот в течение 4 недель")
        elif not validation_result['is_valid'] and skip_time_adjustment:
            # Для технических интервью не переносим время, даже если слот занят
            slot_occupied_error = next((err for err in validation_result['errors'] if err['type'] == 'slot_occupied'), None)
            if slot_occupied_error:
                print(f"🔒 [ENHANCED_PARSER] Техническое интервью: слот {result_datetime.strftime('%d.%m %H:%M')} занят, но время НЕ переносится (строгое время)")
                # Добавляем предупреждение, но не изменяем время
                validation_result['warnings'] = validation_result.get('warnings', [])
                validation_result['warnings'].append({
                    'type': 'slot_occupied_warning',
                    'description': f'Слот занят, но время сохранено без изменений (техническое интервью)'
                })
        
        # Генерация альтернатив
        alternatives = self.generate_alternatives(result_datetime, existing_bookings)
        
        # Формирование итогового ответа
        response = {
            'success': True,
            'parsed_datetime': result_datetime.strftime("%d.%m.%Y %H:%M"),
            'confidence': confidence,
            'alternatives': alternatives,
            'corrections': all_corrections,
            'validation': validation_result,
            'metadata': metadata
        }
        
        print(f"[ENHANCED_PARSER] Итоговый результат: {response['parsed_datetime']}")
        print(f"[ENHANCED_PARSER] Уверенность: {confidence:.2f}")
        print(f"[ENHANCED_PARSER] Исправлений: {len(all_corrections)}")
        
        return response
    
    def generate_alternatives(self, dt: datetime, existing_bookings: List = None, count: int = 3) -> List[Dict]:
        """Генерация альтернативных временных слотов"""
        alternatives = []
        
        # Альтернатива 1: Тот же день недели следующей недели
        next_week = dt + timedelta(weeks=1)
        alternatives.append({
            'datetime': next_week.strftime("%d.%m.%Y %H:%M"),
            'confidence': 0.85,
            'reason': 'тот же день недели следующей недели'
        })
        
        # Альтернатива 2: Следующий рабочий день в то же время
        next_day = dt + timedelta(days=1)
        while next_day.weekday() >= 5:  # Пропускаем выходные
            next_day += timedelta(days=1)
        
        alternatives.append({
            'datetime': next_day.strftime("%d.%m.%Y %H:%M"),
            'confidence': 0.80,
            'reason': 'следующий рабочий день'
        })
        
        # Альтернатива 3: Другое время в тот же день
        alt_time = dt.replace(hour=14, minute=0)
        if alt_time.hour != dt.hour:
            alternatives.append({
                'datetime': alt_time.strftime("%d.%m.%Y %H:%M"),
                'confidence': 0.75,
                'reason': 'другое время в тот же день'
            })
        
        return alternatives[:count]


def parse_datetime_with_validation(
    text: str, 
    user=None,
    existing_bookings: List = None, 
    vacancy_prompt: str = None,
    timezone_name: str = 'Europe/Minsk',
    skip_time_adjustment: bool = False
) -> Dict:
    """
    Функция для парсинга даты и времени с полной валидацией
    
    Args:
        text: Текст для анализа
        user: Объект пользователя Django (для получения рабочих часов)
        existing_bookings: Список существующих бронирований
        vacancy_prompt: Промпт из вакансии для дополнительного контекста
        timezone_name: Название временной зоны
        skip_time_adjustment: Если True, не переносит время при конфликтах (для технических интервью)
    
    Returns:
        Словарь с результатами парсинга
    """
    parser = EnhancedDateTimeParser(user, timezone_name)
    return parser.parse_datetime(text, existing_bookings, vacancy_prompt, skip_time_adjustment)


# Обратная совместимость с существующим кодом
def parse_datetime_from_text(text: str, user=None, timezone_name: str = 'Europe/Minsk') -> Tuple[Optional[datetime], str]:
    """
    Простая функция для парсинга даты и времени (для обратной совместимости)
    
    Args:
        text: Текст для анализа
        user: Объект пользователя Django (для получения рабочих часов)
        timezone_name: Название временной зоны
    
    Returns:
        Кортеж (datetime_object, error_message)
    """
    parser = EnhancedDateTimeParser(user, timezone_name)
    result = parser.parse_datetime(text)
    
    if result['success']:
        # Парсим дату из строки обратно в datetime для обратной совместимости
        dt = datetime.strptime(result['parsed_datetime'], "%d.%m.%Y %H:%M")
        minsk_tz = pytz.timezone(timezone_name)
        dt = minsk_tz.localize(dt)
        return dt, "Успешно"
    else:
        return None, result.get('error', 'Не удалось определить дату и время')

