"""Сервисы для OAuth интеграций"""
import os
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.google_oauth.models import GoogleOAuthAccount
from apps.google_oauth.cache_service import GoogleAPICache
from logic.base.api_client import BaseAPIClient


class GoogleOAuthService(BaseAPIClient):
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
        # Инициализируем базовый класс с пустыми параметрами для Google OAuth
        super().__init__("", "")
        self.user = user
        self.credentials = None
    
    def _setup_auth(self):
        """Настройка аутентификации для Google OAuth"""
        # Для Google OAuth аутентификация происходит через Google API клиенты
        # Дополнительные заголовки не нужны
        pass
    
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
        
        return flow
    
    def get_authorization_url(self):
        """Получить (auth_url, state) для авторизации. Вызываем oauth2session напрямую, чтобы избежать
        'too many values to unpack' в flow.authorization_url() (requests_oauthlib может возвращать 3+ значения)."""
        try:
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
            auth_url = result[0] if result else None
            state = result[1] if len(result) > 1 else None
            return auth_url, state
        except Exception as e:
            print(f"Ошибка создания URL авторизации: {e}")
            raise
    
    def handle_oauth_callback(self, request):
        """Обработка callback от Google OAuth"""
        try:
            flow = self.create_oauth_flow()
            
            # Получаем код авторизации из URL
            authorization_response = request.build_absolute_uri()
            flow.fetch_token(authorization_response=authorization_response)
            
            # Получаем информацию о пользователе
            credentials = flow.credentials
            
            # Получаем профиль пользователя
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            # Создаем или обновляем OAuth аккаунт
            oauth_account, created = GoogleOAuthAccount.objects.update_or_create(
                user=self.user,
                defaults={
                    'google_id': user_info.get('id'),
                    'email': user_info.get('email'),
                    'name': user_info.get('name'),
                    'picture_url': user_info.get('picture'),
                    'access_token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_expires_at': timezone.now() + timedelta(seconds=credentials.expiry - timezone.now().timestamp()) if credentials.expiry else timezone.now() + timedelta(hours=1),
                    'scopes': self.SCOPES,
                    'last_sync_at': timezone.now(),
                }
            )
            
            if created:
                message = 'Google аккаунт успешно подключен'
            else:
                message = 'Google аккаунт успешно обновлен'
            
            return {
                'success': True,
                'message': message,
                'oauth_account': oauth_account
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка обработки OAuth callback: {str(e)}'
            }
    
    def get_credentials(self):
        """Получить действительные credentials"""
        oauth_account = self.get_oauth_account()
        if not oauth_account:
            return None
        
        # Проверяем, нужно ли обновить токен
        if oauth_account.needs_refresh() and oauth_account.refresh_token:
            try:
                self._refresh_token(oauth_account)
                print(f"✅ Токен автоматически обновлен для пользователя: {self.user.username}")
            except Exception as e:
                print(f"❌ Ошибка при автоматическом обновлении токена для {self.user.username}: {e}")
                # Продолжаем с текущим токеном, возможно он еще валиден
        
        # Создаем credentials
        credentials = Credentials(
            token=oauth_account.access_token,
            refresh_token=oauth_account.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=oauth_account.scopes
        )
        
        return credentials
    
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
        oauth_account.token_expires_at = timezone.now() + timedelta(hours=1)
        oauth_account.save()
    
    def revoke_access(self):
        """Отозвать доступ к Google аккаунту"""
        try:
            oauth_account = self.get_oauth_account()
            if not oauth_account:
                return True
            
            credentials = self.get_credentials()
            if credentials:
                # Отзываем токен через Google API
                credentials.revoke(Request())
            
            # Удаляем аккаунт из базы данных
            oauth_account.delete()
            
            return True
            
        except Exception as e:
            print(f"Ошибка отзыва доступа: {e}")
            # Все равно удаляем локально
            oauth_account = self.get_oauth_account()
            if oauth_account:
                oauth_account.delete()
            return True
    
    def test_connection(self):
        """Тестирование подключения к Google API"""
        from logic.base.api_client import APIResponse
        
        try:
            credentials = self.get_credentials()
            if not credentials:
                return APIResponse(
                    success=False,
                    data={"error": "Нет действительных credentials"}
                )
            
            # Тестируем подключение к UserInfo API
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            if user_info:
                return APIResponse(
                    success=True,
                    data={"message": "Подключение к Google API успешно", "user_info": user_info}
                )
            else:
                return APIResponse(
                    success=False,
                    data={"error": "Не удалось получить информацию о пользователе"}
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                data={"error": f"Ошибка подключения к Google API: {str(e)}"}
            )


