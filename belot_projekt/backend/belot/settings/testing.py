"""
Django postavke za testno okruženje Belot projekta.

Ove postavke proširuju i modificiraju osnovne postavke iz base.py,
prilagođavajući ih za brzo i pouzdano izvođenje automatiziranih testova.
Fokus je na brzini izvođenja testova i izolaciji od vanjskih servisa.

Za korištenje ovih postavki, postavite environment varijablu:
DJANGO_ENVIRONMENT=testing
"""

import os
from .base import *  # noqa

# Postavke za testiranje - debugging isključen da bi testovi bili realniji
DEBUG = False

# Tajni ključ za testno okruženje
SECRET_KEY = 'django-insecure-test-key-not-for-production-use-only-for-testing'

# Dozvoljeni hostovi za testno okruženje
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Postavke baze podataka - koristi SQLite u memoriji za brzo izvođenje testova
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Koristi bazu u memoriji za maksimalnu brzinu
    }
}

# Korištenje brže implementacije hashiranja lozinki za testove
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Isključivanje middleware komponenti koje nisu esencijalne za testove
MIDDLEWARE = [m for m in MIDDLEWARE if m not in [
    'middleware.rate_limiter.RateLimiterMiddleware',  # Isključi rate limiting
]]

# Konfiguracija testnog email backeenda
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Isključivanje CSRF provjere za testove
CSRF_VERIFY = False

# Postavke za keširanje - koristi dummy (nepostojeći) keš za testove
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Postavke za Channels - koristi in-memory backend za testove
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Celery postavke za testiranje - izvršavanje zadataka sinkrono
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Postavke za testni runner
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Konfiguracija medijskih datoteka za testiranje
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')
STATIC_ROOT = os.path.join(BASE_DIR, 'test_static')

# Postavke za logiranje - smanji logiranje tijekom testova
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,  # Isključi većinu logginga
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        # Utišaj Django logiranje
        'django': {
            'handlers': ['null'],
            'propagate': False,
        },
        # Utišaj logiranje aplikacije
        'belot': {
            'handlers': ['null'],
            'propagate': False,
        },
        'game': {
            'handlers': ['null'],
            'propagate': False,
        },
        'lobby': {
            'handlers': ['null'],
            'propagate': False,
        },
    },
}

# Onemogući razne sigurnosne provjere koje usporavaju testove
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Postavke za Belot igru prilagođene za testiranje
BELOT_GAME.update({
    'TURN_TIMEOUT': 1,        # Brzi timeoutovi za testove
    'INACTIVE_TIMEOUT': 1,    # Brzi timeoutovi za testove
})

# REST Framework postavke za testiranje
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'TEST_REQUEST_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# Konfiguracija stalne direktne veze s bazom podataka za testove
DATABASES['default']['ATOMIC_REQUESTS'] = True

# Postavke za testne korisnike
TEST_ADMIN_USERNAME = 'admin'
TEST_ADMIN_PASSWORD = 'admin'
TEST_ADMIN_EMAIL = 'admin@example.com'

TEST_USER1_USERNAME = 'user1'
TEST_USER1_PASSWORD = 'user1pass'
TEST_USER1_EMAIL = 'user1@example.com'

TEST_USER2_USERNAME = 'user2'
TEST_USER2_PASSWORD = 'user2pass'
TEST_USER2_EMAIL = 'user2@example.com'

# Postavke za testiranje transakcija i izolacije
DATABASES['default']['OPTIONS'] = {'isolation_level': 'SERIALIZABLE'}

print(f"Belot aplikacija pokrenuta u testnom (testing) okruženju")