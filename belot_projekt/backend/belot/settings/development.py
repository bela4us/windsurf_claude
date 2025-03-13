"""
Django postavke za razvojno okruženje Belot projekta.

Ove postavke proširuju i modificiraju osnovne postavke iz base.py,
prilagođavajući ih za lokalno razvojno okruženje. Ovdje su uključene
postavke koje olakšavaju razvoj i debugging, ali NISU namijenjene
za korištenje u produkcijskom okruženju.

Za korištenje ovih postavki, postavite environment varijablu:
DJANGO_ENVIRONMENT=development
"""

from .base import *  # noqa

# SIGURNOSNO UPOZORENJE: Ove postavke nisu namijenjene za produkcijsko okruženje!
DEBUG = True

# Tajni ključ za razvojno okruženje - U produkciji koristiti stvarni tajni ključ!
SECRET_KEY = 'django-insecure-dev-3n2j@)nzoy4*i0*i4@pzjd@16zcxzcy_0zn7dz53z@e#u2c'

# Dozvoljeni hostovi za razvojno okruženje
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Dozvoljeni CORS origins za razvojno okruženje
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Isključivanje određenih sigurnosnih postavki tijekom razvoja
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Konfiguracija baze podataka za razvoj (SQLite za jednostavnost)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Konfiguracija Redis poslužitelja za lokalno razvojno okruženje
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

# Konfiguracija Channels za razvoj
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# Cache postavke za razvoj
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Email backend za razvoj - ispisuje emailove u konzolu
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Celery postavke za razvojno okruženje
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/2'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/2'
CELERY_TASK_ALWAYS_EAGER = True  # Izvršavanje zadataka sinkrono za lakši debugging

# Podešavanje logginga za detaljnije informacije tijekom razvoja
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['belot']['level'] = 'DEBUG'
LOGGING['loggers']['game']['level'] = 'DEBUG'
LOGGING['loggers']['lobby']['level'] = 'DEBUG'

# Dodatne postavke za debugging
INTERNAL_IPS = [
    '127.0.0.1',
]

# Uključivanje Django Debug Toolbar-a ako je instaliran
try:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.common.CommonMiddleware') + 1,
                      'debug_toolbar.middleware.DebugToolbarMiddleware')
except ImportError:
    pass

# Smanjivanje postavki za ograničavanje broja API zahtjeva (throttling)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '1000/day',
    'user': '10000/day'
}

# Postavke za brži rad tijekom razvoja
TEMPLATES[0]['OPTIONS']['debug'] = True
TEMPLATES[0]['APP_DIRS'] = False  # Dodajte ovu liniju
TEMPLATES[0]['OPTIONS']['loaders'] = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
]

# Postavke za Belot igru prilagođene za razvoj
BELOT_GAME['TURN_TIMEOUT'] = 60  # Duži timeout za poteze tijekom razvoja
BELOT_GAME['INACTIVE_TIMEOUT'] = 600  # Duži timeout za neaktivnost tijekom razvoja

# Postavke za testne korisnike
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'belotadmin'
DEFAULT_ADMIN_EMAIL = 'admin@example.com'

# Isključivanje generiranja minificirane verzije CSS i JS datoteka
COMPRESS_ENABLED = False

# Omogućavanje hot reloadinga u React/Vue aplikaciji
WEBPACK_LOADER = {
    'DEFAULT': {
        'CACHE': not DEBUG,
    }
}

print(f"Belot aplikacija pokrenuta u razvojnom (development) okruženju")