class GoogleCalendarService(BaseAPIClient):
    """Сервис для работы с Google Calendar API"""
    
    def __init__(self, oauth_account):
        super().__init__("", "")
        self.oauth_account = oauth_account
        self.service = None
        self.cache = GoogleAPICache()
    
    def _setup_auth(self):
        """Настройка аутентификации для Google Calendar API"""
        # Для Google Calendar API аутентификация происходит через Google API клиенты
        # Дополнительные заголовки не нужны
        pass
    
    def test_connection(self):
        """Тестирование подключения к Google Calendar API"""
        from logic.base.api_client import APIResponse
        
        try:
            service = self._get_service()
            calendar_list = service.calendarList().list().execute()
            
            return APIResponse(
                success=True,
                data={"message": "Подключение к Google Calendar API успешно", "calendars_count": len(calendar_list.get('items', []))}
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                data={"error": f"Ошибка подключения к Google Calendar API: {str(e)}"}
            )
    
    def _get_service(self):
        """Получить сервис Google Calendar"""
        if self.service:
            return self.service
        
        from logic.integration.oauth.oauth_services import GoogleOAuthService
        oauth_service = GoogleOAuthService(self.oauth_account.user)
        credentials = oauth_service.get_credentials()
        
        if not credentials:
            raise Exception("Нет действительных credentials")
        
        self.service = build('calendar', 'v3', credentials=credentials)
        return self.service
    
    def get_events_count(self):
        """Получить количество событий в календаре"""
        try:
            cache_key = f"calendar_events_count_{self.oauth_account.id}"
            cached_count = self.cache.get(cache_key)
            
            if cached_count is not None:
                return cached_count
            
            service = self._get_service()
            
            # Получаем список календарей
            calendar_list = service.calendarList().list().execute()
            
            total_events = 0
            for calendar in calendar_list.get('items', []):
                calendar_id = calendar['id']
                
                # Получаем события за последние 30 дней
                now = timezone.now()
                time_min = (now - timedelta(days=30)).isoformat() + 'Z'
                time_max = (now + timedelta(days=30)).isoformat() + 'Z'
                
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                total_events += len(events)
            
            # Кэшируем результат на 5 минут
            self.cache.set(cache_key, total_events, 300)
            
            return total_events
            
        except Exception as e:
            print(f"Ошибка получения количества событий: {e}")
            return 0
    
    def get_events(self, days_ahead=30, calendar_id='primary'):
        """Получить события календаря. calendar_id: 'primary' или ID календаря."""
        try:
            service = self._get_service()
            all_events = []
            now = timezone.now()
            from datetime import datetime
            time_min = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            time_max = (now + timedelta(days=days_ahead)).strftime('%Y-%m-%dT%H:%M:%SZ')
            try:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max
                ).execute()
                events = events_result.get('items', [])
                for event in events:
                    event['calendar_name'] = 'Основной календарь' if calendar_id == 'primary' else str(calendar_id)
                    event['calendar_id'] = calendar_id
                    all_events.append(event)
            except Exception as e:
                print(f"Ошибка получения событий из календаря {calendar_id}: {e}")
            
            # Сортируем события по времени начала
            all_events.sort(key=lambda x: x.get('start', {}).get('dateTime', x.get('start', {}).get('date', '')))
            
            return all_events
            
        except Exception as e:
            print(f"Ошибка получения событий календаря: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def sync_events(self):
        """Синхронизация событий календаря"""
        try:
            service = self._get_service()
            
            # Получаем список календарей
            calendar_list = service.calendarList().list().execute()
            
            synced_events = 0
            for calendar in calendar_list.get('items', []):
                calendar_id = calendar['id']
                calendar_name = calendar.get('summary', 'Unnamed Calendar')
                
                # Получаем события за последние 30 дней
                now = timezone.now()
                time_min = (now - timedelta(days=30)).isoformat() + 'Z'
                time_max = (now + timedelta(days=30)).isoformat() + 'Z'
                
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                
                # Кэшируем события
                for event in events:
                    cache_key = f"calendar_event_{self.oauth_account.id}_{event['id']}"
                    self.cache.set(cache_key, event, 3600)  # Кэшируем на час
                
                synced_events += len(events)
            
            return {
                'success': True,
                'synced_events': synced_events,
                'message': f'Синхронизировано {synced_events} событий'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка синхронизации событий: {str(e)}'
            }


class GoogleDriveService(BaseAPIClient):
    """Сервис для работы с Google Drive API"""
    
    def __init__(self, oauth_account):
        super().__init__("", "")
        self.oauth_account = oauth_account
        self.service = None
        self.cache = GoogleAPICache()
    
    def _setup_auth(self):
        """Настройка аутентификации для Google Drive API"""
        # Для Google Drive API аутентификация происходит через Google API клиенты
        # Дополнительные заголовки не нужны
        pass
    
    def test_connection(self):
        """Тестирование подключения к Google Drive API"""
        from logic.base.api_client import APIResponse
        
        try:
            service = self._get_service()
            results = service.files().list(pageSize=1).execute()
            
            return APIResponse(
                success=True,
                data={"message": "Подключение к Google Drive API успешно", "files_count": results.get('files', [])}
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                data={"error": f"Ошибка подключения к Google Drive API: {str(e)}"}
            )
    
    def _get_service(self):
        """Получить сервис Google Drive"""
        if self.service:
            return self.service
        
        from logic.integration.oauth.oauth_services import GoogleOAuthService
        oauth_service = GoogleOAuthService(self.oauth_account.user)
        credentials = oauth_service.get_credentials()
        
        if not credentials:
            raise Exception("Нет действительных credentials")
        
        self.service = build('drive', 'v3', credentials=credentials)
        return self.service
    
    def get_files_count(self):
        """Получить количество файлов в Drive"""
        try:
            cache_key = f"drive_files_count_{self.oauth_account.id}"
            cached_count = self.cache.get(cache_key)
            
            if cached_count is not None:
                return cached_count
            
            service = self._get_service()
            
            # Получаем список файлов
            results = service.files().list(
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, createdTime)"
            ).execute()
            
            files = results.get('files', [])
            total_files = len(files)
            
            # Кэшируем результат на 10 минут
            self.cache.set(cache_key, total_files, 600)
            
            return total_files
            
        except Exception as e:
            print(f"Ошибка получения количества файлов: {e}")
            return 0
    
    def get_files(self, max_results=100):
        """Получить список файлов Drive (для дашборда и отображения)."""
        try:
            service = self._get_service()
            results = service.files().list(
                pageSize=max_results,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, shared, sharedWithMe)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"Ошибка получения файлов Drive: {e}")
            return []

    def sync_files(self):
        """Синхронизация файлов Drive"""
        try:
            service = self._get_service()
            
            # Получаем список файлов
            results = service.files().list(
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, createdTime, size)"
            ).execute()
            
            files = results.get('files', [])
            
            # Кэшируем файлы
            synced_files = 0
            for file in files:
                cache_key = f"drive_file_{self.oauth_account.id}_{file['id']}"
                self.cache.set(cache_key, file, 1800)  # Кэшируем на 30 минут
                synced_files += 1
            
            return {
                'success': True,
                'synced_files': synced_files,
                'message': f'Синхронизировано {synced_files} файлов'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка синхронизации файлов: {str(e)}'
            }


