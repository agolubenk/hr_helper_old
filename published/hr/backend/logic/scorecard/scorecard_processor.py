"""
Процессор скоркардов - настраиваемая логика обработки Google Sheets скоркардов
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from django.utils import timezone

# from apps.vacancies.models import ScorecardRule  # Модель не существует
from apps.google_oauth.models import Invite
from .config import get_scorecard_rules


def _get_column_letter(col_index: int) -> str:
    """Преобразует индекс колонки (0-based) в букву колонки (A, B, C, ..., Z, AA, AB, ...)"""
    result = ""
    col_index += 1  # Переводим в 1-based
    while col_index > 0:
        col_index -= 1
        result = chr(65 + (col_index % 26)) + result
        col_index //= 26
    return result


class ScorecardProcessor:
    """
    Процессор для настраиваемой обработки скоркардов
    
    Поддерживает:
    - Управление листами (удаление/сохранение)
    - Заполнение полей кандидата
    - Формирование названий файлов
    """
    
    def __init__(self, vacancy, sheets_service, candidate_grade=None):
        self.vacancy = vacancy
        self.sheets_service = sheets_service
        self.candidate_grade = candidate_grade
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, List[Dict]]:
        """Загружает правила для вакансии из конфигурации"""
        try:
            # Получаем правила из конфигурации
            config_rules = get_scorecard_rules(
                vacancy_name=self.vacancy.name,
                candidate_grade=self.candidate_grade
            )
        except Exception as e:
            print(f"⚠️ SCORECARD: Ошибка загрузки правил из конфигурации: {e}")
            config_rules = {
                'sheet_management': [],
                'field_filling': [],
                'naming': []
            }
        
        # Объединяем правила из конфигурации
        combined_rules = {
            'sheet_management': [],
            'field_filling': [],
            'naming': []
        }
        
        # Добавляем правила из конфигурации
        for rule_type, rule_list in config_rules.items():
            combined_rules[rule_type].extend(rule_list)
        
        # Сортируем по приоритету
        for rule_type in combined_rules:
            combined_rules[rule_type].sort(key=lambda x: x.get('priority', 999))
        
        return combined_rules
    
    def process_scorecard(self, invite: Invite, file_id: str) -> Dict[str, Any]:
        """
        Основной метод обработки скоркарда
        
        Args:
            invite: Объект инвайта
            file_id: ID файла Google Sheets
            
        Returns:
            Dict с результатами обработки
        """
        print(f"🚀 SCORECARD: Начинаем обработку скоркарда для {invite.candidate_name}")
        print(f"📁 SCORECARD: File ID: {file_id}")
        print(f"👤 SCORECARD: Кандидат: {invite.candidate_name}")
        print(f"📊 SCORECARD: Грейд: {invite.candidate_grade}")
        print(f"🔗 SCORECARD: candidate_url: {getattr(invite, 'candidate_url', 'не найден')}")
        print(f"📋 SCORECARD: vacancy_id: {getattr(invite, 'vacancy_id', 'не найден')}")
        
        result = {
            'success': True,
            'errors': [],
            'actions_performed': [],
            'sheets_processed': [],
            'fields_filled': []
        }
        
        try:
            # 1. Обработка листов
            print(f"📄 SCORECARD: Шаг 1 - Обработка листов")
            sheet_result = self._process_sheets(invite, file_id)
            result.update(sheet_result)
            
            # 2. Заполнение полей
            print(f"✏️ SCORECARD: Шаг 2 - Заполнение полей и замена плейсхолдеров")
            field_result = self._fill_fields(invite, file_id)
            result.update(field_result)
            
            # 3. Формирование названия файла (если нужно)
            print(f"📝 SCORECARD: Шаг 3 - Формирование названия файла")
            name_result = self._generate_filename(invite)
            result.update(name_result)
            
            print(f"✅ SCORECARD: Обработка завершена успешно")
            
        except Exception as e:
            result['success'] = False
            error_msg = f"Ошибка обработки скоркарда: {str(e)}"
            result['errors'].append(error_msg)
            print(f"❌ SCORECARD: {error_msg}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def _process_sheets(self, invite: Invite, file_id: str) -> Dict[str, Any]:
        """Обработка листов согласно правилам"""
        result = {
            'sheets_processed': [],
            'actions_performed': []
        }
        
        try:
            # Получаем список защищённых листов пользователя (их нельзя удалять)
            protected_lower = []
            try:
                from apps.google_oauth.models import ScorecardPathSettings
                settings_obj = ScorecardPathSettings.get_or_create_for_user(invite.user)
                protected_lower = [s.lower() for s in settings_obj.get_protected_sheet_names_list()]
            except Exception as e:
                print(f"⚠️ SCORECARD: Не удалось получить список защищённых листов: {e}")

            # Получаем список всех листов
            sheets = self.sheets_service.get_sheets(file_id)
            if not sheets:
                result['errors'] = result.get('errors', [])
                result['errors'].append("Не удалось получить список листов")
                return result
            
            # Определяем листы для сохранения/удаления
            sheets_to_keep = self._get_sheets_to_keep(invite)
            sheets_to_delete = self._get_sheets_to_delete(invite)
            
            # Создаем регистронезависимые списки для сравнения
            sheets_to_keep_lower = [s.lower() for s in sheets_to_keep]
            sheets_to_delete_lower = [s.lower() for s in sheets_to_delete]
            
            # Обрабатываем каждый лист
            for sheet in sheets:
                sheet_title = sheet.get('properties', {}).get('title', sheet.get('title', 'Unknown'))
                sheet_id = sheet.get('properties', {}).get('sheetId', sheet.get('sheetId'))
                sheet_title_lower = sheet_title.lower()
                
                # Проверяем, нужно ли сохранить или удалить лист (регистронезависимо)
                should_keep = sheet_title_lower in sheets_to_keep_lower
                should_delete = sheet_title_lower in sheets_to_delete_lower
                is_protected = sheet_title_lower in protected_lower
                
                print(f"🔍 SCORECARD: Обработка листа: '{sheet_title}' (keep: {should_keep}, delete: {should_delete})")
                
                if is_protected:
                    result['sheets_processed'].append({
                        'name': sheet_title,
                        'action': 'protected',
                        'success': True
                    })
                    result['actions_performed'].append(f"Оставлен защищённый лист: {sheet_title}")
                    continue

                if should_delete:
                    try:
                        self.sheets_service.delete_sheet(file_id, sheet_id)
                        result['sheets_processed'].append({
                            'name': sheet_title,
                            'action': 'deleted',
                            'success': True
                        })
                        result['actions_performed'].append(f"Удален лист: {sheet_title}")
                    except Exception as e:
                        result['sheets_processed'].append({
                            'name': sheet_title,
                            'action': 'delete_failed',
                            'error': str(e)
                        })
                        result['errors'] = result.get('errors', [])
                        result['errors'].append(f"Не удалось удалить лист {sheet_title}: {str(e)}")
                elif should_keep:
                    result['sheets_processed'].append({
                        'name': sheet_title,
                        'action': 'kept',
                        'success': True
                    })
                    result['actions_performed'].append(f"Сохранен лист: {sheet_title}")
                else:
                    # Лист не в списке для сохранения и не в списке для удаления
                    # По умолчанию удаляем его (если есть хотя бы один лист для сохранения)
                    if sheets_to_keep:
                        try:
                            self.sheets_service.delete_sheet(file_id, sheet_id)
                            result['sheets_processed'].append({
                                'name': sheet_title,
                                'action': 'deleted',
                                'success': True
                            })
                            result['actions_performed'].append(f"Удален лист (не в списке сохранения): {sheet_title}")
                        except Exception as e:
                            result['sheets_processed'].append({
                                'name': sheet_title,
                                'action': 'delete_failed',
                                'error': str(e)
                            })
                            result['errors'] = result.get('errors', [])
                            result['errors'].append(f"Не удалось удалить лист {sheet_title}: {str(e)}")
                    else:
                        # Если нет листов для сохранения, оставляем все
                        result['sheets_processed'].append({
                            'name': sheet_title,
                            'action': 'kept',
                            'success': True
                        })
                        result['actions_performed'].append(f"Сохранен лист (нет правил): {sheet_title}")
            
        except Exception as e:
            result['errors'] = result.get('errors', [])
            result['errors'].append(f"Ошибка обработки листов: {str(e)}")
        
        return result
    
    def _get_sheets_to_keep(self, invite: Invite) -> List[str]:
        """Определяет листы для сохранения"""
        sheets_to_keep = []
        
        # Применяем правила сохранения
        for rule in self.rules['sheet_management']:
            if rule.get('action') == 'keep' and self._rule_applies(rule, invite):
                for sheet_name in rule.get('sheets', []):
                    # Для статических названий листов (без плейсхолдеров) не обрабатываем как шаблон
                    # Проверяем, есть ли плейсхолдеры в названии
                    if any(placeholder in sheet_name for placeholder in ['[F_NAME]', '[NAME]', '[DATE]', '[GRADE]', '[HUNTFLOW_LINK]', '[LINK]', '[VACANCY_NAME]', '[INTERVIEW_TIME]']):
                        processed_sheet = self._process_field_value(sheet_name, invite)
                    else:
                        # Статическое название листа - используем как есть
                        processed_sheet = sheet_name
                    
                    if processed_sheet and processed_sheet not in sheets_to_keep:
                        sheets_to_keep.append(processed_sheet)
        
        print(f"📋 SCORECARD: Листы для сохранения: {sheets_to_keep}")
        return sheets_to_keep
    
    def _get_sheets_to_delete(self, invite: Invite) -> List[str]:
        """Определяет листы для удаления"""
        sheets_to_delete = []
        
        # Применяем правила удаления
        for rule in self.rules['sheet_management']:
            if rule.get('action') == 'delete' and self._rule_applies(rule, invite):
                for sheet_name in rule.get('sheets', []):
                    processed_sheet = self._process_field_value(sheet_name, invite)
                    if processed_sheet and processed_sheet not in sheets_to_delete:
                        sheets_to_delete.append(processed_sheet)
        
        return sheets_to_delete
    
    def _fill_fields(self, invite: Invite, file_id: str) -> Dict[str, Any]:
        """Заполнение полей согласно правилам"""
        result = {
            'fields_filled': [],
            'actions_performed': []
        }
        
        try:
            # Сначала выполняем глобальную замену тегов во всех ячейках
            self._replace_placeholders_in_all_cells(invite, file_id, result)
            
            # Затем применяем правила заполнения полей
            for rule in self.rules['field_filling']:
                if not self._rule_applies(rule, invite):
                    continue
                
                # Заполняем поля из правила
                fields = rule.get('fields', {})
                for field_name, field_template in fields.items():
                    field_value = self._process_field_value(field_template, invite)
                    
                    try:
                        # Заполняем конкретное поле в Google Sheets
                        success = self._fill_specific_field(file_id, field_name, field_value)
                        
                        result['fields_filled'].append({
                            'field': field_name,
                            'value': field_value,
                            'success': success
                        })
                        
                        if success:
                            result['actions_performed'].append(f"Заполнено поле {field_name}: {field_value}")
                        else:
                            result['errors'] = result.get('errors', [])
                            result['errors'].append(f"Не удалось заполнить поле {field_name}")
                        
                    except Exception as e:
                        result['fields_filled'].append({
                            'field': field_name,
                            'value': field_value,
                            'error': str(e)
                        })
                        result['errors'] = result.get('errors', [])
                        result['errors'].append(f"Не удалось заполнить поле {field_name}: {str(e)}")
        
        except Exception as e:
            result['errors'] = result.get('errors', [])
            result['errors'].append(f"Ошибка заполнения полей: {str(e)}")
        
        return result
    
    def _generate_filename(self, invite: Invite) -> Dict[str, Any]:
        """Генерация названия файла согласно правилам"""
        result = {
            'filename_generated': None,
            'actions_performed': []
        }
        
        try:
            # Ищем правило для формирования названия
            naming_rule = None
            for rule in self.rules['naming']:
                if self._rule_applies(rule, invite):
                    naming_rule = rule
                    break
            
            if naming_rule:
                template = naming_rule.get('template', '[NAME] - [VACANCY_NAME]')
                filename = self._process_field_value(template, invite)
                result['filename_generated'] = filename
                result['actions_performed'].append(f"Сгенерировано название: {filename}")
            else:
                # Используем стандартное название
                filename = f"{invite.candidate_name} {self.vacancy.scorecard_title}"
                result['filename_generated'] = filename
                result['actions_performed'].append(f"Использовано стандартное название: {filename}")
        
        except Exception as e:
            result['errors'] = result.get('errors', [])
            result['errors'].append(f"Ошибка генерации названия: {str(e)}")
        
        return result
    
    def _process_field_value(self, template: str, invite: Invite) -> str:
        """Обрабатывает шаблон поля, заменяя плейсхолдеры на реальные значения"""
        if not template:
            return ""
        
        # Получаем реальную ссылку на Huntflow кандидата
        huntflow_link = self._get_huntflow_link(invite)
        
        # Получаем реальный грейд кандидата
        candidate_grade = self._get_candidate_grade(invite)
        
        # Словарь замен
        replacements = {
            '[F_NAME]': invite.candidate_name.split()[0] if invite.candidate_name else '',
            '[NAME]': invite.candidate_name or '',
            '[DATE]': invite.interview_datetime.strftime('%d.%m.%Y') if invite.interview_datetime else '',
            '[GRADE]': candidate_grade,
            '[HUNTFLOW_LINK]': huntflow_link,
            '[LINK]': huntflow_link,  # Алиас для [HUNTFLOW_LINK]
            '[VACANCY_NAME]': self.vacancy.name or '',
            '[INTERVIEW_TIME]': invite.interview_datetime.strftime('%H:%M') if invite.interview_datetime else '',
        }
        
        # Заменяем плейсхолдеры
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, str(value))
        
        return result
    
    def _rule_applies(self, rule: Dict, invite: Invite) -> bool:
        """Проверяет, применяется ли правило к данному инвайту"""
        conditions = rule.get('conditions', {})
        
        # Проверяем условие по грейду
        if 'grade' in conditions and invite.candidate_grade != conditions['grade']:
            return False
        
        # Проверяем условие по типу интервью (если есть такое поле)
        if 'interview_type' in conditions and hasattr(invite, 'interview_type'):
            if invite.interview_type != conditions['interview_type']:
                return False
        
        # Проверяем условие по вакансии
        if 'vacancy' in conditions and self.vacancy.name != conditions['vacancy']:
            return False
        
        return True
    
    def _get_huntflow_link(self, invite: Invite) -> str:
        """Получает реальную ссылку на кандидата в Huntflow"""
        try:
            # Проверяем наличие необходимых данных
            if not hasattr(invite, 'candidate_url') or not invite.candidate_url:
                print(f"⚠️ SCORECARD: candidate_url не найден в инвайте")
                return ""
            
            if not hasattr(invite, 'vacancy_id') or not invite.vacancy_id:
                print(f"⚠️ SCORECARD: vacancy_id не найден в инвайте")
                return ""
            
            # Используем метод из модели Invite для генерации ссылки
            huntflow_link = invite._generate_huntflow_candidate_link()
            if huntflow_link:
                print(f"🔗 SCORECARD: Получена ссылка Huntflow: {huntflow_link}")
                return huntflow_link
            else:
                print(f"⚠️ SCORECARD: Метод _generate_huntflow_candidate_link вернул None")
                print(f"⚠️ SCORECARD: candidate_url={invite.candidate_url}, vacancy_id={getattr(invite, 'vacancy_id', 'не найден')}")
                return ""
        except Exception as e:
            print(f"❌ SCORECARD: Ошибка получения ссылки Huntflow: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _get_candidate_grade(self, invite: Invite) -> str:
        """Получает реальный грейд кандидата"""
        try:
            # Сначала проверяем, есть ли грейд в инвайте
            if invite.candidate_grade and invite.candidate_grade != "Не указан":
                print(f"📊 SCORECARD: Используем грейд из инвайте: {invite.candidate_grade}")
                return invite.candidate_grade
            
            # Если грейда нет в инвайте, пытаемся получить из Huntflow
            if hasattr(invite, 'candidate_url') and invite.candidate_url:
                print(f"📊 SCORECARD: Получаем грейд из Huntflow для кандидата")
                grade_from_huntflow = self._get_grade_from_huntflow(invite)
                if grade_from_huntflow:
                    print(f"📊 SCORECARD: Получен грейд из Huntflow: {grade_from_huntflow}")
                    return grade_from_huntflow
            
            print(f"⚠️ SCORECARD: Грейд не найден")
            return ""
            
        except Exception as e:
            print(f"❌ SCORECARD: Ошибка получения грейда: {e}")
            return ""
    
    def _get_grade_from_huntflow(self, invite: Invite) -> Optional[str]:
        """Получает грейд кандидата из Huntflow API"""
        try:
            from apps.huntflow.services import HuntflowService
            
            # Получаем данные аккаунта
            huntflow_service = HuntflowService(invite.user)
            accounts = huntflow_service.get_accounts()
            
            if not accounts or 'items' not in accounts or not accounts['items']:
                print(f"⚠️ SCORECARD: Нет доступных аккаунтов Huntflow")
                return None
            
            account_id = accounts['items'][0]['id']
            
            # Извлекаем candidate_id из URL кандидата
            import re
            candidate_match = re.search(r'/id/(\d+)', invite.candidate_url)
            if not candidate_match:
                print(f"⚠️ SCORECARD: Не удалось извлечь candidate_id из URL: {invite.candidate_url}")
                return None
            
            candidate_id = candidate_match.group(1)
            
            # Получаем данные кандидата из Huntflow
            candidate_data = huntflow_service.get_applicant(account_id, int(candidate_id))
            
            if candidate_data and 'grade' in candidate_data:
                grade = candidate_data['grade']
                if grade and grade.get('name'):
                    return grade['name']
            
            return None
            
        except Exception as e:
            print(f"❌ SCORECARD: Ошибка получения грейда из Huntflow: {e}")
            return None
    
    def _replace_placeholders_in_all_cells(self, invite: Invite, file_id: str, result: Dict[str, Any]):
        """Заменяет плейсхолдеры [HUNTFLOW_LINK], [LINK] и [GRADE] во всех ячейках таблицы"""
        try:
            print(f"🔄 SCORECARD: Начинаем замену плейсхолдеров в файле {file_id}")
            
            # Получаем реальную ссылку на Huntflow кандидата
            huntflow_link = self._get_huntflow_link(invite)
            print(f"🔗 SCORECARD: Ссылка Huntflow: {huntflow_link if huntflow_link else 'не получена'}")
            
            # Получаем реальный грейд кандидата
            candidate_grade = self._get_candidate_grade(invite)
            print(f"📊 SCORECARD: Грейд кандидата: {candidate_grade if candidate_grade else 'не получен'}")
            
            replaced_count = 0
            
            # Заменяем [HUNTFLOW_LINK]
            if huntflow_link:
                print(f"🔄 SCORECARD: Заменяем [HUNTFLOW_LINK] на {huntflow_link[:50]}...")
                success = self.sheets_service.find_and_replace_cells(
                    file_id, '[HUNTFLOW_LINK]', huntflow_link
                )
                if success:
                    replaced_count += 1
                    result['actions_performed'].append(f"Заменены плейсхолдеры [HUNTFLOW_LINK] на реальную ссылку")
                    print(f"✅ SCORECARD: [HUNTFLOW_LINK] заменен успешно")
                else:
                    print(f"⚠️ SCORECARD: Не удалось заменить [HUNTFLOW_LINK]")
            else:
                print(f"⚠️ SCORECARD: Ссылка Huntflow не получена, пропускаем замену [HUNTFLOW_LINK]")
            
            # Заменяем [LINK] (алиас для [HUNTFLOW_LINK])
            if huntflow_link:
                print(f"🔄 SCORECARD: Заменяем [LINK] на {huntflow_link[:50]}...")
                success = self.sheets_service.find_and_replace_cells(
                    file_id, '[LINK]', huntflow_link
                )
                if success:
                    replaced_count += 1
                    result['actions_performed'].append(f"Заменены плейсхолдеры [LINK] на реальную ссылку")
                    print(f"✅ SCORECARD: [LINK] заменен успешно")
                else:
                    print(f"⚠️ SCORECARD: Не удалось заменить [LINK]")
            else:
                print(f"⚠️ SCORECARD: Ссылка Huntflow не получена, пропускаем замену [LINK]")
            
            # Заменяем [GRADE]
            if candidate_grade:
                print(f"🔄 SCORECARD: Заменяем [GRADE] на {candidate_grade}")
                success = self.sheets_service.find_and_replace_cells(
                    file_id, '[GRADE]', candidate_grade
                )
                if success:
                    replaced_count += 1
                    result['actions_performed'].append(f"Заменены плейсхолдеры [GRADE] на реальный грейд: {candidate_grade}")
                    print(f"✅ SCORECARD: [GRADE] заменен успешно")
                else:
                    print(f"⚠️ SCORECARD: Не удалось заменить [GRADE]")
            else:
                print(f"⚠️ SCORECARD: Грейд не получен, пропускаем замену [GRADE]")
            
            # Заменяем комбинированные плейсхолдеры (если оба тега в одной ячейке)
            if huntflow_link and candidate_grade:
                print(f"🔄 SCORECARD: Заменяем комбинированные плейсхолдеры")
                # Ищем ячейки, содержащие оба тега
                success = self._replace_combined_placeholders(file_id, huntflow_link, candidate_grade)
                if success:
                    result['actions_performed'].append("Заменены комбинированные плейсхолдеры")
                    print(f"✅ SCORECARD: Комбинированные плейсхолдеры заменены успешно")
            
            print(f"🔧 SCORECARD: Всего заменено плейсхолдеров: {replaced_count}")
            
        except Exception as e:
            error_msg = f"Ошибка замены плейсхолдеров: {str(e)}"
            print(f"❌ SCORECARD: {error_msg}")
            import traceback
            traceback.print_exc()
            result['errors'] = result.get('errors', [])
            result['errors'].append(error_msg)
    
    def _replace_combined_placeholders(self, file_id: str, huntflow_link: str, candidate_grade: str) -> bool:
        """Заменяет комбинированные плейсхолдеры в ячейках"""
        try:
            # Получаем все листы
            sheets = self.sheets_service.get_sheets(file_id)
            if not sheets:
                return False
            
            replaced_count = 0
            
            for sheet in sheets:
                sheet_title = sheet.get('properties', {}).get('title', sheet.get('title', 'Unknown'))
                
                # Получаем данные листа
                range_name = f"{sheet_title}!A1:Z1000"
                result = self.sheets_service._get_service().spreadsheets().values().get(
                    spreadsheetId=file_id,
                    range=range_name
                ).execute()
                
                values = result.get('values', [])
                if not values:
                    continue
                
                # Ищем ячейки с комбинированными плейсхолдерами
                updated_values = []
                for row_index, row in enumerate(values):
                    updated_row = []
                    for col_index, cell_value in enumerate(row):
                        cell_str = str(cell_value)
                        cell_updated = False
                        new_value = cell_str
                        
                        # Проверяем, содержит ли ячейка теги ссылки и грейда
                        has_link_placeholder = '[HUNTFLOW_LINK]' in cell_str or '[LINK]' in cell_str
                        has_grade_placeholder = '[GRADE]' in cell_str
                        
                        if has_link_placeholder and has_grade_placeholder:
                            # Заменяем оба плейсхолдера
                            new_value = new_value.replace('[HUNTFLOW_LINK]', huntflow_link)
                            new_value = new_value.replace('[LINK]', huntflow_link)
                            new_value = new_value.replace('[GRADE]', candidate_grade)
                            cell_updated = True
                        elif has_link_placeholder:
                            # Заменяем только плейсхолдер ссылки
                            new_value = new_value.replace('[HUNTFLOW_LINK]', huntflow_link)
                            new_value = new_value.replace('[LINK]', huntflow_link)
                            cell_updated = True
                        elif has_grade_placeholder:
                            # Заменяем только плейсхолдер грейда
                            new_value = new_value.replace('[GRADE]', candidate_grade)
                            cell_updated = True
                        
                        if cell_updated:
                            replaced_count += 1
                            print(f"🔄 Заменена ячейка {sheet_title}!{_get_column_letter(col_index)}{row_index + 1}")
                        
                        updated_row.append(new_value)
                    updated_values.append(updated_row)
                
                # Обновляем лист, если были изменения
                has_placeholders = any(
                    ('[HUNTFLOW_LINK]' in str(cell) or '[LINK]' in str(cell) or '[GRADE]' in str(cell))
                    for row in values for cell in row
                )
                if has_placeholders:
                    body = {'values': updated_values}
                    self.sheets_service._get_service().spreadsheets().values().update(
                        spreadsheetId=file_id,
                        range=range_name,
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
                    print(f"✅ Лист {sheet_title} обновлен с комбинированными плейсхолдерами")
            
            return replaced_count > 0
            
        except Exception as e:
            print(f"❌ Ошибка замены комбинированных плейсхолдеров: {e}")
            return False
    
    def _fill_specific_field(self, file_id: str, field_name: str, field_value: str) -> bool:
        """Заполняет конкретное поле в Google Sheets"""
        try:
            # Парсим field_name для получения листа и ячейки
            # Ожидаемый формат: "SheetName!A1" или "A1" (для первого листа)
            if '!' in field_name:
                sheet_name, cell_range = field_name.split('!', 1)
            else:
                # Если лист не указан, используем первый лист
                sheets = self.sheets_service.get_sheets(file_id)
                if not sheets:
                    return False
                sheet_name = sheets[0].get('properties', {}).get('title', 'Sheet1')
                cell_range = field_name
            
            # Обновляем ячейку
            success = self.sheets_service.update_cell_value(
                file_id, sheet_name, cell_range, field_value
            )
            
            if success:
                print(f"✅ SCORECARD: Заполнено поле {sheet_name}!{cell_range}: {field_value}")
            else:
                print(f"❌ SCORECARD: Не удалось заполнить поле {sheet_name}!{cell_range}")
            
            return success
            
        except Exception as e:
            print(f"❌ SCORECARD: Ошибка заполнения поля {field_name}: {e}")
            return False