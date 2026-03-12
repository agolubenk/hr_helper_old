"""
Команда для миграции данных из SQLite в PostgreSQL
Мигрирует только указанные таблицы: вакансии, настройки компании, финансы, план найма, отчеты, интервьюеры, настройки scorecard
"""
import os
import sys
import sqlite3
try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    execute_values = None

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections
from django.apps import apps


class Command(BaseCommand):
    help = 'Мигрирует данные из SQLite в PostgreSQL для указанных приложений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sqlite-db',
            type=str,
            default='db.sqlite3',
            help='Путь к SQLite базе данных (по умолчанию: db.sqlite3)'
        )
        parser.add_argument(
            '--postgres-db',
            type=str,
            help='Имя PostgreSQL базы данных (из переменных окружения или settings)'
        )
        parser.add_argument(
            '--postgres-user',
            type=str,
            help='Пользователь PostgreSQL (из переменных окружения или settings)'
        )
        parser.add_argument(
            '--postgres-password',
            type=str,
            help='Пароль PostgreSQL (из переменных окружения или settings)'
        )
        parser.add_argument(
            '--postgres-host',
            type=str,
            default='localhost',
            help='Хост PostgreSQL (по умолчанию: localhost)'
        )
        parser.add_argument(
            '--postgres-port',
            type=int,
            default=5432,
            help='Порт PostgreSQL (по умолчанию: 5432)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Пробный запуск без сохранения данных'
        )

    def handle(self, *args, **options):
        # Проверяем наличие psycopg2
        if psycopg2 is None:
            self.stdout.write(self.style.ERROR('❌ psycopg2 не установлен. Установите: pip install psycopg2-binary'))
            return
        
        self.stdout.write(self.style.SUCCESS('🚀 Начинаем миграцию данных из SQLite в PostgreSQL...'))
        
        # Получаем параметры подключения
        sqlite_path = options['sqlite_db']
        if not os.path.exists(sqlite_path):
            self.stdout.write(self.style.ERROR(f'❌ SQLite база данных не найдена: {sqlite_path}'))
            return
        
        # Параметры PostgreSQL
        pg_db = options['postgres_db'] or os.environ.get('DB_NAME', 'hrhelper_production')
        pg_user = options['postgres_user'] or os.environ.get('DB_USER', 'hrhelper_user')
        pg_password = options['postgres_password'] or os.environ.get('DB_PASSWORD', '')
        pg_host = options['postgres_host']
        pg_port = options['postgres_port']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  РЕЖИМ ПРОБНОГО ЗАПУСКА - данные не будут сохранены'))
        
        # Подключаемся к базам данных
        try:
            sqlite_conn = sqlite3.connect(sqlite_path)
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_cursor = sqlite_conn.cursor()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Подключено к SQLite: {sqlite_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка подключения к SQLite: {e}'))
            return
        
        try:
            pg_conn = psycopg2.connect(
                dbname=pg_db,
                user=pg_user,
                password=pg_password,
                host=pg_host,
                port=pg_port
            )
            pg_cursor = pg_conn.cursor()
            self.stdout.write(self.style.SUCCESS(f'✅ Подключено к PostgreSQL: {pg_host}:{pg_port}/{pg_db}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка подключения к PostgreSQL: {e}'))
            self.stdout.write(self.style.WARNING('💡 Убедитесь, что PostgreSQL запущен и база данных создана'))
            sqlite_conn.close()
            return
        
        # Определяем таблицы для миграции в порядке зависимостей
        tables_to_migrate = [
            # Базовые таблицы (без зависимостей)
            ('finance_grade', 'finance.Grade'),
            ('interviewers_interviewer', 'interviewers.Interviewer'),
            
            # Таблицы с зависимостями от Grade
            ('interviewers_interviewrule', 'interviewers.InterviewRule'),
            ('company_settings_rejectiontemplate', 'company_settings.RejectionTemplate'),
            
            # Настройки компании
            ('company_settings_companysettings', 'company_settings.CompanySettings'),
            ('company_settings_vacancyprompt', 'company_settings.VacancyPrompt'),
            ('company_settings_vacancyprompthistory', 'company_settings.VacancyPromptHistory'),
            
            # Финансы (зависит от Grade)
            ('finance_currencyrate', 'finance.CurrencyRate'),
            ('finance_plntax', 'finance.PLNTax'),
            ('finance_benchmarksettings', 'finance.BenchmarkSettings'),
            
            # Вакансии (зависит от User, но User не мигрируем)
            ('vacancies_vacancy', 'vacancies.Vacancy'),
            
            # Финансы (зависит от Vacancy и Grade)
            ('finance_salaryrange', 'finance.SalaryRange'),
            ('finance_benchmark', 'finance.Benchmark'),
            
            # План найма (зависит от Vacancy, Grade, User)
            ('hiring_plan_planperiodtype', 'hiring_plan.PlanPeriodType'),
            ('hiring_plan_positiontype', 'hiring_plan.PositionType'),
            ('hiring_plan_hiringplan', 'hiring_plan.HiringPlan'),
            ('hiring_plan_plankpiokrblock', 'hiring_plan.PlanKPIOKRBlock'),
            ('hiring_plan_positionkpiokr', 'hiring_plan.PositionKPIOKR'),
            ('hiring_plan_vacancysla', 'hiring_plan.VacancySLA'),
            ('hiring_plan_hiringplanposition', 'hiring_plan.HiringPlanPosition'),
            ('hiring_plan_hiringrequest', 'hiring_plan.HiringRequest'),
            ('hiring_plan_recruiterassignment', 'hiring_plan.RecruiterAssignment'),
            ('hiring_plan_recruitmentmetrics', 'hiring_plan.RecruitmentMetrics'),
            ('hiring_plan_demandforecast', 'hiring_plan.DemandForecast'),
            ('hiring_plan_recruitercapacity', 'hiring_plan.RecruiterCapacity'),
            ('hiring_plan_planmetrics', 'hiring_plan.PlanMetrics'),
            ('hiring_plan_huntflowsync', 'hiring_plan.HuntflowSync'),
            
            # Отчеты (зависит от User, Vacancy)
            ('reporting_reportcache', 'reporting.ReportCache'),
            ('reporting_calendarevent', 'reporting.CalendarEvent'),
            
            # Google OAuth (настройки scorecard, зависит от User)
            ('google_oauth_scorecardpathsettings', 'google_oauth.ScorecardPathSettings'),
        ]
        
        # ManyToMany таблицы (мигрируются после основных)
        m2m_tables = [
            ('vacancies_vacancy_available_grades', 'vacancies.Vacancy.available_grades'),
            ('vacancies_vacancy_interviewers', 'vacancies.Vacancy.interviewers'),
            ('company_settings_companysettings_active_grades', 'company_settings.CompanySettings.active_grades'),
            ('hiring_plan_hiringplanposition_grades', 'hiring_plan.HiringPlanPosition.grades'),
            ('hiring_plan_plankpiokrblock_position_types', 'hiring_plan.PlanKPIOKRBlock.position_types'),
            ('hiring_plan_plankpiokrblock_grades', 'hiring_plan.PlanKPIOKRBlock.grades'),
            ('hiring_plan_hiringplanposition_applied_kpi_okr_blocks', 'hiring_plan.HiringPlanPosition.applied_kpi_okr_blocks'),
        ]
        
        total_migrated = 0
        total_errors = 0
        
        # Мигрируем основные таблицы
        for table_name, model_path in tables_to_migrate:
            try:
                app_label, model_name = model_path.split('.')
                model = apps.get_model(app_label, model_name)
                
                # Проверяем, существует ли таблица в SQLite
                sqlite_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not sqlite_cursor.fetchone():
                    self.stdout.write(self.style.WARNING(f'⚠️  Таблица {table_name} не найдена в SQLite, пропускаем'))
                    continue
                
                # Получаем данные из SQLite
                sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    self.stdout.write(self.style.WARNING(f'⚠️  Таблица {table_name} пуста, пропускаем'))
                    continue
                
                self.stdout.write(f'📦 Мигрируем {table_name} ({len(rows)} записей)...')
                
                if not dry_run:
                    # Получаем колонки из SQLite
                    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
                    sqlite_columns = {col[1]: col for col in sqlite_cursor.fetchall()}
                    
                    # Получаем колонки из PostgreSQL
                    pg_cursor.execute(f"""
                        SELECT column_name, data_type, is_nullable 
                        FROM information_schema.columns 
                        WHERE table_name = %s
                    """, (table_name,))
                    pg_columns = {col[0]: col for col in pg_cursor.fetchall()}
                    
                    # Очищаем таблицу в PostgreSQL (опционально, можно закомментировать)
                    # pg_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
                    
                    # Вставляем данные
                    inserted_count = 0
                    for row in rows:
                        row_dict = dict(row)
                        # Фильтруем только существующие колонки в PostgreSQL
                        filtered_row = {k: v for k, v in row_dict.items() if k in pg_columns}
                        
                        if not filtered_row:
                            continue
                        
                        # Обрабатываем NULL значения
                        for key, value in list(filtered_row.items()):
                            if value is None and pg_columns[key][2] == 'NO':
                                # Пропускаем записи с NULL в NOT NULL полях
                                filtered_row = None
                                break
                        
                        if not filtered_row:
                            continue
                        
                        columns_list = list(filtered_row.keys())
                        values_list = list(filtered_row.values())
                        placeholders = ', '.join(['%s'] * len(values_list))
                        
                        # Пропускаем записи с NULL в обязательных полях (кроме автоинкрементных)
                        try:
                            pg_cursor.execute(
                                f"INSERT INTO {table_name} ({', '.join(columns_list)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                                values_list
                            )
                            inserted_count += pg_cursor.rowcount
                        except psycopg2.IntegrityError as e:
                            # Пропускаем дубликаты и ошибки целостности
                            self.stdout.write(self.style.WARNING(f'⚠️  Пропущена запись из-за конфликта: {str(e)[:100]}'))
                            continue
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'❌ Ошибка при вставке записи: {e}'))
                            total_errors += 1
                            continue
                    
                    pg_conn.commit()
                    total_migrated += inserted_count
                    self.stdout.write(self.style.SUCCESS(f'✅ Мигрировано {inserted_count} записей из {table_name} (всего было {len(rows)})'))
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️  [DRY RUN] Будет мигрировано {len(rows)} записей из {table_name}'))
                    total_migrated += len(rows)
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при миграции {table_name}: {e}'))
                import traceback
                traceback.print_exc()
                total_errors += 1
                continue
        
        # Мигрируем ManyToMany таблицы
        self.stdout.write(self.style.SUCCESS('\n📋 Мигрируем ManyToMany связи...'))
        
        for table_name, model_path in m2m_tables:
            try:
                # Проверяем, существует ли таблица в SQLite
                sqlite_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not sqlite_cursor.fetchone():
                    continue
                
                sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    continue
                
                self.stdout.write(f'📦 Мигрируем M2M таблицу {table_name} ({len(rows)} записей)...')
                
                if not dry_run:
                    # Получаем колонки
                    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [col[1] for col in sqlite_cursor.fetchall()]
                    
                    for row in rows:
                        row_dict = dict(row)
                        columns_list = list(row_dict.keys())
                        values_list = list(row_dict.values())
                        placeholders = ', '.join(['%s'] * len(values_list))
                        
                        try:
                            pg_cursor.execute(
                                f"INSERT INTO {table_name} ({', '.join(columns_list)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                                values_list
                            )
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'⚠️  Пропущена M2M запись: {e}'))
                            continue
                    
                    pg_conn.commit()
                    self.stdout.write(self.style.SUCCESS(f'✅ Мигрировано {len(rows)} M2M записей из {table_name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️  [DRY RUN] Будет мигрировано {len(rows)} M2M записей из {table_name}'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при миграции M2M таблицы {table_name}: {e}'))
                total_errors += 1
                continue
        
        # Закрываем соединения
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()
        
        # Итоги
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  РЕЖИМ ПРОБНОГО ЗАПУСКА - данные НЕ были сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Миграция завершена!'))
        self.stdout.write(self.style.SUCCESS(f'📊 Всего мигрировано записей: {total_migrated}'))
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'❌ Ошибок: {total_errors}'))
        self.stdout.write(self.style.SUCCESS('='*60))
