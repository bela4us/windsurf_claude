"""
Signali za Django aplikaciju "users".

Ovaj modul definira Django signale koji se okidaju na događaje vezane uz korisnike,
poput stvaranja korisnika, ažuriranja profila, itd.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal koji se aktivira kada se kreira novi korisnik.
    Stvara profil korisnika ako je korisnik tek stvoren.
    """
    if created:
        # Ovdje bi inače kreirali Profile objekt, 
        # ali ga preskačemo jer trenutno nemamo Profile model
        pass

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal koji se aktivira pri svakom spremanju korisnika.
    Ažurira profil korisnika.
    """
    # Ovdje bi inače ažurirali Profile objekt
    pass 