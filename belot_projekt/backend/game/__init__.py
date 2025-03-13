"""
Inicijalizacijski modul za Django aplikaciju "game".

Ova aplikacija implementira svu funkcionalnost koja se odnosi na igru Belot,
uključujući modele za igru, rundu, poteze i zvanja, kao i logiku igre,
validatore, serializatore i viewove.

Ovaj modul također definira verziju aplikacije i druge meta-informacije.
"""

# Verzija aplikacije
__version__ = '1.0.0'

# Zadana Django konfiguracija aplikacije
default_app_config = 'game.apps.GameConfig'