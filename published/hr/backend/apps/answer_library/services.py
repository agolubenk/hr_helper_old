"""
Логика подбора блоков по триггерам и формирование запроса к Gemini.
"""
import logging
import re
from typing import List

from .models import TriggerTopic

logger = logging.getLogger(__name__)

# Минимальная длина слова для сравнения по стему (русские формы: компания/компании, работа/работы)
STEM_MIN_LEN = 4
STEM_PREFIX_LEN = 5


def normalize_text_for_triggers(text: str) -> str:
    """Приводит текст к виду для поиска триггеров (нижний регистр, без лишних символов)."""
    if not text:
        return ''
    text = (text or '').lower().strip()
    text = re.sub(r'[^\w\s\u0400-\u04ff]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _trigger_matches_text(trigger: str, normalized: str, words: List[str]) -> bool:
    """
    Проверяет, совпадает ли триггер с текстом.
    1) Триггер как подстрока всего текста (как раньше).
    2) Триггер совпадает со словом по общему префиксу (русские формы слов: компания/компании, работа/работы).
    """
    if not trigger:
        return False
    if trigger in normalized:
        return True
    # Совпадение по стему: общий префикс не короче STEM_MIN_LEN (компания/компании → «комп»)
    if len(trigger) >= STEM_MIN_LEN:
        for w in words:
            if len(w) < STEM_MIN_LEN:
                continue
            n = min(STEM_PREFIX_LEN, len(trigger), len(w))
            if trigger[:n] == w[:n]:
                return True
            # Триггер как подстрока слова или наоборот (формат/формате, график/графика)
            if trigger in w or w in trigger:
                return True
    return False


def get_matching_topics(user_text: str, vacancy_id: int = None) -> List[TriggerTopic]:
    """
    По тексту пользователя (вопросы кандидата) возвращает активные темы,
    у которых хотя бы один триггер встретился в тексте (с учётом форм слов).
    Если задан vacancy_id: подходят темы без привязки к вакансии (vacancy=None)
    и темы, привязанные к этой вакансии. Иначе подходят все подходящие по триггерам.
    """
    normalized = normalize_text_for_triggers(user_text)
    if not normalized:
        return []
    words = normalized.split()
    topics = []
    qs = TriggerTopic.objects.filter(is_active=True).select_related('vacancy')
    if vacancy_id is not None:
        from django.db.models import Q
        qs = qs.filter(Q(vacancy_id__isnull=True) | Q(vacancy_id=vacancy_id))
    for topic in qs:
        triggers = topic.get_trigger_list()
        if any(_trigger_matches_text(t, normalized, words) for t in triggers):
            topics.append(topic)
    if not topics:
        logger.warning(
            "Answer library: no topics matched for message (normalized=%r). "
            "Check that TriggerTopic records exist and trigger_words match the question.",
            normalized[:200],
        )
    return topics


def build_context_blocks(topics: List[TriggerTopic]) -> str:
    """
    Собирает для Gemini блоки по темам: название, пример ответа, доп. данные.
    Без триггеров и без лишней информации.
    """
    blocks = []
    for t in topics:
        parts = [f"Тема: {t.title}"]
        if t.example_answer and t.example_answer.strip():
            parts.append(f"Пример ответа: {t.example_answer.strip()}")
        if t.extra_data and t.extra_data.strip():
            parts.append(f"Доп. данные: {t.extra_data.strip()}")
        blocks.append("\n".join(parts))
    return "\n\n---\n\n".join(blocks) if blocks else ""


def build_unified_message(
    question_body: str,
    intro: str = "",
    outro: str = "",
) -> str:
    """
    Собирает единое сообщение кандидата: формулировки до тела + тело вопроса + формулировки после.
    """
    parts = []
    if (intro or "").strip():
        parts.append(intro.strip())
    parts.append((question_body or "").strip())
    if (outro or "").strip():
        parts.append(outro.strip())
    return "\n\n".join(p for p in parts if p)


SYSTEM_INSTRUCTION = (
    "Ты — помощник HR. Кандидат задал вопрос (сообщение ниже). "
    "Ниже даны справочные блоки с примерами и данными — используй их только как источник фактов. "
    "Отвечай строго на поставленный вопрос: своими словами, кратко, по существу. "
    "Не копируй и не вставляй целиком блоки из справочника. Не добавляй информацию, которую кандидат не спрашивал. "
    "Факты бери только из приведённых данных; если по вопросу данных нет — скажи об этом кратко."
)

NO_CONTEXT_NOTE = (
    "[По запросу в справочнике не найдено подходящих тем. "
    "Ответь кратко: по этой теме в базе нет данных, кандидату стоит уточнить у HR или переформулировать вопрос.]"
)


def build_prompt_for_gemini(
    unified_message: str,
    context_blocks: str,
) -> str:
    """
    Формирует единый промпт для Gemini: инструкция + сообщение кандидата + блоки из библиотеки.
    Ответ модели возвращается в чат как есть.
    """
    sections = [
        SYSTEM_INSTRUCTION,
        "",
        "--- Сообщение кандидата (контекст и вопрос) ---",
        unified_message.strip() or "(текст вопроса пуст)",
        "--- Конец сообщения кандидата ---",
        "",
    ]
    if context_blocks:
        sections.extend([
            "--- Справочные блоки (темы, примеры ответов, доп. данные) ---",
            context_blocks,
            "--- Конец справочных блоков ---",
        ])
    else:
        sections.append(NO_CONTEXT_NOTE)
    sections.extend([
        "",
        "Ответь кандидату кратко и только на его вопрос, не пересказывая и не копируя справочник целиком.",
    ])
    return "\n".join(sections)
