from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import models
from apps.hiring_plan.models import HiringRequest

User = get_user_model()


class Command(BaseCommand):
    help = 'Получает данные кандидатов из Huntflow (имя, дата закрытия, дата выхода) для всех заявок с candidate_id'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID пользователя для получения данных из Huntflow (если не указан, используется первый активный пользователь)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие заявки будут обработаны без фактического обновления',
        )

    def handle(self, *args, **options):
        # Получаем пользователя
        if options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Пользователь с ID {options["user_id"]} не найден')
                )
                return
        else:
            user = User.objects.filter(is_active=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('Не найдено активных пользователей')
                )
                return

        # Находим заявки с candidate_id, но без полных данных
        requests = HiringRequest.objects.filter(
            candidate_id__isnull=False,
            candidate_id__gt=''
        ).filter(
            models.Q(candidate_name__isnull=True) | 
            models.Q(candidate_name='') |
            models.Q(closed_date__isnull=True) |
            models.Q(hire_date__isnull=True)
        )

        if not requests.exists():
            self.stdout.write(
                self.style.SUCCESS('Нет заявок для обработки')
            )
            return

        self.stdout.write(
            f'Найдено {requests.count()} заявок для обработки'
        )

        if options['dry_run']:
            self.stdout.write('DRY RUN - заявки не будут обновлены:')
            for request in requests:
                self.stdout.write(f'  - ID {request.id}: candidate_id={request.candidate_id}')
            return

        # Обрабатываем заявки
        success_count = 0
        error_count = 0

        for request in requests:
            try:
                self.stdout.write(f'Обрабатываем заявку ID {request.id} (candidate_id={request.candidate_id})...')
                
                success = request.fetch_candidate_data_from_huntflow(user)
                if success:
                    updated_data = []
                    if request.candidate_name:
                        updated_data.append(f'имя: {request.candidate_name}')
                    if request.closed_date:
                        updated_data.append(f'дата закрытия: {request.closed_date.strftime("%d.%m.%Y")}')
                    if request.hire_date:
                        updated_data.append(f'дата выхода: {request.hire_date.strftime("%d.%m.%Y")}')
                    
                    if updated_data:
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ Получены данные: {", ".join(updated_data)}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'  ℹ️ Данные проверены, но новых данных не найдено')
                        )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️ Не удалось получить данные для candidate_id={request.candidate_id}')
                    )
                    error_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Ошибка при обработке заявки ID {request.id}: {e}')
                )
                error_count += 1

        # Итоги
        self.stdout.write('')
        self.stdout.write('=' * 50)
        self.stdout.write(f'Обработано заявок: {success_count + error_count}')
        self.stdout.write(f'Успешно: {success_count}')
        self.stdout.write(f'Ошибок: {error_count}')
        self.stdout.write('=' * 50)