class GoogleSheetsService(BaseAPIClient):
    """Сервис для работы с Google Sheets API"""
    
    def __init__(self, oauth_account):
        super().__init__("", "")
        self.oauth_account = oauth_account
        self.service = None
        self.cache = GoogleAPICache()
    
    def _setup_auth(self):
        """Настройка аутентификации для Google Sheets API"""
        # Для Google Sheets API аутентификация происходит через Google API клиенты
        # Дополнительные заголовки не нужны
        pass
    
    def test_connection(self):
        """Тестирование подключения к Google Sheets API"""
        from logic.base.api_client import APIResponse
        
        try:
            service = self._get_service()
            # Тестируем подключение через простой запрос
            return APIResponse(
                success=True,
                data={"message": "Подключение к Google Sheets API успешно"}
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                data={"error": f"Ошибка подключения к Google Sheets API: {str(e)}"}
            )
    
    def _get_service(self):
        """Получить сервис Google Sheets"""
        if self.service:
            return self.service
        
        from logic.integration.oauth.oauth_services import GoogleOAuthService
        oauth_service = GoogleOAuthService(self.oauth_account.user)
        credentials = oauth_service.get_credentials()
        
        if not credentials:
            raise Exception("Нет действительных credentials")
        
        self.service = build('sheets', 'v4', credentials=credentials)
        return self.service
    
    def get_sheets_count(self):
        """Получить количество таблиц"""
        try:
            cache_key = f"sheets_count_{self.oauth_account.id}"
            cached_count = self.cache.get(cache_key)
            
            if cached_count is not None:
                return cached_count
            
            # Используем Drive API для поиска Google Sheets
            from logic.integration.oauth.oauth_services import GoogleDriveService
            drive_service = GoogleDriveService(self.oauth_account)
            drive_service_obj = drive_service._get_service()
            
            # Ищем файлы с MIME типом Google Sheets
            results = drive_service_obj.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                pageSize=1000,
                fields="files(id, name, createdTime)"
            ).execute()
            
            sheets = results.get('files', [])
            total_sheets = len(sheets)
            
            # Кэшируем результат на 15 минут
            self.cache.set(cache_key, total_sheets, 900)
            
            return total_sheets
            
        except Exception as e:
            print(f"Ошибка получения количества таблиц: {e}")
            return 0
    
    def get_spreadsheets(self, max_results=50):
        """Список таблиц Google Sheets (для отображения в интерфейсе)."""
        try:
            from logic.integration.oauth.oauth_services import GoogleDriveService
            drive_service = GoogleDriveService(self.oauth_account)
            service = drive_service._get_service()
            results = service.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                pageSize=max_results,
                fields="files(id, name, mimeType, createdTime, modifiedTime)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"Ошибка получения списка таблиц: {e}")
            return []

    def sync_sheets(self):
        """Синхронизация таблиц"""
        try:
            # Используем Drive API для поиска Google Sheets
            from logic.integration.oauth.oauth_services import GoogleDriveService
            drive_service = GoogleDriveService(self.oauth_account)
            drive_service_obj = drive_service._get_service()
            
            # Ищем файлы с MIME типом Google Sheets
            results = drive_service_obj.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                pageSize=1000,
                fields="files(id, name, createdTime)"
            ).execute()
            
            sheets = results.get('files', [])
            
            # Кэшируем информацию о таблицах
            synced_sheets = 0
            for sheet in sheets:
                cache_key = f"sheet_info_{self.oauth_account.id}_{sheet['id']}"
                self.cache.set(cache_key, sheet, 1800)  # Кэшируем на 30 минут
                synced_sheets += 1
            
            return {
                'success': True,
                'synced_sheets': synced_sheets,
                'message': f'Синхронизировано {synced_sheets} таблиц'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка синхронизации таблиц: {str(e)}'
            }
