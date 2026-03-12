from django.core.management.base import BaseCommand
from apps.accounts.models import User
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Проверяет состояние токенов Huntflow'
    
    def handle(self, *args, **options):
        users = User.objects.exclude(huntflow_access_token='')
        
        expiring_soon = []
        expired = []
        
        for user in users:
            if user.huntflow_token_expires_at:
                if user.huntflow_token_expires_at < timezone.now():
                    expired.append(user)
                elif user.huntflow_token_expires_at < timezone.now() + timedelta(days=1):
                    expiring_soon.append(user)
        
        if expired:
            self.stdout.write(
                self.style.ERROR(f"Пользователи с истекшими токенами: {len(expired)}")
            )
            for user in expired:
                self.stdout.write(f"  - {user.username}")
        
        if expiring_soon:
            self.stdout.write(
                self.style.WARNING(f"Токены истекают в ближайшие 24 часа: {len(expiring_soon)}")
            )
            for user in expiring_soon:
                self.stdout.write(f"  - {user.username}")
        
        if not expired and not expiring_soon:
            self.stdout.write(self.style.SUCCESS("Все токены в порядке"))
