"""
Event klase za Belot igru.

Ovaj modul definira strukturu događaja (events) koji se koriste za komunikaciju
između različitih dijelova sustava. Svaki event predstavlja nešto što se dogodilo
u igri, poput stvaranja igre, igranja poteza, završetka štiha, itd.

Ovi eventi se prosljeđuju event handlerima putem dispatch_event funkcije,
što omogućuje reagiranje na promjene stanja igre bez čvrste povezanosti komponenti.
"""

from abc import ABC
from typing import Dict, Any, Optional, List
from django.utils import timezone


class GameEvent(ABC):
    """
    Apstraktna bazna klasa za sve događaje u Belot igri.
    
    Pruža osnovnu strukturu i funkcionalnost koju naslijeđuju
    svi specifični tipovi događaja.
    """
    
    def __init__(self, event_type: str):
        """
        Inicijalizira instancu GameEvent.
        
        Args:
            event_type: Tip događaja (npr. 'game.created', 'move.played')
        """
        self.event_type = event_type
        self.timestamp = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Pretvara objekt događaja u rječnik za serijalizaciju.
        
        Returns:
            Rječnik s atributima događaja
        """
        return {
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat()
        }


class GameCreatedEvent(GameEvent):
    """Događaj koji se emitira kada je stvorena nova igra."""
    
    def __init__(self, game_id: str, creator_id: int, creator_name: str, is_private: bool):
        """
        Inicijalizira GameCreatedEvent.
        
        Args:
            game_id: UUID igre koja je stvorena
            creator_id: ID korisnika koji je stvorio igru
            creator_name: Korisničko ime kreatora
            is_private: Zastavica koja označava je li igra privatna
        """
        super().__init__('game.created')
        self.game_id = game_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.is_private = is_private
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara GameCreatedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'creator_id': self.creator_id,
            'creator_name': self.creator_name,
            'is_private': self.is_private
        })
        return data


class GameJoinedEvent(GameEvent):
    """Događaj koji se emitira kada se igrač pridruži igri."""
    
    def __init__(self, game_id: str, player_id: int, player_name: str):
        """
        Inicijalizira GameJoinedEvent.
        
        Args:
            game_id: UUID igre kojoj se igrač pridružio
            player_id: ID igrača koji se pridružio
            player_name: Korisničko ime igrača
        """
        super().__init__('game.joined')
        self.game_id = game_id
        self.player_id = player_id
        self.player_name = player_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara GameJoinedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'player_id': self.player_id,
            'player_name': self.player_name
        })
        return data


class GameStartedEvent(GameEvent):
    """Događaj koji se emitira kada igra započne."""
    
    def __init__(self, game_id: str, dealer_id: int, dealer_name: str, 
                 team_a_players: List[Dict[str, Any]], team_b_players: List[Dict[str, Any]]):
        """
        Inicijalizira GameStartedEvent.
        
        Args:
            game_id: UUID igre koja je započela
            dealer_id: ID igrača koji je prvi djelitelj
            dealer_name: Korisničko ime djelitelja
            team_a_players: Lista rječnika s informacijama o igračima tima A
            team_b_players: Lista rječnika s informacijama o igračima tima B
        """
        super().__init__('game.started')
        self.game_id = game_id
        self.dealer_id = dealer_id
        self.dealer_name = dealer_name
        self.team_a_players = team_a_players
        self.team_b_players = team_b_players
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara GameStartedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'dealer_id': self.dealer_id,
            'dealer_name': self.dealer_name,
            'team_a_players': self.team_a_players,
            'team_b_players': self.team_b_players
        })
        return data


class GameFinishedEvent(GameEvent):
    """Događaj koji se emitira kada igra završi."""
    
    def __init__(self, game_id: str, winner_team: str, team_a_score: int, team_b_score: int,
                 duration_seconds: int):
        """
        Inicijalizira GameFinishedEvent.
        
        Args:
            game_id: UUID igre koja je završila
            winner_team: Oznaka pobjedničkog tima ('a' ili 'b')
            team_a_score: Ukupni bodovi tima A
            team_b_score: Ukupni bodovi tima B
            duration_seconds: Trajanje igre u sekundama
        """
        super().__init__('game.finished')
        self.game_id = game_id
        self.winner_team = winner_team
        self.team_a_score = team_a_score
        self.team_b_score = team_b_score
        self.duration_seconds = duration_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara GameFinishedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'winner_team': self.winner_team,
            'team_a_score': self.team_a_score,
            'team_b_score': self.team_b_score,
            'duration_seconds': self.duration_seconds
        })
        return data


class RoundStartedEvent(GameEvent):
    """Događaj koji se emitira kada započne nova runda."""
    
    def __init__(self, game_id: str, round_id: str, round_number: int,
                 dealer_id: int, dealer_name: str):
        """
        Inicijalizira RoundStartedEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde koja je započela
            round_number: Redni broj runde
            dealer_id: ID igrača koji je djelitelj u ovoj rundi
            dealer_name: Korisničko ime djelitelja
        """
        super().__init__('round.started')
        self.game_id = game_id
        self.round_id = round_id
        self.round_number = round_number
        self.dealer_id = dealer_id
        self.dealer_name = dealer_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara RoundStartedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'round_number': self.round_number,
            'dealer_id': self.dealer_id,
            'dealer_name': self.dealer_name
        })
        return data


class RoundFinishedEvent(GameEvent):
    """Događaj koji se emitira kada završi runda."""
    
    def __init__(self, game_id: str, round_id: str, round_number: int,
                 team_a_score: int, team_b_score: int, winner_team: str,
                 game_team_a_score: int, game_team_b_score: int):
        """
        Inicijalizira RoundFinishedEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde koja je završila
            round_number: Redni broj runde
            team_a_score: Bodovi tima A u ovoj rundi
            team_b_score: Bodovi tima B u ovoj rundi
            winner_team: Oznaka pobjedničkog tima u ovoj rundi ('a' ili 'b')
            game_team_a_score: Ukupni bodovi tima A u igri nakon runde
            game_team_b_score: Ukupni bodovi tima B u igri nakon runde
        """
        super().__init__('round.finished')
        self.game_id = game_id
        self.round_id = round_id
        self.round_number = round_number
        self.team_a_score = team_a_score
        self.team_b_score = team_b_score
        self.winner_team = winner_team
        self.game_team_a_score = game_team_a_score
        self.game_team_b_score = game_team_b_score
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara RoundFinishedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'round_number': self.round_number,
            'team_a_score': self.team_a_score,
            'team_b_score': self.team_b_score,
            'winner_team': self.winner_team,
            'game_team_a_score': self.game_team_a_score,
            'game_team_b_score': self.game_team_b_score
        })
        return data


class TrumpCalledEvent(GameEvent):
    """Događaj koji se emitira kada igrač zove aduta."""
    
    def __init__(self, game_id: str, round_id: str, player_id: int, player_name: str,
                 trump_suit: str, calling_team: str):
        """
        Inicijalizira TrumpCalledEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde
            player_id: ID igrača koji je zvao aduta
            player_name: Korisničko ime igrača
            trump_suit: Adutska boja (spades, hearts, diamonds, clubs)
            calling_team: Oznaka tima koji je zvao aduta ('a' ili 'b')
        """
        super().__init__('trump.called')
        self.game_id = game_id
        self.round_id = round_id
        self.player_id = player_id
        self.player_name = player_name
        self.trump_suit = trump_suit
        self.calling_team = calling_team
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara TrumpCalledEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'trump_suit': self.trump_suit,
            'calling_team': self.calling_team
        })
        return data


class MovePlayedEvent(GameEvent):
    """Događaj koji se emitira kada igrač odigra potez."""
    
    def __init__(self, game_id: str, round_id: str, player_id: int, player_name: str,
                 card: str, trick_number: int, card_order: int, is_first_in_trick: bool):
        """
        Inicijalizira MovePlayedEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde
            player_id: ID igrača koji je odigrao kartu
            player_name: Korisničko ime igrača
            card: Kod karte (npr. "7S", "AH", "JD")
            trick_number: Redni broj štiha (počevši od 0)
            card_order: Redni broj karte u štihu (0-3)
            is_first_in_trick: Je li ovo prva karta u štihu
        """
        super().__init__('move.played')
        self.game_id = game_id
        self.round_id = round_id
        self.player_id = player_id
        self.player_name = player_name
        self.card = card
        self.trick_number = trick_number
        self.card_order = card_order
        self.is_first_in_trick = is_first_in_trick
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara MovePlayedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'card': self.card,
            'trick_number': self.trick_number,
            'card_order': self.card_order,
            'is_first_in_trick': self.is_first_in_trick
        })
        return data


class TrickCompletedEvent(GameEvent):
    """Događaj koji se emitira kada je štih završen."""
    
    def __init__(self, game_id: str, round_id: str, trick_number: int,
                 winner_id: int, winner_name: str, winner_team: str,
                 trick_points: int, is_last_trick: bool):
        """
        Inicijalizira TrickCompletedEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde
            trick_number: Redni broj štiha (počevši od 0)
            winner_id: ID igrača koji je osvojio štih
            winner_name: Korisničko ime pobjednika štiha
            winner_team: Oznaka tima koji je osvojio štih ('a' ili 'b')
            trick_points: Bodovi osvojeni u štihu
            is_last_trick: Je li ovo zadnji štih u rundi
        """
        super().__init__('trick.completed')
        self.game_id = game_id
        self.round_id = round_id
        self.trick_number = trick_number
        self.winner_id = winner_id
        self.winner_name = winner_name
        self.winner_team = winner_team
        self.trick_points = trick_points
        self.is_last_trick = is_last_trick
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara TrickCompletedEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'trick_number': self.trick_number,
            'winner_id': self.winner_id,
            'winner_name': self.winner_name,
            'winner_team': self.winner_team,
            'trick_points': self.trick_points,
            'is_last_trick': self.is_last_trick
        })
        return data


class DeclarationMadeEvent(GameEvent):
    """Događaj koji se emitira kada igrač prijavi zvanje."""
    
    def __init__(self, game_id: str, round_id: str, player_id: int, player_name: str,
                 declaration_type: str, cards: List[str], value: int, suit: Optional[str] = None):
        """
        Inicijalizira DeclarationMadeEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde
            player_id: ID igrača koji je prijavio zvanje
            player_name: Korisničko ime igrača
            declaration_type: Tip zvanja (npr. 'sequence_3', 'four_jacks')
            cards: Lista kodova karata koje čine zvanje
            value: Bodovna vrijednost zvanja
            suit: Boja za sekvence i belu (opcionalno)
        """
        super().__init__('declaration.made')
        self.game_id = game_id
        self.round_id = round_id
        self.player_id = player_id
        self.player_name = player_name
        self.declaration_type = declaration_type
        self.cards = cards
        self.value = value
        self.suit = suit
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara DeclarationMadeEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'declaration_type': self.declaration_type,
            'cards': self.cards,
            'value': self.value
        })
        
        if self.suit:
            data['suit'] = self.suit
            
        return data


class BelaCalledEvent(GameEvent):
    """Događaj koji se emitira kada igrač prijavi belu."""
    
    def __init__(self, game_id: str, round_id: str, player_id: int, player_name: str, suit: str):
        """
        Inicijalizira BelaCalledEvent.
        
        Args:
            game_id: UUID igre
            round_id: UUID runde
            player_id: ID igrača koji je prijavio belu
            player_name: Korisničko ime igrača
            suit: Boja bele (ista kao adut)
        """
        super().__init__('bela.called')
        self.game_id = game_id
        self.round_id = round_id
        self.player_id = player_id
        self.player_name = player_name
        self.suit = suit
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara BelaCalledEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'round_id': self.round_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'suit': self.suit
        })
        return data


class ChatMessageEvent(GameEvent):
    """Događaj koji se emitira kada igrač pošalje poruku u chat."""
    
    def __init__(self, game_id: str, player_id: int, player_name: str, message: str):
        """
        Inicijalizira ChatMessageEvent.
        
        Args:
            game_id: UUID igre
            player_id: ID igrača koji šalje poruku
            player_name: Korisničko ime igrača
            message: Tekst poruke
        """
        super().__init__('chat.message')
        self.game_id = game_id
        self.player_id = player_id
        self.player_name = player_name
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        """Pretvara ChatMessageEvent u rječnik."""
        data = super().to_dict()
        data.update({
            'game_id': self.game_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'message': self.message
        })
        return data