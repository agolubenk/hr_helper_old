"""
Django settings for hrhelper project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-hrhelper-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Логирование для отладки OAuth
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'apps.accounts.views': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'allauth.socialaccount': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# ALLOWED_HOSTS - для продакшена использовать переменную окружения
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'testserver,127.0.0.1,localhost,hr.sftntx.com,192.168.100.7,*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Приложения проекта
    'apps.accounts',
    'apps.finance',
    'apps.huntflow',
    'apps.gemini',
    'apps.common',
    'apps.interviewers',
    'apps.vacancies',
    'apps.google_oauth',
    'apps.hhru',
    'apps.clickup_int',
    'apps.hiring_plan',
    'apps.company_settings',
    'apps.wiki',
    'apps.reporting',
    'apps.answer_library',
    'django_summernote',  # WYSIWYG редактор для вики
    # Django REST Framework
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    
    # Django Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    
    # Django Celery Beat
    'django_celery_beat',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.common.context_processors.sidebar_menu_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Minsk'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images). Ведущий слэш — абсолютные URL с любого пути.
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Медиа-файлы (загрузки Summernote и др.)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Summernote (WYSIWYG для вики)
SUMMERNOTE_THEME = 'bs4'


def _summernote_upload_to(instance, filename):
    """Путь для загрузок Summernote: media/django-summernote/YYYY-MM-DD/uuid.ext"""
    import uuid
    from datetime import datetime
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    name = f'{uuid.uuid4().hex}.{ext}'
    today = datetime.now().strftime('%Y-%m-%d')
    return f'django-summernote/{today}/{name}'


SUMMERNOTE_CONFIG = {
    'iframe': True,
    'summernote': {
        'width': '100%',
        'height': '400',
        'toolbar': [
            ['style', ['style']],
            ['font', ['bold', 'italic', 'underline', 'clear']],
            ['fontname', ['fontname']],
            ['color', ['color']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['table', ['table']],
            ['insert', ['link', 'picture']],
            ['view', ['fullscreen', 'codeview', 'help']],
        ],
    },
    'attachment_require_authentication': True,
    'disable_attachment': False,
    'attachment_upload_to': _summernote_upload_to,
    'attachment_filesize_limit': 5 * 1024 * 1024,  # 5 МБ
    'attachment_absolute_uri': True,
    'test_func_upload_view': lambda request: request.user.is_authenticated,
}


# Создаём каталоги для загрузок Summernote при старте (избегаем IOError при сохранении)
try:
    _summernote_dir = MEDIA_ROOT / 'django-summernote'
    _summernote_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Настройки для массовых операций в Django Admin
# Увеличиваем лимит количества полей в POST запросе для массового удаления
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100000

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Django Auth настройки
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_REDIRECT_URL = '/google-oauth/chat/'
LOGIN_URL = '/accounts/login/'
LOGOUT_URL = '/accounts/logout/'

# Google OAuth — явные значения по умолчанию (env переопределяет; пустая строка в env тоже заменяется на default)
_GOOGLE_CLIENT_ID = '968014303116-vtqq5f39tkaningitmj3dbq25snnmdgp.apps.googleusercontent.com'
_GOOGLE_CLIENT_SECRET = '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'
_GOOGLE_REDIRECT_URI = 'https://hr.sftntx.com/google-oauth/callback/'
GOOGLE_OAUTH2_CLIENT_ID = (os.environ.get('GOOGLE_OAUTH2_CLIENT_ID') or _GOOGLE_CLIENT_ID)
GOOGLE_OAUTH2_CLIENT_SECRET = (os.environ.get('GOOGLE_OAUTH2_CLIENT_SECRET') or _GOOGLE_CLIENT_SECRET)
GOOGLE_OAUTH_REDIRECT_URI = (os.environ.get('GOOGLE_OAUTH_REDIRECT_URI') or _GOOGLE_REDIRECT_URI)
# Список для client_config: первый — активный redirect (должен совпадать с GOOGLE_OAUTH_REDIRECT_URI в Google Console)
_GOOGLE_OAUTH_REDIRECT_URIS_EXTRA = [
    'https://hr.sftntx.com/google-automation/oauth/callback/',
    'https://hr.sftntx.com/auth/google/login/callback/',
    'http://localhost:8000/google-oauth/callback/',
    'http://127.0.0.1:8000/google-oauth/callback/',
]
GOOGLE_OAUTH_REDIRECT_URIS = [GOOGLE_OAUTH_REDIRECT_URI] + [
    u for u in _GOOGLE_OAUTH_REDIRECT_URIS_EXTRA if u != GOOGLE_OAUTH_REDIRECT_URI
]

# Redis настройки для кэширования
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Настройки кэширования API данных
API_CACHE_TIMEOUT = {
    'google_calendar_events': 180,       # 3 минуты
    'slot_events_both_variants': 180,   # 3 минуты — слоты для обоих вариантов настройки «игнорировать не принятые»
    'google_drive_files': 600,          # 10 минут
    'google_sheets': 600,               # 10 минут
    'huntflow_candidates': 100,         # 
    'huntflow_vacancies': 14400,        # 4 часа
    'huntflow_accounts': 43200,         # 12 часов
}

# Celery настройки
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'  # Используем стандартную базу Redis
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Применяем настройки к дефолтному экземпляру Celery
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Импортируем и настраиваем Celery
try:
    from celery import current_app
    current_app.conf.update(
        broker_url=CELERY_BROKER_URL,
        result_backend=CELERY_RESULT_BACKEND,
        accept_content=CELERY_ACCEPT_CONTENT,
        task_serializer=CELERY_TASK_SERIALIZER,
        result_serializer=CELERY_RESULT_SERIALIZER,
        timezone=CELERY_TIMEZONE,
        enable_utc=CELERY_ENABLE_UTC,
    )
except ImportError:
    pass

# Настройки для ClickUp массового импорта
# CELERY_TASK_ROUTES = {
#     'apps.clickup_int.tasks.bulk_import_clickup_tasks': {'queue': 'clickup_import'},
#     'apps.clickup_int.tasks.import_single_task': {'queue': 'clickup_import'},
# }


# Notion API настройки
NOTION_VERSION = '2022-06-28'

# Django REST Framework настройки
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# CORS настройки
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Django dev server
    "http://127.0.0.1:8000",
    "https://hr.sftntx.com",  # Production frontend
]
# Запросы из Chrome-расширения (HRHelper LinkedIn → Huntflow); ID может отличаться при загрузке unpacked
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^chrome-extension://[a-z]{32}$",  # стандартный ID расширения
]

# Django Allauth настройки
SITE_ID = 1

# Настройки allauth (обновленные)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_UNIQUE_EMAIL = True

# Настройки Google OAuth через allauth
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets',
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline',
            'prompt': 'consent',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}

# Настройки для автоматического создания пользователей через социальные аккаунты
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_QUERY_EMAIL = True

# Адаптеры для allauth
ACCOUNT_ADAPTER = 'apps.accounts.logic.auth_adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.accounts.logic.auth_adapters.CustomSocialAccountAdapter'

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Только для разработки

# HeadHunter.ru OAuth (опционально: задать в .env для предзаполнения конфигурации)
HH_RU_CLIENT_ID = os.environ.get('HH_RU_CLIENT_ID', '')
HH_RU_CLIENT_SECRET = os.environ.get('HH_RU_CLIENT_SECRET', '')
HH_RU_REDIRECT_URI = os.environ.get('HH_RU_REDIRECT_URI', '')