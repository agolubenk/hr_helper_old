from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.google_oauth.cache_service import GoogleAPICache, HuntflowAPICache, CacheService

User = get_user_model()


class Command(BaseCommand):
    help = 'Тестировать работу кэша API данных'

    def handle(self, *args, **options):
        # Получаем первого пользователя для тестирования
        try:
            user = User.objects.first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('❌ Нет пользователей в системе')
                )
                return
            
            user_id = user.id
            self.stdout.write(
                self.style.SUCCESS(f'🧪 Тестируем кэш для пользователя: {user.username} (ID: {user_id})')
            )
            
            # Тестируем Google API кэш
            self.stdout.write('\n📅 Тестируем Google Calendar кэш:')
            calendar_events = GoogleAPICache.get_calendar_events(user_id, 'primary', 100)
            if calendar_events is not None:
                self.stdout.write(f'  ✅ События календаря в кэше: {len(calendar_events)} событий')
            else:
                self.stdout.write('  ⚠️ События календаря не найдены в кэше')
            
            # Тестируем Google Drive кэш
            self.stdout.write('\n📁 Тестируем Google Drive кэш:')
            drive_files = GoogleAPICache.get_drive_files(user_id, 100)
            if drive_files is not None:
                self.stdout.write(f'  ✅ Файлы Drive в кэше: {len(drive_files)} файлов')
            else:
                self.stdout.write('  ⚠️ Файлы Drive не найдены в кэше')
            
            # Тестируем Google Sheets кэш
            self.stdout.write('\n📊 Тестируем Google Sheets кэш:')
            sheets = GoogleAPICache.get_sheets(user_id, 100)
            if sheets is not None:
                self.stdout.write(f'  ✅ Таблицы в кэше: {len(sheets)} таблиц')
            else:
                self.stdout.write('  ⚠️ Таблицы не найдены в кэше')
            
            # Тестируем Huntflow API кэш
            self.stdout.write('\n👥 Тестируем Huntflow кэш:')
            candidate = HuntflowAPICache.get_candidate(user_id, 694, 1)
            if candidate is not None:
                self.stdout.write(f'  ✅ Кандидат в кэше: {candidate.get("first_name", "Unknown")}')
            else:
                self.stdout.write('  ⚠️ Кандидат не найден в кэше')
            
            # Показываем общую статистику
            self.stdout.write('\n📊 Общая статистика кэша:')
            stats = CacheService.get_cache_stats()
            self.stdout.write(f'  Всего ключей: {stats["total_keys"]}')
            
            if stats['services']:
                for service, count in stats['services'].items():
                    self.stdout.write(f'  {service}: {count} ключей')
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ Тест кэша завершен')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка тестирования кэша: {e}')
            )
