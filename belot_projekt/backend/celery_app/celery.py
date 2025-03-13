"""
Konfiguracija Celery-a za Belot aplikaciju.

Ovaj modul sadrži osnovnu konfiguraciju Celery instance koja se koristi
za asinkronu obradu zadataka u Belot aplikaciji. Ovdje se definiraju
postavke poput brokera, rezultata, rasporeda zadataka i drugo.
"""

import os
from celery import Celery
from django.conf import settings

# Postavljanje zadane Django postavke okoline
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')

# Stvaranje Celery instance
app = Celery('belot')

# Konfiguracija Celery-a pomoću postavki iz Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatsko učitavanje zadataka iz svih instaliranih aplikacija
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Dodatne postavke Celery-a
app.conf.update(
    # Rezultati se spremaju u Redis
    result_backend='redis://localhost:6379/1',
    
    # Automatsko brisanje rezultata zadataka nakon 24 sata
    result_expires=86400,
    
    # Zadaci se šalju putem Redis brokera
    broker_url='redis://localhost:6379/0',
    
    # Maksimalno 10 zadataka koji se izvršavaju istovremeno
    worker_concurrency=10,
    
    # Prefetch multiplicator - koliko zadataka worker dohvaća odjednom
    worker_prefetch_multiplier=4,
    
    # Zadaci se šalju s prioritetom 0-9 (9 je najviši)
    task_default_priority=5,
    
    # Maksimalno vrijeme izvršavanja zadatka
    task_time_limit=600,  # 10 minuta
    
    # Vremenska zona
    timezone='Europe/Zagreb',
    
    # Omogućuje praćenje zadataka
    task_track_started=True,
    
    # Ne dozvoli dupliciranje zadataka
    task_acks_late=False,
    
    # Format vremenskih oznaka
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
)

# Periodički zadaci (raspored)
app.conf.beat_schedule = {
    'osvjezi-statistiku-svaki-sat': {
        'task': 'stats.tasks.update_global_statistics',
        'schedule': 3600.0,  # Svaki sat
    },
    'provjeri-istekle-sobe-svakih-10-minuta': {
        'task': 'lobby.tasks.check_expired_rooms',
        'schedule': 600.0,  # Svakih 10 minuta
    },
    'provjeri-istekle-pozivnice-svakih-15-minuta': {
        'task': 'lobby.tasks.check_expired_invitations',
        'schedule': 900.0,  # Svakih 15 minuta
    },
    'obriši-stare-poruke-svaka-24-sata': {
        'task': 'lobby.tasks.delete_old_messages',
        'schedule': 86400.0,  # Svaka 24 sata
        'kwargs': {'days': 30}  # Briši poruke starije od 30 dana
    },
    'pošalji-dnevne-obavijesti-u-8-ujutro': {
        'task': 'users.tasks.send_daily_notifications',
        'schedule': {
            'hour': 8,
            'minute': 0,
        },
    },
}


@app.task(bind=True)
def debug_task(self):
    """
    Zadatak za testiranje Celery sustava.
    
    Ispisuje podatke o trenutnom zadatku u log.
    """
    print(f'Zahtjev: {self.request!r}')