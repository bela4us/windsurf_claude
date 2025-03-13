"""
Modeli za Django aplikaciju "users".

Ovaj modul definira modele podataka za korisnike Belot igre,
uključujući profil, postavke, statistike i prijateljstva.
Modeli proširuju osnovni Django User model dodatnim poljima
potrebnim za Belot aplikaciju.
"""

import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(AbstractUser):
    """
    Prilagođeni User model za Belot aplikaciju.
    
    Proširuje osnovni Django AbstractUser model s dodatnim poljima
    specifičnim za Belot aplikaciju.
    """
    
    # ID korisnika kao UUID umjesto auto-increment
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dodatna polja za korisnički račun
    nickname = models.CharField(_('Nadimak'), max_length=50, blank=True)
    avatar = models.ImageField(_('Avatar'), upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(_('O meni'), max_length=500, blank=True)
    date_of_birth = models.DateField(_('Datum rođenja'), null=True, blank=True)
    
    # Polja za verifikaciju
    is_email_verified = models.BooleanField(_('Email verificiran'), default=False)
    verification_token = models.CharField(_('Token za verifikaciju'), max_length=100, blank=True)
    
    # Postavke privatnosti
    is_profile_public = models.BooleanField(_('Javni profil'), default=True)
    show_online_status = models.BooleanField(_('Prikaži online status'), default=True)
    
    # Igračka statistika
    rating = models.IntegerField(_('Rejting'), default=1500)
    games_played = models.PositiveIntegerField(_('Odigrane igre'), default=0)
    games_won = models.PositiveIntegerField(_('Pobjede'), default=0)
    games_lost = models.PositiveIntegerField(_('Porazi'), default=0)
    
    # Online status
    is_online = models.BooleanField(_('Online'), default=False)
    last_activity = models.DateTimeField(_('Zadnja aktivnost'), default=timezone.now)
    
    # Postavke notifikacija
    receive_email_notifications = models.BooleanField(_('Email obavijesti'), default=True)
    receive_game_invites = models.BooleanField(_('Pozivnice za igru'), default=True)
    receive_friend_requests = models.BooleanField(_('Zahtjevi za prijateljstvo'), default=True)
    
    # Proširena meta-informacija
    class Meta:
        verbose_name = _('Korisnik')
        verbose_name_plural = _('Korisnici')
        ordering = ['-date_joined']
    
    def __str__(self):
        """Vraća korisničko ime ili nadimak ako postoji."""
        return self.nickname or self.username
    
    def get_full_name(self):
        """Vraća puno ime korisnika ili korisničko ime ako ime nije postavljeno."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_win_rate(self):
        """Izračunava postotak pobjeda korisnika."""
        if self.games_played == 0:
            return 0
        return round((self.games_won / self.games_played) * 100, 2)
    
    def update_rating(self, new_rating):
        """Ažurira rejting korisnika nakon igre."""
        self.rating = new_rating
        self.save(update_fields=['rating'])
    
    def update_game_stats(self, won):
        """Ažurira statistiku igara korisnika."""
        self.games_played += 1
        if won:
            self.games_won += 1
        else:
            self.games_lost += 1
        self.save(update_fields=['games_played', 'games_won', 'games_lost'])
    
    def update_online_status(self, is_online=True):
        """Ažurira online status korisnika."""
        self.is_online = is_online
        self.last_activity = timezone.now()
        self.save(update_fields=['is_online', 'last_activity'])


class Profile(models.Model):
    """
    Prošireni korisnički profil s dodatnim podacima.
    
    Ovaj model sadrži dodatne podatke o korisniku koji nisu dio
    osnovnog User modela, poput igračkih preferencija i postavki.
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Korisnik')
    )
    
    # Preferencije igranja
    preferred_game_type = models.CharField(
        _('Preferirana vrsta igre'),
        max_length=20,
        choices=[
            ('classic', _('Klasični Belot')),
            ('open', _('Otvoreni Belot')),
            ('alla', _('Belot Alla')),
            ('call', _('Belot na Zvanje')),
        ],
        default='classic'
    )
    preferred_card_deck = models.CharField(
        _('Preferirani špil karata'),
        max_length=20,
        choices=[
            ('classic', _('Klasični špil')),
            ('modern', _('Moderni špil')),
            ('custom', _('Prilagođeni špil')),
        ],
        default='classic'
    )
    
    # Postavke zvuka i vizuala
    sound_enabled = models.BooleanField(_('Zvuk uključen'), default=True)
    music_enabled = models.BooleanField(_('Glazba uključena'), default=True)
    animation_speed = models.CharField(
        _('Brzina animacija'),
        max_length=10,
        choices=[
            ('slow', _('Sporo')),
            ('normal', _('Normalno')),
            ('fast', _('Brzo')),
        ],
        default='normal'
    )
    
    # Jezične postavke
    language = models.CharField(
        _('Jezik'),
        max_length=10,
        choices=[
            ('hr', _('Hrvatski')),
            ('en', _('Engleski')),
            ('de', _('Njemački')),
        ],
        default='hr'
    )
    
    # Ostale postavke
    auto_ready = models.BooleanField(_('Automatski spreman'), default=False)
    show_game_tips = models.BooleanField(_('Prikaži savjete'), default=True)
    
    # Značke i postignuća
    achievements = models.ManyToManyField(
        'Achievement',
        through='UserAchievement',
        related_name='users',
        verbose_name=_('Postignuća')
    )
    
    created_at = models.DateTimeField(_('Stvoreno'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Ažurirano'), auto_now=True)
    
    class Meta:
        verbose_name = _('Profil')
        verbose_name_plural = _('Profili')
    
    def __str__(self):
        return f"Profil za {self.user.username}"


class Friendship(models.Model):
    """
    Model za praćenje prijateljstava između korisnika.
    
    Prati veze prijateljstva između korisnika, uključujući status
    (zahtjev, prihvaćeno, odbijeno).
    """
    
    STATUS_CHOICES = [
        ('pending', _('Na čekanju')),
        ('accepted', _('Prihvaćeno')),
        ('declined', _('Odbijeno')),
        ('blocked', _('Blokirano')),
    ]
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_friendships',
        verbose_name=_('Pošiljatelj')
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_friendships',
        verbose_name=_('Primatelj')
    )
    status = models.CharField(
        _('Status'),
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(_('Stvoreno'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Ažurirano'), auto_now=True)
    
    class Meta:
        verbose_name = _('Prijateljstvo')
        verbose_name_plural = _('Prijateljstva')
        unique_together = ('sender', 'receiver')
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.get_status_display()})"


class Achievement(models.Model):
    """
    Model za postignuća i značke u igri.
    
    Definira postignuća koja korisnici mogu otključati,
    poput određenog broja pobjeda, savršenih igara, itd.
    """
    
    name = models.CharField(_('Naziv'), max_length=100)
    description = models.TextField(_('Opis'))
    icon = models.ImageField(_('Ikona'), upload_to='achievements/')
    points = models.PositiveIntegerField(_('Bodovi'), default=0)
    
    # Tip postignuća za automatsko dodjeljivanje
    achievement_type = models.CharField(
        _('Tip postignuća'),
        max_length=50,
        choices=[
            ('games_played', _('Broj odigranih igara')),
            ('games_won', _('Broj pobjeda')),
            ('perfect_games', _('Savršene igre')),
            ('win_streak', _('Niz pobjeda')),
            ('rating', _('Rejting')),
            ('special', _('Posebno postignuće')),
        ]
    )
    
    # Uvjet za osvajanje (npr. 100 pobjeda)
    threshold = models.PositiveIntegerField(_('Prag'), default=0)
    
    created_at = models.DateTimeField(_('Stvoreno'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Postignuće')
        verbose_name_plural = _('Postignuća')
    
    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """
    Veza između korisnika i postignuća.
    
    Prati koja postignuća je korisnik otključao i kada.
    """
    
    user = models.ForeignKey(
        'Profile',
        on_delete=models.CASCADE,
        related_name='user_achievements',
        verbose_name=_('Korisnik')
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_achievements',
        verbose_name=_('Postignuće')
    )
    unlocked_at = models.DateTimeField(_('Otključano'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Korisničko postignuće')
        verbose_name_plural = _('Korisnička postignuća')
        unique_together = ('user', 'achievement')
    
    def __str__(self):
        return f"{self.user.user.username} - {self.achievement.name}"


class Notification(models.Model):
    """
    Model za korisničke obavijesti.
    
    Prati obavijesti poslane korisnicima, kao što su zahtjevi
    za prijateljstvo, pozivnice za igru, postignuća, itd.
    """
    
    TYPE_CHOICES = [
        ('friend_request', _('Zahtjev za prijateljstvo')),
        ('friend_accept', _('Prihvaćeno prijateljstvo')),
        ('game_invite', _('Pozivnica za igru')),
        ('achievement', _('Otključano postignuće')),
        ('game_result', _('Rezultat igre')),
        ('system', _('Sistemska obavijest')),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Korisnik')
    )
    notification_type = models.CharField(
        _('Tip obavijesti'),
        max_length=20,
        choices=TYPE_CHOICES
    )
    title = models.CharField(_('Naslov'), max_length=100)
    message = models.TextField(_('Poruka'))
    is_read = models.BooleanField(_('Pročitano'), default=False)
    related_object_id = models.CharField(_('ID povezanog objekta'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('Stvoreno'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Obavijest')
        verbose_name_plural = _('Obavijesti')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} za {self.user.username}"
    
    def mark_as_read(self):
        """Označava obavijest kao pročitanu."""
        self.is_read = True
        self.save(update_fields=['is_read'])


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatski stvara profil za novog korisnika."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sprema profil prilikom spremanja korisnika."""
    if not hasattr(instance, 'profile'):
        Profile.objects.create(user=instance)
    instance.profile.save()