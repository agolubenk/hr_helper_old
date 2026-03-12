#!/bin/bash

# 📊 Скрипт мониторинга системы
# Автор: AI Assistant
# Дата: $(date)

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_metric() {
    echo -e "${CYAN}[METRIC]${NC} $1"
}

# Переменные
BASE_URL="http://127.0.0.1:8000"
LOG_FILE="monitoring_$(date +%Y%m%d_%H%M%S).log"
INTERVAL=30  # Интервал проверки в секундах

# Функция проверки здоровья системы
check_health() {
    log_info "Проверка здоровья системы..."
    
    # Проверка Django
    if python3 manage.py check --deploy > /dev/null 2>&1; then
        log_success "Django: ✅ Здоров"
    else
        log_error "Django: ❌ Ошибки"
        return 1
    fi
    
    # Проверка сервера
    if curl -s "$BASE_URL/" > /dev/null; then
        log_success "Сервер: ✅ Работает"
    else
        log_error "Сервер: ❌ Недоступен"
        return 1
    fi
    
    # Проверка API endpoints
    check_api_endpoints
    
    # Проверка производительности
    check_performance
    
    return 0
}

# Функция проверки API endpoints
check_api_endpoints() {
    log_info "Проверка API endpoints..."
    
    ENDPOINTS=(
        "finance/grades"
        "vacancies/vacancies"
        "huntflow/cache"
        "gemini/chat-sessions"
        "accounts/users"
    )
    
    for endpoint in "${ENDPOINTS[@]}"; do
        response_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/$endpoint/")
        
        if [ "$response_code" = "401" ] || [ "$response_code" = "403" ]; then
            log_success "API $endpoint: ✅ Доступен (код: $response_code)"
        elif [ "$response_code" = "200" ]; then
            log_success "API $endpoint: ✅ Работает (код: $response_code)"
        else
            log_warning "API $endpoint: ⚠️ Неожиданный код: $response_code"
        fi
    done
}

# Функция проверки производительности
check_performance() {
    log_info "Проверка производительности..."
    
    # Проверка времени отклика API
    start_time=$(date +%s.%N)
    curl -s "$BASE_URL/api/v1/finance/grades/" > /dev/null
    end_time=$(date +%s.%N)
    
    response_time=$(echo "$end_time - $start_time" | bc)
    response_time_ms=$(echo "$response_time * 1000" | bc)
    
    if (( $(echo "$response_time_ms < 500" | bc -l) )); then
        log_success "Время отклика API: ✅ ${response_time_ms}ms (отлично)"
    elif (( $(echo "$response_time_ms < 1000" | bc -l) )); then
        log_warning "Время отклика API: ⚠️ ${response_time_ms}ms (приемлемо)"
    else
        log_error "Время отклика API: ❌ ${response_time_ms}ms (медленно)"
    fi
    
    # Проверка использования ресурсов
    check_system_resources
}

