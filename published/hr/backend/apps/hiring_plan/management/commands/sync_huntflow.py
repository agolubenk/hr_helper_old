from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from hiring_plan.huntflow_services.huntflow_sync_service import HuntflowSyncService


class Command(BaseCommand):
    help = 'Синхронизация закрытых вакансий из HuntFlow'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vacancy-id',
            type=int,
            help='ID конкретной вакансии для синхронизации'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Синхронизировать все вакансии'
        )
        
        parser.add_argument(
            '--username',
            type=str,
            help='Имя пользователя с токенами HuntFlow (по умолчанию первый найденный)'
        )
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Находим пользователя с токенами HuntFlow
        if options['username']:
            user = User.objects.get(username=options['username'])
        else:
            user = User.objects.filter(huntflow_access_token__isnull=False).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Не найден пользователь с токенами HuntFlow'))
            return
        
        self.stdout.write(f'Используем токены пользователя: {user.username}')
        
        sync_service = HuntflowSyncService(user)
        
        if options['all']:
            self.stdout.write('Starting bulk sync...')
            sync_service.bulk_sync_all_vacancies()
            self.stdout.write(self.style.SUCCESS('Bulk sync completed'))
        
        elif options['vacancy_id']:
            vacancy_id = options['vacancy_id']
            self.stdout.write(f'Syncing vacancy {vacancy_id}...')
            requests = sync_service.sync_all_hired_for_vacancy(vacancy_id)
            self.stdout.write(
                self.style.SUCCESS(f'Synced {len(requests)} hired applicants')
            )
        
        else:
            self.stdout.write(self.style.ERROR('Specify --vacancy-id or --all'))

from hiring_plan.huntflow_services.huntflow_sync_service import HuntflowSyncService


class Command(BaseCommand):
    help = 'Синхронизация закрытых вакансий из HuntFlow'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vacancy-id',
            type=int,
            help='ID конкретной вакансии для синхронизации'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Синхронизировать все вакансии'
        )
        
        parser.add_argument(
            '--username',
            type=str,
            help='Имя пользователя с токенами HuntFlow (по умолчанию первый найденный)'
        )
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Находим пользователя с токенами HuntFlow
        if options['username']:
            user = User.objects.get(username=options['username'])
        else:
            user = User.objects.filter(huntflow_access_token__isnull=False).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Не найден пользователь с токенами HuntFlow'))
            return
        
        self.stdout.write(f'Используем токены пользователя: {user.username}')
        
        sync_service = HuntflowSyncService(user)
        
        if options['all']:
            self.stdout.write('Starting bulk sync...')
            sync_service.bulk_sync_all_vacancies()
            self.stdout.write(self.style.SUCCESS('Bulk sync completed'))
        
        elif options['vacancy_id']:
            vacancy_id = options['vacancy_id']
            self.stdout.write(f'Syncing vacancy {vacancy_id}...')
            requests = sync_service.sync_all_hired_for_vacancy(vacancy_id)
            self.stdout.write(
                self.style.SUCCESS(f'Synced {len(requests)} hired applicants')
            )
        
        else:
            self.stdout.write(self.style.ERROR('Specify --vacancy-id or --all'))
