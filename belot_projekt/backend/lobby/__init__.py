"""
Inicijalizacijski modul za Django aplikaciju "lobby".

Ova aplikacija implementira funkcionalnosti predvorja Belot igre, uključujući:
- Prikaz i upravljanje dostupnim sobama za igru
- Traženje javnih i privatnih igara
- Pridruživanje igrama pomoću koda sobe
- Chat sustav u predvorju
- Stvaranje novih igara s prilagođenim postavkama

Ovaj modul također definira verziju aplikacije i druge meta-informacije.
"""

# Verzija aplikacije
__version__ = '1.0.0'

# Zadana Django konfiguracija aplikacije
default_app_config = 'lobby.apps.LobbyConfig'