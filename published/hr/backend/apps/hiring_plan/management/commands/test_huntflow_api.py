from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.hiring_plan.huntflow_services.huntflow_sync_service import HuntflowSyncService


class Command(BaseCommand):
    help = 'Тестирование подключения к HuntFlow API'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Имя пользователя для тестирования (по умолчанию первый найденный)'
        )
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Находим пользователя
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Пользователь {options["username"]} не найден'))
                return
        else:
            user = User.objects.filter(huntflow_access_token__isnull=False).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Не найден пользователь с токенами HuntFlow'))
            return
        
        self.stdout.write(f'Тестируем API для пользователя: {user.username}')
        self.stdout.write(f'Активная система: {user.active_system}')
        
        # Проверяем настройки пользователя
        if user.active_system == 'prod':
            url = user.huntflow_prod_url
        else:
            url = user.huntflow_sandbox_url
        
        self.stdout.write(f'URL: {url}')
        self.stdout.write(f'Access token: {"Настроен" if user.huntflow_access_token else "Не настроен"}')
        self.stdout.write(f'Refresh token: {"Настроен" if user.huntflow_refresh_token else "Не настроен"}')
        self.stdout.write(f'Token valid: {user.is_huntflow_token_valid}')
        self.stdout.write(f'Refresh valid: {user.is_huntflow_refresh_valid}')
        
        # Тестируем API
        try:
            sync_service = HuntflowSyncService(user)
            
            self.stdout.write('\n--- Тестирование API ---')
            
            # Тестируем получение вакансий
            self.stdout.write('Получаем список вакансий...')
            vacancies_data = sync_service._make_request('vacancies')
            
            if vacancies_data:
                self.stdout.write(self.style.SUCCESS('✅ API работает!'))
                self.stdout.write(f'Получено вакансий: {len(vacancies_data.get("items", []))}')
                
                # Показываем первые 3 вакансии
                for i, vacancy in enumerate(vacancies_data.get('items', [])[:3]):
                    self.stdout.write(f'  {i+1}. ID: {vacancy.get("id")}, Название: {vacancy.get("position", "Unknown")}')
            else:
                self.stdout.write(self.style.ERROR('❌ API не вернул данные'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при тестировании API: {e}'))

from apps.hiring_plan.huntflow_services.huntflow_sync_service import HuntflowSyncService


class Command(BaseCommand):
    help = 'Тестирование подключения к HuntFlow API'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Имя пользователя для тестирования (по умолчанию первый найденный)'
        )
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Находим пользователя
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Пользователь {options["username"]} не найден'))
                return
        else:
            user = User.objects.filter(huntflow_access_token__isnull=False).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Не найден пользователь с токенами HuntFlow'))
            return
        
        self.stdout.write(f'Тестируем API для пользователя: {user.username}')
        self.stdout.write(f'Активная система: {user.active_system}')
        
        # Проверяем настройки пользователя
        if user.active_system == 'prod':
            url = user.huntflow_prod_url
        else:
            url = user.huntflow_sandbox_url
        
        self.stdout.write(f'URL: {url}')
        self.stdout.write(f'Access token: {"Настроен" if user.huntflow_access_token else "Не настроен"}')
        self.stdout.write(f'Refresh token: {"Настроен" if user.huntflow_refresh_token else "Не настроен"}')
        self.stdout.write(f'Token valid: {user.is_huntflow_token_valid}')
        self.stdout.write(f'Refresh valid: {user.is_huntflow_refresh_valid}')
        
        # Тестируем API
        try:
            sync_service = HuntflowSyncService(user)
            
            self.stdout.write('\n--- Тестирование API ---')
            
            # Тестируем получение вакансий
            self.stdout.write('Получаем список вакансий...')
            vacancies_data = sync_service._make_request('vacancies')
            
            if vacancies_data:
                self.stdout.write(self.style.SUCCESS('✅ API работает!'))
                self.stdout.write(f'Получено вакансий: {len(vacancies_data.get("items", []))}')
                
                # Показываем первые 3 вакансии
                for i, vacancy in enumerate(vacancies_data.get('items', [])[:3]):
                    self.stdout.write(f'  {i+1}. ID: {vacancy.get("id")}, Название: {vacancy.get("position", "Unknown")}')
            else:
                self.stdout.write(self.style.ERROR('❌ API не вернул данные'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при тестировании API: {e}'))
