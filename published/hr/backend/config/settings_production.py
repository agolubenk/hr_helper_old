"""Настройки для продакшена"""
import os
from .settings import *

# Google OAuth — явно задаём для прода (env переопределяет; без env используются те же defaults)
GOOGLE_OAUTH2_CLIENT_ID = os.environ.get('GOOGLE_OAUTH2_CLIENT_ID') or '968014303116-vtqq5f39tkaningitmj3dbq25snnmdgp.apps.googleusercontent.com'
GOOGLE_OAUTH2_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH2_CLIENT_SECRET') or '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'
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI') or 'https://hr.sftntx.com/google-oauth/callback/'
_EXTRA = [
    'https://hr.sftntx.com/google-automation/oauth/callback/',
    'https://hr.sftntx.com/auth/google/login/callback/',
    'http://localhost:8000/google-oauth/callback/',
    'http://127.0.0.1:8000/google-oauth/callback/',
]
GOOGLE_OAUTH_REDIRECT_URIS = [GOOGLE_OAUTH_REDIRECT_URI] + [u for u in _EXTRA if u != GOOGLE_OAUTH_REDIRECT_URI]

# Режим отладки
DEBUG = False

# Разрешенные хосты (IP сервера добавлен, чтобы запросы по IP не вызывали DisallowedHost)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,hr.sftntx.com,89.167.20.136').split(',') if h.strip()]

# Безопасность
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# SSL обрабатывается Cloudflare, не редиректим на HTTPS
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ['https://hr.sftntx.com']

# База данных для продакшена
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'hrhelper'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Логирование (docker logs собирает stdout/stderr)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'logic': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Статические файлы (абсолютный URL, чтобы картинки грузились с любого пути)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Медиа файлы
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Кэширование
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}

# Email настройки
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Celery настройки
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')

# CORS настройки для Chrome расширения
# Extension ID для Chrome расширения LinkedIn → Huntflow
# Получите ID после установки расширения из chrome://extensions/
CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID', '')

# Обновляем CORS_ALLOWED_ORIGINS из базовых настроек
if CHROME_EXTENSION_ID:
    # Добавляем Chrome расширение в разрешенные источники
    CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS + [
        f"chrome-extension://{CHROME_EXTENSION_ID}",
    ]
    # Или разрешить все расширения (менее безопасно, но проще для разработки):
    # CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS + [
    #     "chrome-extension://*",
    # ]

# Убеждаемся, что credentials разрешены для расширения
CORS_ALLOW_CREDENTIALS = True

# API настройки
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
