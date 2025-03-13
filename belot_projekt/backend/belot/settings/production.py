"""
Django postavke za produkcijsko okruženje Belot projekta.

Ove postavke proširuju i modificiraju osnovne postavke iz base.py,
prilagođavajući ih za sigurno, stabilno i optimizirano produkcijsko okruženje.
Uključuju dodatne sigurnosne mjere, optimizacije performansi i postavke
za robusnost aplikacije pri radu s pravim korisnicima.

Za korištenje ovih postavki, postavite environment varijablu:
DJANGO_ENVIRONMENT=production
"""

import os
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa

# Produkcijsko okruženje - debugging isključen
DEBUG = False

# Tajni ključ učitan iz environment varijable
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is missing. Ova postavka je obavezna u produkciji.")

# Dozvoljeni hostovi učitani iz environment varijable
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    raise ImproperlyConfigured("ALLOWED_HOSTS environment variable is missing. Ova postavka je obavezna u produkciji.")

# CORS postavke za produkciju
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
if not CORS_ALLOWED_ORIGINS or CORS_ALLOWED_ORIGINS == ['']:
    CORS_ALLOWED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host != '*']

# Sigurnosne postavke za produkciju
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 godina
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Proxy postavke - pretpostavi da se koristi HTTPS proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Konfiguracija baze podataka za produkciju
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME'),
        'USER': os.environ.get('DATABASE_USER'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
        'HOST': os.environ.get('DATABASE_HOST'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # 10 minuta perzistentne konekcije
        'OPTIONS': {
            'sslmode': 'require',  # Zahtijevaj SSL za konekciju
            'connect_timeout': 10,
        }
    }
}

# Provjera kritičnih postavki baze podataka
if not all([
    DATABASES['default'].get('NAME'),
    DATABASES['default'].get('USER'),
    DATABASES['default'].get('PASSWORD'),
    DATABASES['default'].get('HOST')
]):
    raise ImproperlyConfigured("DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD i DATABASE_HOST environment varijable su obavezne")

# Redis konfiguracija za produkciju
REDIS_HOST = os.environ.get('REDIS_HOST')
if not REDIS_HOST:
    raise ImproperlyConfigured("REDIS_HOST environment varijabla je obavezna")

REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
REDIS_SSL = os.environ.get('REDIS_SSL', 'True').lower() == 'true'

# Redis URL s podrškom za SSL i lozinku
def build_redis_url(db_number):
    """Gradi Redis URL s podrškom za SSL i autentikaciju"""
    scheme = 'rediss' if REDIS_SSL else 'redis'
    auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    return f"{scheme}://{auth}{REDIS_HOST}:{REDIS_PORT}/{db_number}"

# Konfiguracija Channels za produkciju
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [build_redis_url(0)],
            'capacity': 5000,  # Povećan kapacitet za veći broj konekcija
            'expiry': 600,  # 10 minuta TTL za poruke
        },
    },
}

# Cache postavke za produkciju
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': build_redis_url(1),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',  # Kompresija za uštedu memorije
            'IGNORE_EXCEPTIONS': True,  # Nastavi s izvršavanjem ako cache nije dostupan
        },
        'TIMEOUT': 3600,  # 1 sat zadani TTL
        'KEY_PREFIX': 'belot_prod',  # Prefiks za izbjegavanje kolizija
    },
    'throttling': {  # Poseban cache za ograničavanje API zahtjeva
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': build_redis_url(4),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_TIMEOUT': 3,
        },
        'TIMEOUT': 600,  # 10 minuta
        'KEY_PREFIX': 'belot_throttle',
    }
}

# Email postavke za produkciju
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@belot-app.hr')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', 'server@belot-app.hr')

# Celery postavke za produkciju
CELERY_BROKER_URL = build_redis_url(2)
CELERY_RESULT_BACKEND = build_redis_url(3)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,  # 1 sat
    'max_retries': 3,
}
CELERY_TASK_ALWAYS_EAGER = False  # Asinkrono izvršavanje zadataka

# Optimizacija postavki predložaka
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]

# Postavke za statičke datoteke
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = os.environ.get('STATIC_URL', '/static/')

# Konfiguracija za AWS S3 ako se koristi (opcija za produkciju)
if os.environ.get('USE_S3', '').lower() == 'true':
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'eu-central-1')
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com")
    
    # Provjera AWS postavki
    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME]):
        raise ImproperlyConfigured("Za korištenje S3 skladišta, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY i AWS_STORAGE_BUCKET_NAME su obavezne")
    
    # Postavke S3 za sigurnost i performanse
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',  # 1 dan
    }
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False
    
    # Konfiguracija za statičke i medijske datoteke na S3
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
    
    # Dodavanje potrebnog paketa u INSTALLED_APPS
    INSTALLED_APPS += ['storages']

# Postavke za sentry.io praćenje grešaka
if os.environ.get('SENTRY_DSN'):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,  # Uzorkuj 10% transakcija za praćenje performansi
        send_default_pii=False,  # Ne šalji osobne podatke korisnika
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
    )

# Postavke za dodatnu zaštitu pristupa admin sučelju
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/')
if ADMIN_URL != 'admin/':
    # Prilagođavanje URL-a za admin sučelje
    from django.contrib import admin
    admin.site.site_url = f"/{ADMIN_URL}"

# Dodatne sigurnosne postavke
# Ograničenje stope API zahtjeva - strože u produkciji
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': os.environ.get('API_THROTTLE_ANON', '100/day'),
    'user': os.environ.get('API_THROTTLE_USER', '1000/day'),
    'game': os.environ.get('API_THROTTLE_GAME', '5000/day'),  # Posebno ograničenje za API igre
}

# Postavke za Belot igru prilagođene za produkciju
BELOT_GAME.update({
    'INACTIVE_TIMEOUT': int(os.environ.get('BELOT_INACTIVE_TIMEOUT', '300')),  # 5 minuta zadano
    'TURN_TIMEOUT': int(os.environ.get('BELOT_TURN_TIMEOUT', '30')),  # 30 sekundi zadano
    'LOG_GAMES': os.environ.get('BELOT_LOG_GAMES', 'True').lower() == 'true',  # Zapisuj sve igre
})

# Konfiguracija za CDN ako se koristi
if os.environ.get('CDN_ENABLED', '').lower() == 'true':
    STATIC_URL = os.environ.get('CDN_STATIC_URL', STATIC_URL)
    MEDIA_URL = os.environ.get('CDN_MEDIA_URL', MEDIA_URL)
    
    # Postavke za sigurnost CDN-a
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
        if origin.strip()
    ]

# Logiranje
LOGGING['handlers']['file']['level'] = 'ERROR'  # Smanji količinu zapisa u datoteku
LOGGING['handlers']['console']['level'] = 'WARNING'  # Prikaži samo upozorenja i greške

print(f"Belot aplikacija pokrenuta u produkcijskom (production) okruženju")