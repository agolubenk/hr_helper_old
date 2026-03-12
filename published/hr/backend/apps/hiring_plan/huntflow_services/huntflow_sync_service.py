import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from ..models import HiringRequest, HuntflowSync, VacancySLA
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade
from apps.huntflow.token_service import HuntflowTokenService


class HuntflowSyncService:
    """Сервис для синхронизации данных с HuntFlow"""
    
    def __init__(self, user=None):
        self.user = user
        self.token_service = HuntflowTokenService(user) if user else None
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def _get_base_url(self):
        """Получает базовый URL для API запросов"""
        if not self.user:
            return "https://api.huntflow.ai/v2"
        
        if self.user.active_system == 'prod':
            base_url = self.user.huntflow_prod_url
        else:
            base_url = self.user.huntflow_sandbox_url
        
        # Убеждаемся, что URL заканчивается на /v2
        if not base_url.endswith('/v2'):
            if base_url.endswith('/'):
                base_url = base_url + 'v2'
            else:
                base_url = base_url + '/v2'
        
        return base_url
    
    def _get_account_id(self):
        """Получить account_id из токена или настроек"""
        # Пытаемся получить account_id из API
        if self.user and self.user.huntflow_access_token:
            try:
                # Получаем информацию об аккаунте
                base_url = self._get_base_url()
                headers = self._get_auth_headers()
                url = f"{base_url}/accounts"
                
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    accounts_data = response.json()
                    if accounts_data and 'items' in accounts_data and accounts_data['items']:
                        account_id = accounts_data['items'][0]['id']
                        return account_id
            except Exception as e:
                pass  # Логируем ошибку, но не выводим в консоль
        
        return 11  # Fallback
    
    def _get_auth_headers(self):
        """Получает заголовки с авторизацией"""
        if not self.user or not self.token_service:
            return self.headers
        
        # Получаем валидный токен
        access_token = self.token_service.ensure_valid_token()
        if not access_token:
            raise Exception("Не удалось получить валидный токен HuntFlow")
        
        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {access_token}'
        return headers
    
    def _make_request(self, endpoint, method='GET', params=None, data=None):
        """Выполнить запрос к HuntFlow API"""
        base_url = self._get_base_url()
        headers = self._get_auth_headers()
        
        # Формируем URL - убираем /v2 из endpoint если он есть
        if endpoint.startswith('v2/'):
            endpoint = endpoint[3:]
        
        # В HuntFlow API нужно указывать account_id в URL
        # Получаем account_id из токена или используем дефолтный
        account_id = self._get_account_id()
        url = f"{base_url}/accounts/{account_id}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )
            
            if response.status_code == 401:
                return None
            elif response.status_code == 403:
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return None
    
    def get_vacancy(self, vacancy_id):
        """Получить вакансию из HuntFlow"""
        return self._make_request(f"vacancies/{vacancy_id}")
    
    def get_applicant(self, applicant_id):
        """Получить кандидата из HuntFlow"""
        return self._make_request(f"applicants/{applicant_id}")
    
    def get_vacancy_applicants(self, vacancy_id, status=None):
        """Получить кандидатов по вакансии"""
        params = {}
        if status:
            params['status'] = status
        
        # Пробуем разные варианты URL
        endpoints_to_try = [
            f"vacancies/{vacancy_id}/applicants",
            f"vacancies/{vacancy_id}/candidates", 
            f"applicants?vacancy={vacancy_id}",
            f"candidates?vacancy={vacancy_id}"
        ]
        
        for endpoint in endpoints_to_try:
            result = self._make_request(endpoint, params=params)
            if result is not None:
                return result
        
        return None
    
    def get_applicant_logs(self, applicant_id):
        """Получить логи кандидата"""
        return self._make_request(f"applicants/{applicant_id}/logs")
    
    def map_huntflow_to_vacancy(self, hf_vacancy_data):
        """Сопоставить вакансию HuntFlow с Vacancy в системе"""
        # Поиск по названию позиции
        position = hf_vacancy_data.get('position', '')
        
        vacancy = Vacancy.objects.filter(
            name__icontains=position
        ).first()
        
        if not vacancy:
            # Создаем новую вакансию (опционально)
            # или возвращаем None для ручного сопоставления
            pass
        
        return vacancy
    
    def map_huntflow_to_grade(self, hf_applicant_data):
        """Определить грейд из дополнительных полей кандидата HuntFlow"""
        # Ищем поле "Уровень" в дополнительных полях кандидата
        additional_fields = hf_applicant_data.get('fields', [])
        
        for field in additional_fields:
            if field.get('name') == 'Уровень' or field.get('field_name') == 'level':
                level_value = field.get('value', '').strip()
                
                if not level_value:
                    continue
                
                # Сопоставляем с грейдами в системе
                level_lower = level_value.lower()
                
                # Сначала ищем точные совпадения
                grade = Grade.objects.filter(name__iexact=level_value).first()
                if grade:
                    return grade
                
                # Затем ищем по ключевым словам
                if any(word in level_lower for word in ['senior', 'сеньор', 'старший']):
                    grade = Grade.objects.filter(name__icontains='Senior').first()
                elif any(word in level_lower for word in ['middle', 'мидл', 'средний']):
                    grade = Grade.objects.filter(name__icontains='Middle').first()
                elif any(word in level_lower for word in ['junior', 'джуниор', 'младший']):
                    grade = Grade.objects.filter(name__icontains='Junior').first()
                elif any(word in level_lower for word in ['lead', 'лид', 'ведущий']):
                    grade = Grade.objects.filter(name__icontains='Lead').first()
                elif any(word in level_lower for word in ['head', 'хед', 'руководитель']):
                    grade = Grade.objects.filter(name__icontains='Head').first()
                else:
                    # Последняя попытка - поиск по частичному совпадению
                    grade = Grade.objects.filter(name__icontains=level_value).first()
                
                if grade:
                    return grade
        
        # Если не нашли в дополнительных полях, возвращаем Middle по умолчанию
        return Grade.objects.filter(name__icontains='Middle').first()
    
    def get_applicant_status_logs(self, applicant_id, target_statuses=None):
        """Получить логи кандидата с определенными статусами"""
        if target_statuses is None:
            target_statuses = [186508, 186507]  # Статусы для проверки
        
        logs = self.get_applicant_logs(applicant_id)
        if not logs:
            return []
        
        filtered_logs = []
        for log in logs.get('items', []):
            status = log.get('status')
            if isinstance(status, dict):
                status_id = status.get('id')
            else:
                status_id = status
            
            if status_id in target_statuses:
                filtered_logs.append(log)
        
        return filtered_logs
    
    def get_hired_date_from_logs(self, applicant_id):
        """Получить дату найма из логов (переход к статусу 186507)"""
        logs = self.get_applicant_status_logs(applicant_id, [186507])
        
        if logs:
            # Берем последний лог с статусом 186507
            latest_log = logs[-1]
            created_date = latest_log.get('created')
            if created_date:
                return datetime.strptime(created_date.split('T')[0], '%Y-%m-%d').date()
        
        return None
    
    def get_vacancy_opening_date(self, vacancy_id):
        """Получить дату открытия вакансии"""
        vacancy_data = self.get_vacancy(vacancy_id)
        if vacancy_data:
            created_date = vacancy_data.get('created')
            if created_date:
                return datetime.strptime(created_date.split('T')[0], '%Y-%m-%d').date()
        return None
    
    def get_vacancy_all_dates(self, vacancy_id):
        """Получить все даты открытия и переоткрытия вакансии"""
        vacancy_data = self.get_vacancy(vacancy_id)
        if not vacancy_data:
            return []
        
        dates = []
        
        # Основная дата создания
        created_date = vacancy_data.get('created')
        if created_date:
            try:
                date_obj = datetime.strptime(created_date.split('T')[0], '%Y-%m-%d').date()
                dates.append({
                    'date': date_obj,
                    'type': 'created',
                    'description': 'Дата создания вакансии'
                })
            except ValueError:
                pass
        
        # Добавляем дату обновления как возможную дату переоткрытия
        updated_date = vacancy_data.get('updated')
        if updated_date and updated_date != created_date:
            try:
                date_obj = datetime.strptime(updated_date.split('T')[0], '%Y-%m-%d').date()
                # Проверяем, что это не та же дата что и создание
                created_date_obj = datetime.strptime(created_date.split('T')[0], '%Y-%m-%d').date()
                if date_obj != created_date_obj:
                    dates.append({
                        'date': date_obj,
                        'type': 'updated',
                        'description': 'Дата последнего обновления вакансии'
                    })
            except ValueError:
                pass
        
        # Пытаемся получить историю изменений вакансии
        try:
            # В HuntFlow API может быть endpoint для истории вакансии
            history_data = self._make_request(f'vacancies/{vacancy_id}/history')
            if history_data and 'items' in history_data:
                for item in history_data['items']:
                    # Ищем события открытия/переоткрытия
                    event_type = item.get('type', '')
                    if event_type in ['opened', 'reopened', 'created']:
                        event_date = item.get('created')
                        if event_date:
                            try:
                                date_obj = datetime.strptime(event_date.split('T')[0], '%Y-%m-%d').date()
                                description = f"Дата {event_type} вакансии"
                                if event_type == 'reopened':
                                    description = "Дата переоткрытия вакансии"
                                elif event_type == 'opened':
                                    description = "Дата открытия вакансии"
                                
                                dates.append({
                                    'date': date_obj,
                                    'type': event_type,
                                    'description': description
                                })
                            except ValueError:
                                pass
        except Exception:
            # Если не удалось получить историю, продолжаем без неё
            pass
        
        # Убираем дубликаты и сортируем по дате
        unique_dates = {}
        for date_info in dates:
            date_key = date_info['date']
            if date_key not in unique_dates:
                unique_dates[date_key] = date_info
        
        sorted_dates = sorted(unique_dates.values(), key=lambda x: x['date'])
        
        return sorted_dates
    
    def import_hiring_request_from_huntflow(self, vacancy_id, applicant_id, custom_data=None):
        """Импортировать заявку на найм из HuntFlow с учетом новой логики"""
        
        # Проверяем, не импортирован ли уже
        existing_sync = HuntflowSync.objects.filter(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            sync_status='success'
        ).first()
        
        if existing_sync:
            return existing_sync.hiring_request, "Уже импортирован"
        
        # Получаем данные из HuntFlow
        hf_vacancy = self.get_vacancy(vacancy_id)
        hf_applicant = self.get_applicant(applicant_id)
        
        if not hf_vacancy or not hf_applicant:
            return None, "Не удалось получить данные из HuntFlow"
        
        # Сопоставляем с нашими данными
        vacancy = self.map_huntflow_to_vacancy(hf_vacancy)
        grade = self.map_huntflow_to_grade(hf_applicant)
        
        if not vacancy:
            return None, f"Вакансия не найдена: {hf_vacancy.get('position', 'Unknown')}"
        
        # Если грейд не найден, но есть в custom_data, используем его
        if not grade and custom_data and custom_data.get('grade'):
            from apps.finance.models import Grade
            try:
                grade_id = int(custom_data['grade'])
                grade = Grade.objects.get(id=grade_id)
            except (ValueError, Grade.DoesNotExist):
                grade = None
        
        # Если грейд все еще не найден, используем автоматически определенный
        if not grade:
            grade = self.map_huntflow_to_grade(hf_applicant)
        
        if not grade:
            return None, "Грейд не определен. Пожалуйста, выберите грейд в полях редактирования."
        
        # Получаем даты (используем данные из полей редактирования если есть)
        if custom_data and custom_data.get('opening_date'):
            try:
                opening_date = datetime.strptime(custom_data['opening_date'], '%Y-%m-%d').date()
            except ValueError:
                opening_date = self.get_vacancy_opening_date(vacancy_id)
        else:
            opening_date = self.get_vacancy_opening_date(vacancy_id)
        
        if custom_data and custom_data.get('hired_date'):
            try:
                hired_date = datetime.strptime(custom_data['hired_date'], '%Y-%m-%d').date()
            except ValueError:
                hired_date = self.get_hired_date_from_logs(applicant_id)
        else:
            hired_date = self.get_hired_date_from_logs(applicant_id)
        
        if not opening_date:
            return None, "Не удалось определить дату открытия вакансии"
        
        if not hired_date:
            return None, "Не найден переход к статусу 186507 (найм)"
        
        # Используем данные из полей редактирования или значения по умолчанию
        project = custom_data.get('project', '') if custom_data else hf_vacancy.get('company', '')
        priority = int(custom_data.get('priority', 2)) if custom_data else 2
        candidate_name = custom_data.get('name', '') if custom_data else f"{hf_applicant.get('first_name', '')} {hf_applicant.get('last_name', '')}".strip()
        notes = custom_data.get('notes', '') if custom_data else f"Импортировано из HuntFlow. Vacancy ID: {vacancy_id}, Applicant ID: {applicant_id}"
        
        # Если указан грейд в полях редактирования, используем его
        if custom_data and custom_data.get('grade'):
            from apps.finance.models import Grade
            custom_grade = Grade.objects.filter(name__icontains=custom_data['grade']).first()
            if custom_grade:
                grade = custom_grade
        
        # Создаем HiringRequest
        hiring_request = HiringRequest.objects.create(
            vacancy=vacancy,
            grade=grade,
            project=project,
            priority=priority,
            status='closed',
            opening_reason='new_position',
            opening_date=opening_date,
            closed_date=hired_date,
            candidate_id=str(applicant_id),
            candidate_name=candidate_name,
            notes=notes
        )
        
        # Создаем запись о синхронизации
        sync_record = HuntflowSync.objects.create(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            hiring_request=hiring_request,
            sync_status='success',
            huntflow_data={
                'vacancy': hf_vacancy,
                'applicant': hf_applicant,
                'opening_date': opening_date.isoformat(),
                'hired_date': hired_date.isoformat()
            },
            synced_at=timezone.now()
        )
        
        return hiring_request, "Успешно импортирован"
    
    def get_importable_applicants(self, vacancy_id=None):
        """Получить список кандидатов для импорта (со статусами 186507 и 186508)"""
        importable = []
        
        # Получаем кандидатов со статусом 186507
        params_507 = {'status': 186507, 'count': 30}
        if vacancy_id:
            params_507['vacancy'] = vacancy_id
        
        applicants_507 = self._make_request('applicants', params=params_507)
        if applicants_507 and 'items' in applicants_507:
            for applicant_item in applicants_507.get('items', []):
                applicant_data = self._process_applicant(applicant_item, 186507)
                if applicant_data:
                    importable.append(applicant_data)
        
        # Получаем кандидатов со статусом 186508
        params_508 = {'status': 186508, 'count': 30}
        if vacancy_id:
            params_508['vacancy'] = vacancy_id
        
        applicants_508 = self._make_request('applicants', params=params_508)
        if applicants_508 and 'items' in applicants_508:
            for applicant_item in applicants_508.get('items', []):
                applicant_data = self._process_applicant(applicant_item, 186508)
                if applicant_data:
                    importable.append(applicant_data)
        
        return importable
    
    def _process_applicant(self, applicant_item, status):
        """Обработать данные кандидата"""
        applicant_id = applicant_item.get('id')
        
        # Получаем дату найма из логов
        hired_date = self.get_hired_date_from_logs(applicant_id)
        
        if hired_date:
            # Используем данные из основного запроса в формате "Фамилия Имя"
            first_name = applicant_item.get('first_name', '').strip()
            last_name = applicant_item.get('last_name', '').strip()
            name = f"{last_name} {first_name}".strip()
            
            # Извлекаем vacancy_id из links
            vacancy_id = None
            links = applicant_item.get('links', [])
            if links and len(links) > 0:
                vacancy_id = links[0].get('vacancy')
            
            # Получаем все даты вакансии
            vacancy_dates = []
            vacancy_opening_date = None
            if vacancy_id:
                vacancy_dates = self.get_vacancy_all_dates(vacancy_id)
                vacancy_opening_date = self.get_vacancy_opening_date(vacancy_id)
            
            # Автоматически определяем грейд
            auto_grade = self.map_huntflow_to_grade(applicant_item)
            
            return {
                'applicant_id': applicant_id,
                'name': name,
                'hired_date': hired_date,
                'vacancy_opening_date': vacancy_opening_date,
                'vacancy_dates': vacancy_dates,  # Все даты вакансии для выбора
                'offer_accepted_date': hired_date,  # Дата перевода в статус Offer Accepted
                'current_status': status,
                'applicant_data': applicant_item,
                'vacancy_id': vacancy_id,
                'auto_grade_id': auto_grade.id if auto_grade else None,
                'auto_grade_name': auto_grade.name if auto_grade else None
            }
        
        return None
    
    def get_all_importable_applicants_by_vacancy(self):
        """Получить всех кандидатов со статусами 186507 и 186508, сгруппированных по вакансиям"""
        # Получаем всех кандидатов со статусами 186507 и 186508
        all_applicants = self.get_importable_applicants()
        
        # Исключаем уже импортированных кандидатов
        filtered_applicants = self._filter_already_imported(all_applicants)
        
        # Группируем по вакансиям
        vacancies_dict = {}
        
        for applicant in filtered_applicants:
            vacancy_id = applicant.get('vacancy_id')
            if vacancy_id:
                if vacancy_id not in vacancies_dict:
                    vacancies_dict[vacancy_id] = {
                        'id': vacancy_id,
                        'name': 'Unknown',  # Будет заполнено позже
                        'importable_count': 0,
                        'importable_applicants': []
                    }
                
                vacancies_dict[vacancy_id]['importable_applicants'].append(applicant)
                vacancies_dict[vacancy_id]['importable_count'] += 1
        
        # Получаем названия вакансий
        for vacancy_id in vacancies_dict.keys():
            vacancy_data = self.get_vacancy(vacancy_id)
            if vacancy_data:
                vacancies_dict[vacancy_id]['name'] = vacancy_data.get('position', 'Unknown')
        
        return list(vacancies_dict.values())
    
    def _filter_already_imported(self, applicants):
        """Исключить кандидатов, которые уже импортированы в план найма"""
        from apps.hiring_plan.models import HuntflowSync, HiringRequest
        
        # Получаем ID уже импортированных кандидатов из HuntflowSync
        imported_applicant_ids = set(
            HuntflowSync.objects.filter(
                huntflow_applicant_id__isnull=False,
                sync_status='success'
            ).values_list('huntflow_applicant_id', flat=True)
        )
        
        # Получаем ID кандидатов из HiringRequest (по candidate_id)
        imported_candidate_ids = set(
            HiringRequest.objects.filter(
                candidate_id__isnull=False,
                candidate_id__ne=''
            ).values_list('candidate_id', flat=True)
        )
        
        # Фильтруем кандидатов
        filtered = []
        for applicant in applicants:
            applicant_id = applicant.get('applicant_id')
            candidate_id_str = str(applicant_id)
            
            # Проверяем, не импортирован ли уже
            if (applicant_id not in imported_applicant_ids and 
                candidate_id_str not in imported_candidate_ids):
                filtered.append(applicant)
        
        return filtered
    
    def sync_hired_applicant(self, vacancy_id, applicant_id, log_data):
        """Синхронизировать нанятого кандидата"""
        
        # Проверяем, не синхронизирован ли уже
        existing_sync = HuntflowSync.objects.filter(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            sync_status='success'
        ).first()
        
        if existing_sync:
            print(f"Applicant {applicant_id} already synced")
            return existing_sync.hiring_request
        
        # Получаем данные из HuntFlow
        hf_vacancy = self.get_vacancy(vacancy_id)
        hf_applicant = self.get_applicant(applicant_id)
        
        if not hf_vacancy or not hf_applicant:
            # Создаем запись об ошибке
            HuntflowSync.objects.create(
                huntflow_vacancy_id=vacancy_id,
                huntflow_applicant_id=applicant_id,
                entity_type='status_change',
                sync_status='failed',
                error_message='Failed to fetch data from HuntFlow API',
                huntflow_data={}
            )
            return None
        
        # Сопоставляем с нашими данными
        vacancy = self.map_huntflow_to_vacancy(hf_vacancy)
        grade = self.map_huntflow_to_grade(hf_vacancy)
        
        if not vacancy or not grade:
            # Создаем запись для ручного сопоставления
            sync_record = HuntflowSync.objects.create(
                huntflow_vacancy_id=vacancy_id,
                huntflow_applicant_id=applicant_id,
                entity_type='status_change',
                sync_status='pending',
                error_message='Manual mapping required: vacancy or grade not found',
                huntflow_data={
                    'vacancy': hf_vacancy,
                    'applicant': hf_applicant,
                    'log': log_data
                }
            )
            return None
        
        # Получаем дату найма из лога
        employment_date = log_data.get('employment_date')
        if employment_date:
            closed_date = datetime.strptime(employment_date, '%Y-%m-%d').date()
        else:
            closed_date = timezone.now().date()
        
        # Определяем дату открытия
        opening_date_str = hf_vacancy.get('created', '')
        if opening_date_str:
            opening_date = datetime.strptime(
                opening_date_str.split('T')[0], '%Y-%m-%d'
            ).date()
        else:
            opening_date = closed_date
        
        # Проект из division
        project = hf_vacancy.get('company', '')
        
        # Создаем HiringRequest
        hiring_request = HiringRequest.objects.create(
            vacancy=vacancy,
            grade=grade,
            project=project,
            priority=2,  # По умолчанию высокий
            status='closed',
            opening_reason='new_position',  # или определить из данных
            opening_date=opening_date,
            closed_date=closed_date,
            candidate_id=str(applicant_id),
            candidate_name=f"{hf_applicant.get('first_name', '')} {hf_applicant.get('last_name', '')}".strip(),
            notes=f"Синхронизировано из HuntFlow. Vacancy ID: {vacancy_id}"
        )
        
        # Создаем запись о синхронизации
        sync_record = HuntflowSync.objects.create(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            hiring_request=hiring_request,
            sync_status='success',
            huntflow_data={
                'vacancy': hf_vacancy,
                'applicant': hf_applicant,
                'log': log_data
            },
            synced_at=timezone.now()
        )
        
        return hiring_request
    
    def sync_all_hired_for_vacancy(self, vacancy_id):
        """Синхронизировать всех нанятых кандидатов по вакансии"""
        
        # Получаем всех кандидатов вакансии
        applicants_data = self.get_vacancy_applicants(vacancy_id)
        
        if not applicants_data:
            return []
        
        hired_requests = []
        
        for applicant_item in applicants_data.get('items', []):
            applicant_id = applicant_item.get('id')
            
            # Получаем логи кандидата
            logs = self.get_applicant_logs(applicant_id)
            
            if not logs:
                continue
            
            # Ищем лог с hired статусом
            hired_log = None
            for log in logs.get('items', []):
                if log.get('type') == 'HIRED' or log.get('status', {}).get('name') == 'Hired':
                    hired_log = log
                    break
            
            if hired_log:
                request = self.sync_hired_applicant(
                    vacancy_id, applicant_id, hired_log
                )
                if request:
                    hired_requests.append(request)
        
        return hired_requests
    
    def bulk_sync_all_vacancies(self):
        """Массовая синхронизация всех вакансий"""
        
        # Получаем список всех вакансий
        vacancies_data = self._make_request('vacancies')
        
        if not vacancies_data:
            return
        
        for vacancy_item in vacancies_data.get('items', []):
            vacancy_id = vacancy_item.get('id')
            
            # Синхронизируем нанятых по каждой вакансии
            self.sync_all_hired_for_vacancy(vacancy_id)