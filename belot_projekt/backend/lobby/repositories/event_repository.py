"""
Repozitorij za pristup i manipulaciju događajima u predvorju.

Ovaj modul sadrži klasu EventRepository koja implementira metode za
dohvaćanje i upravljanje događajima u predvorju Belot igre.
Repozitorij apstrahira upite na bazu podataka i osigurava konzistentnost
pri manipulaciji podacima o događajima.
"""

from django.db.models import Q
from django.utils import timezone

from ..models import LobbyEvent, LobbyRoom


class EventRepository:
    """
    Repozitorij za rad s događajima u predvorju.
    
    Implementira metode za pristup i manipulaciju događajima,
    uključujući dohvaćanje, bilježenje i filtriranje događaja.
    """
    
    @staticmethod
    def get_room_events(room, limit=20):
        """
        Dohvaća događaje za određenu sobu.
        
        Args:
            room: Soba za koju se dohvaćaju događaji
            limit: Maksimalni broj događaja za dohvat
            
        Returns:
            QuerySet: QuerySet s događajima sobe
        """
        return LobbyEvent.objects.filter(
            room=room,
            is_private=False
        ).select_related('user').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_user_events(user, limit=20):
        """
        Dohvaća događaje koji se odnose na određenog korisnika.
        
        Args:
            user: Korisnik čiji se događaji dohvaćaju
            limit: Maksimalni broj događaja za dohvat
            
        Returns:
            QuerySet: QuerySet s događajima korisnika
        """
        return LobbyEvent.objects.filter(
            Q(user=user) | Q(private_recipient=user)
        ).select_related('room', 'user').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_user_private_events(user, limit=20):
        """
        Dohvaća privatne događaje za određenog korisnika.
        
        Args:
            user: Korisnik čiji se privatni događaji dohvaćaju
            limit: Maksimalni broj događaja za dohvat
            
        Returns:
            QuerySet: QuerySet s privatnim događajima korisnika
        """
        return LobbyEvent.objects.filter(
            is_private=True,
            private_recipient=user
        ).select_related('room', 'user').order_by('-created_at')[:limit]
    
    @staticmethod
    def create_event(room, user, event_type, message, is_private=False, private_recipient=None):
        """
        Stvara novi događaj.
        
        Args:
            room: Soba u kojoj se stvara događaj
            user: Korisnik koji je uzrokovao događaj
            event_type: Tip događaja
            message: Poruka događaja
            is_private: Je li događaj privatan
            private_recipient: Primatelj privatnog događaja
            
        Returns:
            LobbyEvent: Stvoreni događaj
        """
        event = LobbyEvent.objects.create(
            room=room,
            user=user,
            event_type=event_type,
            message=message,
            is_private=is_private,
            private_recipient=private_recipient
        )
        
        return event
    
    @staticmethod
    def get_events_by_type(event_type, limit=20):
        """
        Dohvaća događaje određenog tipa.
        
        Args:
            event_type: Tip događaja koji se dohvaća
            limit: Maksimalni broj događaja za dohvat
            
        Returns:
            QuerySet: QuerySet s događajima određenog tipa
        """
        return LobbyEvent.objects.filter(
            event_type=event_type,
            is_private=False
        ).select_related('room', 'user').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_recent_global_events(limit=10):
        """
        Dohvaća nedavne globalne događaje.
        
        Args:
            limit: Maksimalni broj događaja za dohvat
            
        Returns:
            QuerySet: QuerySet s nedavnim globalnim događajima
        """
        return LobbyEvent.objects.filter(
            is_private=False,
            event_type__in=['game_start', 'new_owner', 'room_change']
        ).select_related('room', 'user').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_event_by_id(event_id):
        """
        Dohvaća događaj prema ID-u.
        
        Args:
            event_id: ID događaja
            
        Returns:
            LobbyEvent: Događaj s traženim ID-om ili None
        """
        try:
            return LobbyEvent.objects.select_related('room', 'user', 'private_recipient').get(pk=event_id)
        except LobbyEvent.DoesNotExist:
            return None
    
    @staticmethod
    def delete_old_events(days=7):
        """
        Briše stare događaje.
        
        Args:
            days: Broj dana nakon kojih se događaji brišu
            
        Returns:
            int: Broj obrisanih događaja
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Dohvati događaje za brisanje
        events_to_delete = LobbyEvent.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = events_to_delete.count()
        events_to_delete.delete()
        
        return count
    
    @staticmethod
    def log_player_join(room, user):
        """
        Logira pridruživanje igrača u sobu.
        
        Args:
            room: Soba u koju se igrač pridružio
            user: Korisnik koji se pridružio
            
        Returns:
            LobbyEvent: Stvoreni događaj
        """
        return EventRepository.create_event(
            room=room,
            user=user,
            event_type='join',
            message=f"{user.username} se pridružio/la sobi."
        )
    
    @staticmethod
    def log_player_leave(room, user):
        """
        Logira napuštanje igrača iz sobe.
        
        Args:
            room: Soba koju je igrač napustio
            user: Korisnik koji je napustio
            
        Returns:
            LobbyEvent: Stvoreni događaj
        """
        return EventRepository.create_event(
            room=room,
            user=user,
            event_type='leave',
            message=f"{user.username} je napustio/la sobu."
        )
    
    @staticmethod
    def log_player_ready_status(room, user, is_ready):
        """
        Logira promjenu statusa spremnosti igrača.
        
        Args:
            room: Soba u kojoj je promijenjen status
            user: Korisnik čiji je status promijenjen
            is_ready: Novi status spremnosti
            
        Returns:
            LobbyEvent: Stvoreni događaj
        """
        if is_ready:
            message = f"{user.username} je spreman/na za igru."
        else:
            message = f"{user.username} više nije spreman/na za igru."
            
        return EventRepository.create_event(
            room=room,
            user=user,
            event_type='ready_status',
            message=message
        )
    
    @staticmethod
    def log_game_start(room, creator):
        """
        Logira početak igre iz sobe.
        
        Args:
            room: Soba iz koje je pokrenuta igra
            creator: Korisnik koji je pokrenuo igru
            
        Returns:
            LobbyEvent: Stvoreni događaj
        """
        return EventRepository.create_event(
            room=room,
            user=creator,
            event_type='game_start',
            message=f"Igra je započela! ID igre: {room.game.id if room.game else 'Unknown'}"
        )