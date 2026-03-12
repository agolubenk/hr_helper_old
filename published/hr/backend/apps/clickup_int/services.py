import requests
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.utils import timezone as django_timezone
import logging

logger = logging.getLogger(__name__)


class ClickUpAPIError(Exception):
    """Исключение для ошибок ClickUp API"""
    pass


class ClickUpService:
    """Сервис для работы с ClickUp API"""
    
    BASE_URL = "https://api.clickup.com/api/v2"
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            'Authorization': api_token,
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Выполняет запрос к ClickUp API"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            logger.info(f"ClickUp API запрос: {method} {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            
            logger.info(f"ClickUp API ответ: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise ClickUpAPIError("Неверный API токен")
            elif response.status_code == 403:
                raise ClickUpAPIError("Недостаточно прав доступа")
            elif response.status_code == 404:
                raise ClickUpAPIError("Ресурс не найден")
            elif response.status_code == 429:
                raise ClickUpAPIError("Превышен лимит запросов")
            else:
                error_msg = f"Ошибка API: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'err' in error_data:
                        error_msg += f" - {error_data['err']}"
                except:
                    error_msg += f" - {response.text}"
                
                raise ClickUpAPIError(error_msg)
                
        except requests.exceptions.Timeout:
            raise ClickUpAPIError("Таймаут запроса к ClickUp API")
        except requests.exceptions.ConnectionError:
            raise ClickUpAPIError("Ошибка подключения к ClickUp API")
        except requests.exceptions.RequestException as e:
            raise ClickUpAPIError(f"Ошибка запроса: {str(e)}")
    
    def test_connection(self) -> bool:
        """Тестирует подключение к ClickUp API"""
        try:
            response = self._make_request('GET', '/user')
            return 'user' in response
        except ClickUpAPIError:
            return False
    
    def get_user_info(self) -> Dict:
        """Получает информацию о пользователе"""
        return self._make_request('GET', '/user')
    
    def get_teams(self) -> List[Dict]:
        """Получает список команд"""
        response = self._make_request('GET', '/team')
        return response.get('teams', [])
    
    def get_spaces(self, team_id: str = None) -> List[Dict]:
        """Получает список пространств команды или все пространства пользователя"""
        if team_id:
            response = self._make_request('GET', f'/team/{team_id}/space')
        else:
            # Получаем все пространства пользователя
            response = self._make_request('GET', '/space')
        return response.get('spaces', [])
    
    def get_folders(self, space_id: str) -> List[Dict]:
        """Получает список папок пространства"""
        response = self._make_request('GET', f'/space/{space_id}/folder')
        return response.get('folders', [])
    
    def get_lists(self, folder_id: str = None, space_id: str = None) -> List[Dict]:
        """Получает список списков задач"""
        if folder_id:
            response = self._make_request('GET', f'/folder/{folder_id}/list')
        elif space_id:
            response = self._make_request('GET', f'/space/{space_id}/list')
        else:
            raise ClickUpAPIError("Необходимо указать folder_id или space_id")
        
        return response.get('lists', [])

    def get_folder_data(
        self,
        folder_id: str,
        include_closed: bool = True,
        max_lists: int = 50,
        max_tasks_per_list: int = 500,
    ) -> Dict[str, Any]:
        """
        Вытягивает из папки все списки и задачи (для плана найма).
        Возвращает: { 'folder_id', 'lists': [ { 'id', 'name', 'task_count', 'tasks': [...] }, ... ] }
        """
        lists_raw = self.get_lists(folder_id=folder_id)
        if not lists_raw:
            return {'folder_id': folder_id, 'lists': []}
        result_lists = []
        for lst in lists_raw[:max_lists]:
            list_id = lst.get('id') or lst.get('list_id')
            list_name = lst.get('name', '')
            if not list_id:
                continue
            tasks = []
            page = 0
            while len(tasks) < max_tasks_per_list:
                try:
                    chunk = self.get_tasks(
                        list_id,
                        include_closed=include_closed,
                        page=page,
                        exclude_huntflow_tagged=None,
                    )
                except ClickUpAPIError:
                    break
                if not chunk:
                    break
                tasks.extend(chunk)
                if len(chunk) < 100:
                    break
                page += 1
            result_lists.append({
                'id': list_id,
                'name': list_name,
                'task_count': len(tasks),
                'tasks': tasks[:max_tasks_per_list],
            })
        return {'folder_id': folder_id, 'lists': result_lists}
    
    def get_tasks(self, list_id: str, include_closed: bool = False, page: int = 0, exclude_huntflow_tagged: bool = None) -> List[Dict]:
        """
        Получает список задач из списка
        
        Args:
            list_id: ID списка задач
            include_closed: Включать ли закрытые задачи
            page: Номер страницы
            exclude_huntflow_tagged: None - все задачи, True - только без тега huntflow, False - только с тегом huntflow
            
        Returns:
            Список задач
        """
        params = {
            'include_closed': include_closed,
            'page': page,
            'order_by': 'updated',
            'reverse': True,
            'subtasks': True
        }
        
        response = self._make_request('GET', f'/list/{list_id}/task', params=params)
        tasks = response.get('tasks', [])
        
        # Фильтруем задачи по тегу huntflow в зависимости от настроек
        if exclude_huntflow_tagged is True:
            # Только задачи БЕЗ тега huntflow
            tasks = [task for task in tasks if not self.has_huntflow_tag(task)]
        elif exclude_huntflow_tagged is False:
            # Только задачи С тегом huntflow
            tasks = [task for task in tasks if self.has_huntflow_tag(task)]
        # Если exclude_huntflow_tagged is None - возвращаем все задачи без фильтрации
        
        return tasks
    
    def has_huntflow_tag(self, task: Dict) -> bool:
        """
        Проверяет, есть ли у задачи тег huntflow
        
        Args:
            task: Данные задачи из ClickUp API
            
        Returns:
            True если у задачи есть тег huntflow, False в противном случае
        """
        tags = task.get('tags', [])
        for tag in tags:
            if isinstance(tag, dict):
                tag_name = tag.get('name', '').lower()
            else:
                tag_name = str(tag).lower()
            
            if tag_name == 'huntflow':
                return True
        
        return False
    
    def get_task(self, task_id: str) -> Dict:
        """Получает детальную информацию о задаче"""
        return self._make_request('GET', f'/task/{task_id}')
    
    def get_task_attachments(self, task_id: str) -> List[Dict]:
        """Получает вложения задачи"""
        try:
            # Сначала пробуем получить вложения из отдельного endpoint'а
            response = self._make_request('GET', f'/task/{task_id}/attachment')
            return response.get('attachments', [])
        except ClickUpAPIError:
            # Если отдельный endpoint не работает, получаем вложения из информации о задаче
            try:
                task_info = self._make_request('GET', f'/task/{task_id}')
                return task_info.get('attachments', [])
            except ClickUpAPIError as e:
                logger.warning(f"Не удалось получить вложения для задачи {task_id}: {e}")
                return []
    
    def get_task_comments(self, task_id: str) -> List[Dict]:
        """Получает комментарии к задаче"""
        response = self._make_request('GET', f'/task/{task_id}/comment')
        comments = response.get('comments', [])
        
        # Парсим комментарии для читаемого отображения
        parsed_comments = []
        for comment in comments:
            parsed_comment = self._parse_comment(comment)
            parsed_comments.append(parsed_comment)
        
        return parsed_comments
    
    def add_tag_to_task(self, task_id: str, tag_name: str) -> bool:
        """
        Добавляет тег к задаче в ClickUp
        
        Args:
            task_id: ID задачи в ClickUp
            tag_name: Название тега для добавления
            
        Returns:
            True если тег успешно добавлен, False в противном случае
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Сначала получаем информацию о задаче
                task_data = self.get_task(task_id)
                if not task_data:
                    logger.error(f"Не удалось получить данные задачи {task_id}")
                    return False
                
                # Получаем текущие теги
                current_tags = task_data.get('tags', [])
                
                # Проверяем, есть ли уже такой тег
                tag_exists = any(
                    tag.get('name', '').lower() == tag_name.lower() 
                    for tag in current_tags if isinstance(tag, dict)
                )
                
                if tag_exists:
                    logger.info(f"Тег '{tag_name}' уже существует для задачи {task_id}")
                    return True
                
                # Проверяем, существует ли тег в пространстве задачи
                tag_exists = False
                try:
                    # Получаем пространство задачи
                    list_id = task_data.get('list', {}).get('id')
                    if list_id:
                        list_info = self._make_request('GET', f'/list/{list_id}')
                        space_id = list_info.get('space', {}).get('id')
                        
                        if space_id:
                            # Проверяем теги в пространстве задачи
                            space_tags_response = self._make_request('GET', f'/space/{space_id}/tag')
                            if space_tags_response:
                                # API может вернуть список тегов или словарь с полем 'tags'
                                if isinstance(space_tags_response, list):
                                    space_tags = space_tags_response
                                elif isinstance(space_tags_response, dict) and 'tags' in space_tags_response:
                                    space_tags = space_tags_response['tags']
                                else:
                                    space_tags = []
                                
                                for tag in space_tags:
                                    if isinstance(tag, dict) and tag.get('name', '').lower() == tag_name.lower():
                                        tag_exists = True
                                        logger.info(f"Тег '{tag_name}' найден в пространстве задачи {space_id}")
                                        break
                except Exception as e:
                    logger.warning(f"Не удалось проверить существование тега в пространстве задачи: {e}")
                
                # Если тег не существует, создаем его
                if not tag_exists:
                    logger.info(f"Тег '{tag_name}' не найден, создаем его")
                    
                    # Для huntflow создаем в пространстве задачи
                    if tag_name.lower() == 'huntflow' and list_id:
                        try:
                            list_info = self._make_request('GET', f'/list/{list_id}')
                            space_id = list_info.get('space', {}).get('id')
                            if space_id:
                                tag_created = self.create_tag(tag_name, space_id)
                                if tag_created:
                                    logger.info(f"Тег 'huntflow' создан в пространстве {space_id}")
                                else:
                                    logger.error(f"Не удалось создать тег 'huntflow' в пространстве {space_id}")
                                    return False
                            else:
                                logger.error(f"Не удалось получить space_id для создания тега")
                                return False
                        except Exception as e:
                            logger.error(f"Ошибка при создании тега в пространстве задачи: {e}")
                            return False
                    else:
                        # Для других тегов создаем в первом доступном пространстве
                        tag_created = self.create_tag(tag_name)
                        if not tag_created:
                            logger.error(f"Не удалось создать тег '{tag_name}'")
                            return False
                
                # Добавляем тег к задаче
                # Согласно ClickUp API документации: POST /task/{task_id}/tag/{tag_name}
                endpoint = f'/task/{task_id}/tag/{tag_name}'
                response = self._make_request('POST', endpoint)
                
                logger.info(f"Тег '{tag_name}' успешно добавлен к задаче {task_id}")
                return True
                
            except ClickUpAPIError as e:
                error_msg = str(e).lower()
                if 'rate limit' in error_msg or '429' in error_msg:
                    # Rate limit - ждем и пробуем еще раз
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Экспоненциальная задержка
                        logger.warning(f"Rate limit при добавлении тега '{tag_name}' к задаче {task_id}. Ждем {wait_time} секунд...")
                        import time
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Превышен лимит попыток при добавлении тега '{tag_name}' к задаче {task_id}")
                        return False
                elif 'not found' in error_msg or '404' in error_msg:
                    logger.error(f"Задача {task_id} или тег '{tag_name}' не найден")
                    return False
                elif 'unauthorized' in error_msg or '401' in error_msg:
                    logger.error(f"Недостаточно прав для добавления тега '{tag_name}' к задаче {task_id}")
                    return False
                else:
                    logger.error(f"API ошибка при добавлении тега '{tag_name}' к задаче {task_id}: {e}")
                    return False
            except Exception as e:
                logger.error(f"Неожиданная ошибка при добавлении тега '{tag_name}' к задаче {task_id}: {e}")
                return False
        
        return False
    
    def find_huntflow_tag_in_task_space(self, task_data: Dict) -> Optional[str]:
        """
        Находит тег huntflow в том же пространстве, где находится задача
        
        Args:
            task_data: Данные задачи из ClickUp API
            
        Returns:
            ID тега huntflow или None если не найден
        """
        try:
            # Получаем информацию о пространстве задачи
            list_id = task_data.get('list', {}).get('id')
            if not list_id:
                logger.warning("Не удалось получить list_id из данных задачи")
                return None
            
            # Получаем информацию о списке задач
            try:
                list_info = self._make_request('GET', f'/list/{list_id}')
                space_id = list_info.get('space', {}).get('id')
                if not space_id:
                    logger.warning(f"Не удалось получить space_id для списка {list_id}")
                    return None
                
                logger.info(f"Задача находится в пространстве {space_id}")
                
                # Получаем теги из этого пространства
                space_tags = self.get_all_tags(space_id)
                
                # Ищем тег huntflow
                for tag in space_tags:
                    tag_name = tag.get('name', '').lower()
                    if tag_name == 'huntflow':
                        tag_id = tag.get('id')
                        logger.info(f"Найден тег 'huntflow' с ID {tag_id} в пространстве задачи")
                        return tag_id
                
                logger.warning(f"Тег 'huntflow' не найден в пространстве {space_id}")
                return None
                
            except Exception as list_error:
                logger.error(f"Ошибка при получении информации о списке {list_id}: {list_error}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при поиске тега huntflow в пространстве задачи: {e}")
            return None
    
    def get_all_tags(self, space_id: str = None) -> List[Dict]:
        """
        Получает список всех доступных тегов
        
        Args:
            space_id: ID пространства для поиска тегов (если не указан, ищет во всех пространствах)
        
        Returns:
            Список доступных тегов
        """
        try:
            if space_id:
                # Получаем теги из конкретного пространства
                response = self._make_request('GET', f'/space/{space_id}/tag')
                tags = response.get('tags', [])
                logger.info(f"Получено {len(tags)} тегов из пространства {space_id}")
                return tags
            else:
                # Получаем теги из всех доступных пространств
                spaces = self.get_spaces()
                if not spaces:
                    logger.warning("Нет доступных пространств для получения тегов")
                    return []
                
                all_tags = []
                for space in spaces:
                    try:
                        space_id = space['id']
                        space_name = space.get('name', 'Unknown')
                        response = self._make_request('GET', f'/space/{space_id}/tag')
                        space_tags = response.get('tags', [])
                        logger.info(f"Пространство '{space_name}' ({space_id}): найдено {len(space_tags)} тегов")
                        
                        # Добавляем информацию о пространстве к каждому тегу
                        for tag in space_tags:
                            tag['space_id'] = space_id
                            tag['space_name'] = space_name
                        
                        all_tags.extend(space_tags)
                    except Exception as space_error:
                        logger.warning(f"Ошибка при получении тегов из пространства {space_id}: {space_error}")
                        continue
                
                logger.info(f"Всего получено {len(all_tags)} тегов из {len(spaces)} пространств")
                return all_tags
            
        except Exception as e:
            logger.error(f"Ошибка при получении тегов: {e}")
            return []
    
    def create_tag(self, tag_name: str, space_id: str = None) -> Optional[str]:
        """
        Создает новый тег
        
        Args:
            tag_name: Название тега
            space_id: ID пространства для создания тега (если не указан, используется первое доступное)
            
        Returns:
            ID созданного тега или None в случае ошибки
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if not space_id:
                    # Получаем доступные пространства
                    spaces = self.get_spaces()
                    if not spaces:
                        logger.error("Нет доступных пространств для создания тега")
                        return None
                    
                    # Берем первое пространство
                    space_id = spaces[0]['id']
                    logger.info(f"Используем первое доступное пространство {space_id} для создания тега '{tag_name}'")
                
                # Создаем тег
                endpoint = f'/space/{space_id}/tag'
                data = {
                    'tag': {
                        'name': tag_name,
                        'tag_fg': '#FFFFFF',  # Белый текст
                        'tag_bg': '#1E88E5'   # Синий фон
                    }
                }
                
                response = self._make_request('POST', endpoint, data=data)
                
                if response:
                    # API может вернуть тег в разных форматах
                    if isinstance(response, dict):
                        if 'tag' in response:
                            tag_id = response['tag'].get('id')
                        elif 'id' in response:
                            tag_id = response['id']
                        else:
                            tag_id = None
                    else:
                        tag_id = None
                    
                    if tag_id:
                        logger.info(f"Тег '{tag_name}' успешно создан с ID {tag_id}")
                        return tag_id
                    else:
                        logger.error(f"Не удалось получить ID созданного тега '{tag_name}'. Ответ: {response}")
                        return None
                else:
                    logger.error(f"Пустой ответ при создании тега '{tag_name}'")
                    return None
                    
            except ClickUpAPIError as e:
                error_msg = str(e).lower()
                if 'rate limit' in error_msg or '429' in error_msg:
                    # Rate limit - ждем и пробуем еще раз
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Экспоненциальная задержка
                        logger.warning(f"Rate limit при создании тега '{tag_name}'. Ждем {wait_time} секунд...")
                        import time
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Превышен лимит попыток при создании тега '{tag_name}'")
                        return None
                elif 'duplicate' in error_msg or 'already exists' in error_msg:
                    # Тег уже существует, пытаемся найти его ID
                    logger.info(f"Тег '{tag_name}' уже существует, ищем его ID")
                    available_tags = self.get_all_tags()
                    for tag in available_tags:
                        if tag.get('name', '').lower() == tag_name.lower():
                            tag_id = tag.get('id')
                            if tag_id:
                                logger.info(f"Найден существующий тег '{tag_name}' с ID {tag_id}")
                                return tag_id
                    logger.error(f"Тег '{tag_name}' существует, но не удалось найти его ID")
                    return None
                elif 'unauthorized' in error_msg or '401' in error_msg:
                    logger.error(f"Недостаточно прав для создания тега '{tag_name}'")
                    return None
                else:
                    logger.error(f"API ошибка при создании тега '{tag_name}': {e}")
                    return None
            except Exception as e:
                logger.error(f"Неожиданная ошибка при создании тега '{tag_name}': {e}")
                return None
        
        return None
    
    def debug_task_tags(self, task_id: str) -> Dict:
        """
        Отладочный метод для получения информации о тегах задачи
        
        Args:
            task_id: ID задачи в ClickUp
            
        Returns:
            Словарь с отладочной информацией
        """
        try:
            # Получаем данные задачи
            task_data = self.get_task(task_id)
            if not task_data:
                return {'error': f'Задача {task_id} не найдена'}
            
            # Получаем информацию о пространстве
            list_id = task_data.get('list', {}).get('id')
            space_info = {}
            if list_id:
                try:
                    list_info = self._make_request('GET', f'/list/{list_id}')
                    space_info = {
                        'list_id': list_id,
                        'list_name': list_info.get('name', 'Unknown'),
                        'space_id': list_info.get('space', {}).get('id'),
                        'space_name': list_info.get('space', {}).get('name', 'Unknown')
                    }
                except Exception as e:
                    space_info = {'error': f'Ошибка получения информации о списке: {e}'}
            
            # Получаем текущие теги задачи
            current_tags = task_data.get('tags', [])
            
            # Получаем все доступные теги в пространстве
            space_tags = []
            if space_info.get('space_id'):
                space_tags = self.get_all_tags(space_info['space_id'])
            
            # Ищем huntflow тег
            huntflow_tag = None
            for tag in space_tags:
                if tag.get('name', '').lower() == 'huntflow':
                    huntflow_tag = tag
                    break
            
            return {
                'task_id': task_id,
                'task_name': task_data.get('name', 'Unknown'),
                'space_info': space_info,
                'current_tags': [
                    {
                        'id': tag.get('id', 'Unknown'),
                        'name': tag.get('name', 'Unknown'),
                        'color': tag.get('tag_fg', 'Unknown')
                    } for tag in current_tags
                ],
                'available_space_tags': [
                    {
                        'id': tag.get('id', 'Unknown'),
                        'name': tag.get('name', 'Unknown'),
                        'color': tag.get('tag_fg', 'Unknown')
                    } for tag in space_tags
                ],
                'huntflow_tag': huntflow_tag,
                'has_huntflow_tag': self.has_huntflow_tag(task_data)
            }
            
        except Exception as e:
            return {'error': f'Ошибка отладки: {e}'}
    
    def force_add_huntflow_tag(self, task_id: str) -> Dict:
        """
        Принудительно добавляет тег huntflow к задаче (для отладки)
        
        Args:
            task_id: ID задачи в ClickUp
            
        Returns:
            Результат операции
        """
        try:
            # Получаем данные задачи
            task_data = self.get_task(task_id)
            if not task_data:
                return {'success': False, 'error': f'Задача {task_id} не найдена'}
            
            logger.info(f"🔍 Принудительное добавление тега huntflow к задаче {task_id}")
            
            # Проверяем, есть ли уже тег huntflow
            if self.has_huntflow_tag(task_data):
                return {'success': True, 'message': 'Тег huntflow уже существует у задачи'}
            
            # Ищем тег huntflow в пространстве задачи
            huntflow_tag_id = self.find_huntflow_tag_in_task_space(task_data)
            
            if not huntflow_tag_id:
                # Создаем тег huntflow в пространстве задачи
                logger.info("Создаем тег huntflow в пространстве задачи")
                list_id = task_data.get('list', {}).get('id')
                if list_id:
                    list_info = self._make_request('GET', f'/list/{list_id}')
                    space_id = list_info.get('space', {}).get('id')
                    if space_id:
                        huntflow_tag_id = self.create_tag('huntflow', space_id)
                        if not huntflow_tag_id:
                            return {'success': False, 'error': 'Не удалось создать тег huntflow'}
                    else:
                        return {'success': False, 'error': 'Не удалось определить пространство задачи'}
                else:
                    return {'success': False, 'error': 'Не удалось определить список задач'}
            
            # Добавляем тег к задаче
            endpoint = f'/task/{task_id}/tag/{huntflow_tag_id}'
            response = self._make_request('POST', endpoint)
            
            logger.info(f"✅ Тег huntflow успешно добавлен к задаче {task_id}")
            return {
                'success': True, 
                'message': f'Тег huntflow добавлен к задаче {task_id}',
                'tag_id': huntflow_tag_id
            }
            
        except Exception as e:
            logger.error(f"Ошибка при принудительном добавлении тега huntflow: {e}")
            return {'success': False, 'error': str(e)}
    
    def has_huntflow_tag(self, task_data: Dict) -> bool:
        """
        Проверяет, есть ли у задачи тег 'huntflow'
        
        Args:
            task_data: Данные задачи из ClickUp API
            
        Returns:
            True если у задачи есть тег huntflow, False в противном случае
        """
        if not task_data:
            return False
        
        tags = task_data.get('tags', [])
        if not tags:
            return False
        
        # Проверяем наличие тега huntflow (нечувствительно к регистру)
        for tag in tags:
            if isinstance(tag, dict):
                tag_name = tag.get('name', '').lower()
                if tag_name == 'huntflow':
                    return True
            elif isinstance(tag, str):
                if tag.lower() == 'huntflow':
                    return True
        
        return False
    
    def _parse_comment(self, comment_data: Dict) -> Dict:
        """Парсит структуру комментария для читаемого отображения"""
        if not comment_data:
            return comment_data
        
        # Копируем базовые данные
        parsed = comment_data.copy()
        
        # Парсим содержимое комментария
        comment_text = comment_data.get('comment', '')
        if isinstance(comment_text, list):
            # Это структурированный комментарий с блоками
            parsed_text = self._parse_comment_blocks(comment_text)
            parsed['comment'] = parsed_text
            parsed['comment_raw'] = comment_text  # Сохраняем оригинал
        elif isinstance(comment_text, str):
            parsed['comment'] = comment_text
            parsed['comment_raw'] = comment_text
        
        # Парсим дату
        date_value = comment_data.get('date', '')
        if date_value:
            parsed_date = self._parse_datetime(date_value)
            parsed['date'] = parsed_date
            parsed['date_raw'] = date_value
        
        return parsed
    
    def _parse_comment_blocks(self, blocks: List[Dict]) -> str:
        """Парсит блоки комментария в читаемый текст"""
        if not blocks:
            return ''
        
        result = []
        for block in blocks:
            text = block.get('text', '')
            attributes = block.get('attributes', {})
            
            if text:
                # Обрабатываем специальные атрибуты
                if attributes.get('bold'):
                    text = f'**{text}**'
                elif attributes.get('italic'):
                    text = f'*{text}*'
                elif attributes.get('underline'):
                    text = f'<u>{text}</u>'
                elif attributes.get('strikethrough'):
                    text = f'~~{text}~~'
                elif attributes.get('link'):
                    link_url = attributes.get('link')
                    text = f'[{text}]({link_url})'
                
                result.append(text)
        
        # Объединяем результат и применяем дополнительное форматирование
        combined_text = ''.join(result)
        
        # Обрабатываем Markdown-подобное форматирование
        combined_text = self._apply_markdown_formatting(combined_text)
        
        return combined_text
    
    def _apply_markdown_formatting(self, text: str) -> str:
        """Применяет Markdown-подобное форматирование к тексту"""
        if not text:
            return text
        
        # Обрабатываем жирный текст (**текст**)
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        # Обрабатываем курсив (*текст*)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        
        # Обрабатываем подчеркивание (__текст__)
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
        
        # Обрабатываем зачеркивание (~~текст~~)
        text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
        
        # Обрабатываем ссылки [текст](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
        
        return text
    
    def parse_task_data(self, task_data: Dict) -> Dict:
        """Парсит данные задачи из ClickUp API в формат для сохранения"""
        if not task_data:
            raise ClickUpAPIError("Данные задачи пусты")
        
        try:
            # Основные поля
            task_id = task_data.get('id', '')
            if not task_id:
                raise ClickUpAPIError("ID задачи не найден")
            
            name = task_data.get('name', '')
            description = task_data.get('description', '')
            
            # Статус и приоритет
            status = ''
            if task_data.get('status'):
                status = task_data['status'].get('status', '') if isinstance(task_data['status'], dict) else str(task_data['status'])
            
            priority = ''
            if task_data.get('priority'):
                priority = task_data['priority'].get('priority', '') if isinstance(task_data['priority'], dict) else str(task_data['priority'])
            
            # Даты
            date_created = self._parse_datetime(task_data.get('date_created'))
            date_updated = self._parse_datetime(task_data.get('date_updated'))
            due_date = self._parse_datetime(task_data.get('due_date'))
            
            # Ссылка
            url = task_data.get('url', '')
            
            # Исполнители
            assignees = task_data.get('assignees', [])
            if assignees and isinstance(assignees, list):
                assignees = [assignee.get('username', '') for assignee in assignees if isinstance(assignee, dict)]
            
            # Теги
            tags = task_data.get('tags', [])
            if tags and isinstance(tags, list):
                tags = [tag.get('name', '') for tag in tags if isinstance(tag, dict)]
            
            # Вложения (получаем отдельно)
            attachments = []
            try:
                attachments_data = self.get_task_attachments(task_id)
                if attachments_data:
                    attachments = [{
                        'id': att.get('id', ''),
                        'name': att.get('name', ''),
                        'url': att.get('url', ''),
                        'size': att.get('size', 0)
                    } for att in attachments_data if isinstance(att, dict)]
            except ClickUpAPIError as e:
                logger.warning(f"Не удалось получить вложения для задачи {task_id}: {e}")
            
            # Дополнительные поля (custom fields)
            custom_fields = {}
            if task_data.get('custom_fields'):
                try:
                    for field in task_data['custom_fields']:
                        if isinstance(field, dict):
                            field_id = field.get('id', '')
                            field_name = field.get('name', '')
                            field_type = field.get('type', 'text')
                            field_value = field.get('value', '')
                            
                            if field_id:
                                custom_fields[field_id] = {
                                    'name': field_name,
                                    'type': field_type,
                                    'value': field_value
                                }
                except Exception as e:
                    logger.warning(f"Ошибка обработки custom fields для задачи {task_id}: {e}")
            
            return {
                'task_id': task_id,
                'name': name,
                'description': description,
                'status': status,
                'priority': priority,
                'date_created': date_created,
                'date_updated': date_updated,
                'due_date': due_date,
                'url': url,
                'assignees': assignees,
                'tags': tags,
                'attachments': attachments,
                'custom_fields': custom_fields
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга данных задачи: {e}")
            raise ClickUpAPIError(f"Ошибка парсинга данных задачи: {str(e)}")
    
    def _parse_datetime(self, date_string) -> Optional[datetime]:
        """Парсит дату из строки ClickUp API"""
        if not date_string:
            return None
        
        try:
            # Если это уже datetime объект
            if isinstance(date_string, datetime):
                return date_string
            
            # Если это timestamp (число или строка с числом)
            if isinstance(date_string, (int, float)) or (isinstance(date_string, str) and date_string.isdigit()):
                # Конвертируем строку в число если нужно
                if isinstance(date_string, str):
                    date_string = int(date_string)
                
                # ClickUp использует timestamp в миллисекундах
                # Проверяем, если число больше 1e12, то это точно миллисекунды
                original_timestamp = date_string
                if date_string > 1e12:  # Если больше 10^12, то это миллисекунды
                    date_string = date_string / 1000
                    logger.debug(f"Конвертировали timestamp из миллисекунд: {original_timestamp} -> {date_string}")
                
                # Проверяем, что timestamp разумный (не в далеком будущем)
                # 1e10 = 2001-09-09, 2e10 = 2033-05-18
                if date_string > 2e10:  # Если все еще очень большое число
                    logger.warning(f"Timestamp слишком большой: {date_string}")
                    return None
                    
                return datetime.fromtimestamp(date_string, tz=timezone.utc)
            
            # Если это строка
            if isinstance(date_string, str):
                # ClickUp использует формат ISO 8601
                if date_string.endswith('Z'):
                    date_string = date_string.replace('Z', '+00:00')
                dt = datetime.fromisoformat(date_string)
                return dt
            
            logger.warning(f"Неизвестный формат даты: {date_string} (тип: {type(date_string)})")
            return None
            
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Не удалось распарсить дату: {date_string} (ошибка: {e})")
            return None
    
    def sync_tasks(self, list_id: str, user, max_pages: int = 10, exclude_huntflow_tagged: bool = True) -> Tuple[int, int, int]:
        """
        Синхронизирует задачи из списка
        
        Args:
            list_id: ID списка задач
            user: Пользователь Django
            max_pages: Максимальное количество страниц для обработки
            exclude_huntflow_tagged: Исключать ли задачи с тегом huntflow (deprecated, используется настройка пользователя)
        """
        from .models import ClickUpTask, ClickUpSyncLog, ClickUpSettings
        
        start_time = django_timezone.now()
        tasks_processed = 0
        tasks_created = 0
        tasks_updated = 0
        
        # Получаем настройку фильтра huntflow из базы данных
        try:
            settings = ClickUpSettings.objects.get(user=user)
            huntflow_filter = settings.huntflow_filter
            logger.info(f"Используется фильтр huntflow: {huntflow_filter}")
        except ClickUpSettings.DoesNotExist:
            huntflow_filter = 'all'  # По умолчанию все задачи
            logger.warning(f"Настройки ClickUp не найдены для пользователя {user.username}, используется фильтр по умолчанию: {huntflow_filter}")
        
        # Определяем параметры фильтрации на основе настроек
        if huntflow_filter == 'with_huntflow':
            exclude_huntflow_tagged = False  # Только с тегом huntflow
        elif huntflow_filter == 'without_huntflow':
            exclude_huntflow_tagged = True   # Только без тега huntflow
        else:  # 'all'
            exclude_huntflow_tagged = None   # Все задачи (передадим None в get_tasks)
        
        try:
            # Получаем все задачи из списка (с пагинацией)
            for page in range(max_pages):
                tasks_data = self.get_tasks(list_id, include_closed=False, page=page, exclude_huntflow_tagged=exclude_huntflow_tagged)
                
                if not tasks_data:
                    break
                
                for task_data in tasks_data:
                    if not task_data:
                        logger.warning("Получены пустые данные задачи, пропускаем")
                        continue
                        
                    try:
                        parsed_data = self.parse_task_data(task_data)
                        
                        # Проверяем обязательные поля
                        if not parsed_data.get('task_id'):
                            logger.warning(f"Задача без ID, пропускаем: {task_data}")
                            continue
                        
                        # Проверяем, существует ли задача
                        task, created = ClickUpTask.objects.get_or_create(
                            task_id=parsed_data['task_id'],
                            user=user,
                            defaults=parsed_data
                        )
                        
                        if created:
                            tasks_created += 1
                        else:
                            # Обновляем существующую задачу
                            for field, value in parsed_data.items():
                                setattr(task, field, value)
                            task.save()
                            tasks_updated += 1
                        
                        tasks_processed += 1
                        
                    except Exception as e:
                        task_id = task_data.get('id', 'unknown') if isinstance(task_data, dict) else 'unknown'
                        logger.error(f"Ошибка обработки задачи {task_id}: {e}")
                        continue
            
            # Создаем лог синхронизации
            sync_duration = (django_timezone.now() - start_time).total_seconds()
            
            ClickUpSyncLog.objects.create(
                user=user,
                status='success',
                tasks_processed=tasks_processed,
                tasks_created=tasks_created,
                tasks_updated=tasks_updated,
                sync_duration=sync_duration
            )
            
            # Обновляем время последней синхронизации в настройках
            settings_obj = ClickUpSettings.get_or_create_for_user(user)
            settings_obj.last_sync_at = django_timezone.now()
            settings_obj.save()
            
            return tasks_processed, tasks_created, tasks_updated
            
        except Exception as e:
            # Создаем лог ошибки
            sync_duration = (django_timezone.now() - start_time).total_seconds()
            
            ClickUpSyncLog.objects.create(
                user=user,
                status='error',
                tasks_processed=tasks_processed,
                error_message=str(e),
                sync_duration=sync_duration
            )
            
            raise ClickUpAPIError(f"Ошибка синхронизации: {str(e)}")


class ClickUpCacheService:
    """Сервис для кэширования данных ClickUp"""
    
    @staticmethod
    def get_cached_tasks(user, limit: int = 50) -> List[Dict]:
        """Получает кэшированные задачи пользователя"""
        from .models import ClickUpTask
        
        tasks = ClickUpTask.objects.filter(user=user).order_by('-date_updated')[:limit]
        
        return [
            {
                'id': task.task_id,
                'name': task.name,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'date_created': task.date_created,
                'date_updated': task.date_updated,
                'due_date': task.due_date,
                'url': task.url,
                'assignees': task.get_assignees_display(),
                'tags': task.get_tags_display(),
                'attachments': task.get_attachments_display(),
            }
            for task in tasks
        ]
    
    @staticmethod
    def clear_user_cache(user):
        """Очищает кэш задач пользователя"""
        from .models import ClickUpTask
        
        ClickUpTask.objects.filter(user=user).delete()
        logger.info(f"Кэш задач очищен для пользователя {user.username}")
    
    def get_tasks_from_list(self, list_id: str, exclude_huntflow_tagged: bool = None) -> List[Dict[str, Any]]:
        """
        Получает все задачи из указанного списка
        
        Args:
            list_id: ID списка ClickUp
            exclude_huntflow_tagged: None - все задачи, True - только без тега huntflow, False - только с тегом huntflow
            
        Returns:
            Список задач из API
        """
        try:
            print(f"🔍 Получаем задачи из списка {list_id}")
            
            all_tasks = []
            page = 0
            
            while True:
                # Получаем задачи постранично
                endpoint = f"/list/{list_id}/task"
                params = {
                    'page': page,
                    'include_closed': 'true',  # Включаем закрытые задачи
                    'subtasks': 'true',        # Включаем подзадачи
                }
                
                response_data = self._make_request('GET', endpoint, params=params)
                
                if not response_data or 'tasks' not in response_data:
                    break
                
                tasks = response_data['tasks']
                if not tasks:
                    break
                
                # Фильтруем задачи по тегу huntflow в зависимости от настроек
                if exclude_huntflow_tagged is True:
                    # Только задачи БЕЗ тега huntflow
                    filtered_tasks = [task for task in tasks if not self.has_huntflow_tag(task)]
                    all_tasks.extend(filtered_tasks)
                    
                    # Логируем количество отфильтрованных задач
                    filtered_count = len(tasks) - len(filtered_tasks)
                    if filtered_count > 0:
                        print(f"🔄 Страница {page}: отфильтровано {filtered_count} задач с тегом huntflow")
                elif exclude_huntflow_tagged is False:
                    # Только задачи С тегом huntflow
                    filtered_tasks = [task for task in tasks if self.has_huntflow_tag(task)]
                    all_tasks.extend(filtered_tasks)
                    
                    # Логируем количество отфильтрованных задач
                    filtered_count = len(tasks) - len(filtered_tasks)
                    if filtered_count > 0:
                        print(f"🔄 Страница {page}: отфильтровано {filtered_count} задач без тега huntflow")
                else:
                    # Все задачи без фильтрации
                    all_tasks.extend(tasks)
                
                page += 1
                
                # Ограничиваем количество страниц для безопасности
                if page > 100:  # Максимум 100 страниц
                    print(f"⚠️ Достигнут лимит страниц (100), останавливаемся")
                    break
            
            filter_desc = "все задачи" if exclude_huntflow_tagged is None else ("без тега huntflow" if exclude_huntflow_tagged is True else "с тегом huntflow")
            print(f"✅ Получено {len(all_tasks)} задач из списка {list_id} (фильтр: {filter_desc})")
            return all_tasks
            
        except Exception as e:
            print(f"❌ Ошибка при получении задач из списка {list_id}: {e}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные одной задачи по ID
        
        Args:
            task_id: ID задачи ClickUp
            
        Returns:
            Данные задачи или None
        """
        try:
            endpoint = f"/task/{task_id}"
            response_data = self._make_request('GET', endpoint)
            return response_data
            
        except Exception as e:
            print(f"❌ Ошибка при получении задачи {task_id}: {e}")
            return None
