"""
Repozitorij za pristup i manipulaciju članstvima u sobama predvorja.

Ovaj modul sadrži klasu MembershipRepository koja implementira metode za
dohvaćanje i upravljanje članstvima korisnika u sobama predvorja Belot igre.
Repozitorij apstrahira upite na bazu podataka i osigurava konzistentnost
pri manipulaciji podacima o članstvima.
"""

from django.db.models import Count, Q, Prefetch
from django.utils import timezone

from ..models import LobbyMembership, LobbyRoom, LobbyEvent


class MembershipRepository:
    """
    Repozitorij za rad s članstvima u sobama predvorja.
    
    Implementira metode za pristup i manipulaciju članstvima,
    uključujući pridruživanje, napuštanje i promjenu statusa spremnosti.
    """
    
    @staticmethod
    def get_room_memberships(room):
        """
        Dohvaća članstva za određenu sobu.
        
        Args:
            room: Soba za koju se dohvaćaju članstva
            
        Returns:
            QuerySet: QuerySet s članstvima sobe
        """
        return LobbyMembership.objects.filter(
            room=room
        ).select_related('user').order_by('joined_at')
    
    @staticmethod
    def get_user_membership(room, user):
        """
        Dohvaća članstvo određenog korisnika u sobi.
        
        Args:
            room: Soba u kojoj se traži članstvo
            user: Korisnik čije se članstvo traži
            
        Returns:
            LobbyMembership: Članstvo korisnika u sobi ili None
        """
        try:
            return LobbyMembership.objects.get(room=room, user=user)
        except LobbyMembership.DoesNotExist:
            return None
    
    @staticmethod
    def get_all_user_memberships(user):
        """
        Dohvaća sva aktivna članstva korisnika.
        
        Args:
            user: Korisnik čija se članstva traže
            
        Returns:
            QuerySet: QuerySet s članstvima korisnika
        """
        return LobbyMembership.objects.filter(
            user=user,
            room__status__in=['open', 'full', 'starting']
        ).select_related('room').order_by('-room__created_at')
    
    @staticmethod
    def add_player_to_room(room, user):
        """
        Dodaje igrača u sobu.
        
        Args:
            room: Soba u koju se dodaje igrač
            user: Korisnik koji se dodaje
            
        Returns:
            bool: True ako je igrač uspješno dodan, False inače
        """
        try:
            return room.add_player(user)
        except ValueError:
            return False
    
    @staticmethod
    def remove_player_from_room(room, user):
        """
        Uklanja igrača iz sobe.
        
        Args:
            room: Soba iz koje se uklanja igrač
            user: Korisnik koji se uklanja
            
        Returns:
            bool: True ako je igrač uspješno uklonjen, False inače
        """
        try:
            return room.remove_player(user)
        except ValueError:
            return False
    
    @staticmethod
    def toggle_player_ready_status(room, user):
        """
        Mijenja status spremnosti igrača.
        
        Args:
            room: Soba u kojoj se mijenja status
            user: Korisnik čiji se status mijenja
            
        Returns:
            bool: Novi status spremnosti ili None ako nije uspjelo
        """
        try:
            membership = LobbyMembership.objects.get(room=room, user=user)
            new_status = not membership.is_ready
            
            # Promijeni status
            success = room.mark_player_ready(user, new_status)
            
            return new_status if success else None
            
        except LobbyMembership.DoesNotExist:
            return None
    
    @staticmethod
    def are_all_players_ready(room):
        """
        Provjerava jesu li svi igrači u sobi spremni.
        
        Args:
            room: Soba koja se provjerava
            
        Returns:
            bool: True ako su svi igrači spremni, False inače
        """
        return room.are_all_players_ready()
    
    @staticmethod
    def count_ready_players(room):
        """
        Broji spremne igrače u sobi.
        
        Args:
            room: Soba koja se provjerava
            
        Returns:
            int: Broj spremnih igrača
        """
        return LobbyMembership.objects.filter(
            room=room,
            is_ready=True
        ).count()
    
    @staticmethod
    def get_rooms_by_player_count(min_players=1, max_players=4, exclude_full=True):
        """
        Dohvaća sobe s određenim brojem igrača.
        
        Args:
            min_players: Minimalni broj igrača
            max_players: Maksimalni broj igrača
            exclude_full: Isključi li pune sobe
            
        Returns:
            QuerySet: QuerySet sa sobama koje imaju traženi broj igrača
        """
        query = LobbyRoom.objects.annotate(
            player_count=Count('players')
        ).filter(
            player_count__gte=min_players,
            player_count__lte=max_players
        )
        
        if exclude_full:
            query = query.exclude(status='full')
        
        return query.order_by('-created_at')
    
    @staticmethod
    def can_start_game(room):
        """
        Provjerava može li se igra pokrenuti.
        
        Args:
            room: Soba koja se provjerava
            
        Returns:
            bool: True ako se igra može pokrenuti, False inače
        """
        # Provjeri broj igrača
        player_count = LobbyMembership.objects.filter(room=room).count()
        if player_count < 4:
            return False
        
        # Provjeri jesu li svi igrači spremni
        return MembershipRepository.are_all_players_ready(room)
    
    @staticmethod
    def get_recently_joined_players(room, limit=5):
        """
        Dohvaća nedavno pridružene igrače u sobi.
        
        Args:
            room: Soba za koju se dohvaćaju igrači
            limit: Maksimalni broj igrača za dohvat
            
        Returns:
            QuerySet: QuerySet s nedavno pridruženim igračima
        """
        return LobbyMembership.objects.filter(
            room=room
        ).select_related('user').order_by('-joined_at')[:limit]
    
    @staticmethod
    def get_active_players_count():
        """
        Dohvaća broj aktivnih igrača u svim sobama.
        
        Returns:
            int: Broj aktivnih igrača
        """
        # Broj jedinstvenih korisnika koji su članovi aktivnih soba
        return LobbyMembership.objects.filter(
            room__status__in=['open', 'full', 'starting']
        ).values('user').distinct().count()