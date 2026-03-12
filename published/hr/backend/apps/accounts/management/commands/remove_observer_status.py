"""
Команда для удаления статуса наблюдателя у существующих пользователей
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Удалить статус наблюдателя у всех существующих пользователей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без применения изменений',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Удалить статус наблюдателя только у конкретного пользователя',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        username = options.get('username')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 РЕЖИМ ПРОСМОТРА - изменения не будут применены')
            )

        try:
            observer_group = Group.objects.get(name='Наблюдатели')
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('❌ Группа "Наблюдатели" не найдена')
            )
            return

        if username:
            # Обрабатываем конкретного пользователя
            try:
                user = User.objects.get(username=username)
                users = [user]
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Пользователь "{username}" не найден')
                )
                return
        else:
            # Обрабатываем всех пользователей со статусом наблюдателя
            users = User.objects.filter(groups__name='Наблюдатели').distinct()

        if not users:
            self.stdout.write(
                self.style.SUCCESS('✅ Пользователей со статусом наблюдателя не найдено')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'🔍 Найдено пользователей со статусом наблюдателя: {len(users)}')
        )

        removed_count = 0
        kept_count = 0

        for user in users:
            current_groups = [g.name for g in user.groups.all()]
            
            # Показываем текущее состояние
            self.stdout.write(f'\n👤 Пользователь: {user.username} ({user.email})')
            self.stdout.write(f'   Текущие группы: {current_groups}')
            self.stdout.write(f'   Статус наблюдателя: {user.is_observer_active}')

            if not dry_run:
                # Удаляем группу Наблюдатели
                user.groups.remove(observer_group)
                user.is_observer_active = False
                user.save()

                removed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'   ✅ Статус наблюдателя удален')
                )
            else:
                # В режиме просмотра показываем что будет изменено
                if 'Наблюдатели' in current_groups:
                    removed_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'   ⚠️ Будет удален статус наблюдателя')
                    )
                else:
                    kept_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'   ✅ Статус наблюдателя уже отсутствует')
                    )

        # Итоговая статистика
        self.stdout.write(f'\n📊 ИТОГОВАЯ СТАТИСТИКА:')
        if dry_run:
            self.stdout.write(f'   Будет удален статус наблюдателя: {removed_count}')
            self.stdout.write(f'   Без изменений: {kept_count}')
            self.stdout.write(
                self.style.WARNING('\n⚠️ Для применения изменений запустите команду без --dry-run')
            )
        else:
            self.stdout.write(f'   Статус наблюдателя удален: {removed_count}')
            self.stdout.write(
                self.style.SUCCESS('🎉 Команда выполнена успешно!')
            )

