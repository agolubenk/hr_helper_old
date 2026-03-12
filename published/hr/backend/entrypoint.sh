#!/bin/sh
set -e
# При монтировании volume staticfiles:/app/staticfiles образ перекрывается пустым volume.
# Собираем статику в volume при каждом старте и даём права пользователю приложения.
if ! python manage.py collectstatic --noinput --settings=config.settings_production; then
    echo " [entrypoint] WARN: collectstatic failed, continuing (run manually: python manage.py collectstatic --noinput)" >&2
fi
chown -R hrhelper:hrhelper /app/staticfiles 2>/dev/null || true

# Каталог для загрузок Summernote (вики): создаём и даём права hrhelper, иначе "Failed to save attachment"
mkdir -p /app/media/django-summernote
chown -R hrhelper:hrhelper /app/media
chmod -R 755 /app/media

exec gosu hrhelper "$@"
