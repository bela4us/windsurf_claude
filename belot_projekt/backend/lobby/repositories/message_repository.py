"""
Repozitorij za pristup i manipulaciju porukama u predvorju.

Ovaj modul sadrži klasu MessageRepository koja implementira metode za
dohvaćanje, stvaranje i upravljanje porukama chata u sobama predvorja Belot igre.
Repozitorij apstrahira upite na bazu podataka i osigurava konzistentnost
pri manipulaciji podacima o porukama.
"""

from django.utils import timezone
from django.db.models import Q

from ..models import LobbyMessage, LobbyRoom, LobbyMembership


class MessageRepository:
    """
    Repozitorij za rad s porukama u predvorju.
    
    Implementira metode za pristup i manipulaciju porukama,
    uključujući dohvaćanje, slanje i filtriranje poruka.
    """
    
    @staticmethod
    def get_room_messages(room, limit=50):
        """
        Dohvaća poruke za određenu sobu.
        
        Args:
            room: Soba za koju se dohvaćaju poruke
            limit: Maksimalni broj poruka za dohvat
            
        Returns:
            QuerySet: QuerySet s porukama sobe
        """
        return LobbyMessage.objects.filter(
            room=room
        ).select_related('sender').order_by('created_at')[:limit]
    
    @staticmethod
    def get_room_messages_since(room, timestamp):
        """
        Dohvaća poruke za određenu sobu od određenog vremena.
        
        Args:
            room: Soba za koju se dohvaćaju poruke
            timestamp: Vrijeme od kojeg se dohvaćaju poruke
            
        Returns:
            QuerySet: QuerySet s porukama sobe nakon timestamp-a
        """
        try:
            since_time = timezone.datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            return LobbyMessage.objects.filter(
                room=room,
                created_at__gt=since_time
            ).select_related('sender').order_by('created_at')
        except (ValueError, TypeError):
            # Ako je timestamp nevažeći, vrati prazni QuerySet
            return LobbyMessage.objects.none()
    
    @staticmethod
    def create_message(room, sender, content):
        """
        Stvara novu poruku u sobi.
        
        Args:
            room: Soba u koju se šalje poruka
            sender: Korisnik koji šalje poruku
            content: Sadržaj poruke
            
        Returns:
            LobbyMessage: Stvorena poruka
            
        Raises:
            ValueError: Ako korisnik nije član sobe
        """
        # Provjeri je li korisnik član sobe
        if not LobbyMembership.objects.filter(room=room, user=sender).exists():
            raise ValueError(f"Korisnik {sender.username} nije član ove sobe.")
        
        # Provjeri da sadržaj nije prazan
        if not content.strip():
            raise ValueError("Sadržaj poruke ne može biti prazan.")
        
        # Stvori novu poruku
        message = LobbyMessage.objects.create(
            room=room,
            sender=sender,
            content=content,
            is_system_message=False
        )
        
        return message
    
    @staticmethod
    def add_system_message(room, content):
        """
        Dodaje sistemsku poruku u sobu.
        
        Args:
            room: Soba u koju se dodaje poruka
            content: Sadržaj sistemske poruke
            
        Returns:
            LobbyMessage: Stvorena sistemska poruka
        """
        return LobbyMessage.add_system_message(room, content)
    
    @staticmethod
    def get_message_by_id(message_id):
        """
        Dohvaća poruku prema ID-u.
        
        Args:
            message_id: ID poruke
            
        Returns:
            LobbyMessage: Poruka s traženim ID-om ili None
        """
        try:
            return LobbyMessage.objects.select_related('room', 'sender').get(pk=message_id)
        except LobbyMessage.DoesNotExist:
            return None
    
    @staticmethod
    def search_messages(room, query):
        """
        Pretražuje poruke u sobi.
        
        Args:
            room: Soba u kojoj se pretražuju poruke
            query: Pojam za pretraživanje
            
        Returns:
            QuerySet: QuerySet s porukama koje sadrže traženi pojam
        """
        return LobbyMessage.objects.filter(
            room=room,
            content__icontains=query
        ).select_related('sender').order_by('-created_at')
    
    @staticmethod
    def get_user_messages(user, limit=50):
        """
        Dohvaća poruke koje je poslao određeni korisnik.
        
        Args:
            user: Korisnik čije se poruke dohvaćaju
            limit: Maksimalni broj poruka za dohvat
            
        Returns:
            QuerySet: QuerySet s porukama korisnika
        """
        return LobbyMessage.objects.filter(
            sender=user,
            is_system_message=False
        ).select_related('room').order_by('-created_at')[:limit]
    
    @staticmethod
    def delete_old_messages(days=30):
        """
        Briše stare poruke iz zatvorenih soba.
        
        Args:
            days: Broj dana nakon kojih se poruke brišu
            
        Returns:
            int: Broj obrisanih poruka
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Dohvati poruke za brisanje (samo iz zatvorenih soba)
        messages_to_delete = LobbyMessage.objects.filter(
            room__status='closed',
            created_at__lt=cutoff_date
        )
        
        count = messages_to_delete.count()
        messages_to_delete.delete()
        
        return count
    
    @staticmethod
    def get_recent_activity_rooms(limit=5):
        """
        Dohvaća sobe s nedavnom aktivnošću poruka.
        
        Args:
            limit: Maksimalni broj soba za dohvat
            
        Returns:
            QuerySet: QuerySet sa sobama koje imaju nedavnu aktivnost
        """
        # Dohvati ID-jeve soba s nedavnim porukama
        active_room_ids = LobbyMessage.objects.values('room').distinct().order_by(
            'room', '-created_at'
        )[:limit].values_list('room', flat=True)
        
        # Dohvati sobe s tim ID-jevima
        return LobbyRoom.objects.filter(
            id__in=active_room_ids
        ).exclude(
            status='closed'
        ).order_by('-created_at')