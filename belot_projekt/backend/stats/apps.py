"""
Konfiguracija Django aplikacije "stats".

Ovaj modul sadrži konfiguraciju aplikacije za statistiku
Belot igre, uključujući naziv aplikacije, label i autodiscovery
signala.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StatsConfig(AppConfig):
    """
    Konfiguracija aplikacije za statistiku.
    
    Definira osnovne postavke i ponašanje aplikacije za statistiku
    Belot igre.
    """
    
    name = 'stats'
    verbose_name = _('Statistika')
    
    def ready(self):
        """
        Metoda koja se poziva kada je aplikacija spremna.
        
        Registrira signale za praćenje događaja i automatsko
        ažuriranje statistike kada se dogode relevantni događaji.
        """
        # Uvoz signala
        import stats.signals