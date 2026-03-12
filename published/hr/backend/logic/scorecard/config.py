"""
Конфигурация правил для обработки скоркардов
"""

from typing import Dict, List, Any

def get_scorecard_rules(vacancy_name: str = None, candidate_grade: str = None) -> Dict[str, List[Dict]]:
    """
    Возвращает правила обработки скоркардов для вакансии и грейда кандидата
    
    Args:
        vacancy_name: Название вакансии
        candidate_grade: Грейд кандидата
        
    Returns:
        Словарь с правилами обработки скоркардов
    """
    
    # Базовые правила для всех вакансий
    rules = {
        'sheet_management': [
            {
                'name': 'default_sheet_cleanup',
                'description': 'Удаление лишних листов по умолчанию',
                'priority': 100,
                'source': 'config',
                'action': 'keep',
                'sheets': ['all', 'score', "Task's"],
                'conditions': {}
            }
        ],
        'field_filling': [
            {
                'name': 'default_field_filling',
                'description': 'Заполнение полей по умолчанию',
                'priority': 100,
                'source': 'config',
                'fields': {},
                'conditions': {}
            }
        ],
        'naming': [
            {
                'name': 'default_naming',
                'description': 'Формирование названия файла по умолчанию',
                'priority': 100,
                'source': 'config',
                'template': '[NAME] - [VACANCY_NAME]',
                'conditions': {}
            }
        ]
    }
    
    # Добавляем лист с грейдом кандидата, если он указан
    if candidate_grade and candidate_grade != "Не указан":
        rules['sheet_management'].append({
            'name': 'grade_sheet_keep',
            'description': f'Сохранение листа с грейдом {candidate_grade}',
            'priority': 50,
            'source': 'config',
            'action': 'keep',
            'sheets': [candidate_grade.lower()],
            'conditions': {'grade': candidate_grade}
        })
    
    # Специфичные правила для разных типов вакансий
    if vacancy_name:
        vacancy_lower = vacancy_name.lower()
        
        # Правила для Python вакансий
        if 'python' in vacancy_lower:
            rules['field_filling'].append({
                'name': 'python_specific_fields',
                'description': 'Специфичные поля для Python вакансий',
                'priority': 50,
                'source': 'config',
                'fields': {
                    # Убрали A1, чтобы не перезаписывать [LINK] или другие плейсхолдеры
                    'B1': '[NAME]',
                    'C1': '[GRADE]'
                },
                'conditions': {'vacancy': vacancy_name}
            })
        
        # Правила для Frontend вакансий
        elif 'frontend' in vacancy_lower or 'react' in vacancy_lower:
            rules['field_filling'].append({
                'name': 'frontend_specific_fields',
                'description': 'Специфичные поля для Frontend вакансий',
                'priority': 50,
                'source': 'config',
                'fields': {
                    # Убрали A1, чтобы не перезаписывать [LINK] или другие плейсхолдеры
                    'B1': '[NAME]',
                    'C1': '[GRADE]'
                },
                'conditions': {'vacancy': vacancy_name}
            })
    
    return rules
