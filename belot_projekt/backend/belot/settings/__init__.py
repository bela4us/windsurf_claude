"""
Inicijalizacijski modul za paket postavki Belot aplikacije.

Ovaj modul učitava odgovarajuće postavke na temelju okoline (development, 
production, testing) definirane kroz environment varijablu DJANGO_ENVIRONMENT.
Ako varijabla nije postavljena, koriste se razvojne postavke kao zadane.
"""

import os
import importlib

# Definiranje podržanih okruženja
ENVIRONMENTS = {
    'development': 'belot.settings.development',
    'production': 'belot.settings.production',
    'testing': 'belot.settings.testing',
}

# Učitavanje postavki na temelju okoline
environment = os.environ.get('DJANGO_ENVIRONMENT', 'development').lower()

if environment not in ENVIRONMENTS:
    raise ImportError(f"Nepoznato okruženje: {environment}. "
                      f"Podržana okruženja su: {', '.join(ENVIRONMENTS.keys())}")

# Dinamičko učitavanje odgovarajućeg modula postavki
settings_module = importlib.import_module(ENVIRONMENTS[environment])

# Učitavanje svih postavki iz odabranog modula u ovaj namespace
for attr_name in dir(settings_module):
    # Preskakanje privatnih atributa
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(settings_module, attr_name)

# Postavljanje varijable koja označava trenutno aktivno okruženje
ACTIVE_ENVIRONMENT = environment