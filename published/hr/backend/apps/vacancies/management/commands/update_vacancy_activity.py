from django.core.management.base import BaseCommand
from apps.vacancies.models import Vacancy


class Command(BaseCommand):
    help = 'Обновляет статус активности всех вакансий на основе заявок на найм'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vacancy-id',
            type=int,
            help='Обновить статус только для конкретной вакансии',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие изменения будут сделаны без их применения',
        )

    def handle(self, *args, **options):
        vacancy_id = options.get('vacancy_id')
        dry_run = options.get('dry_run', False)
        
        if vacancy_id:
            try:
                vacancy = Vacancy.objects.get(id=vacancy_id)
                self.update_single_vacancy(vacancy, dry_run)
            except Vacancy.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Вакансия с ID {vacancy_id} не найдена')
                )
        else:
            self.update_all_vacancies(dry_run)

    def update_single_vacancy(self, vacancy, dry_run=False):
        """Обновляет статус одной вакансии"""
        self.stdout.write(f'Обновление вакансии: {vacancy.name}')
        
        # Получаем текущий статус
        current_status = vacancy.is_active
        
        if dry_run:
            # Симулируем обновление
            from apps.hiring_plan.models import HiringRequest
            from django.utils import timezone
            
            today = timezone.now().date()
            active_requests = HiringRequest.objects.filter(
                vacancy=vacancy,
                status__in=['planned', 'in_progress', 'overdue']
            ).exists()
            
            future_requests = HiringRequest.objects.filter(
                vacancy=vacancy,
                opening_date__gt=today
            ).exists()
            
            new_status = active_requests or future_requests
            
            if current_status != new_status:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Статус изменится: {current_status} → {new_status}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('  Статус не изменится')
                )
        else:
            # Реальное обновление
            if vacancy.update_activity_status():
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Статус обновлен: {current_status} → {vacancy.is_active}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('  Статус не изменился')
                )

    def update_all_vacancies(self, dry_run=False):
        """Обновляет статус всех вакансий"""
        vacancies = Vacancy.objects.all()
        total_vacancies = vacancies.count()
        
        self.stdout.write(f'Обновление статуса активности для {total_vacancies} вакансий...')
        
        if dry_run:
            updated_count = 0
            for vacancy in vacancies:
                current_status = vacancy.is_active
                
                # Симулируем обновление
                from apps.hiring_plan.models import HiringRequest
                from django.utils import timezone
                
                today = timezone.now().date()
                active_requests = HiringRequest.objects.filter(
                    vacancy=vacancy,
                    status__in=['planned', 'in_progress', 'overdue']
                ).exists()
                
                future_requests = HiringRequest.objects.filter(
                    vacancy=vacancy,
                    opening_date__gt=today
                ).exists()
                
                new_status = active_requests or future_requests
                
                if current_status != new_status:
                    updated_count += 1
                    self.stdout.write(
                        f'  {vacancy.name}: {current_status} → {new_status}'
                    )
            
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: {updated_count} вакансий будут обновлены'
                )
            )
        else:
            updated_count = Vacancy.update_all_activity_statuses()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Обновлено {updated_count} из {total_vacancies} вакансий'
                )
            )
