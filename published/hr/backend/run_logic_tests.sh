#!/bin/bash

# 🧪 Скрипт для запуска тестов logic модулей
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
TEST_DIR="logic/tests"
COVERAGE_DIR="htmlcov"
COVERAGE_REPORT="coverage_report.txt"

# Функция запуска всех тестов
run_all_tests() {
    log_info "Запуск всех тестов logic модулей..."
    
    cd "$TEST_DIR"
    
    # Запуск тестов с подробным выводом
    python3 -m unittest discover -v -s . -p "test_*.py"
    
    if [ $? -eq 0 ]; then
        log_success "Все тесты прошли успешно!"
        return 0
    else
        log_error "Некоторые тесты провалились!"
        return 1
    fi
}

# Функция запуска конкретного теста
run_specific_test() {
    local test_file="$1"
    
    if [ -z "$test_file" ]; then
        log_error "Не указан файл теста"
        return 1
    fi
    
    if [ ! -f "$TEST_DIR/$test_file" ]; then
        log_error "Файл теста не найден: $TEST_DIR/$test_file"
        return 1
    fi
    
    log_info "Запуск теста: $test_file"
    
    cd "$TEST_DIR"
    python3 -m unittest "$test_file" -v
    
    if [ $? -eq 0 ]; then
        log_success "Тест $test_file прошел успешно!"
        return 0
    else
        log_error "Тест $test_file провалился!"
        return 1
    fi
}

# Функция запуска тестов с покрытием
run_tests_with_coverage() {
    log_info "Запуск тестов с проверкой покрытия кода..."
    
    # Проверяем установлен ли coverage
    if ! command -v coverage &> /dev/null; then
        log_warning "coverage не установлен. Устанавливаем..."
        pip3 install coverage
    fi
    
    # Создаем директорию для отчетов
    mkdir -p "$COVERAGE_DIR"
    
    cd "$TEST_DIR"
    
    # Запуск тестов с покрытием
    coverage run --source=../../logic -m unittest discover -v -s . -p "test_*.py"
    
    if [ $? -eq 0 ]; then
        log_success "Все тесты прошли успешно!"
        
        # Генерация отчета
        log_info "Генерация отчета о покрытии..."
        coverage report > "../../$COVERAGE_REPORT"
        coverage html -d "../../$COVERAGE_DIR"
        
        # Вывод краткого отчета
        log_info "Отчет о покрытии:"
        coverage report
        
        log_success "Отчет о покрытии создан в $COVERAGE_DIR/"
        return 0
    else
        log_error "Некоторые тесты провалились!"
        return 1
    fi
}

# Функция запуска быстрых тестов
run_quick_tests() {
    log_info "Запуск быстрых тестов (без покрытия)..."
    
    cd "$TEST_DIR"
    
    # Запуск только основных тестов
    python3 -m unittest test_base.py test_response_handler.py -v
    
    if [ $? -eq 0 ]; then
        log_success "Быстрые тесты прошли успешно!"
        return 0
    else
        log_error "Быстрые тесты провалились!"
        return 1
    fi
}

# Функция проверки структуры тестов
check_test_structure() {
    log_info "Проверка структуры тестов..."
    
    # Проверяем наличие всех файлов тестов
    test_files=(
        "test_base.py"
        "test_api_client.py"
        "test_response_handler.py"
        "test_exceptions.py"
        "test_shared_modules.py"
        "test_integration.py"
    )
    
    missing_files=()
    
    for file in "${test_files[@]}"; do
        if [ ! -f "$TEST_DIR/$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        log_success "Все файлы тестов найдены"
        return 0
    else
        log_error "Отсутствуют файлы тестов:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        return 1
    fi
}

# Функция очистки результатов тестов
cleanup_test_results() {
    log_info "Очистка результатов тестов..."
    
    # Удаляем файлы покрытия
    rm -rf "$COVERAGE_DIR"
    rm -f "$COVERAGE_REPORT"
    rm -f ".coverage"
    rm -f "coverage.xml"
    
    # Удаляем временные файлы Python
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Результаты тестов очищены"
}

# Функция показа справки
show_help() {
    echo "Использование: $0 {all|specific|coverage|quick|check|cleanup|help}"
    echo ""
    echo "Команды:"
    echo "  all <file>     - Запустить все тесты"
    echo "  specific <file> - Запустить конкретный тест"
    echo "  coverage       - Запустить тесты с покрытием кода"
    echo "  quick          - Запустить быстрые тесты"
    echo "  check          - Проверить структуру тестов"
    echo "  cleanup        - Очистить результаты тестов"
    echo "  help           - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 all"
    echo "  $0 specific test_api_client.py"
    echo "  $0 coverage"
    echo "  $0 quick"
}

# Основная логика
case "${1:-all}" in
    "all")
        run_all_tests
        ;;
    "specific")
        run_specific_test "$2"
        ;;
    "coverage")
        run_tests_with_coverage
        ;;
    "quick")
        run_quick_tests
        ;;
    "check")
        check_test_structure
        ;;
    "cleanup")
        cleanup_test_results
        ;;
    "help")
        show_help
        ;;
    *)
        echo "Неизвестная команда: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

