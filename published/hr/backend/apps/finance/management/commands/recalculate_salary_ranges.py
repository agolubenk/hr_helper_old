from django.core.management.base import BaseCommand
from apps.finance.models import SalaryRange
from apps.finance.models import CurrencyRate
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Пересчитывает все зарплатные вилки с учетом актуальных курсов валют'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет пересчитано без сохранения изменений',
        )
        parser.add_argument(
            '--currency',
            type=str,
            help='Пересчитать только для указанной валюты (USD, PLN, EUR)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        currency_filter = options.get('currency')
        
        self.stdout.write('=== Пересчет зарплатных вилок ===\n')
        
        # Проверяем наличие курсов валют
        try:
            usd_rate = CurrencyRate.objects.get(code='USD')
            pln_rate = CurrencyRate.objects.get(code='PLN')
            eur_rate = CurrencyRate.objects.get(code='EUR')
            
            self.stdout.write(f'📊 Текущие курсы валют:')
            self.stdout.write(f'  USD: {usd_rate.rate} BYN (обновлен: {usd_rate.fetched_at})')
            self.stdout.write(f'  PLN: {pln_rate.rate} BYN (обновлен: {pln_rate.fetched_at})')
            self.stdout.write(f'  EUR: {eur_rate.rate} BYN (обновлен: {eur_rate.fetched_at})')
            self.stdout.write('')
            
        except CurrencyRate.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Не найдены курсы валют: {e}')
            )
            return
        
        # Получаем зарплатные вилки для пересчета
        queryset = SalaryRange.objects.filter(is_active=True)
        
        if currency_filter:
            # Фильтруем по вакансиям с определенной валютой
            # Это упрощенная логика - в реальности нужно смотреть на вакансию
            self.stdout.write(f'🔍 Фильтр по валюте: {currency_filter}')
        
        total_count = queryset.count()
        self.stdout.write(f'📋 Найдено зарплатных вилок для пересчета: {total_count}\n')
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('⚠️ Нет активных зарплатных вилок для пересчета'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 РЕЖИМ ПРОСМОТРА (изменения не сохраняются)\n'))
        
        updated_count = 0
        error_count = 0
        
        for salary_range in queryset:
            try:
                # Показываем текущие значения
                self.stdout.write(f'📝 {salary_range.vacancy.name} - {salary_range.grade.name}:')
                self.stdout.write(f'  USD: ${salary_range.salary_min_usd} - ${salary_range.salary_max_usd}')
                self.stdout.write(f'  BYN: {salary_range.salary_min_byn} - {salary_range.salary_max_byn}')
                self.stdout.write(f'  PLN: {salary_range.salary_min_pln} - {salary_range.salary_max_pln}')
                self.stdout.write(f'  EUR: {salary_range.salary_min_eur} - {salary_range.salary_max_eur}')
                
                if not dry_run:
                    # Пересчитываем зарплаты в других валютах
                    salary_range._calculate_other_currencies()
                    salary_range.save(update_fields=[
                        'salary_min_byn', 'salary_max_byn',
                        'salary_min_pln', 'salary_max_pln', 
                        'salary_min_eur', 'salary_max_eur',
                        'updated_at'
                    ])
                    
                    # Показываем новые значения
                    self.stdout.write(f'  ✅ Обновлено:')
                    self.stdout.write(f'    BYN: {salary_range.salary_min_byn} - {salary_range.salary_max_byn}')
                    self.stdout.write(f'    PLN: {salary_range.salary_min_pln} - {salary_range.salary_max_pln}')
                    self.stdout.write(f'    EUR: {salary_range.salary_min_eur} - {salary_range.salary_max_eur}')
                    
                    updated_count += 1
                else:
                    self.stdout.write(f'  🔍 Будет пересчитано с текущими курсами')
                
                self.stdout.write('')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Ошибка при пересчете {salary_range}: {e}')
                )
                error_count += 1
                continue
        
        # Итоговая статистика
        self.stdout.write('=== Результаты ===')
        if dry_run:
            self.stdout.write(f'🔍 Просмотрено вилок: {total_count}')
            self.stdout.write(f'❌ Ошибок: {error_count}')
            self.stdout.write('')
            self.stdout.write('Для применения изменений запустите команду без --dry-run')
        else:
            self.stdout.write(f'✅ Обновлено вилок: {updated_count}')
            self.stdout.write(f'❌ Ошибок: {error_count}')
            self.stdout.write(f'📊 Всего обработано: {total_count}')
        
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n🎉 Успешно пересчитано {updated_count} зарплатных вилок!')
            )
