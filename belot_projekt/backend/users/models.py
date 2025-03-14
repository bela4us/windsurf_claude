"""
Modeli podataka za Django aplikaciju "users".

Ovaj modul sadrži definicije modela za korisnike Belot sustava,
uključujući prošireni korisnički model, profile, i druge povezane entitete.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Prošireni korisnički model za Belot sustav."""
    
    # Dodatna polja za korisnike
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Statistike i preferencije
    total_games = models.PositiveIntegerField(default=0)
    games_won = models.PositiveIntegerField(default=0)
    elo_rating = models.PositiveIntegerField(default=1200)
    
    # Postavke i preferencije
    theme_preference = models.CharField(
        max_length=20,
        choices=[('light', 'Svjetla'), ('dark', 'Tamna'), ('system', 'Prema sustavu')],
        default='system'
    )
    email_notifications = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _('korisnik')
        verbose_name_plural = _('korisnici')
        
    @property
    def win_rate(self):
        """Izračunava postotak pobjeda za korisnika."""
        if self.total_games > 0:
            return (self.games_won / self.total_games) * 100
        return 0
    
    def __str__(self):
        return self.username 