"""
Repozitorij za pristup i manipulaciju pozivnicama u predvorje.

Ovaj modul sadrži klasu InvitationRepository koja implementira metode za
dohvaćanje, stvaranje, ažuriranje i brisanje pozivnica u predvorje Belot igre.
Repozitorij apstrahira upite na bazu podataka i osigurava konzistentnost
pri manipulaciji podacima o pozivnicama.
"""

from django.db.models import Q
from django.utils import timezone

from ..models import LobbyInvitation, LobbyEvent


class InvitationRepository:
    """
    Repozitorij za rad s pozivnicama u predvorje.
    
    Implementira metode za pristup i manipulaciju pozivnicama,
    uključujući slanje, prihvaćanje, odbijanje i istek pozivnica.
    """
    
    @staticmethod
    def get_user_pending_invitations(user):
        """
        Dohvaća pozivnice koje čekaju odgovor korisnika.
        
        Args:
            user: Korisnik za kojeg se dohvaćaju pozivnice
            
        Returns:
            QuerySet: QuerySet s pozivnicama koje čekaju odgovor
        """
        return LobbyInvitation.objects.filter(
            recipient=user,
            status='pending'
        ).select_related('room', 'sender').order_by('-created_at')
    
    @staticmethod
    def get_user_sent_invitations(user):
        """
        Dohvaća pozivnice koje je poslao korisnik.
        
        Args:
            user: Korisnik koji je poslao pozivnice
            
        Returns:
            QuerySet: QuerySet s poslanim pozivnicama
        """
        return LobbyInvitation.objects.filter(
            sender=user
        ).select_related('room', 'recipient').order_by('-created_at')
    
    @staticmethod
    def get_invitation_by_id(invitation_id):
        """
        Dohvaća pozivnicu prema ID-u.
        
        Args:
            invitation_id: ID pozivnice
            
        Returns:
            LobbyInvitation: Pozivnica s traženim ID-om ili None
        """
        try:
            return LobbyInvitation.objects.select_related(
                'room', 'sender', 'recipient'
            ).get(pk=invitation_id)
        except LobbyInvitation.DoesNotExist:
            return None
    
    @staticmethod
    def create_invitation(room, sender, recipient, message=''):
        """
        Stvara novu pozivnicu.
        
        Args:
            room: Soba za koju se šalje pozivnica
            sender: Korisnik koji šalje pozivnicu
            recipient: Korisnik koji prima pozivnicu
            message: Opcionalna poruka uz pozivnicu
            
        Returns:
            LobbyInvitation: Stvorena pozivnica
            
        Raises:
            ValueError: Ako korisnik već ima aktivnu pozivnicu za tu sobu
        """
        # Provjeri ima li korisnik već pozivnicu za tu sobu
        existing = LobbyInvitation.objects.filter(
            room=room,
            recipient=recipient,
            status='pending'
        ).exists()
        
        if existing:
            raise ValueError(f"Korisnik {recipient.username} već ima aktivnu pozivnicu za ovu sobu.")
        
        # Provjeri je li korisnik već član sobe
        if room.lobbymembership_set.filter(user=recipient).exists():
            raise ValueError(f"Korisnik {recipient.username} je već član ove sobe.")
        
        # Stvori novu pozivnicu
        invitation = LobbyInvitation.objects.create(
            room=room,
            sender=sender,
            recipient=recipient,
            message=message,
            status='pending',
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        
        # Stvori događaj za slanje pozivnice
        LobbyEvent.objects.create(
            room=room,
            user=sender,
            event_type='invitation_sent',
            message=f"{sender.username} je poslao/la pozivnicu za {recipient.username}."
        )
        
        return invitation
    
    @staticmethod
    def accept_invitation(invitation_id, recipient):
        """
        Prihvaća pozivnicu i dodaje korisnika u sobu.
        
        Args:
            invitation_id: ID pozivnice
            recipient: Korisnik koji prihvaća pozivnicu (mora biti primatelj)
            
        Returns:
            bool: True ako je pozivnica uspješno prihvaćena, False inače
            
        Raises:
            ValueError: Ako pozivnica ne postoji ili korisnik nije primatelj
        """
        try:
            invitation = LobbyInvitation.objects.select_related('room').get(
                pk=invitation_id,
                recipient=recipient,
                status='pending'
            )
            
            return invitation.accept()
            
        except LobbyInvitation.DoesNotExist:
            raise ValueError("Pozivnica ne postoji ili nije namijenjena ovom korisniku.")
        except Exception as e:
            # Za ostale greške (npr. ako je soba puna)
            return False
    
    @staticmethod
    def decline_invitation(invitation_id, recipient):
        """
        Odbija pozivnicu.
        
        Args:
            invitation_id: ID pozivnice
            recipient: Korisnik koji odbija pozivnicu (mora biti primatelj)
            
        Returns:
            bool: True ako je pozivnica uspješno odbijena, False inače
            
        Raises:
            ValueError: Ako pozivnica ne postoji ili korisnik nije primatelj
        """
        try:
            invitation = LobbyInvitation.objects.select_related('room').get(
                pk=invitation_id,
                recipient=recipient,
                status='pending'
            )
            
            return invitation.decline()
            
        except LobbyInvitation.DoesNotExist:
            raise ValueError("Pozivnica ne postoji ili nije namijenjena ovom korisniku.")
        except Exception:
            return False
    
    @staticmethod
    def expire_old_invitations():
        """
        Označava sve istekle pozivnice.
        
        Returns:
            int: Broj označenih pozivnica
        """
        return LobbyInvitation.expire_old_invitations()
    
    @staticmethod
    def get_room_pending_invitations(room):
        """
        Dohvaća pozivnice koje čekaju odgovor za određenu sobu.
        
        Args:
            room: Soba za koju se dohvaćaju pozivnice
            
        Returns:
            QuerySet: QuerySet s pozivnicama koje čekaju odgovor
        """
        return LobbyInvitation.objects.filter(
            room=room,
            status='pending'
        ).select_related('sender', 'recipient').order_by('-created_at')
    
    @staticmethod
    def cancel_invitation(invitation_id, sender):
        """
        Otkazuje poslanu pozivnicu.
        
        Args:
            invitation_id: ID pozivnice
            sender: Korisnik koji otkazuje pozivnicu (mora biti pošiljatelj)
            
        Returns:
            bool: True ako je pozivnica uspješno otkazana, False inače
            
        Raises:
            ValueError: Ako pozivnica ne postoji ili korisnik nije pošiljatelj
        """
        try:
            invitation = LobbyInvitation.objects.select_related('room', 'recipient').get(
                pk=invitation_id,
                sender=sender,
                status='pending'
            )
            
            # Označi pozivnicu kao otkazanu (koristimo "expired" status za to)
            invitation.status = 'expired'
            invitation.save()
            
            # Stvori događaj za otkazivanje pozivnice
            LobbyEvent.objects.create(
                room=invitation.room,
                user=sender,
                event_type='invitation_cancelled',
                message=f"{sender.username} je otkazao/la pozivnicu za {invitation.recipient.username}.",
                is_private=True,
                private_recipient=invitation.recipient
            )
            
            return True
            
        except LobbyInvitation.DoesNotExist:
            raise ValueError("Pozivnica ne postoji ili nije poslana od strane ovog korisnika.")
        except Exception:
            return False
    
    @staticmethod
    def cancel_all_room_invitations(room):
        """
        Otkazuje sve pozivnice za određenu sobu.
        
        Args:
            room: Soba za koju se otkazuju pozivnice
            
        Returns:
            int: Broj otkazanih pozivnica
        """
        pending = LobbyInvitation.objects.filter(
            room=room,
            status='pending'
        )
        
        count = pending.count()
        pending.update(status='expired')
        
        return count