"""
Inicijalizacijski modul za Django aplikaciju "users".

Ova aplikacija implementira funkcionalnosti vezane uz korisnike Belot igre, uključujući:
- Registraciju i prijavu korisnika
- Upravljanje korisničkim profilima
- Postavke privatnosti i obavijesti
- Statistiku igrača i praćenje napretka
- Integraciju s društvenim mrežama
- API za korisničke podatke

Ovaj modul također definira verziju aplikacije i druge meta-informacije.
"""

# Verzija aplikacije
__version__ = '1.0.0'

# Zadana Django konfiguracija aplikacije
default_app_config = 'users.apps.UsersConfig'
