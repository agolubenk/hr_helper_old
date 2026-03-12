from django.core.management.base import BaseCommand
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Миграция с API ключей на токенную систему'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        users_with_api_keys = User.objects.filter(
            huntflow_prod_api_key__isnull=False
        ).exclude(huntflow_prod_api_key='')
        
        self.stdout.write(f"Найдено пользователей с API ключами: {users_with_api_keys.count()}")
        
        for user in users_with_api_keys:
            self.stdout.write(f"\nПользователь: {user.username}")
            self.stdout.write(f"Текущий API ключ: {user.huntflow_prod_api_key[:20]}...")
            
            if user.huntflow_access_token:
                self.stdout.write("  ✅ Уже использует токенную систему")
                continue
            
            if dry_run:
                self.stdout.write("  [DRY RUN] Требуется ручная настройка токенов")
            else:
                self.stdout.write("  ⚠️  Требуется ручная настройка токенов в интерфейсе Huntflow")
                self.stdout.write("     1. Перейдите в Настройки → API → Добавить токен")
                self.stdout.write("     2. Получите access_token и refresh_token")
                self.stdout.write("     3. Обновите профиль пользователя")
        
        if not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nВНИМАНИЕ: Автоматическая миграция API ключей невозможна. "
                    "Каждый пользователь должен получить новые токены через интерфейс Huntflow."
                )
            )