# Функция проверки системных ресурсов
check_system_resources() {
    # CPU
    cpu_usage=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')
    if (( $(echo "$cpu_usage < 80" | bc -l) )); then
        log_success "CPU: ✅ ${cpu_usage}% (норма)"
    else
        log_warning "CPU: ⚠️ ${cpu_usage}% (высокая нагрузка)"
    fi
    
    # Память
    memory_info=$(python3 -c "
import psutil
mem = psutil.virtual_memory()
print(f'{mem.percent:.1f}')
")
    
    if (( $(echo "$memory_info < 85" | bc -l) )); then
        log_success "Память: ✅ ${memory_info}% (норма)"
    else
        log_warning "Память: ⚠️ ${memory_info}% (много используется)"
    fi
    
    # Диск
    disk_info=$(python3 -c "
import psutil
disk = psutil.disk_usage('/')
print(f'{disk.percent:.1f}')
")
    
    if (( $(echo "$disk_info < 90" | bc -l) )); then
        log_success "Диск: ✅ ${disk_info}% (норма)"
    else
        log_warning "Диск: ⚠️ ${disk_info}% (мало места)"
    fi
}

# Функция проверки логов на ошибки
check_logs() {
    log_info "Проверка логов на ошибки..."
    
    # Поиск ошибок в Django логах
    if [ -f "server.log" ]; then
        error_count=$(grep -i "error\|exception\|traceback" server.log | wc -l)
        if [ "$error_count" -eq 0 ]; then
            log_success "Django логи: ✅ Ошибок не найдено"
        else
            log_warning "Django логи: ⚠️ Найдено $error_count ошибок"
            
            # Показать последние ошибки
            log_info "Последние ошибки:"
            grep -i "error\|exception\|traceback" server.log | tail -3
        fi
    fi
    
    # Поиск ошибок в системных логах
    if [ -f "logs/django.log" ]; then
        error_count=$(grep -i "error\|exception\|traceback" logs/django.log | wc -l)
        if [ "$error_count" -eq 0 ]; then
            log_success "Системные логи: ✅ Ошибок не найдено"
        else
            log_warning "Системные логи: ⚠️ Найдено $error_count ошибок"
        fi
    fi
}

# Функция проверки модулей logic
check_logic_modules() {
    log_info "Проверка logic модулей..."
    
    MODULES=(
        "logic.base.api_client"
        "logic.base.response_handler"
        "logic.integration.shared.candidate_operations"
        "logic.integration.shared.gemini_operations"
        "logic.utilities.common_api"
    )
    
    healthy_count=0
    total_count=${#MODULES[@]}
    
    for module in "${MODULES[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            log_success "Модуль $module: ✅ Импортируется"
            ((healthy_count++))
        else
            log_error "Модуль $module: ❌ Ошибка импорта"
        fi
    done
    
    log_metric "Logic модули: $healthy_count/$total_count здоровы"
}

# Функция непрерывного мониторинга
continuous_monitor() {
    log_info "Запуск непрерывного мониторинга (интервал: ${INTERVAL}с)..."
    log_info "Для остановки нажмите Ctrl+C"
    
    while true; do
        echo ""
        echo "=========================================="
        echo "Мониторинг: $(date)"
        echo "=========================================="
        
        check_health
        check_logs
        check_logic_modules
        
        echo ""
        log_info "Следующая проверка через $INTERVAL секунд..."
        sleep $INTERVAL
    done
}

# Функция генерации отчета
generate_report() {
    log_info "Генерация отчета о состоянии системы..."
    
    REPORT_FILE="system_report_$(date +%Y%m%d_%H%M%S).txt"
    
    {
        echo "=========================================="
        echo "ОТЧЕТ О СОСТОЯНИИ СИСТЕМЫ"
        echo "=========================================="
        echo "Дата: $(date)"
        echo ""
        
        echo "1. ЗДОРОВЬЕ СИСТЕМЫ:"
        if check_health; then
            echo "   ✅ Система здорова"
        else
            echo "   ❌ Обнаружены проблемы"
        fi
        echo ""
        
        echo "2. API ENDPOINTS:"
        check_api_endpoints
        echo ""
        
        echo "3. ПРОИЗВОДИТЕЛЬНОСТЬ:"
        check_performance
        echo ""
        
        echo "4. ЛОГИ:"
        check_logs
        echo ""
        
        echo "5. LOGIC МОДУЛИ:"
        check_logic_modules
        echo ""
        
        echo "=========================================="
        echo "ОТЧЕТ ЗАВЕРШЕН"
        echo "=========================================="
        
    } > "$REPORT_FILE"
    
    log_success "Отчет сохранен: $REPORT_FILE"
}

# Функция быстрой проверки
quick_check() {
    log_info "Быстрая проверка системы..."
    
    # Проверка Django
    if python3 manage.py check --deploy > /dev/null 2>&1; then
        echo "Django: ✅"
    else
        echo "Django: ❌"
        return 1
    fi
    
    # Проверка сервера
    if curl -s "$BASE_URL/" > /dev/null; then
        echo "Сервер: ✅"
    else
        echo "Сервер: ❌"
        return 1
    fi
    
    # Проверка API
    response_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/finance/grades/")
    if [ "$response_code" = "401" ] || [ "$response_code" = "403" ]; then
        echo "API: ✅"
    else
        echo "API: ❌ (код: $response_code)"
        return 1
    fi
    
    log_success "Быстрая проверка пройдена"
}

# Обработка аргументов командной строки
case "${1:-quick}" in
    "quick")
        quick_check
        ;;
    "full")
        check_health
        check_logs
        check_logic_modules
        ;;
    "continuous")
        continuous_monitor
        ;;
    "report")
        generate_report
        ;;
    "health")
        check_health
        ;;
    "performance")
        check_performance
        ;;
    "logs")
        check_logs
        ;;
    "modules")
        check_logic_modules
        ;;
    *)
        echo "Использование: $0 {quick|full|continuous|report|health|performance|logs|modules}"
        echo ""
        echo "Команды:"
        echo "  quick       - Быстрая проверка основных компонентов"
        echo "  full        - Полная проверка системы"
        echo "  continuous  - Непрерывный мониторинг"
        echo "  report      - Генерация отчета"
        echo "  health      - Проверка здоровья системы"
        echo "  performance - Проверка производительности"
        echo "  logs        - Проверка логов"
        echo "  modules     - Проверка logic модулей"
        exit 1
        ;;
esac

