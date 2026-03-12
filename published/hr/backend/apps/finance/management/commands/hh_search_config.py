# -*- coding: utf-8 -*-
"""
Конфигурация для поиска вакансий на hh.ru

ВХОДЯЩИЕ ДАННЫЕ:
- Нет (конфигурационный файл)

ИСТОЧНИКИ ДАННЫХ:
- hh.ru API: коды локаций, специализаций и ключевые слова

ОБРАБОТКА:
- Определение локаций для поиска (Беларусь, Польша)
- Определение специализаций для поиска (IT роли)
- Определение ключевых слов для каждой специализации
- Определение параметров поиска и фильтрации

ВЫХОДЯЩИЕ ДАННЫЕ:
- Константы для использования в management командах и задачах

СВЯЗИ:
- Используется в: apps.finance.tasks, management командах
- Передает данные в: hh.ru API запросы
- Может вызываться из: Celery задачи, management команды
"""

# Локации для поиска (исправленные коды)
HH_LOCATIONS = [
    {
        "name": "Беларусь",
        "code": "16",  # Код Беларуси на hh.ru
        "cities": [
            {"name": "Минск", "code": "2"},
            {"name": "Гомель", "code": "3"},
            {"name": "Могилев", "code": "4"},
            {"name": "Витебск", "code": "5"},
            {"name": "Гродно", "code": "6"},
            {"name": "Брест", "code": "7"},
        ]
    },
    {
        "name": "Польша",
        "code": "74",  # Исправленный код Польши на hh.ru
    }
]

# Специализации для поиска
HH_SPECIALIZATIONS = [
    {
        "id": "1.221",  # Информационные технологии/Программист, разработчик
        "name": "Программист, разработчик",
        "keywords": ["java", "javascript", "spring", "typescript", "frontend", "kotlin", "kotlin multiplatform", "react", "redux"]
    },
    {
        "id": "1.89",   # Информационные технологии/Дизайнер, художник
        "name": "Дизайнер, художник",
        "keywords": ["ui", "ux", "веб-дизайн", "графический дизайн", "интерфейс"]
    },
    {
        "id": "1.83",   # Информационные технологии/DevOps-инженер
        "name": "DevOps-инженер",
        "keywords": ["devops", "k8s", "kubernetes", "gitlab", "cloud", "docker", "ci/cd"]
    },
    {
        "id": "1.82",   # Информационные технологии/Менеджер продукта
        "name": "Менеджер продукта",
        "keywords": ["продуктовая разработка", "product manager", "продукт-менеджер"]
    },
    {
        "id": "1.84",   # Информационные технологии/Руководитель проектов
        "name": "Руководитель проектов",
        "keywords": ["управление проектами", "scrum", "agile", "project manager", "пм"]
    },
    {
        "id": "1.85",   # Информационные технологии/Сетевой инженер
        "name": "Сетевой инженер",
        "keywords": ["сетевые схемы", "network engineer", "сетевой администратор"]
    },
    {
        "id": "1.86",   # Информационные технологии/Системный администратор
        "name": "Системный администратор",
        "keywords": ["системное администрирование", "системный администратор", "linux", "windows server"]
    },
    {
        "id": "1.87",   # Информационные технологии/Специалист технической поддержки
        "name": "Специалист технической поддержки",
        "keywords": ["поддержка", "сопровождение", "техподдержка", "support engineer"]
    },
    {
        "id": "1.88",   # Информационные технологии/Тестировщик
        "name": "Тестировщик",
        "keywords": ["qa", "aqa", "тестирование", "selenium", "автотесты", "manual testing"]
    }
]

# Дополнительные ключевые слова для поиска
ADDITIONAL_KEYWORDS = [
    # Технологии
    "java", "javascript", "spring", "typescript", "qa", "aqa", 
    "frontend", "kotlin", "kotlin multiplatform", "react", "redux", 
    "selenium", "k8s", "kubernetes", "gitlab", "cloud", "devops",
    
    # Процессы и методологии
    "поддержка", "сопровождение", "администрирование", "сетевые схемы", 
    "системное администрирование", "тестирование", "управление проектами", 
    "scrum", "agile", "продуктовая разработка",
    
    # Названия специализаций
    "программист", "разработчик", "дизайнер", "художник", "devops-инженер",
    "менеджер продукта", "руководитель проектов", "сетевой инженер",
    "системный администратор", "специалист технической поддержки", "тестировщик"
]

# Параметры поиска по умолчанию (упрощенные)
DEFAULT_SEARCH_PARAMS = {
    "text": "",  # Будет заполнено ключевыми словами
    "area": "",  # Будет заполнено кодами локаций
    "specialization": "",  # Будет заполнено кодами специализаций
    "order_by": "publication_time",  # Сортировка по времени публикации
    "per_page": "100",  # Количество результатов на страницу
}

def get_search_url_params(specialization_ids=None, location_codes=None, keywords=None):
    """
    Генерирует параметры для поиска на hh.ru
    
    Args:
        specialization_ids: Список ID специализаций
        location_codes: Список кодов локаций
        keywords: Дополнительные ключевые слова
    
    Returns:
        dict: Параметры для URL
    """
    params = DEFAULT_SEARCH_PARAMS.copy()
    
    # Специализации
    if specialization_ids:
        params["specialization"] = ",".join(specialization_ids)
    
    # Локации
    if location_codes:
        params["area"] = ",".join(location_codes)
    
    # Ключевые слова (используем только переданные, без дополнительных)
    if keywords:
        params["text"] = " ".join(keywords)  # Используем пробел вместо OR
    
    return params

def get_specialization_by_id(specialization_id):
    """Получить специализацию по ID"""
    for spec in HH_SPECIALIZATIONS:
        if spec["id"] == specialization_id:
            return spec
    return None

def get_location_by_code(location_code):
    """Получить локацию по коду"""
    for location in HH_LOCATIONS:
        if location["code"] == location_code:
            return location
        for city in location["cities"]:
            if city["code"] == location_code:
                return city
    return None

def get_all_specialization_ids():
    """Получить все ID специализаций"""
    return [spec["id"] for spec in HH_SPECIALIZATIONS]

def get_all_location_codes():
    """Получить все коды локаций (страны + города)"""
    codes = []
    for location in HH_LOCATIONS:
        codes.append(location["code"])
        codes.extend([city["code"] for city in location["cities"]])
    return codes

