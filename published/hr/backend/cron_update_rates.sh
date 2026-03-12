#!/bin/bash
# Скрипт для автоматического обновления курсов валют НБРБ
# Рекомендуется добавить в cron: 5 18 * * * /path/to/backend/cron_update_rates.sh

cd "$(dirname "$0")"
source venv/bin/activate
python3 manage.py update_nbrb_rates >> logs/nbrb_update.log 2>&1
