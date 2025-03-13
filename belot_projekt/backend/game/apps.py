from django.apps import AppConfig

class GameConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "game"
    verbose_name = "Belot Igra"
    
    def ready(self):
        """
        Metoda koja se poziva kada je aplikacija učitana.
        Ovdje registriramo signale i obavljamo druge inicijalizacije.
        """
        try:
            import game.signals  # Uvoz signala kad je aplikacija spremna
        except ImportError:
            pass  # Signali možda još nisu implementirani
