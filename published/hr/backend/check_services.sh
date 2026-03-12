#!/bin/bash

# 🔍 Скрипт для проверки статуса всех сервисов HR Helper
# Использование: ./check_services.sh

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo -e "${BLUE}🔍 Проверка статуса HR Helper сервисов${NC}"
echo "=================================="

# Проверяем Redis
echo -n "Redis: "
if redis-cli ping >/dev/null 2>&1; then
    print_success "✅ Работает"
    REDIS_VERSION=$(redis-cli --version | cut -d' ' -f3)
    echo "   Версия: $REDIS_VERSION"
else
    print_error "❌ Не работает"
fi

# Проверяем Celery Worker
echo -n "Celery Worker: "
CELERY_PROCESSES=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)
if [ $CELERY_PROCESSES -gt 0 ]; then
    print_success "✅ Работает ($CELERY_PROCESSES процессов)"
    ps aux | grep "celery.*worker" | grep -v grep | while read line; do
        PID=$(echo $line | awk '{print $2}')
        echo "   PID: $PID"
    done
else
    print_error "❌ Не работает"
fi

# Проверяем Django сервер
echo -n "Django сервер: "
DJANGO_PROCESSES=$(ps aux | grep "manage.py.*runserver" | grep -v grep | wc -l)
if [ $DJANGO_PROCESSES -gt 0 ]; then
    print_success "✅ Работает ($DJANGO_PROCESSES процессов)"
    ps aux | grep "manage.py.*runserver" | grep -v grep | while read line; do
        PID=$(echo $line | awk '{print $2}')
        echo "   PID: $PID"
    done
else
    print_error "❌ Не работает"
fi

# Проверяем порты
echo ""
print_status "Проверка портов:"

# Проверяем порт 6379 (Redis)
echo -n "Порт 6379 (Redis): "
if lsof -i :6379 >/dev/null 2>&1; then
    print_success "✅ Занят"
else
    print_error "❌ Свободен"
fi

# Проверяем порт 8000 (Django)
echo -n "Порт 8000 (Django): "
if lsof -i :8000 >/dev/null 2>&1; then
    print_success "✅ Занят"
else
    print_error "❌ Свободен"
fi

# Проверяем HTTP доступность
echo ""
print_status "Проверка HTTP доступности:"

echo -n "Веб-интерфейс (http://127.0.0.1:8000/): "
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ | grep -q "200\|301\|302"; then
    print_success "✅ Доступен"
else
    print_error "❌ Недоступен"
fi

# Проверяем Celery задачи
echo ""
print_status "Проверка Celery:"

if command -v celery >/dev/null 2>&1; then
    echo -n "Активные задачи: "
    ACTIVE_TASKS=$(celery -A hrhelper inspect active 2>/dev/null | grep -c "celery@" || echo "0")
    if [ "$ACTIVE_TASKS" -gt 0 ]; then
        print_warning "⚠️ $ACTIVE_TASKS активных задач"
    else
        print_success "✅ Нет активных задач"
    fi
    
    echo -n "Запланированные задачи: "
    SCHEDULED_TASKS=$(celery -A hrhelper inspect scheduled 2>/dev/null | grep -c "celery@" || echo "0")
    if [ "$SCHEDULED_TASKS" -gt 0 ]; then
        print_warning "⚠️ $SCHEDULED_TASKS запланированных задач"
    else
        print_success "✅ Нет запланированных задач"
    fi
else
    print_warning "⚠️ Celery CLI недоступен"
fi

# Проверяем логи
echo ""
print_status "Проверка логов:"

if [ -f "logs/django.log" ]; then
    DJANGO_LOG_SIZE=$(wc -l < logs/django.log)
    print_success "✅ Django лог: $DJANGO_LOG_SIZE строк"
else
    print_warning "⚠️ Django лог не найден"
fi

if [ -f "logs/celery.log" ]; then
    CELERY_LOG_SIZE=$(wc -l < logs/celery.log)
    print_success "✅ Celery лог: $CELERY_LOG_SIZE строк"
else
    print_warning "⚠️ Celery лог не найден"
fi

# Проверяем базу данных
echo ""
print_status "Проверка базы данных:"

if [ -f "db.sqlite3" ]; then
    DB_SIZE=$(du -h db.sqlite3 | cut -f1)
    print_success "✅ База данных: $DB_SIZE"
else
    print_error "❌ База данных не найдена"
fi

# Итоговый статус
echo ""
echo "=================================="
ALL_SERVICES_OK=true

# Проверяем все сервисы
if ! redis-cli ping >/dev/null 2>&1; then
    ALL_SERVICES_OK=false
fi

if [ $CELERY_PROCESSES -eq 0 ]; then
    ALL_SERVICES_OK=false
fi

if [ $DJANGO_PROCESSES -eq 0 ]; then
    ALL_SERVICES_OK=false
fi

if [ "$ALL_SERVICES_OK" = true ]; then
    print_success "🎉 Все сервисы работают корректно!"
    echo ""
    echo -e "${BLUE}📋 Полезные ссылки:${NC}"
    echo -e "  • Веб-интерфейс: ${GREEN}http://127.0.0.1:8000/${NC}"
    echo -e "  • Админка: ${GREEN}http://127.0.0.1:8000/admin/${NC}"
    echo -e "  • ClickUp импорт: ${GREEN}http://127.0.0.1:8000/clickup/bulk-import/${NC}"
else
    print_error "❌ Некоторые сервисы не работают!"
    echo ""
    echo -e "${YELLOW}💡 Для запуска всех сервисов выполните:${NC}"
    echo -e "  ${BLUE}./start_services.sh${NC}"
fi

echo ""


