#!/bin/bash

# 💾 Скрипт автоматического backup системы
# Автор: AI Assistant
# Дата: $(date)

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Переменные
BACKUP_DIR="../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hrhelper_backup_$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
RETENTION_DAYS=30  # Хранить backup'ы 30 дней

# Создание директории для backup'ов
mkdir -p "$BACKUP_DIR"

# Функция создания backup кода
backup_code() {
    log_info "Создание backup кода приложения..."
    
    mkdir -p "$BACKUP_PATH/code"
    
    # Копирование всех файлов кроме исключений
    rsync -av --exclude='__pycache__' \
              --exclude='*.pyc' \
              --exclude='.git' \
              --exclude='node_modules' \
              --exclude='venv' \
              --exclude='env' \
              --exclude='.env' \
              --exclude='logs' \
              --exclude='staticfiles' \
              --exclude='media' \
              --exclude='backups' \
              --exclude='db.sqlite3' \
              . "$BACKUP_PATH/code/"
    
    log_success "Backup кода создан: $BACKUP_PATH/code"
}

# Функция создания backup базы данных
backup_database() {
    log_info "Создание backup базы данных..."
    
    mkdir -p "$BACKUP_PATH/database"
    
    # Проверяем тип базы данных
    if [ -f "db.sqlite3" ]; then
        # SQLite backup
        cp db.sqlite3 "$BACKUP_PATH/database/db.sqlite3"
        log_success "SQLite backup создан"
    else
        # PostgreSQL backup
        if command -v pg_dump &> /dev/null; then
            pg_dump -h localhost -U postgres hrhelper > "$BACKUP_PATH/database/db_dump.sql"
            log_success "PostgreSQL backup создан"
        else
            log_warning "pg_dump не найден, пропускаем PostgreSQL backup"
        fi
    fi
}

# Функция создания backup конфигурации
backup_config() {
    log_info "Создание backup конфигурации..."
    
    mkdir -p "$BACKUP_PATH/config"
    
    # Копирование конфигурационных файлов
    if [ -f "config/settings.py" ]; then
        cp config/settings.py "$BACKUP_PATH/config/"
    fi
    
    if [ -f "config/settings_production.py" ]; then
        cp config/settings_production.py "$BACKUP_PATH/config/"
    fi
    
    if [ -f "requirements.txt" ]; then
        cp requirements.txt "$BACKUP_PATH/config/"
    fi
    
    # Копирование переменных окружения (без секретов)
    if [ -f "env_production_example.txt" ]; then
        cp env_production_example.txt "$BACKUP_PATH/config/"
    fi
    
    log_success "Backup конфигурации создан"
}

