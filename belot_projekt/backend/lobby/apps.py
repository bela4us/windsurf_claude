"""
Konfiguracija Django aplikacije "lobby".

Ovaj modul definira LobbyConfig klasu koja konfigurira
Django aplikaciju za predvorje Belot igre.
"""

from django.apps import AppConfig


class LobbyConfig(AppConfig):
    """
    Klasa za konfiguraciju Django aplikacije 'lobby'.
    
    Ova klasa definira osnovne postavke aplikacije i potencijalno
    može registrirati signale i druge resurse pri pokretanju.
    """
    
    # Puno ime aplikacije - koristi se za identifikaciju u projektu
    name = 'lobby'
    
    # Čitljivo ime aplikacije - koristi se u admin sučelju
    verbose_name = 'Belot Predvorje'
    
    def ready(self):
        """
        Metoda koja se poziva kada je aplikacija spremna.
        
        Ovo je mjesto gdje se registriraju signali i inicijaliziraju
        resursi pri pokretanju aplikacije.
        """
        # Uvoz signala ako postoje
        try:
            import lobby.signals
        except ImportError:
            pass