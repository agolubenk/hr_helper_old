#!/bin/bash

# 🛑 Скрипт для остановки всех сервисов HR Helper
# Использование: ./stop_services.sh

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

print_status "Остановка HR Helper сервисов..."

# Проверяем, есть ли файл с PIDs
if [ -f "logs/services.pid" ]; then
    print_status "Останавливаем сервисы по сохраненным PID..."
    PIDS=$(cat logs/services.pid)
    
    for PID in $PIDS; do
        if kill -0 $PID 2>/dev/null; then
            print_status "Останавливаем процесс $PID..."
            kill $PID
            sleep 1
            
            # Если процесс не остановился, принудительно убиваем
            if kill -0 $PID 2>/dev/null; then
                print_warning "Принудительная остановка процесса $PID..."
                kill -9 $PID
            fi
        fi
    done
    
    rm -f logs/services.pid
fi

# Останавливаем все процессы по имени
print_status "Остановка всех процессов Django и Celery..."

# Останавливаем Celery Worker
pkill -f "celery.*worker" 2>/dev/null && print_success "Celery Worker остановлен" || print_warning "Celery Worker не был запущен"

# Останавливаем Django сервер
pkill -f "manage.py.*runserver" 2>/dev/null && print_success "Django сервер остановлен" || print_warning "Django сервер не был запущен"

# Ждем завершения процессов
sleep 2

# Проверяем, что все процессы остановлены
REMAINING_PROCESSES=$(ps aux | grep -E "(celery.*worker|manage.py.*runserver)" | grep -v grep | wc -l)

if [ $REMAINING_PROCESSES -eq 0 ]; then
    print_success "✅ Все сервисы остановлены!"
else
    print_warning "⚠️ Некоторые процессы все еще работают:"
    ps aux | grep -E "(celery.*worker|manage.py.*runserver)" | grep -v grep
    print_warning "Выполните принудительную остановку:"
    print_warning "pkill -9 -f 'celery.*worker'"
    print_warning "pkill -9 -f 'manage.py.*runserver'"
fi

# Очищаем файлы PID
rm -f logs/celery.pid logs/django.pid 2>/dev/null

print_success "Готово! 🛑"