# Функция создания backup медиа файлов
backup_media() {
    log_info "Создание backup медиа файлов..."
    
    if [ -d "media" ] && [ "$(ls -A media)" ]; then
        mkdir -p "$BACKUP_PATH/media"
        cp -r media/* "$BACKUP_PATH/media/"
        log_success "Backup медиа файлов создан"
    else
        log_info "Медиа файлы не найдены, пропускаем"
    fi
}

# Функция создания backup логов
backup_logs() {
    log_info "Создание backup логов..."
    
    if [ -d "logs" ] && [ "$(ls -A logs)" ]; then
        mkdir -p "$BACKUP_PATH/logs"
        cp -r logs/* "$BACKUP_PATH/logs/"
        log_success "Backup логов создан"
    else
        log_info "Логи не найдены, пропускаем"
    fi
}

# Функция создания архива
create_archive() {
    log_info "Создание архива backup..."
    
    cd "$BACKUP_DIR"
    tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
    
    # Удаление исходной папки
    rm -rf "$BACKUP_NAME"
    
    # Подсчет размера
    ARCHIVE_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    
    log_success "Архив создан: ${BACKUP_NAME}.tar.gz (размер: $ARCHIVE_SIZE)"
}

# Функция очистки старых backup'ов
cleanup_old_backups() {
    log_info "Очистка старых backup'ов (старше $RETENTION_DAYS дней)..."
    
    # Поиск и удаление старых backup'ов
    find "$BACKUP_DIR" -name "hrhelper_backup_*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
    
    # Подсчет оставшихся backup'ов
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "hrhelper_backup_*.tar.gz" -type f | wc -l)
    
    log_success "Очистка завершена. Осталось backup'ов: $BACKUP_COUNT"
}

# Функция создания метаданных backup
create_backup_metadata() {
    log_info "Создание метаданных backup..."
    
    METADATA_FILE="$BACKUP_PATH/metadata.json"
    
    cat > "$METADATA_FILE" << EOF
{
    "backup_name": "$BACKUP_NAME",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "version": "1.0",
    "components": {
        "code": true,
        "database": true,
        "config": true,
        "media": $([ -d "media" ] && [ "$(ls -A media)" ] && echo "true" || echo "false"),
        "logs": $([ -d "logs" ] && [ "$(ls -A logs)" ] && echo "true" || echo "false")
    },
    "system_info": {
        "python_version": "$(python3 --version 2>&1)",
        "django_version": "$(python3 -c 'import django; print(django.get_version())' 2>/dev/null || echo 'unknown')",
        "disk_usage": "$(df -h . | tail -1 | awk '{print $5}')",
        "memory_usage": "$(free -h | grep Mem | awk '{print $3 "/" $2}')"
    },
    "created_by": "backup.sh",
    "notes": "Automated backup of HRHelper application"
}
EOF
    
    log_success "Метаданные созданы: $METADATA_FILE"
}

# Функция проверки целостности backup
verify_backup() {
    log_info "Проверка целостности backup..."
    
    # Проверка архива
    if [ -f "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" ]; then
        if tar -tzf "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" > /dev/null; then
            log_success "Архив корректен"
        else
            log_error "Архив поврежден"
            return 1
        fi
    else
        log_error "Архив не найден"
        return 1
    fi
    
    # Проверка размера
    ARCHIVE_SIZE=$(stat -f%z "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" 2>/dev/null || stat -c%s "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" 2>/dev/null)
    if [ "$ARCHIVE_SIZE" -gt 1000 ]; then  # Минимум 1KB
        log_success "Размер архива корректен: $ARCHIVE_SIZE байт"
    else
        log_error "Размер архива подозрительно мал: $ARCHIVE_SIZE байт"
        return 1
    fi
}

# Функция восстановления из backup
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Не указан файл backup для восстановления"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Файл backup не найден: $backup_file"
        return 1
    fi
    
    log_warning "ВНИМАНИЕ: Это действие перезапишет текущие данные!"
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Восстановление отменено"
        return 0
    fi
    
    log_info "Восстановление из backup: $backup_file"
    
    # Создание backup текущего состояния
    log_info "Создание backup текущего состояния..."
    ./backup.sh
    
    # Остановка сервисов
    log_info "Остановка сервисов..."
    ./stop_services.sh 2>/dev/null || true
    
    # Извлечение архива
    log_info "Извлечение архива..."
    cd "$BACKUP_DIR"
    tar -xzf "$(basename "$backup_file")"
    
    # Восстановление файлов
    log_info "Восстановление файлов..."
    cd ..
    rm -rf backend
    mv "backups/$(basename "$backup_file" .tar.gz)" backend
    
    # Восстановление базы данных
    if [ -f "backend/database/db.sqlite3" ]; then
        log_info "Восстановление SQLite базы данных..."
        cp backend/database/db.sqlite3 .
    elif [ -f "backend/database/db_dump.sql" ]; then
        log_info "Восстановление PostgreSQL базы данных..."
        # Здесь нужно добавить команды для восстановления PostgreSQL
        log_warning "PostgreSQL восстановление не реализовано автоматически"
    fi
    
    log_success "Восстановление завершено"
}

# Функция списка доступных backup'ов
list_backups() {
    log_info "Доступные backup'ы:"
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -la "$BACKUP_DIR"/hrhelper_backup_*.tar.gz 2>/dev/null | while read -r line; do
            echo "  $line"
        done
        
        BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/hrhelper_backup_*.tar.gz 2>/dev/null | wc -l)
        log_info "Всего backup'ов: $BACKUP_COUNT"
    else
        log_warning "Директория backup'ов не найдена: $BACKUP_DIR"
    fi
}

# Основная функция создания backup
create_backup() {
    log_info "Начало создания backup: $BACKUP_NAME"
    
    # Создание компонентов backup
    backup_code
    backup_database
    backup_config
    backup_media
    backup_logs
    create_backup_metadata
    
    # Создание архива
    create_archive
    
    # Проверка целостности
    if verify_backup; then
        log_success "Backup создан успешно: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
        
        # Очистка старых backup'ов
        cleanup_old_backups
        
        # Вывод информации о backup
        ARCHIVE_SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" | cut -f1)
        log_info "Размер backup: $ARCHIVE_SIZE"
        log_info "Путь: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
        
    else
        log_error "Backup создан с ошибками"
        return 1
    fi
}

# Обработка аргументов командной строки
case "${1:-create}" in
    "create")
        create_backup
        ;;
    "restore")
        restore_backup "$2"
        ;;
    "list")
        list_backups
        ;;
    "cleanup")
        cleanup_old_backups
        ;;
    "verify")
        if [ -n "$2" ]; then
            verify_backup "$2"
        else
            log_error "Укажите файл backup для проверки"
            exit 1
        fi
        ;;
    *)
        echo "Использование: $0 {create|restore|list|cleanup|verify}"
        echo ""
        echo "Команды:"
        echo "  create [name]  - Создать backup"
        echo "  restore <file> - Восстановить из backup"
        echo "  list          - Показать список backup'ов"
        echo "  cleanup       - Удалить старые backup'ы"
        echo "  verify <file> - Проверить целостность backup"
        echo ""
        echo "Примеры:"
        echo "  $0 create"
        echo "  $0 restore backups/hrhelper_backup_20240101_120000.tar.gz"
        echo "  $0 list"
        exit 1
        ;;
esac

