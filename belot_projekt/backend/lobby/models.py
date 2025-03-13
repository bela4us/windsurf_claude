"""
Modeli za Django aplikaciju "lobby".

Ovaj modul definira modele podataka za predvorje Belot igre, uključujući
sobe za čekanje, poruke chata, pozivnice i događaje. Ovi modeli omogućuju
korisnicima da pronađu igre, komuniciraju prije početka igre i upravljaju
statusom soba.

Modeli su dizajnirani da funkcioniraju zajedno s modelima iz 'game' aplikacije,
posebno s Game modelom koji predstavlja stvarnu igru.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from game.models import Game

User = get_user_model()


class LobbyRoom(models.Model):
    """
    Model za sobu u predvorju igre.
    
    Soba u predvorju predstavlja mjesto gdje igrači čekaju pridruživanje
    igri prije nego što igra stvarno počne. Kada svi igrači budu spremni,
    stvara se stvarna Game instanca.
    """
    
    STATUS_CHOICES = [
        ('open', _('Otvorena')),
        ('full', _('Popunjena')),
        ('starting', _('Započinje')),
        ('closed', _('Zatvorena')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Ime sobe'), max_length=100)
    creator = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_lobby_rooms',
        verbose_name=_('Kreator')
    )
    status = models.CharField(
        _('Status'), 
        max_length=20, 
        choices=STATUS_CHOICES,
        default='open'
    )
    is_private = models.BooleanField(_('Privatna soba'), default=False)
    room_code = models.CharField(_('Kod sobe'), max_length=10, unique=True)
    max_players = models.PositiveSmallIntegerField(_('Maksimalni broj igrača'), default=4)
    points_to_win = models.PositiveIntegerField(_('Bodovi za pobjedu'), default=1001)
    use_quick_format = models.BooleanField(_('Brži format'), default=False, help_text=_('Koristi 701 bodova umjesto 1001'))
    created_at = models.DateTimeField(_('Vrijeme stvaranja'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Vrijeme zadnjeg ažuriranja'), auto_now=True)
    active_until = models.DateTimeField(_('Aktivna do'), null=True, blank=True)
    
    # Poveznica s Game modelom (postavlja se kad se igra stvori iz lobbyja)
    game = models.OneToOneField(
        Game, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='lobby_room',
        verbose_name=_('Igra')
    )
    
    # Igrači u sobi
    players = models.ManyToManyField(
        User,
        through='LobbyMembership',
        related_name='lobby_rooms',
        verbose_name=_('Igrači')
    )
    
    class Meta:
        verbose_name = _('Soba u predvorju')
        verbose_name_plural = _('Sobe u predvorju')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.room_code})"
    
    def save(self, *args, **kwargs):
        """Generira jedinstveni kod sobe ako nije postavljen."""
        if not self.room_code:
            self.room_code = self.generate_room_code()
        
        # Postavlja trajanje aktivnosti ako nije postavljeno
        if not self.active_until:
            # Soba je aktivna 1 sat od stvaranja
            self.active_until = timezone.now() + timezone.timedelta(hours=1)
            
        super().save(*args, **kwargs)
    
    def generate_room_code(self):
        """Generira jedinstveni kod sobe od 6 znakova."""
        import random
        import string
        
        while True:
            # Generira slučajni alfanumerički kod od 6 znakova
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Provjeri je li kod jedinstven
            if not LobbyRoom.objects.filter(room_code=code).exists():
                return code
    
    def add_player(self, user):
        """
        Dodaje igrača u sobu.
        
        Args:
            user: Korisnik koji se dodaje
            
        Returns:
            bool: True ako je igrač uspješno dodan, False inače
        
        Raises:
            ValueError: Ako je soba puna ili zatvorena
        """
        if self.status in ['full', 'closed']:
            raise ValueError("Soba je puna ili zatvorena")
        
        current_count = self.lobbymembership_set.count()
        if current_count >= self.max_players:
            self.status = 'full'
            self.save()
            raise ValueError("Soba je popunjena")
        
        # Provjeri je li korisnik već u sobi
        if LobbyMembership.objects.filter(room=self, user=user).exists():
            return False
        
        # Dodaj korisnika u sobu
        membership = LobbyMembership.objects.create(
            room=self,
            user=user,
            is_ready=False
        )
        
        # Stvori događaj za pridruživanje
        LobbyEvent.objects.create(
            room=self,
            user=user,
            event_type='join',
            message=f"{user.username} se pridružio/la sobi."
        )
        
        # Ažuriraj status sobe ako je popunjena
        if self.lobbymembership_set.count() >= self.max_players:
            self.status = 'full'
            self.save()
        
        return True
    
    def remove_player(self, user):
        """
        Uklanja igrača iz sobe.
        
        Args:
            user: Korisnik koji se uklanja
            
        Returns:
            bool: True ako je igrač uspješno uklonjen, False inače
            
        Raises:
            ValueError: Ako je soba već zatvorena
        """
        if self.status == 'closed':
            raise ValueError("Soba je zatvorena")
            
        try:
            membership = LobbyMembership.objects.get(room=self, user=user)
            membership.delete()
            
            # Stvori događaj za napuštanje
            LobbyEvent.objects.create(
                room=self,
                user=user,
                event_type='leave',
                message=f"{user.username} je napustio/la sobu."
            )
            
            # Ako je kreator napustio sobu, promijeni kreatora ili zatvori sobu
            if user == self.creator:
                # Pokušaj pronaći novog kreatora među preostalim igračima
                remaining = self.lobbymembership_set.exclude(user=user).first()
                if remaining:
                    self.creator = remaining.user
                    self.save()
                    
                    LobbyEvent.objects.create(
                        room=self,
                        user=remaining.user,
                        event_type='new_owner',
                        message=f"{remaining.user.username} je novi vlasnik sobe."
                    )
                else:
                    # Ako nema preostalih igrača, zatvori sobu
                    self.status = 'closed'
                    self.save()
            
            # Ako soba više nije puna, vrati status na 'open'
            if self.status == 'full' and self.lobbymembership_set.count() < self.max_players:
                self.status = 'open'
                self.save()
                
            return True
            
        except LobbyMembership.DoesNotExist:
            return False
    
    def mark_player_ready(self, user, is_ready=True):
        """
        Označava igrača kao spremnog za igru.
        
        Args:
            user: Korisnik koji se označava
            is_ready: Je li korisnik spreman
            
        Returns:
            bool: True ako je igrač uspješno označen, False inače
        """
        try:
            membership = LobbyMembership.objects.get(room=self, user=user)
            membership.is_ready = is_ready
            membership.save()
            
            # Stvori događaj za spremnost
            if is_ready:
                message = f"{user.username} je spreman/na za igru."
            else:
                message = f"{user.username} više nije spreman/na za igru."
                
            LobbyEvent.objects.create(
                room=self,
                user=user,
                event_type='ready_status',
                message=message
            )
            
            # Provjeri jesu li svi igrači spremni
            all_ready = self.are_all_players_ready()
            if all_ready and self.lobbymembership_set.count() >= 4:
                self.status = 'starting'
                self.save()
            
            return True
            
        except LobbyMembership.DoesNotExist:
            return False
    
    def are_all_players_ready(self):
        """
        Provjerava jesu li svi igrači spremni za igru.
        
        Returns:
            bool: True ako su svi igrači spremni, False inače
        """
        memberships = self.lobbymembership_set.all()
        if not memberships.exists():
            return False
            
        return all(m.is_ready for m in memberships)
    
    def start_game(self):
        """
        Započinje igru od sobe u predvorju.
        
        Stvara novu instancu Game i povezuje ju s ovom sobom.
        
        Returns:
            Game: Stvorena igra
            
        Raises:
            ValueError: Ako nema dovoljno igrača ili nisu svi spremni
        """
        if self.lobbymembership_set.count() < 4:
            raise ValueError("Nije moguće započeti igru s manje od 4 igrača")
            
        if not self.are_all_players_ready():
            raise ValueError("Svi igrači moraju biti spremni za početak igre")
        
        # Stvori novu igru
        from game.models import Game
        game = Game.objects.create(
            creator=self.creator,
            points_to_win=self.points_to_win,
            is_private=self.is_private,
            status='waiting'
        )
        
        # Dodaj igrače u igru
        for membership in self.lobbymembership_set.all():
            game.players.add(membership.user)
            game.active_players.add(membership.user)
        
        # Poveži igru sa sobom
        self.game = game
        self.status = 'closed'
        self.save()
        
        # Stvori događaj za početak igre
        LobbyEvent.objects.create(
            room=self,
            user=self.creator,
            event_type='game_start',
            message=f"Igra je započela! ID igre: {game.id}"
        )
        
        return game


class LobbyMembership(models.Model):
    """
    Model za članstvo korisnika u sobi predvorja.
    
    Ovo je veza između korisnika i sobe u predvorju, koja prati
    dodatne podatke o članstvu, poput statusa spremnosti.
    """
    
    room = models.ForeignKey(LobbyRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(_('Vrijeme pridruživanja'), auto_now_add=True)
    is_ready = models.BooleanField(_('Spreman za igru'), default=False)
    
    class Meta:
        verbose_name = _('Članstvo u predvorju')
        verbose_name_plural = _('Članstva u predvorju')
        unique_together = ('room', 'user')
    
    def __str__(self):
        return f"{self.user.username} u {self.room.name}"


class LobbyInvitation(models.Model):
    """
    Model za pozivnice u sobu predvorja.
    
    Pozivnice omogućuju igračima da pozovu prijatelje u svoju sobu
    za igru, čak i ako je soba postavljena kao privatna.
    """
    
    STATUS_CHOICES = [
        ('pending', _('Na čekanju')),
        ('accepted', _('Prihvaćena')),
        ('declined', _('Odbijena')),
        ('expired', _('Istekla')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        LobbyRoom, 
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name=_('Soba')
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name=_('Pošiljatelj')
    )
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='received_invitations',
        verbose_name=_('Primatelj')
    )
    created_at = models.DateTimeField(_('Vrijeme stvaranja'), auto_now_add=True)
    expires_at = models.DateTimeField(_('Istječe'), null=True, blank=True)
    status = models.CharField(
        _('Status'), 
        max_length=20, 
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.TextField(_('Poruka'), blank=True)
    
    class Meta:
        verbose_name = _('Pozivnica u predvorje')
        verbose_name_plural = _('Pozivnice u predvorje')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Pozivnica od {self.sender.username} za {self.recipient.username} u sobu {self.room.name}"
    
    def save(self, *args, **kwargs):
        """Postavlja vrijeme isteka ako nije postavljeno."""
        if not self.expires_at:
            # Pozivnica istječe za 24 sata
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
            
        super().save(*args, **kwargs)
    
    def accept(self):
        """
        Prihvaća pozivnicu i dodaje korisnika u sobu.
        
        Returns:
            bool: True ako je pozivnica uspješno prihvaćena, False inače
        """
        if self.status != 'pending':
            return False
            
        if timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save()
            return False
        
        try:
            # Dodaj korisnika u sobu
            self.room.add_player(self.recipient)
            
            # Ažuriraj status pozivnice
            self.status = 'accepted'
            self.save()
            
            # Stvori događaj za prihvaćanje pozivnice
            LobbyEvent.objects.create(
                room=self.room,
                user=self.recipient,
                event_type='invitation_accepted',
                message=f"{self.recipient.username} je prihvatio/la pozivnicu od {self.sender.username}."
            )
            
            return True
            
        except ValueError as e:
            # Ako nije moguće dodati korisnika u sobu
            return False
    
    def decline(self):
        """
        Odbija pozivnicu.
        
        Returns:
            bool: True ako je pozivnica uspješno odbijena, False inače
        """
        if self.status != 'pending':
            return False
            
        self.status = 'declined'
        self.save()
        
        # Stvori događaj za odbijanje pozivnice (vidljiv samo pošiljatelju)
        LobbyEvent.objects.create(
            room=self.room,
            user=self.recipient,
            event_type='invitation_declined',
            message=f"{self.recipient.username} je odbio/la pozivnicu.",
            is_private=True,
            private_recipient=self.sender
        )
        
        return True
    
    @classmethod
    def expire_old_invitations(cls):
        """
        Označava sve istekle pozivnice.
        
        Returns:
            int: Broj označenih pozivnica
        """
        expired = cls.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        )
        
        count = expired.count()
        expired.update(status='expired')
        
        return count


class LobbyMessage(models.Model):
    """
    Model za poruke chata u predvorju.
    
    Omogućuje korisnicima da komuniciraju u sobi predvorja
    prije nego što igra započne.
    """
    
    room = models.ForeignKey(
        LobbyRoom, 
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Soba')
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='lobby_messages',
        verbose_name=_('Pošiljatelj')
    )
    content = models.TextField(_('Sadržaj'))
    created_at = models.DateTimeField(_('Vrijeme slanja'), auto_now_add=True)
    is_system_message = models.BooleanField(_('Sistemska poruka'), default=False)
    
    class Meta:
        verbose_name = _('Poruka u predvorju')
        verbose_name_plural = _('Poruke u predvorju')
        ordering = ['created_at']
    
    def __str__(self):
        if self.is_system_message:
            return f"Sistem: {self.content[:30]}..."
        return f"{self.sender.username}: {self.content[:30]}..."
    
    @classmethod
    def add_system_message(cls, room, content):
        """
        Dodaje sistemsku poruku u chat sobe.
        
        Args:
            room: Soba u koju se dodaje poruka
            content: Sadržaj poruke
            
        Returns:
            LobbyMessage: Stvorena poruka
        """
        return cls.objects.create(
            room=room,
            sender=room.creator,  # Koristi kreatora sobe kao pošiljatelja
            content=content,
            is_system_message=True
        )


class LobbyEvent(models.Model):
    """
    Model za događaje u predvorju.
    
    Prati različite događaje u sobi predvorja, poput pridruživanja/napuštanja
    igrača, promjene statusa spremnosti, itd.
    """
    
    EVENT_TYPES = [
        ('join', _('Pridruživanje')),
        ('leave', _('Napuštanje')),
        ('ready_status', _('Status spremnosti')),
        ('new_owner', _('Novi vlasnik')),
        ('game_start', _('Početak igre')),
        ('room_change', _('Promjena postavki sobe')),
        ('invitation_sent', _('Poslana pozivnica')),
        ('invitation_accepted', _('Prihvaćena pozivnica')),
        ('invitation_declined', _('Odbijena pozivnica')),
        ('custom', _('Prilagođeni događaj')),
    ]
    
    room = models.ForeignKey(
        LobbyRoom, 
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name=_('Soba')
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='lobby_events',
        verbose_name=_('Korisnik')
    )
    event_type = models.CharField(
        _('Tip događaja'), 
        max_length=50, 
        choices=EVENT_TYPES
    )
    message = models.TextField(_('Poruka'))
    created_at = models.DateTimeField(_('Vrijeme'), auto_now_add=True)
    is_private = models.BooleanField(_('Privatni događaj'), default=False)
    private_recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='private_lobby_events',
        verbose_name=_('Privatni primatelj'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('Događaj u predvorju')
        verbose_name_plural = _('Događaji u predvorju')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_event_type_display()}: {self.message[:30]}..."