#!/bin/bash

# Скрипт для обновления manifest.json с продакшен доменом
# Использование: ./update_manifest.sh https://your-domain.com

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}❌ Ошибка: не указан домен${NC}"
    echo -e "${YELLOW}Использование:${NC} $0 https://your-domain.com"
    echo -e "${YELLOW}Пример:${NC} $0 https://hrhelper.example.com"
    exit 1
fi

DOMAIN="$1"
MANIFEST_FILE="manifest.json"

# Проверка формата URL
if [[ ! "$DOMAIN" =~ ^https?:// ]]; then
    echo -e "${YELLOW}⚠️  Предупреждение: домен должен начинаться с http:// или https://${NC}"
    echo -e "${BLUE}💡 Добавляю https:// автоматически...${NC}"
    DOMAIN="https://${DOMAIN}"
fi

# Убираем слеш в конце
DOMAIN=$(echo "$DOMAIN" | sed 's|/$||')

# Проверка существования manifest.json
if [ ! -f "$MANIFEST_FILE" ]; then
    echo -e "${RED}❌ Ошибка: файл $MANIFEST_FILE не найден${NC}"
    exit 1
fi

echo -e "${BLUE}🔧 Обновление manifest.json...${NC}"
echo -e "${BLUE}Домен: ${GREEN}$DOMAIN${NC}"

# Создаем резервную копию
cp "$MANIFEST_FILE" "${MANIFEST_FILE}.bak"
echo -e "${YELLOW}📦 Создана резервная копия: ${MANIFEST_FILE}.bak${NC}"

# Обновляем host_permissions
# Используем Python для более надежного парсинга JSON
python3 << EOF
import json
import sys

manifest_file = "$MANIFEST_FILE"
domain = "$DOMAIN"

try:
    # Читаем manifest.json
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    # Получаем host_permissions
    host_permissions = manifest.get('host_permissions', [])
    
    # Удаляем старые продакшен домены (если есть)
    host_permissions = [
        perm for perm in host_permissions 
        if not (perm.startswith('https://') and 'localhost' not in perm and '127.0.0.1' not in perm)
    ]
    
    # Добавляем новый домен
    domain_pattern = f"{domain}/*"
    if domain_pattern not in host_permissions:
        host_permissions.append(domain_pattern)
        print(f"✅ Добавлен домен: {domain_pattern}")
    else:
        print(f"ℹ️  Домен уже присутствует: {domain_pattern}")
    
    # Обновляем manifest
    manifest['host_permissions'] = sorted(host_permissions)
    
    # Сохраняем
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"✅ manifest.json обновлен успешно!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Готово!${NC}"
    echo -e "${BLUE}📋 Проверьте обновленный файл: ${MANIFEST_FILE}${NC}"
    echo ""
    echo -e "${YELLOW}Следующие шаги:${NC}"
    echo -e "1. Проверьте manifest.json"
    echo -e "2. Установите расширение в Chrome"
    echo -e "3. Получите Extension ID из chrome://extensions/"
    echo -e "4. Настройте CORS на сервере с Extension ID"
else
    echo -e "${RED}❌ Ошибка при обновлении${NC}"
    # Восстанавливаем из резервной копии
    if [ -f "${MANIFEST_FILE}.bak" ]; then
        mv "${MANIFEST_FILE}.bak" "$MANIFEST_FILE"
        echo -e "${YELLOW}📦 Восстановлен из резервной копии${NC}"
    fi
    exit 1
fi
