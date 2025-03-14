"""
Konfiguracija Django aplikacije za "users".

Ovaj modul definira postavke aplikacije koje Django koristi
pri registraciji i inicijalizaciji aplikacije.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Konfiguracija Django aplikacije za korisnike Belot sustava."""
    
    name = 'users'
    verbose_name = 'Korisnici'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        Inicijalizacija aplikacije nakon što je Django spreman.
        
        Ovdje se registriraju signali, očitavaju početni podaci,
        i obavljaju druge inicijalizacijske radnje.
        """
        # Uvozimo signale kako bi se automatski povezali
        try:
            import users.signals  # noqa
        except ImportError:
            pass 