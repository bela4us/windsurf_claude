"""
Konfiguracija Django aplikacije "users".

Ovaj modul definira UsersConfig klasu koja konfigurira
Django aplikaciju za upravljanje korisnicima Belot igre.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """
    Klasa za konfiguraciju Django aplikacije 'users'.
    
    Ova klasa definira osnovne postavke aplikacije i registrira
    signale pri pokretanju.
    """
    
    # Puno ime aplikacije - koristi se za identifikaciju u projektu
    name = 'users'
    
    # Čitljivo ime aplikacije - koristi se u admin sučelju
    verbose_name = 'Belot Korisnici'
    
    def ready(self):
        """
        Metoda koja se poziva kada je aplikacija spremna.
        
        Registrira signale za korisničke događaje poput registracije,
        prijave, odjave itd.
        """
        # Uvoz signala za registraciju korisničkih događaja
        try:
            import users.signals
        except ImportError:
            # U slučaju da uvoz ne uspije, zabilježimo grešku bez prekida inicijalizacije
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Nije moguće uvesti module users.signals")