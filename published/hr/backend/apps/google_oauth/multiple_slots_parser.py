"""
Парсер для обработки множественных временных слотов от кандидатов
Пример: "завтра 15-18, послезавтра 14-15.30, на следующей неделе любой день с 12 до 19"
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz


class MultipleSlotsParser:
    """
    Парсер для извлечения множественных временных слотов из текста кандидата
    """
    
    def __init__(self, timezone_name: str = 'Europe/Minsk'):
        self.timezone = pytz.timezone(timezone_name)
        
        # Паттерны для относительных дат
        self.relative_dates = {
            'сегодня': 0, 'сёдня': 0, 'today': 0,
            'завтра': 1, 'зафтра': 1, 'tomorrow': 1,
            'послезавтра': 2, 'послезафтра': 2, 'day_after_tomorrow': 2,
            'вчера': -1, 'вчира': -1, 'yesterday': -1,
            'позавчера': -2, 'позавчира': -2, 'day_before_yesterday': -2
        }
        
        # Паттерны для дней недели
        self.weekdays = {
            'понедельник': 0, 'пн': 0, 'monday': 0, 'mon': 0,
            'вторник': 1, 'вт': 1, 'tuesday': 1, 'tue': 1,
            'среда': 2, 'ср': 2, 'wednesday': 2, 'wed': 2,
            'четверг': 3, 'чт': 3, 'thursday': 3, 'thu': 3,
            'пятница': 4, 'пт': 4, 'friday': 4, 'fri': 4,
            'суббота': 5, 'сб': 5, 'saturday': 5, 'sat': 5,
            'воскресенье': 6, 'вс': 6, 'sunday': 6, 'sun': 6
        }
        
        # Паттерны для временных периодов
        self.time_periods = {
            'утром': (9, 12), 'morning': (9, 12),
            'днем': (12, 18), 'днём': (12, 18), 'afternoon': (12, 18),
            'вечером': (18, 22), 'evening': (18, 22),
            'ночью': (22, 24), 'night': (22, 24)
        }
    
    def parse_multiple_slots(self, text: str) -> List[Dict]:
        """
        Парсит текст и извлекает все временные слоты
        
        Args:
            text: Текст с временными слотами
            
        Returns:
            List[Dict]: Список слотов с информацией о дате и времени
        """
        slots = []
        
        # Разделяем текст на отдельные слоты по запятым или переносам строк
        slot_texts = self._split_slot_texts(text)
        
        for slot_text in slot_texts:
            slot = self._parse_single_slot(slot_text.strip())
            if slot:
                slots.append(slot)
        
        return slots
    
    def _split_slot_texts(self, text: str) -> List[str]:
        """Разделяет текст на отдельные слоты"""
        # Сначала разделяем по запятым, переносам строк и союзам
        separators = [',', '\n', '\r\n', ' и ', ' или ', ';']
        
        parts = [text]
        for sep in separators:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            parts = new_parts
        
        # Фильтруем пустые части
        slots = [part.strip() for part in parts if part.strip()]
        
        # Дополнительная обработка: если слот содержит только дату без времени,
        # объединяем его со следующим слотом
        processed_slots = []
        i = 0
        while i < len(slots):
            current_slot = slots[i]
            
            # Проверяем, содержит ли слот только дату (без времени)
            if self._contains_only_date(current_slot):
                # Если есть следующий слот, объединяем их
                if i + 1 < len(slots):
                    next_slot = slots[i + 1]
                    combined_slot = f"{current_slot} {next_slot}"
                    processed_slots.append(combined_slot)
                    i += 2  # Пропускаем следующий слот
                else:
                    processed_slots.append(current_slot)
                    i += 1
            else:
                processed_slots.append(current_slot)
                i += 1
        
        return processed_slots
    
    def _contains_only_date(self, text: str) -> bool:
        """Проверяет, содержит ли текст только дату без времени"""
        text_lower = text.lower()
        
        # Проверяем наличие дат
        has_date = any(rel_date in text_lower for rel_date in self.relative_dates.keys())
        has_weekday = any(day in text_lower for day in self.weekdays.keys())
        
        # Проверяем отсутствие времени
        has_time = False
        time_indicators = ['любое время', 'утром', 'днем', 'вечером', ':', '.', '-']
        for indicator in time_indicators:
            if indicator in text_lower:
                has_time = True
                break
        
        # Также проверяем числовые паттерны времени
        import re
        time_patterns = [r'\d{1,2}:\d{2}', r'\d{1,2}\.\d{2}', r'\d{1,2}\s*-\s*\d{1,2}']
        for pattern in time_patterns:
            if re.search(pattern, text):
                has_time = True
                break
        
        return (has_date or has_weekday) and not has_time
    
    def _parse_single_slot(self, slot_text: str) -> Optional[Dict]:
        """Парсит один временной слот"""
        slot_text_lower = slot_text.lower()
        
        # Определяем дату
        date_info = self._extract_date(slot_text_lower)
        if not date_info:
            return None
        
        # Определяем время
        time_info = self._extract_time(slot_text_lower)
        if not time_info:
            return None
        
        return {
            'original_text': slot_text,
            'date_info': date_info,
            'time_info': time_info,
            'confidence': self._calculate_confidence(slot_text, date_info, time_info)
        }
    
    def _extract_date(self, text: str) -> Optional[Dict]:
        """Извлекает информацию о дате"""
        current_date = datetime.now(self.timezone)
        
        # Проверяем относительные даты (ищем точное совпадение слов)
        text_lower = text.lower()
        for rel_date, days_offset in self.relative_dates.items():
            # Используем регулярные выражения для точного поиска слов
            import re
            pattern = r'\b' + re.escape(rel_date) + r'\b'
            if re.search(pattern, text_lower):
                target_date = current_date + timedelta(days=days_offset)
                return {
                    'type': 'relative',
                    'value': rel_date,
                    'date': target_date,
                    'days_offset': days_offset
                }
        
        # Проверяем дни недели
        for weekday, day_num in self.weekdays.items():
            if weekday in text:
                # Находим ближайший день недели
                days_ahead = day_num - current_date.weekday()
                if days_ahead <= 0:  # Если день уже прошел на этой неделе
                    days_ahead += 7
                
                # Проверяем, не указана ли "следующая неделя"
                if 'следующ' in text or 'next' in text:
                    days_ahead += 7
                
                target_date = current_date + timedelta(days=days_ahead)
                return {
                    'type': 'weekday',
                    'value': weekday,
                    'date': target_date,
                    'day_number': day_num
                }
        
        # Проверяем "любой день" или "на следующей неделе"
        if 'любой день' in text or 'any day' in text:
            return {
                'type': 'flexible',
                'value': 'любой день',
                'date': None,  # Будет определен позже
                'flexible': True
            }
        
        # Проверяем "любое время"
        if 'любое время' in text or 'any time' in text:
            return {
                'type': 'flexible',
                'value': 'любое время',
                'date': None,  # Будет определен позже
                'flexible': True
            }
        
        return None
    
    def _extract_time(self, text: str) -> Optional[Dict]:
        """Извлекает информацию о времени"""
        
        # Паттерны для конкретного времени
        time_patterns = [
            r'(\d{1,2})\s*-\s*(\d{1,2}):(\d{2})',  # 15-16:30 (приоритет - более специфичный)
            r'(\d{1,2})\s*-\s*(\d{1,2})\.(\d{2})',  # 14-15.30
            r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})',  # 15:30-16:30
            r'(\d{1,2}):(\d{2})',  # 15:30
            r'(\d{1,2})\.(\d{2})',  # 15.30
            r'(\d{1,2})\s*-\s*(\d{1,2})',  # 15-18
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:  # 15:30 или 15-18
                    if ':' in match.group(0):  # 15:30
                        start_hour, start_min = int(groups[0]), int(groups[1])
                        return {
                            'type': 'specific',
                            'start_time': {'hour': start_hour, 'minute': start_min},
                            'end_time': None,
                            'flexible': False
                        }
                    else:  # 15-18
                        start_hour, start_min = int(groups[0]), 0
                        end_hour, end_min = int(groups[1]), 0
                        return {
                            'type': 'range',
                            'start_time': {'hour': start_hour, 'minute': start_min},
                            'end_time': {'hour': end_hour, 'minute': end_min},
                            'flexible': False
                        }
                elif len(groups) == 3:  # 15-16:30, 15:30-16:30 или 14-15.30
                    if ':' in match.group(0):  # 15:30-16:30 или 15-16:30
                        if match.group(0).count(':') == 2:  # 15:30-16:30
                            start_hour, start_min = int(groups[0]), int(groups[1])
                            end_hour, end_min = int(groups[2]), 0
                        else:  # 15-16:30
                            start_hour, start_min = int(groups[0]), 0
                            end_hour, end_min = int(groups[1]), int(groups[2])
                    else:  # 14-15.30
                        start_hour, start_min = int(groups[0]), 0
                        end_hour, end_min = int(groups[1]), int(groups[2])
                    
                    return {
                        'type': 'range',
                        'start_time': {'hour': start_hour, 'minute': start_min},
                        'end_time': {'hour': end_hour, 'minute': end_min},
                        'flexible': False
                    }
        
        # Проверяем временные периоды
        for period, (start_hour, end_hour) in self.time_periods.items():
            if period in text:
                return {
                    'type': 'period',
                    'value': period,
                    'start_time': {'hour': start_hour, 'minute': 0},
                    'end_time': {'hour': end_hour, 'minute': 0},
                    'flexible': True
                }
        
        # Проверяем "с X до Y"
        range_match = re.search(r'с\s*(\d{1,2})\s*до\s*(\d{1,2})', text)
        if range_match:
            start_hour = int(range_match.group(1))
            end_hour = int(range_match.group(2))
            return {
                'type': 'range',
                'start_time': {'hour': start_hour, 'minute': 0},
                'end_time': {'hour': end_hour, 'minute': 0},
                'flexible': True
            }
        
        # Проверяем "любое время"
        if 'любое время' in text or 'any time' in text:
            return {
                'type': 'flexible',
                'value': 'любое время',
                'flexible': True
            }
        
        return None
    
    def _calculate_confidence(self, original_text: str, date_info: Dict, time_info: Dict) -> float:
        """Вычисляет уверенность в правильности парсинга"""
        confidence = 0.5  # Базовая уверенность
        
        # Бонус за конкретную дату
        if date_info['type'] == 'relative':
            confidence += 0.3
        elif date_info['type'] == 'weekday':
            confidence += 0.2
        
        # Бонус за конкретное время
        if time_info['type'] == 'specific':
            confidence += 0.3
        elif time_info['type'] == 'range':
            confidence += 0.2
        elif time_info['type'] == 'period':
            confidence += 0.1
        
        # Штраф за гибкие слоты
        if date_info.get('flexible') or time_info.get('flexible'):
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))
    
    def find_matching_slots(self, candidate_slots: List[Dict], recruiter_slots: List[Dict]) -> List[Dict]:
        """
        Находит совпадающие слоты между кандидатом и рекрутером
        
        Args:
            candidate_slots: Слоты кандидата
            recruiter_slots: Слоты рекрутера
            
        Returns:
            List[Dict]: Список совпадающих слотов
        """
        matches = []
        
        for candidate_slot in candidate_slots:
            for recruiter_slot in recruiter_slots:
                match = self._check_slot_match(candidate_slot, recruiter_slot)
                if match:
                    matches.append(match)
        
        # Сортируем по уверенности
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches
    
    def _check_slot_match(self, candidate_slot: Dict, recruiter_slot: Dict) -> Optional[Dict]:
        """Проверяет совпадение двух слотов"""
        # Проверяем совпадение дат
        date_match = self._check_date_match(
            candidate_slot['date_info'],
            recruiter_slot['date_info']
        )
        
        if not date_match:
            return None
        
        # Проверяем совпадение времени
        time_match = self._check_time_match(
            candidate_slot['time_info'],
            recruiter_slot['time_info']
        )
        
        if not time_match:
            return None
        
        return {
            'candidate_slot': candidate_slot,
            'recruiter_slot': recruiter_slot,
            'date_match': date_match,
            'time_match': time_match,
            'confidence': (date_match['confidence'] + time_match['confidence']) / 2
        }
    
    def _check_date_match(self, candidate_date: Dict, recruiter_date: Dict) -> Optional[Dict]:
        """Проверяет совпадение дат"""
        if candidate_date['type'] == 'flexible' or recruiter_date['type'] == 'flexible':
            return {'confidence': 0.8, 'type': 'flexible'}
        
        if candidate_date.get('date') and recruiter_date.get('date'):
            if candidate_date['date'].date() == recruiter_date['date'].date():
                return {'confidence': 1.0, 'type': 'exact'}
        
        return None
    
    def _check_time_match(self, candidate_time: Dict, recruiter_time: Dict) -> Optional[Dict]:
        """Проверяет совпадение времени"""
        if candidate_time['type'] == 'flexible' or recruiter_time['type'] == 'flexible':
            return {'confidence': 0.8, 'type': 'flexible'}
        
        # Проверяем пересечение временных интервалов
        candidate_start = self._time_to_minutes(candidate_time['start_time'])
        candidate_end = self._time_to_minutes(candidate_time.get('end_time', candidate_time['start_time']))
        
        recruiter_start = self._time_to_minutes(recruiter_time['start_time'])
        recruiter_end = self._time_to_minutes(recruiter_time.get('end_time', recruiter_time['start_time']))
        
        # Проверяем пересечение
        if candidate_start <= recruiter_end and recruiter_start <= candidate_end:
            overlap_start = max(candidate_start, recruiter_start)
            overlap_end = min(candidate_end, recruiter_end)
            overlap_duration = overlap_end - overlap_start
            
            if overlap_duration >= 30:  # Минимум 30 минут пересечения
                confidence = overlap_duration / 60.0  # Уверенность пропорциональна длительности
                return {'confidence': min(1.0, confidence), 'type': 'overlap'}
        
        return None
    
    def _time_to_minutes(self, time_dict: Dict) -> int:
        """Конвертирует время в минуты"""
        return time_dict['hour'] * 60 + time_dict.get('minute', 0)


def parse_candidate_slots(text: str, timezone_name: str = 'Europe/Minsk') -> List[Dict]:
    """
    Основная функция для парсинга множественных слотов кандидата
    
    Args:
        text: Текст с временными слотами
        timezone_name: Часовой пояс
        
    Returns:
        List[Dict]: Список распарсенных слотов
    """
    parser = MultipleSlotsParser(timezone_name)
    return parser.parse_multiple_slots(text)


def find_slot_matches(candidate_slots: List[Dict], recruiter_slots: List[Dict], timezone_name: str = 'Europe/Minsk') -> List[Dict]:
    """
    Находит совпадающие слоты между кандидатом и рекрутером
    
    Args:
        candidate_slots: Слоты кандидата
        recruiter_slots: Слоты рекрутера
        timezone_name: Часовой пояс
        
    Returns:
        List[Dict]: Список совпадающих слотов
    """
    parser = MultipleSlotsParser(timezone_name)
    return parser.find_matching_slots(candidate_slots, recruiter_slots)
