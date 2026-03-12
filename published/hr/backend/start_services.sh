#!/bin/bash

# 🚀 Скрипт для автоматического запуска всех сервисов HR Helper
# Использование: ./start_services.sh

set -e  # Останавливаем выполнение при ошибке

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

# Проверяем, что мы в правильной директории
if [ ! -f "manage.py" ]; then
    print_error "Скрипт должен быть запущен из папки backend!"
    print_error "Текущая директория: $(pwd)"
    exit 1
fi

# Получаем абсолютный путь к backend
BACKEND_DIR=$(pwd)
PYTHONPATH=$BACKEND_DIR

print_status "Запуск HR Helper сервисов..."
print_status "Backend директория: $BACKEND_DIR"

# Проверяем виртуальное окружение
if [ ! -d "venv" ]; then
    print_error "Виртуальное окружение не найдено!"
    print_error "Создайте его командой: python3 -m venv venv"
    exit 1
fi

# Активируем виртуальное окружение
print_status "Активация виртуального окружения..."
source venv/bin/activate

# Проверяем зависимости
print_status "Проверка зависимостей..."
if ! python -c "import django, celery, redis" 2>/dev/null; then
    print_error "Не все зависимости установлены!"
    print_error "Выполните: pip install -r requirements.txt"
    exit 1
fi

# Проверяем Redis
print_status "Проверка Redis..."
if ! redis-cli ping >/dev/null 2>&1; then
    print_warning "Redis не запущен, пытаемся запустить..."
    
    # Пытаемся запустить Redis в зависимости от ОС
    if command -v brew >/dev/null 2>&1; then
        # macOS
        brew services start redis
    elif command -v systemctl >/dev/null 2>&1; then
        # Linux
        sudo systemctl start redis-server
    else
        print_error "Не удалось определить способ запуска Redis"
        print_error "Запустите Redis вручную и повторите попытку"
        exit 1
    fi
    
    # Ждем запуска Redis
    sleep 3
    
    if ! redis-cli ping >/dev/null 2>&1; then
        print_error "Redis не запустился!"
        exit 1
    fi
fi

print_success "Redis работает!"

# Проверяем миграции
print_status "Проверка миграций базы данных..."
python3 manage.py migrate --check >/dev/null 2>&1 || {
    print_warning "Применяем миграции..."
    python3 manage.py migrate
}

# Останавливаем старые процессы
print_status "Остановка старых процессов..."
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "manage.py.*runserver" 2>/dev/null || true
sleep 2

# Создаем папку для логов
mkdir -p logs

# Запускаем Celery Worker в фоне
print_status "Запуск Celery Worker..."
nohup celery -A config worker --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > logs/celery.pid

# Ждем запуска Celery
sleep 3

# Проверяем, что Celery запустился
if ! kill -0 $CELERY_PID 2>/dev/null; then
    print_error "Celery Worker не запустился!"
    print_error "Проверьте логи: tail -f logs/celery.log"
    exit 1
fi

print_success "Celery Worker запущен (PID: $CELERY_PID)!"

# Запускаем Django сервер
print_status "Запуск Django сервера..."
nohup python3 manage.py runserver 8000 --insecure > logs/django.log 2>&1 &
DJANGO_PID=$!
echo $DJANGO_PID > logs/django.pid

# Ждем запуска Django
sleep 3

# Проверяем, что Django запустился
if ! kill -0 $DJANGO_PID 2>/dev/null; then
    print_error "Django сервер не запустился!"
    print_error "Проверьте логи: tail -f logs/django.log"
    kill $CELERY_PID 2>/dev/null || true
    exit 1
fi

print_success "Django сервер запущен (PID: $DJANGO_PID)!"

# Финальная проверка
print_status "Проверка всех сервисов..."
sleep 2

# Проверяем Redis
if redis-cli ping >/dev/null 2>&1; then
    print_success "✅ Redis работает"
else
    print_error "❌ Redis не работает"
fi

# Проверяем Celery
if kill -0 $CELERY_PID 2>/dev/null; then
    print_success "✅ Celery Worker работает (PID: $CELERY_PID)"
else
    print_error "❌ Celery Worker не работает"
fi

# Проверяем Django
if kill -0 $DJANGO_PID 2>/dev/null; then
    print_success "✅ Django сервер работает (PID: $DJANGO_PID)"
else
    print_error "❌ Django сервер не работает"
fi

# Проверяем HTTP доступность
if curl -s http://127.0.0.1:8000/ >/dev/null 2>&1; then
    print_success "✅ Веб-интерфейс доступен"
else
    print_warning "⚠️ Веб-интерфейс пока недоступен (возможно, еще загружается)"
fi

echo ""
print_success "🎉 Все сервисы запущены!"
echo ""
echo -e "${BLUE}📋 Информация о сервисах:${NC}"
echo -e "  • Веб-интерфейс: ${GREEN}http://127.0.0.1:8000/${NC}"
echo -e "  • Админка: ${GREEN}http://127.0.0.1:8000/admin/${NC}"
echo -e "  • ClickUp импорт: ${GREEN}http://127.0.0.1:8000/clickup/bulk-import/${NC}"
echo ""
echo -e "${BLUE}📁 Логи:${NC}"
echo -e "  • Django: ${YELLOW}tail -f logs/django.log${NC}"
echo -e "  • Celery: ${YELLOW}tail -f logs/celery.log${NC}"
echo ""
echo -e "${BLUE}🛑 Остановка сервисов:${NC}"
echo -e "  • Выполните: ${YELLOW}./stop_services.sh${NC}"
echo -e "  • Или вручную: ${YELLOW}kill $CELERY_PID $DJANGO_PID${NC}"
echo ""

# Сохраняем PIDs для остановки
echo "$CELERY_PID $DJANGO_PID" > logs/services.pid

print_success "Готово к работе! 🚀"


