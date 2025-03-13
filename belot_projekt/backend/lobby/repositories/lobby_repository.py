"""
Repozitorij za rad s LobbyRoom entitetima.

Ovaj modul implementira repozitorij obrazac za pristup podatkovnom sloju
vezan uz sobe za igru (LobbyRoom). Sadrži metode za dohvaćanje, stvaranje,
ažuriranje i brisanje soba, kao i specijalizirane metode za filtriranje
i druge operacije specifične za sobe.
"""

from django.db.models import Q, F, Count, Avg, Sum
from django.db.models.query import QuerySet
from django.utils import timezone
from typing import Optional, List, Dict, Any, Union, Tuple

from lobby.models import LobbyRoom, LobbyMembership, LobbyMessage, LobbyInvitation


class LobbyRepository:
    """
    Repozitorij za pristup i manipulaciju LobbyRoom entitetima.
    
    Ova klasa implementira repozitorij obrazac i pruža sučelje
    za rad sa sobama za igru (LobbyRoom), zadržavajući svu logiku
    pristupa podacima na jednom mjestu.
    """
    
    @staticmethod
    def get_room_by_id(room_id: int) -> Optional[LobbyRoom]:
        """
        Dohvaća sobu prema ID-u.
        
        Args:
            room_id: ID sobe koja se traži
            
        Returns:
            LobbyRoom objekt ili None ako soba nije pronađena
        """
        try:
            return LobbyRoom.objects.get(id=room_id)
        except LobbyRoom.DoesNotExist:
            return None
    
    @staticmethod
    def get_room_by_code(code: str) -> Optional[LobbyRoom]:
        """
        Dohvaća sobu prema kodu za pristup.
        
        Args:
            code: Kod za pristup sobi
            
        Returns:
            LobbyRoom objekt ili None ako soba nije pronađena
        """
        try:
            return LobbyRoom.objects.get(access_code=code)
        except LobbyRoom.DoesNotExist:
            return None
    
    @staticmethod
    def get_all_rooms(status: Optional[str] = None) -> QuerySet[LobbyRoom]:
        """
        Dohvaća sve sobe, opcionalno filtrirane po statusu.
        
        Args:
            status: Opcijski filter statusa (npr. 'open', 'closed')
            
        Returns:
            QuerySet soba koje odgovaraju kriterijima
        """
        queryset = LobbyRoom.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        return queryset
    
    @staticmethod
    def get_public_rooms(status: Optional[str] = None) -> QuerySet[LobbyRoom]:
        """
        Dohvaća sve javne sobe, opcionalno filtrirane po statusu.
        
        Args:
            status: Opcijski filter statusa (npr. 'open', 'closed')
            
        Returns:
            QuerySet javnih soba koje odgovaraju kriterijima
        """
        queryset = LobbyRoom.objects.filter(is_private=False)
        if status:
            queryset = queryset.filter(status=status)
        return queryset
    
    @staticmethod
    def get_rooms_by_user(user_id: int, include_private: bool = True) -> QuerySet[LobbyRoom]:
        """
        Dohvaća sobe u kojima je korisnik član.
        
        Args:
            user_id: ID korisnika
            include_private: Uključi privatne sobe
            
        Returns:
            QuerySet soba u kojima je korisnik član
        """
        queryset = LobbyRoom.objects.filter(
            members__user_id=user_id
        )
        
        if not include_private:
            queryset = queryset.filter(is_private=False)
            
        return queryset
    
    @staticmethod
    def get_rooms_created_by_user(user_id: int) -> QuerySet[LobbyRoom]:
        """
        Dohvaća sobe koje je kreirao korisnik.
        
        Args:
            user_id: ID korisnika
            
        Returns:
            QuerySet soba koje je kreirao korisnik
        """
        return LobbyRoom.objects.filter(creator_id=user_id)
    
    @staticmethod
    def search_rooms(query: str, status: Optional[str] = None, include_private: bool = False) -> QuerySet[LobbyRoom]:
        """
        Pretražuje sobe prema ključnoj riječi.
        
        Args:
            query: Tekst za pretraživanje
            status: Opcijski filter statusa
            include_private: Uključi privatne sobe
            
        Returns:
            QuerySet soba koje odgovaraju kriterijima pretrage
        """
        queryset = LobbyRoom.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(creator__username__icontains=query)
        )
        
        if not include_private:
            queryset = queryset.filter(is_private=False)
            
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset
    
    @staticmethod
    def create_room(data: Dict[str, Any]) -> LobbyRoom:
        """
        Stvara novu sobu.
        
        Args:
            data: Podaci za novu sobu (name, creator_id, itd.)
            
        Returns:
            Novostvoreni LobbyRoom objekt
        """
        return LobbyRoom.objects.create(**data)
    
    @staticmethod
    def update_room(room_id: int, data: Dict[str, Any]) -> Optional[LobbyRoom]:
        """
        Ažurira postojeću sobu.
        
        Args:
            room_id: ID sobe za ažuriranje
            data: Podaci za ažuriranje
            
        Returns:
            Ažurirani LobbyRoom objekt ili None ako soba nije pronađena
        """
        rooms = LobbyRoom.objects.filter(id=room_id)
        if not rooms.exists():
            return None
            
        rooms.update(**data)
        return rooms.first()
    
    @staticmethod
    def delete_room(room_id: int) -> bool:
        """
        Briše sobu prema ID-u.
        
        Args:
            room_id: ID sobe za brisanje
            
        Returns:
            True ako je soba uspješno obrisana, False ako nije pronađena
        """
        room = LobbyRepository.get_room_by_id(room_id)
        if not room:
            return False
            
        room.delete()
        return True
    
    @staticmethod
    def get_active_player_count(room_id: int) -> int:
        """
        Dohvaća broj aktivnih igrača u sobi.
        
        Args:
            room_id: ID sobe
            
        Returns:
            Broj aktivnih igrača
        """
        return LobbyMembership.objects.filter(
            room_id=room_id, 
            is_active=True
        ).count()
    
    @staticmethod
    def get_ready_player_count(room_id: int) -> int:
        """
        Dohvaća broj spremnih igrača u sobi.
        
        Args:
            room_id: ID sobe
            
        Returns:
            Broj spremnih igrača
        """
        return LobbyMembership.objects.filter(
            room_id=room_id, 
            is_ready=True
        ).count()
    
    @staticmethod
    def get_popular_rooms(limit: int = 10) -> QuerySet[LobbyRoom]:
        """
        Dohvaća najpopularnije sobe prema broju članova.
        
        Args:
            limit: Maksimalni broj soba za dohvaćanje
            
        Returns:
            QuerySet najpopularnijih soba
        """
        return LobbyRoom.objects.filter(
            is_private=False, 
            status='open'
        ).annotate(
            member_count=Count('members')
        ).order_by('-member_count')[:limit]
    
    @staticmethod
    def get_recent_rooms(limit: int = 10) -> QuerySet[LobbyRoom]:
        """
        Dohvaća nedavno stvorene sobe.
        
        Args:
            limit: Maksimalni broj soba za dohvaćanje
            
        Returns:
            QuerySet nedavno stvorenih soba
        """
        return LobbyRoom.objects.filter(
            is_private=False, 
            status='open'
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def is_room_full(room_id: int) -> bool:
        """
        Provjerava je li soba puna.
        
        Args:
            room_id: ID sobe
            
        Returns:
            True ako je soba puna, False inače
        """
        room = LobbyRepository.get_room_by_id(room_id)
        if not room:
            return False
            
        active_players = LobbyRepository.get_active_player_count(room_id)
        return active_players >= room.max_players
    
    @staticmethod
    def is_user_in_room(room_id: int, user_id: int) -> bool:
        """
        Provjerava je li korisnik član sobe.
        
        Args:
            room_id: ID sobe
            user_id: ID korisnika
            
        Returns:
            True ako je korisnik član sobe, False inače
        """
        return LobbyMembership.objects.filter(
            room_id=room_id, 
            user_id=user_id
        ).exists()
    
    @staticmethod
    def get_rooms_starting_soon() -> QuerySet[LobbyRoom]:
        """
        Dohvaća sobe koje će uskoro početi (status 'starting').
        
        Returns:
            QuerySet soba koje će uskoro početi
        """
        return LobbyRoom.objects.filter(status='starting')
    
    @staticmethod
    def count_rooms_by_status() -> Dict[str, int]:
        """
        Broji sobe prema statusu.
        
        Returns:
            Rječnik s brojem soba po statusu
        """
        result = LobbyRoom.objects.values('status').annotate(count=Count('id'))
        return {item['status']: item['count'] for item in result}
    
    @staticmethod
    def update_room_status(room_id: int, status: str) -> Optional[LobbyRoom]:
        """
        Ažurira status sobe.
        
        Args:
            room_id: ID sobe
            status: Novi status
            
        Returns:
            Ažurirani LobbyRoom objekt ili None ako soba nije pronađena
        """
        return LobbyRepository.update_room(room_id, {'status': status})
    
    @staticmethod
    def check_expired_rooms(timeout_minutes: int = 60) -> List[LobbyRoom]:
        """
        Dohvaća neaktivne sobe koje su istekle.
        
        Args:
            timeout_minutes: Broj minuta neaktivnosti nakon kojeg se soba smatra isteklom
            
        Returns:
            Lista isteklih soba
        """
        threshold = timezone.now() - timezone.timedelta(minutes=timeout_minutes)
        
        expired_rooms = LobbyRoom.objects.filter(
            status__in=['open', 'waiting'],
            updated_at__lt=threshold
        )
        
        return list(expired_rooms)
    
    @staticmethod
    def get_user_recent_rooms(user_id: int, limit: int = 5) -> QuerySet[LobbyRoom]:
        """
        Dohvaća sobe koje je korisnik nedavno posjetio.
        
        Args:
            user_id: ID korisnika
            limit: Maksimalni broj soba za dohvaćanje
            
        Returns:
            QuerySet nedavno posjećenih soba
        """
        memberships = LobbyMembership.objects.filter(
            user_id=user_id
        ).order_by('-joined_at')[:limit]
        
        room_ids = [m.room_id for m in memberships]
        
        return LobbyRoom.objects.filter(id__in=room_ids).order_by('-updated_at')