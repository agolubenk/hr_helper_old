import os
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import GoogleOAuthAccount
from .cache_service import GoogleAPICache

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Сервис для работы с Google OAuth и API"""
    
    # Области доступа для Google API
    SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
    ]
    
    def __init__(self, user):
        self.user = user
        self.credentials = None
    
    def get_oauth_account(self):
        """Получить Google OAuth аккаунт пользователя"""
        try:
            return GoogleOAuthAccount.objects.get(user=self.user)
        except GoogleOAuthAccount.DoesNotExist:
            return None
    
    def create_oauth_flow(self):
        """Создать OAuth flow для авторизации"""
        # Используем все доступные redirect URIs
        redirect_uris = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URIS', [settings.GOOGLE_OAUTH_REDIRECT_URI])
        
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": redirect_uris
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI
        )
        
        # Отключаем проверку HTTPS для разработки
        import os
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        
        return flow
    
    def get_authorization_url(self):
        """Получить URL для авторизации. Вызываем oauth2session напрямую и берём (url, state) —
        иначе flow.authorization_url() падает с 'too many values to unpack' в части окружений (requests_oauthlib возвращает 3+ значения)."""
        flow = self.create_oauth_flow()
        auth_uri = 'https://accounts.google.com/o/oauth2/auth'
        if isinstance(getattr(flow, 'client_config', None), dict):
            auth_uri = flow.client_config.get('auth_uri', auth_uri)
        kwargs = dict(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        result = flow.oauth2session.authorization_url(auth_uri, **kwargs)
        auth_url = result[0]
        state = result[1] if len(result) > 1 else None
        return auth_url, state
    
    def handle_callback(self, authorization_response, state):
        """Обработать callback от Google OAuth"""
        flow = self.create_oauth_flow()
        
        # Получаем токены, игнорируем предупреждения о scopes
        import warnings
        import logging
        
        # Отключаем предупреждения о scopes
        warnings.filterwarnings("ignore", message="Scope has changed")
        logging.getLogger('oauthlib').setLevel(logging.ERROR)
        
        try:
            flow.fetch_token(authorization_response=authorization_response)
            credentials = flow.credentials
        except Exception as e:
            # Если ошибка связана с scopes, пробуем без проверки
            if "Scope has changed" in str(e):
                print(f"⚠️ Scope warning ignored: {e}")
                # Создаем credentials вручную из response
                from urllib.parse import parse_qs, urlparse
                parsed_url = urlparse(authorization_response)
                query_params = parse_qs(parsed_url.query)
                
                # Получаем токены из callback
                code = query_params.get('code', [None])[0]
                if code:
                    # Создаем новый flow для получения токенов
                    flow = self.create_oauth_flow()
                    flow.fetch_token(code=code)
                    credentials = flow.credentials
                else:
                    raise e
            else:
                raise e
        
        # Получаем информацию о пользователе
        user_info = self._get_user_info(credentials)
        
        # Создаем или обновляем аккаунт
        oauth_account, created = GoogleOAuthAccount.objects.get_or_create(
            user=self.user,
            defaults={
                'google_id': user_info['id'],
                'email': user_info['email'],
                'name': user_info['name'],
                'picture_url': user_info.get('picture', ''),
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_expires_at': timezone.now() + timedelta(seconds=credentials.expires_in),
                'scopes': credentials.scopes,
            }
        )
        
        if not created:
            # Обновляем существующий аккаунт
            oauth_account.google_id = user_info['id']
            oauth_account.email = user_info['email']
            oauth_account.name = user_info['name']
            oauth_account.picture_url = user_info.get('picture', '')
            oauth_account.access_token = credentials.token
            oauth_account.refresh_token = credentials.refresh_token
            oauth_account.token_expires_at = timezone.now() + timedelta(seconds=credentials.expires_in)
            oauth_account.scopes = credentials.scopes
            oauth_account.save()
        
        return oauth_account
    
    def _get_user_info(self, credentials):
        """Получить информацию о пользователе"""
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    
    def get_credentials(self):
        """Получить действительные credentials"""
        oauth_account = self.get_oauth_account()
        if not oauth_account:
            return None
        
        # Проверяем, нужно ли обновить токен
        if oauth_account.needs_refresh() and oauth_account.refresh_token:
            try:
                self._refresh_token(oauth_account)
                logger.info(f"✅ Токен автоматически обновлен для пользователя: {self.user.username}")
            except Exception as e:
                logger.error(f"❌ Ошибка при автоматическом обновлении токена для {self.user.username}: {e}")
                # Продолжаем с текущим токеном, возможно он еще валиден
        
        # Создаем credentials
        self.credentials = Credentials(
            token=oauth_account.access_token,
            refresh_token=oauth_account.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=oauth_account.scopes
        )
        
        return self.credentials
    
    def _refresh_token(self, oauth_account):
        """Обновить токен доступа"""
        credentials = Credentials(
            token=oauth_account.access_token,
            refresh_token=oauth_account.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=oauth_account.scopes
        )
        
        # Обновляем токен
        credentials.refresh(Request())
        
        # Сохраняем новый токен
        oauth_account.access_token = credentials.token
        # Google access token обычно действителен 1 час (3600 секунд)
        oauth_account.token_expires_at = timezone.now() + timedelta(seconds=3600)
        oauth_account.save()
    
    def refresh_token(self):
        """Публичный метод для обновления токена доступа"""
        oauth_account = self.get_oauth_account()
        if not oauth_account:
            return False
        
        if not oauth_account.refresh_token:
            return False
        
        try:
            self._refresh_token(oauth_account)
            return True
        except Exception as e:
            print(f"Ошибка при обновлении токена: {e}")
            return False
    
    def revoke_access(self):
        """Отозвать доступ к Google аккаунту"""
        oauth_account = self.get_oauth_account()
        if not oauth_account:
            return False
        
        try:
            credentials = Credentials(token=oauth_account.access_token)
            credentials.revoke(Request())
        except:
            pass  # Игнорируем ошибки при отзыве
        
        # Удаляем аккаунт
        oauth_account.delete()
        return True


class GoogleCalendarService:
    """Сервис для работы с Google Calendar"""
    
    def __init__(self, oauth_service):
        self.oauth_service = oauth_service
        self.service = None
    
    def _get_service(self):
        """Получить сервис Google Calendar"""
        if not self.service:
            credentials = self.oauth_service.get_credentials()
            if not credentials:
                return None
            
            self.service = build('calendar', 'v3', credentials=credentials)
        
        return self.service
    
    def get_calendars(self):
        """Получить список календарей"""
        service = self._get_service()
        if not service:
            return []
        
        try:
            calendar_list = service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except HttpError as e:
            print(f"Ошибка получения календарей: {e}")
            return []
    
    def get_calendar_public_link(self, calendar_id='primary'):
        """Получить публичную ссылку на календарь"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Получаем информацию о календаре
            calendar = service.calendars().get(calendarId=calendar_id).execute()
            
            # Проверяем, есть ли публичная ссылка
            if 'id' in calendar:
                # Формируем публичную ссылку на календарь
                public_link = f"https://calendar.google.com/calendar/embed?src={calendar['id']}"
                return public_link
            
            return None
        except HttpError as e:
            print(f"Ошибка получения публичной ссылки на календарь: {e}")
            return None
    
    def get_calendar_by_email(self, email):
        """Найти календарь по email адресу"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Получаем список всех календарей
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            # Ищем календарь с нужным email
            for calendar in calendars:
                if calendar.get('id') == email:
                    return calendar
            
            return None
        except HttpError as e:
            print(f"Ошибка поиска календаря по email: {e}")
            return None
    
    def get_events(self, calendar_id='primary', max_results=100, days_ahead=100, force_refresh=False):
        """Получить события календаря (ближайшие события на указанное количество дней вперед)"""
        user_id = self.oauth_service.user.id
        
        # Проверяем кэш только если не принудительное обновление
        if not force_refresh:
            cached_events = GoogleAPICache.get_calendar_events(user_id, calendar_id, days_ahead)
            
            if cached_events is not None:
                print(f"📦 Получены события календаря из кэша: {len(cached_events)} событий")
                return cached_events
        
        # Если в кэше нет или принудительное обновление, получаем из API
        service = self._get_service()
        if not service:
            return []
        
        try:
            from datetime import timedelta
            
            # Время начала - сейчас
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            
            # Время окончания - через указанное количество дней
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            # Получаем полную информацию о каждом событии
            events = []
            for event in events_result.get('items', []):
                try:
                    # Запрашиваем полную информацию о событии
                    full_event = service.events().get(
                        calendarId=calendar_id,
                        eventId=event['id']
                    ).execute()
                    events.append(full_event)
                except Exception as e:
                    print(f"Ошибка получения полной информации о событии {event.get('id', 'unknown')}: {e}")
                    # Если не удалось получить полную информацию, используем базовую
                    events.append(event)
            
            # Сохраняем в кэш
            GoogleAPICache.set_calendar_events(user_id, events, calendar_id, days_ahead)
            print(f"💾 Сохранены события календаря в кэш: {len(events)} событий")
            
            return events
        except HttpError as e:
            print(f"Ошибка получения событий: {e}")
            return []
    
    def get_events_for_date(self, date, calendar_id='primary'):
        """
        Получить все события календаря на указанную дату (целый день) с полной информацией,
        включая responseStatus участников (accepted/declined/tentative).
        
        Args:
            date: datetime.date или datetime с датой
            calendar_id: ID календаря (по умолчанию 'primary')
            
        Returns:
            Список словарей, пригодных для JSON: summary, start, end, htmlLink, id,
            attendees: [{ email, responseStatus }], organizer, status
        """
        service = self._get_service()
        if not service:
            return []
        try:
            import pytz
            if hasattr(date, 'date'):
                day = date.date() if hasattr(date, 'date') else date
            else:
                day = date
            tz = pytz.timezone('Europe/Minsk')
            time_min_dt = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
            time_max_dt = time_min_dt + timedelta(days=1)
            time_min = time_min_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            time_max = time_max_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=250,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            snapshot = []
            for event in events_result.get('items', []):
                try:
                    full = service.events().get(
                        calendarId=calendar_id,
                        eventId=event['id']
                    ).execute()
                    attendees_data = []
                    for att in full.get('attendees') or []:
                        attendees_data.append({
                            'email': att.get('email', ''),
                            'responseStatus': att.get('responseStatus', 'needsAction'),
                            'displayName': att.get('displayName', ''),
                        })
                    start = full.get('start') or {}
                    end = full.get('end') or {}
                    snapshot.append({
                        'id': full.get('id'),
                        'summary': full.get('summary', '(без названия)'),
                        'start': start.get('dateTime') or start.get('date'),
                        'end': end.get('dateTime') or end.get('date'),
                        'htmlLink': full.get('htmlLink', ''),
                        'status': full.get('status', ''),
                        'organizer': full.get('organizer', {}),
                        'attendees': attendees_data,
                    })
                except Exception as e:
                    logger.warning("Ошибка получения полного события %s: %s", event.get('id'), e)
                    snapshot.append({
                        'id': event.get('id'),
                        'summary': event.get('summary', '(без названия)'),
                        'start': (event.get('start') or {}).get('dateTime') or (event.get('start') or {}).get('date'),
                        'end': (event.get('end') or {}).get('dateTime') or (event.get('end') or {}).get('date'),
                        'htmlLink': event.get('htmlLink', ''),
                        'status': event.get('status', ''),
                        'attendees': [],
                    })
            return snapshot
        except HttpError as e:
            logger.warning("Ошибка get_events_for_date: %s", e)
            return []
    
    def create_event(self, title, start_time, end_time, description='', location='', attendees=None, calendar_id='primary', create_conference=True):
        """
        Создает событие в Google Calendar
        
        Args:
            title: Название события
            start_time: Время начала (datetime объект)
            end_time: Время окончания (datetime объект)
            description: Описание события
            location: Местоположение
            attendees: Список email адресов участников
            calendar_id: ID календаря (по умолчанию 'primary')
            
        Returns:
            Созданное событие или None в случае ошибки
        """
        service = self._get_service()
        if not service:
            return None
        
        try:
            from django.utils import timezone
            import pytz
            
            # Форматируем время для Google Calendar API
            if start_time.tzinfo is None:
                # Если время без timezone, считаем его в часовом поясе Minsk
                minsk_tz = pytz.timezone('Europe/Minsk')
                start_time = minsk_tz.localize(start_time)
                end_time = minsk_tz.localize(end_time)
                print(f"🔍 Время без timezone, локализовано в Minsk: {start_time}")
            else:
                print(f"🔍 Время с timezone: {start_time}")
            
            # Конвертируем в UTC для Google Calendar API
            start_time_utc = start_time.astimezone(pytz.UTC)
            end_time_utc = end_time.astimezone(pytz.UTC)
            
            # Форматируем для API (без 'Z' в конце, так как указываем timeZone отдельно)
            start_time_str = start_time_utc.strftime('%Y-%m-%dT%H:%M:%S')
            end_time_str = end_time_utc.strftime('%Y-%m-%dT%H:%M:%S')
            
            print(f"🔍 Время начала (UTC): {start_time_utc}")
            print(f"🔍 Время окончания (UTC): {end_time_utc}")
            print(f"🔍 Строка времени начала: {start_time_str}")
            print(f"🔍 Строка времени окончания: {end_time_str}")
            
            # Подготавливаем участников
            attendees_list = []
            if attendees:
                for email in attendees:
                    attendees_list.append({'email': email})
            
            # Создаем событие
            event = {
                'summary': title,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_time_str,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time_str,
                    'timeZone': 'UTC',
                },
                'attendees': attendees_list,
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # За день
                        {'method': 'popup', 'minutes': 10},       # За 10 минут
                    ],
                },
            }
            
            # Добавляем конференцию только для онлайн формата
            if create_conference:
                event['conferenceData'] = {
                    'createRequest': {
                        'requestId': f"meet-{start_time.strftime('%Y%m%d%H%M')}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                }
            
            # Создаем событие в календаре
            print(f"📅 Создаем событие: {title}")
            print(f"📅 Время начала: {start_time_str}")
            print(f"📅 Время окончания: {end_time_str}")
            print(f"📅 Формат: {'онлайн' if create_conference else 'офис'}")
            print(f"📅 Данные события: {event}")
            
            # Используем conferenceDataVersion только если создаем конференцию
            insert_params = {
                'calendarId': calendar_id,
                'body': event
            }
            if create_conference:
                insert_params['conferenceDataVersion'] = 1
            
            created_event = service.events().insert(**insert_params).execute()
            
            # Вычисляем длительность события
            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            print(f"✅ Событие создано: {title} ({start_time} - {end_time})")
            print(f"⏱️ Длительность: {duration_minutes} минут")
            print(f"🔗 Ссылка на событие: {created_event.get('htmlLink', '')}")
            
            return created_event
            
        except HttpError as e:
            print(f"❌ Ошибка создания события: {e}")
            print(f"❌ Детали ошибки: {e.error_details}")
            print(f"❌ Код ошибки: {e.resp.status}")
            return None
        except Exception as e:
            print(f"❌ Неожиданная ошибка создания события: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def delete_event(self, event_id, calendar_id='primary'):
        """
        Удаляет событие из Google Calendar
        
        Args:
            event_id: ID события для удаления
            calendar_id: ID календаря (по умолчанию 'primary')
            
        Returns:
            True если событие удалено успешно, False в случае ошибки
        """
        service = self._get_service()
        if not service:
            return False
        
        try:
            print(f"🗑️ Удаляем событие: {event_id}")
            
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            print(f"✅ Событие успешно удалено: {event_id}")
            return True
            
        except HttpError as e:
            if e.resp.status == 410:  # Событие уже удалено
                print(f"⚠️ Событие уже удалено: {event_id}")
                return True
            else:
                print(f"❌ Ошибка удаления события: {e}")
                print(f"❌ Детали ошибки: {e.error_details}")
                print(f"❌ Код ошибки: {e.resp.status}")
                return False
        except Exception as e:
            print(f"❌ Неожиданная ошибка удаления события: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def sync_events(self, oauth_account, days_ahead=100):
        """Синхронизировать события календаря (данные кэшируются, не сохраняются в БД)"""
        events = self.get_events(days_ahead=days_ahead)
        print(f"🔄 Синхронизация событий календаря: {len(events)} событий (кэшированы)")
        return len(events)


class GoogleDriveService:
    """Сервис для работы с Google Drive"""
    
    def __init__(self, oauth_service):
        self.oauth_service = oauth_service
        self.service = None
    
    def _get_service(self):
        """Получить сервис Google Drive"""
        if not self.service:
            credentials = self.oauth_service.get_credentials()
            if not credentials:
                return None
            
            self.service = build('drive', 'v3', credentials=credentials)
        
        return self.service
    
    def get_files(self, max_results=100):
        """Получить список файлов"""
        # Сначала проверяем кэш
        user_id = self.oauth_service.user.id
        cached_files = GoogleAPICache.get_drive_files(user_id, max_results)
        
        if cached_files is not None:
            print(f"📦 Получены файлы Drive из кэша: {len(cached_files)} файлов")
            return cached_files
        
        # Если в кэше нет, получаем из API
        service = self._get_service()
        if not service:
            return []
        
        try:
            results = service.files().list(
                pageSize=max_results,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, parents)"
            ).execute()
            
            files = results.get('files', [])
            
            # Сохраняем в кэш
            GoogleAPICache.set_drive_files(user_id, files, max_results)
            print(f"💾 Сохранены файлы Drive в кэш: {len(files)} файлов")
            
            return files
        except HttpError as e:
            print(f"Ошибка получения файлов: {e}")
            return []
    
    def sync_files(self, oauth_account):
        """Синхронизировать файлы Google Drive (данные кэшируются, не сохраняются в БД)"""
        files = self.get_files()
        print(f"🔄 Синхронизация файлов Drive: {len(files)} файлов (кэшированы)")
        return len(files)
    
    def create_folder_structure(self, folder_path):
        """Создает структуру папок по заданному пути"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Разбиваем путь на части
            path_parts = folder_path.split('/')
            current_parent_id = 'root'  # Начинаем с корневой папки
            
            for folder_name in path_parts:
                # Проверяем, существует ли папка с таким именем в текущей родительской папке
                existing_folders = service.files().list(
                    q=f"name='{folder_name}' and parents in '{current_parent_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id, name)"
                ).execute()
                
                if existing_folders.get('files'):
                    # Папка уже существует, используем её ID
                    current_parent_id = existing_folders['files'][0]['id']
                else:
                    # Создаем новую папку
                    folder_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent_id]
                    }
                    
                    folder = service.files().create(
                        body=folder_metadata,
                        fields='id'
                    ).execute()
                    
                    current_parent_id = folder.get('id')
            
            return current_parent_id
            
        except HttpError as e:
            print(f"Ошибка создания структуры папок: {e}")
            return None
    
    def copy_file(self, file_id, new_name, parent_folder_id=None):
        """Копирует файл с новым именем"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Подготавливаем метаданные для копии
            copy_metadata = {
                'name': new_name
            }
            
            if parent_folder_id:
                copy_metadata['parents'] = [parent_folder_id]
            
            # Копируем файл
            copied_file = service.files().copy(
                fileId=file_id,
                body=copy_metadata,
                fields='id'
            ).execute()
            
            return copied_file.get('id')
            
        except HttpError as e:
            print(f"Ошибка копирования файла: {e}")
            return None
    
    def file_exists(self, file_id):
        """Проверить существование файла"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            service.files().get(fileId=file_id, fields='id').execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:
                return False
            print(f"Ошибка проверки существования файла: {e}")
            return False
    
    def delete_file(self, file_id):
        """Удалить файл"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            service.files().delete(fileId=file_id).execute()
            return True
        except HttpError as e:
            print(f"Ошибка удаления файла: {e}")
            return False


class GoogleSheetsService:
    """Сервис для работы с Google Sheets"""
    
    def __init__(self, oauth_service):
        self.oauth_service = oauth_service
        self.service = None
    
    def _get_service(self):
        """Получить сервис Google Sheets"""
        if not self.service:
            credentials = self.oauth_service.get_credentials()
            if not credentials:
                return None
            
            self.service = build('sheets', 'v4', credentials=credentials)
        
        return self.service
    
    def get_spreadsheets(self, max_results=100):
        """Получить список таблиц"""
        # Сначала проверяем кэш
        user_id = self.oauth_service.user.id
        cached_sheets = GoogleAPICache.get_sheets(user_id, max_results)
        
        if cached_sheets is not None:
            print(f"📦 Получены таблицы из кэша: {len(cached_sheets)} таблиц")
            return cached_sheets
        
        # Если в кэше нет, получаем из API
        # Используем Drive API для получения таблиц
        drive_service = GoogleDriveService(self.oauth_service)
        files = drive_service.get_files(max_results)
        
        # Фильтруем только Google Sheets
        spreadsheets = [f for f in files if f['mimeType'] == 'application/vnd.google-apps.spreadsheet']
        
        # Сохраняем в кэш
        GoogleAPICache.set_sheets(user_id, spreadsheets, max_results)
        print(f"💾 Сохранены таблицы в кэш: {len(spreadsheets)} таблиц")
        
        return spreadsheets
    
    def sync_spreadsheets(self, oauth_account):
        """Синхронизировать Google Sheets (данные кэшируются, не сохраняются в БД)"""
        spreadsheets = self.get_spreadsheets()
        print(f"🔄 Синхронизация таблиц: {len(spreadsheets)} таблиц (кэшированы)")
        return len(spreadsheets)
    
    def get_sheets(self, spreadsheet_id):
        """Получить список листов в таблице"""
        service = self._get_service()
        if not service:
            return []
        
        try:
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return spreadsheet.get('sheets', [])
        except HttpError as e:
            print(f"Ошибка получения листов таблицы: {e}")
            return []
    
    def delete_sheet(self, spreadsheet_id, sheet_id):
        """Удалить лист из таблицы"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            # Создаем запрос на удаление листа
            request_body = {
                'requests': [{
                    'deleteSheet': {
                        'sheetId': sheet_id
                    }
                }]
            }
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request_body
            ).execute()
            
            return True
        except HttpError as e:
            print(f"Ошибка удаления листа: {e}")
            return False
    
    def get_spreadsheet_content(self, spreadsheet_id):
        """Получить содержимое таблицы"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Получаем все листы таблицы
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            content = {}
            for sheet in sheets:
                sheet_name = sheet['properties']['title']
                sheet_id = sheet['properties']['sheetId']
                
                # Получаем данные листа
                range_name = f"{sheet_name}!A1:Z1000"  # Достаточно большой диапазон
                result = service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name
                ).execute()
                
                values = result.get('values', [])
                content[sheet_name] = {
                    'sheet_id': sheet_id,
                    'values': values
                }
            
            return content
            
        except HttpError as e:
            print(f"Ошибка получения содержимого таблицы: {e}")
            return None
    
    def update_spreadsheet_content(self, target_spreadsheet_id, source_content):
        """Обновить содержимое таблицы новыми данными"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            # Получаем информацию о целевой таблице
            target_spreadsheet = service.spreadsheets().get(spreadsheetId=target_spreadsheet_id).execute()
            target_sheets = target_spreadsheet.get('sheets', [])
            
            requests = []
            
            # Обновляем каждый лист
            for sheet_name, sheet_data in source_content.items():
                # Ищем соответствующий лист в целевой таблице
                target_sheet = None
                for ts in target_sheets:
                    if ts['properties']['title'] == sheet_name:
                        target_sheet = ts
                        break
                
                if not target_sheet:
                    # Если листа нет, создаем его
                    requests.append({
                        'addSheet': {
                            'properties': {
                                'title': sheet_name
                            }
                        }
                    })
                
                # Очищаем лист и заполняем новыми данными
                if sheet_data['values']:
                    # Очистка листа
                    requests.append({
                        'updateCells': {
                            'range': {
                                'sheetId': target_sheet['properties']['sheetId'] if target_sheet else 0,
                                'startRowIndex': 0,
                                'endRowIndex': 1000,  # Большой диапазон для очистки
                                'startColumnIndex': 0,
                                'endColumnIndex': 26  # A-Z
                            },
                            'fields': 'userEnteredValue'
                        }
                    })
                    
                    # Заполнение данными
                    requests.append({
                        'pasteData': {
                            'coordinate': {
                                'sheetId': target_sheet['properties']['sheetId'] if target_sheet else 0,
                                'rowIndex': 0,
                                'columnIndex': 0
                            },
                            'data': self._values_to_csv(sheet_data['values']),
                            'type': 'PASTE_NORMAL',
                            'delimiter': ','
                        }
                    })
            
            # Выполняем все запросы
            if requests:
                batch_update_body = {'requests': requests}
                service.spreadsheets().batchUpdate(
                    spreadsheetId=target_spreadsheet_id,
                    body=batch_update_body
                ).execute()
            
            return True
            
        except HttpError as e:
            print(f"Ошибка обновления содержимого таблицы: {e}")
            return False
    
    def _values_to_csv(self, values):
        """Конвертирует массив значений в CSV строку"""
        csv_rows = []
        for row in values:
            # Экранируем значения и объединяем запятыми
            escaped_row = []
            for cell in row:
                if ',' in str(cell) or '"' in str(cell):
                    escaped_row.append('"{}"'.format(str(cell).replace('"', '""')))
                else:
                    escaped_row.append(str(cell))
            csv_rows.append(','.join(escaped_row))
        
        return '\n'.join(csv_rows)
    
    def file_exists(self, file_id):
        """Проверить существование файла"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            service.files().get(fileId=file_id, fields='id').execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:
                return False
            print(f"Ошибка проверки существования файла: {e}")
            return False
    
    def find_and_replace_cells(self, spreadsheet_id, search_text, replace_text, sheet_name=None):
        """Найти и заменить текст во всех ячейках таблицы"""
        service = self._get_service()
        if not service:
            print(f"❌ SCORECARD: Сервис не доступен")
            return False
        
        try:
            print(f"🔍 SCORECARD: Ищем '{search_text}' для замены на '{replace_text[:50] if len(replace_text) > 50 else replace_text}...'")
            
            # Получаем все листы
            sheets = self.get_sheets(spreadsheet_id)
            if not sheets:
                print(f"❌ SCORECARD: Не удалось получить список листов")
                return False
            
            print(f"📋 SCORECARD: Найдено листов: {len(sheets)}")
            
            requests = []
            
            for sheet in sheets:
                sheet_title = sheet.get('properties', {}).get('title', 'Unknown')
                sheet_id = sheet.get('properties', {}).get('sheetId')
                
                # Если указан конкретный лист, обрабатываем только его
                if sheet_name and sheet_title != sheet_name:
                    print(f"⏭️ SCORECARD: Пропускаем лист '{sheet_title}' (требуется '{sheet_name}')")
                    continue
                
                print(f"📄 SCORECARD: Обрабатываем лист '{sheet_title}' (ID: {sheet_id}) для замены '{search_text}'")
                
                # Создаем запрос на поиск и замену для каждого листа
                requests.append({
                    'findReplace': {
                        'find': search_text,
                        'replacement': replace_text,
                        'sheetId': sheet_id,
                        'matchCase': False,
                        'matchEntireCell': False,
                        'searchByRegex': False,
                        'includeFormulas': True
                    }
                })
            
            if requests:
                print(f"🔄 SCORECARD: Отправляем {len(requests)} запросов на замену")
                body = {'requests': requests}
                response = service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()
                
                # Проверяем результаты
                replies = response.get('replies', [])
                occurrences_changed = sum(reply.get('findReplace', {}).get('occurrencesChanged', 0) for reply in replies)
                
                print(f"✅ SCORECARD: Заменено '{search_text}' на '{replace_text[:50] if len(replace_text) > 50 else replace_text}...' в {occurrences_changed} местах на {len(requests)} листах")
                
                if occurrences_changed == 0:
                    print(f"⚠️ SCORECARD: Плейсхолдер '{search_text}' не найден в таблице")
                
                return occurrences_changed > 0
            
            print(f"⚠️ SCORECARD: Нет листов для обработки")
            return False
            
        except HttpError as e:
            error_details = f"HTTP {e.resp.status}: {e.content.decode('utf-8') if hasattr(e, 'content') else str(e)}"
            print(f"❌ SCORECARD: Ошибка поиска и замены в ячейках: {error_details}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"❌ SCORECARD: Неожиданная ошибка при замене: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_cell_value(self, spreadsheet_id, sheet_name, cell_range, value):
        """Обновить значение конкретной ячейки"""
        service = self._get_service()
        if not service:
            return False
        
        try:
            range_name = f"{sheet_name}!{cell_range}"
            body = {
                'values': [[value]]
            }
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            return True
        except HttpError as e:
            print(f"❌ SCORECARD: Ошибка обновления ячейки: {e}")
            return False