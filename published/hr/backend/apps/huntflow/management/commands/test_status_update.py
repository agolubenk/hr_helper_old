from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.huntflow.services import HuntflowService


class Command(BaseCommand):
    help = 'Тестирует обновление статуса кандидата через правильный эндпоинт'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Получаем пользователя admin
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Пользователь admin не найден'))
            return
        
        self.stdout.write(self.style.SUCCESS('=== ТЕСТИРОВАНИЕ ОБНОВЛЕНИЯ СТАТУСА ===\n'))
        
        # Создаем сервис
        huntflow_service = HuntflowService(user)
        
        # Получаем аккаунты
        accounts = huntflow_service.get_accounts()
        if not accounts or 'items' not in accounts:
            self.stdout.write(self.style.ERROR('❌ Не удалось получить аккаунты'))
            return
        
        account_id = accounts['items'][0]['id']
        self.stdout.write(f'📋 Используем аккаунт: {account_id}')
        
        # Получаем кандидатов
        applicants = huntflow_service.get_applicants(account_id, count=1)
        if not applicants or 'items' not in applicants or not applicants['items']:
            self.stdout.write(self.style.ERROR('❌ Не удалось получить кандидатов'))
            return
        
        applicant_id = applicants['items'][0]['id']
        self.stdout.write(f'👤 Используем кандидата: {applicant_id}')
        
        # Получаем статусы
        statuses = huntflow_service.get_vacancy_statuses(account_id)
        if not statuses or 'items' not in statuses:
            self.stdout.write(self.style.ERROR('❌ Не удалось получить статусы'))
            return
        
        # Находим статус "Новые" (обычно ID 3321)
        new_status = None
        for status in statuses['items']:
            if status.get('name') == 'Новые':
                new_status = status
                break
        
        if not new_status:
            new_status = statuses['items'][0]  # Берем первый доступный
        
        status_id = new_status['id']
        self.stdout.write(f'📊 Используем статус: {new_status["name"]} (ID: {status_id})')
        
        # Получаем информацию о кандидате для получения текущей вакансии
        applicant_data = huntflow_service.get_applicant(account_id, applicant_id)
        if not applicant_data or not applicant_data.get('links'):
            self.stdout.write(self.style.ERROR('❌ У кандидата нет привязанной вакансии'))
            return
        
        current_vacancy = applicant_data['links'][0]['vacancy']
        self.stdout.write(f'💼 Текущая вакансия: {current_vacancy}')
        
        # Тестируем обновление статуса
        self.stdout.write(f'\n🔄 Тестируем обновление статуса...')
        test_comment = f'Тестовый комментарий от Django - {self.get_timestamp()}'
        
        result = huntflow_service.update_applicant_status(
            account_id, 
            applicant_id, 
            status_id, 
            test_comment
        )
        
        if result:
            self.stdout.write(self.style.SUCCESS('✅ Статус успешно обновлен!'))
            self.stdout.write(f'📝 Комментарий: {test_comment}')
        else:
            self.stdout.write(self.style.ERROR('❌ Не удалось обновить статус'))
        
        # Ждем немного и проверяем логи
        import time
        time.sleep(2)
        
        # Получаем логи кандидата
        self.stdout.write(f'\n📋 Проверяем логи кандидата...')
        logs = huntflow_service.get_applicant_logs(account_id, applicant_id)
        if logs and 'items' in logs:
            recent_logs = logs['items'][:3]  # Последние 3 лога
            for log in recent_logs:
                log_type = log.get('type', 'UNKNOWN')
                comment = log.get('comment', '')
                created = log.get('created', '')
                self.stdout.write(f'  - {log_type}: {comment} ({created})')
        
        self.stdout.write(self.style.SUCCESS('\n=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ==='))
        self.stdout.write('\nПроверьте логи в админке Django:')
        self.stdout.write('http://127.0.0.1:8000/admin/huntflow/huntflowlog/')
    
    def get_timestamp(self):
        """Возвращает текущее время в формате строки"""
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S')
