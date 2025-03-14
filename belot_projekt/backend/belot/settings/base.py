"""
Osnovne Django postavke za Belot projekt.

Ova datoteka sadrži zajedničke postavke koje se koriste u svim okolinama
(razvoj, produkcija, testiranje). Specifične postavke za pojedine okoline
nalaze se u odgovarajućim datotekama (development.py, production.py, testing.py).

Za više informacija o Django postavkama pogledajte:
https://docs.djangoproject.com/en/4.2/topics/settings/
"""

import os
from pathlib import Path
from utils.decorators import cached_property

# Osnovni direktorij projekta - dvije razine iznad ovog filea
# (belot/settings/base.py -> belot -> backend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Sigurnosni ključ nije definiran ovdje - mora biti postavljen u svakoj okolini
# kako bi se izbjegao rizik od slučajnog korištenja development ključa u produkciji

# SIGURNOSNA UPOZORENJA: Ne pokreći s uključenim debugom u produkciji!
# Ova postavka će biti prepisana u drugim okolinama
DEBUG = False

# Dozvoljeni hostovi - bit će prepisani u drugim okolinama
ALLOWED_HOSTS = []

# Aplikacije definirane u ovom projektu
LOCAL_APPS = [
    'users.apps.UsersConfig',
    'game.apps.GameConfig',
    'lobby.apps.LobbyConfig',
    'stats.apps.StatsConfig',
]

# Aplikacije trećih strana
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'channels',
    'corsheaders',
    'drf_yasg',
    'django_celery_beat',
    'django_celery_results',
]

# Ugrađene Django aplikacije
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Sve instalirane aplikacije
INSTALLED_APPS = LOCAL_APPS + THIRD_PARTY_APPS + DJANGO_APPS

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS - mora biti prije CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'middleware.rate_limiter.RateLimiterMiddleware',  # Vlastiti middleware za ograničenje brzine
    'middleware.request_logger.RequestLoggerMiddleware',  # Logiranje zahtjeva
    'middleware.auth_middleware.TokenAuthMiddleware',  # Token autentikacija
    'middleware.cors_middleware.CORSMiddleware',  # CORS podrška
    'middleware.cors_middleware.SameSiteMiddleware',  # SameSite kolačići
]

# Konfiguracija za routing
ROOT_URLCONF = 'belot.urls'

# Konfiguracija ASGI aplikacije
ASGI_APPLICATION = 'belot.asgi.application'

# Konfiguracija predložaka
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Konfiguracija baze podataka - bit će prepisana u specifičnim okolinama
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME', ''),
        'USER': os.environ.get('DATABASE_USER', ''),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
        'HOST': os.environ.get('DATABASE_HOST', ''),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # 10 minuta
    }
}

# Konfiguracija za Django Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(os.environ.get('REDIS_HOST', 'localhost'), 
                      int(os.environ.get('REDIS_PORT', 6379)))],
        },
    },
}

# Validacija lozinki
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Konfiguracija korisničkog modela
AUTH_USER_MODEL = 'users.User'

# Konfiguracija REST Frameworka
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Konfiguracija CORS-a - bit će prepisana u specifičnim okolinama
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = []

# Konfiguracija cachea
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Konfiguracija sesija
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 sata u sekundama
SESSION_COOKIE_HTTPONLY = True  # Nije dostupno kroz JavaScript

# Sigurnosne postavke - neke će biti prepisane u produkcijskim postavkama
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Internacionalizacija i lokalizacija
LANGUAGE_CODE = 'hr-hr'  # Hrvatski
TIME_ZONE = 'Europe/Zagreb'  # Vremenska zona za Hrvatsku
USE_I18N = True
USE_TZ = True

# Statičke datoteke (CSS, JavaScript, slike)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Medijske datoteke (korisničke slike, itd.)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Stvaranje potrebnih direktorija ako ne postoje
import os
if not os.path.exists(STATIC_ROOT):
    os.makedirs(STATIC_ROOT)
if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT)
if not os.path.exists(os.path.join(BASE_DIR, 'static')):
    os.makedirs(os.path.join(BASE_DIR, 'static'))

# Zadani primarni ključ za modele
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Postavke za e-mail - bit će prepisane u specifičnim okolinama
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@belot-app.hr')

# Logging konfiguracija
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
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'belot.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
        'belot': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'game': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'lobby': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Konstante specifične za Belot igru
BELOT_GAME = {
    'POINTS_TO_WIN': 1001,
    'POINTS_PER_GAME': 162,  # 152 za karte + 10 za zadnji štih
    'MAX_PLAYERS': 4,
    'MAX_ROUNDS': 13,
    'INACTIVE_TIMEOUT': 300,  # 5 minuta neaktivnosti prije automatskog napuštanja igre
    'TURN_TIMEOUT': 30,  # 30 sekundi za odigravanje poteza
}

# Belot specifične postavke koje traži verify_backend.py
BELOT_POINTS_TO_WIN = BELOT_GAME['POINTS_TO_WIN']
BELOT_ROUND_TIMEOUT = BELOT_GAME['MAX_ROUNDS'] * 60  # Pretpostavljeno vrijeme za rundu (u sekundama)
BELOT_MOVE_TIMEOUT = BELOT_GAME['TURN_TIMEOUT']
BELOT_MAX_PLAYERS_PER_GAME = BELOT_GAME['MAX_PLAYERS']

# Postavke za Celery (asinkroni zadaci)
CELERY_BROKER_URL = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/2"
CELERY_RESULT_BACKEND = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/2"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Direktorij za pohranu logova
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)