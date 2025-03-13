"""
WSGI konfiguracija za Belot projekt.

Ova datoteka definira WSGI aplikacijski objekt koji omogućuje 
pokretanje Django projekta na WSGI-kompatibilnim web serverima 
kao što su Gunicorn, uWSGI ili Apache s mod_wsgi.

Za razliku od ASGI (asgi.py), WSGI se koristi za standardne HTTP 
zahtjeve i ne podržava WebSockets. U Belot projektu, WSGI se koristi 
za obradu običnih HTTP zahtjeva, dok se WebSocket komunikacija 
odvija kroz ASGI konfiguraciju.

Za više informacija o WSGI konfiguraciji:
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

# Dodavanje putanje projekta u Python putanju ako nije već dodana
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# Postavljanje zadanih Django postavki
# Koristi produkcijske postavke kao zadane za siguran deployment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.production')

# Kreiranje WSGI aplikacije
application = get_wsgi_application()

# Provjera ispravljenog postavljanja WSGI aplikacije
try:
    from django.conf import settings
    if not settings.configured:
        import django
        django.setup()
    
    # Logiranje uspješne inicijalizacije
    import logging
    logger = logging.getLogger('belot')
    logger.info('WSGI aplikacija za Belot uspješno konfigurirana')

except Exception as e:
    # U slučaju greške, pokušaj logirati problem ako je logging dostupan
    import logging
    logger = logging.getLogger('belot')
    logger.error(f'Greška pri konfiguraciji WSGI aplikacije: {str(e)}')
    # Propagiraj grešku dalje
    raise