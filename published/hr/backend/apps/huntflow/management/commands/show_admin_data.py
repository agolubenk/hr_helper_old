from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.finance.models import Grade, CurrencyRate
from apps.huntflow.models import HuntflowCache, HuntflowLog
from django.contrib.admin.models import LogEntry


class Command(BaseCommand):
    help = 'Показывает все данные, доступные в админке Django'

    def handle(self, *args, **options):
        User = get_user_model()
        
        self.stdout.write(self.style.SUCCESS('=== ДАННЫЕ В АДМИНКЕ DJANGO ===\n'))
        
        # Пользователи
        self.stdout.write(self.style.WARNING('👥 ПОЛЬЗОВАТЕЛИ:'))
        users = User.objects.all()
        for user in users:
            self.stdout.write(f'  ID: {user.id}, Username: {user.username}, Full name: {user.full_name}')
            self.stdout.write(f'    - Huntflow prod URL: {user.huntflow_prod_url or "Не указан"}')
            self.stdout.write(f'    - Huntflow sandbox URL: {user.huntflow_sandbox_url or "Не указан"}')
            self.stdout.write(f'    - Active system: {user.active_system}')
            self.stdout.write(f'    - Groups: {", ".join([g.name for g in user.groups.all()])}')
            self.stdout.write()
        
        # Грейды
        self.stdout.write(self.style.WARNING('📊 ГРЕЙДЫ:'))
        grades = Grade.objects.all()
        for grade in grades:
            self.stdout.write(f'  ID: {grade.id}, Name: {grade.name}')
        self.stdout.write()
        
        # Курсы валют
        self.stdout.write(self.style.WARNING('💰 КУРСЫ ВАЛЮТ:'))
        rates = CurrencyRate.objects.all()
        for rate in rates:
            self.stdout.write(f'  ID: {rate.id}, Currency: {rate.code}, Rate: {rate.rate}, Date: {rate.fetched_at}')
        self.stdout.write()
        
        # Кэш Huntflow
        self.stdout.write(self.style.WARNING('🗄️ КЭШ HUNTFLOW:'))
        cache_items = HuntflowCache.objects.all()
        if cache_items:
            for item in cache_items:
                self.stdout.write(f'  ID: {item.id}, Key: {item.cache_key}, Age: {item.age_minutes} мин, Status: {"Истек" if item.is_expired else "Активен"}')
        else:
            self.stdout.write('  Кэш пуст')
        self.stdout.write()
        
        # Логи Huntflow
        self.stdout.write(self.style.WARNING('📝 ЛОГИ HUNTFLOW:'))
        logs = HuntflowLog.objects.all()
        if logs:
            for log in logs:
                status = "✅" if log.is_success else "❌" if log.is_error else "⚠️"
                self.stdout.write(f'  ID: {log.id}, {status} {log.method} {log.endpoint}, Status: {log.status_code}, Time: {log.created_at}')
        else:
            self.stdout.write('  Логи пусты')
        self.stdout.write()
        
        # Логи админки Django
        self.stdout.write(self.style.WARNING('🔧 ЛОГИ АДМИНКИ DJANGO:'))
        admin_logs = LogEntry.objects.all().order_by('-action_time')[:10]  # Последние 10
        for log in admin_logs:
            self.stdout.write(f'  ID: {log.id}, User: {log.user.username}, Action: {log.get_action_flag_display()}, Object: {log.object_repr}, Time: {log.action_time}')
        self.stdout.write()
        
        self.stdout.write(self.style.SUCCESS('=== КОНЕЦ ДАННЫХ ==='))
        self.stdout.write()
        self.stdout.write('Для просмотра в веб-интерфейсе перейдите в админку Django:')
        self.stdout.write('http://127.0.0.1:8000/admin/')
