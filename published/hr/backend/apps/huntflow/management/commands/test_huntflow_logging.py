from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.huntflow.services import HuntflowService


class Command(BaseCommand):
    help = 'Тестирует Huntflow API и логирует все запросы'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Получаем пользователя admin
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Пользователь admin не найден'))
            return
        
        self.stdout.write(self.style.SUCCESS('=== ТЕСТИРОВАНИЕ HUNTFLOW API С ЛОГИРОВАНИЕМ ===\n'))
        
        # Создаем сервис
        huntflow_service = HuntflowService(user)
        
        # Тестируем подключение
        self.stdout.write('🔍 Тестируем подключение к Huntflow API...')
        if huntflow_service.test_connection():
            self.stdout.write(self.style.SUCCESS('✅ Подключение успешно!'))
        else:
            self.stdout.write(self.style.ERROR('❌ Подключение не удалось'))
            return
        
        # Получаем аккаунты
        self.stdout.write('\n📋 Получаем список аккаунтов...')
        accounts = huntflow_service.get_accounts()
        if accounts and 'items' in accounts:
            self.stdout.write(f'✅ Найдено {len(accounts["items"])} аккаунтов')
            for account in accounts['items']:
                self.stdout.write(f'  - ID: {account.get("id")}, Name: {account.get("name")}')
        else:
            self.stdout.write('❌ Не удалось получить аккаунты')
            return
        
        # Получаем вакансии для первого аккаунта
        if accounts and 'items' in accounts:
            account_id = accounts['items'][0]['id']
            self.stdout.write(f'\n💼 Получаем вакансии для аккаунта {account_id}...')
            vacancies = huntflow_service.get_vacancies(account_id, count=5)
            if vacancies and 'items' in vacancies:
                self.stdout.write(f'✅ Найдено {len(vacancies["items"])} вакансий')
                for vacancy in vacancies['items']:
                    self.stdout.write(f'  - ID: {vacancy.get("id")}, Position: {vacancy.get("position")}')
            else:
                self.stdout.write('❌ Не удалось получить вакансии')
        
        # Получаем статусы
        if accounts and 'items' in accounts:
            self.stdout.write(f'\n📊 Получаем статусы для аккаунта {account_id}...')
            statuses = huntflow_service.get_vacancy_statuses(account_id)
            if statuses and 'items' in statuses:
                self.stdout.write(f'✅ Найдено {len(statuses["items"])} статусов')
                for status in statuses['items']:
                    self.stdout.write(f'  - ID: {status.get("id")}, Name: {status.get("name")}')
            else:
                self.stdout.write('❌ Не удалось получить статусы')
        
        # Получаем метки
        if accounts and 'items' in accounts:
            self.stdout.write(f'\n🏷️ Получаем метки для аккаунта {account_id}...')
            tags = huntflow_service.get_tags(account_id)
            if tags and 'items' in tags:
                self.stdout.write(f'✅ Найдено {len(tags["items"])} меток')
                for tag in tags['items']:
                    self.stdout.write(f'  - ID: {tag.get("id")}, Name: {tag.get("name")}, Color: {tag.get("color")}')
            else:
                self.stdout.write('❌ Не удалось получить метки')
        
        self.stdout.write(self.style.SUCCESS('\n=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ==='))
        self.stdout.write('\nТеперь проверьте логи в админке Django:')
        self.stdout.write('http://127.0.0.1:8000/admin/huntflow/huntflowlog/')
