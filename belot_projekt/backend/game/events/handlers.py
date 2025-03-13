"""
Event handleri za obradu događaja u Belot igri.

Ovaj modul implementira mehanizam za rukovanje događajima (event handling)
koji omogućuje različitim komponentama sustava da reagiraju na događaje
bez čvrste međusobne povezanosti. Temelji se na obrascu promatrača (observer pattern).

Osnovni koncept je da emitelji događaja (event emitters) pozivaju funkciju
dispatch_event, a handleri (event handlers) reagiraju na specifične tipove događaja.
"""

import logging
import asyncio
from typing import Dict, List, Type, Callable, Optional, Any, Set
from abc import ABC, abstractmethod
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger('game.events')

# Registry za event handler-e
_handlers: Dict[str, List[Callable]] = {}

def register_handler(event_type: str, handler: Callable) -> None:
    """
    Registrira handler funkciju za specifični tip događaja.
    
    Args:
        event_type: Tip događaja (npr. 'game.created', 'move.played')
        handler: Funkcija koja će obrađivati događaj
    """
    if event_type not in _handlers:
        _handlers[event_type] = []
    
    if handler not in _handlers[event_type]:
        _handlers[event_type].append(handler)
        logger.debug(f"Registriran handler za '{event_type}': {handler.__name__}")


def unregister_handler(event_type: str, handler: Callable) -> None:
    """
    Poništava registraciju handler funkcije za specifični tip događaja.
    
    Args:
        event_type: Tip događaja
        handler: Funkcija koja je bila registrirana
    """
    if event_type in _handlers and handler in _handlers[event_type]:
        _handlers[event_type].remove(handler)
        logger.debug(f"Poništena registracija handlera za '{event_type}': {handler.__name__}")


def dispatch_event(event: 'GameEvent') -> None:
    """
    Dispečira događaj svim registriranim handlerima.
    
    Args:
        event: Objekt događaja koji će biti obrađen
    """
    event_type = event.event_type
    
    if event_type in _handlers:
        for handler in _handlers[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Greška u handleru {handler.__name__} za događaj {event_type}: {str(e)}")
    else:
        logger.debug(f"Nema registriranih handlera za događaj: {event_type}")


class EventHandler(ABC):
    """
    Apstraktna bazna klasa za sve event handlere.
    
    Ova klasa definira osnovni obrazac za implementacije handlera i
    pruža metodu za automatsku registraciju na određene tipove događaja.
    """
    
    def __init__(self):
        """Inicijalizira handler i registrira ga na odgovarajuće događaje."""
        self.registered_events: Set[str] = set()
        self._register_handlers()
    
    @abstractmethod
    def _register_handlers(self) -> None:
        """
        Registrira handler na specifične tipove događaja.
        
        Konkretne implementacije ove metode trebaju pozvati self._register
        za svaki tip događaja koji handler želi obrađivati.
        """
        pass
    
    def _register(self, event_type: str) -> None:
        """
        Pomoćna metoda za registraciju handlera na specifični tip događaja.
        
        Args:
            event_type: Tip događaja za registraciju
        """
        register_handler(event_type, self.handle_event)
        self.registered_events.add(event_type)
    
    def _unregister_all(self) -> None:
        """Poništava registraciju handlera sa svih događaja."""
        for event_type in self.registered_events:
            unregister_handler(event_type, self.handle_event)
        self.registered_events.clear()
    
    @abstractmethod
    def handle_event(self, event: 'GameEvent') -> None:
        """
        Obrađuje događaj.
        
        Args:
            event: Objekt događaja koji se obrađuje
        """
        pass
    
    def __del__(self):
        """Čisti registracije prilikom uništavanja objekta."""
        self._unregister_all()


class WebSocketEventHandler(EventHandler):
    """
    Handler koji prosljeđuje događaje igre svim povezanim WebSocket klijentima.
    
    Koristi Django Channels za slanje poruka preko WebSocket-a.
    """
    
    def _register_handlers(self) -> None:
        """Registrira se na sve relevantne događaje igre."""
        self._register('game.created')
        self._register('game.joined')
        self._register('game.started')
        self._register('game.finished')
        self._register('round.started')
        self._register('round.finished')
        self._register('trump.called')
        self._register('move.played')
        self._register('trick.completed')
        self._register('declaration.made')
        self._register('bela.called')
        self._register('chat.message')
    
    def handle_event(self, event: 'GameEvent') -> None:
        """
        Prosljeđuje događaj na odgovarajuće WebSocket grupe.
        
        Args:
            event: Objekt događaja koji će biti proslijeđen
        """
        try:
            # Dohvaćanje channel layer-a za slanje poruka
            channel_layer = get_channel_layer()
            
            # Generiranje imena grupe za igru
            if hasattr(event, 'game_id'):
                # Koristi ID igre za emititranje događaja samo igračima te igre
                group_name = f"game_{event.game_id}"
                
                # Priprema podataka za slanje
                message = {
                    'type': 'game_event',  # Ovo se mapira na game_event metodu u consumer-u
                    'event_type': event.event_type,
                    'data': event.to_dict()
                }
                
                # Asinkrono slanje poruke na grupu
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    message
                )
                
                logger.debug(f"Poslana WebSocket poruka grupi {group_name}: {event.event_type}")
            else:
                logger.warning(f"Događaj nema game_id, nije moguće odrediti grupu: {event.event_type}")
        
        except Exception as e:
            logger.error(f"Greška pri slanju WebSocket poruke: {str(e)}")


class GameStateUpdateHandler(EventHandler):
    """
    Handler koji ažurira stanje igre i modele u bazi podataka.
    
    Ovaj handler osigurava da su modeli u bazi podataka usklađeni s
    trenutnim stanjem igre nakon svakog događaja.
    """
    
    def _register_handlers(self) -> None:
        """Registrira se na događaje koji zahtijevaju ažuriranje stanja."""
        self._register('game.joined')
        self._register('game.started')
        self._register('game.finished')
        self._register('round.started')
        self._register('round.finished')
        self._register('trump.called')
        self._register('move.played')
        self._register('trick.completed')
        self._register('declaration.made')
    
    def handle_event(self, event: 'GameEvent') -> None:
        """
        Ažurira stanje igre u bazi podataka.
        
        Args:
            event: Objekt događaja koji sadrži podatke za ažuriranje
        """
        try:
            # Uvoz modela ovdje da se izbjegnu cirkularni importi
            from game.models import Game, Round, Move, Declaration
            
            # Ažuriranje modela ovisno o tipu događaja
            if event.event_type == 'game.joined':
                self._handle_game_joined(event, Game)
            elif event.event_type == 'game.started':
                self._handle_game_started(event, Game)
            elif event.event_type == 'game.finished':
                self._handle_game_finished(event, Game)
            elif event.event_type == 'round.started':
                self._handle_round_started(event, Round)
            elif event.event_type == 'round.finished':
                self._handle_round_finished(event, Round, Game)
            elif event.event_type == 'trump.called':
                self._handle_trump_called(event, Round)
            elif event.event_type == 'move.played':
                self._handle_move_played(event, Move)
            elif event.event_type == 'trick.completed':
                self._handle_trick_completed(event, Move)
            elif event.event_type == 'declaration.made':
                self._handle_declaration_made(event, Declaration)
                
        except Exception as e:
            logger.error(f"Greška pri ažuriranju stanja igre: {str(e)}")
    
    def _handle_game_joined(self, event, Game):
        """Ažurira model Game kada se igrač pridruži."""
        game = Game.objects.get(id=event.game_id)
        user = User.objects.get(id=event.player_id)
        if not game.players.filter(id=user.id).exists():
            game.players.add(user)
            game.active_players.add(user)
        
    def _handle_game_started(self, event, Game):
        """Ažurira model Game kada igra započne."""
        game = Game.objects.get(id=event.game_id)
        game.status = 'in_progress'
        game.started_at = timezone.now()
        game.save()
        
    def _handle_game_finished(self, event, Game):
        """Ažurira model Game kada igra završi."""
        game = Game.objects.get(id=event.game_id)
        game.status = 'finished'
        game.finished_at = timezone.now()
        game.winner_team = event.winner_team
        game.save()
        
    def _handle_round_started(self, event, Round):
        """Ažurira ili stvara model Round kada započne nova runda."""
        # Logika za stvaranje nove runde ili ažuriranje postojeće
        pass
        
    def _handle_round_finished(self, event, Round, Game):
        """Ažurira modele Round i Game kada završi runda."""
        round_obj = Round.objects.get(id=event.round_id)
        round_obj.is_completed = True
        round_obj.completed_at = timezone.now()
        round_obj.team_a_score = event.team_a_score
        round_obj.team_b_score = event.team_b_score
        round_obj.winner_team = event.winner_team
        round_obj.save()
        
        # Ažuriranje ukupnog rezultata igre
        game = round_obj.game
        game.team_a_score = event.game_team_a_score
        game.team_b_score = event.game_team_b_score
        game.save()
        
    def _handle_trump_called(self, event, Round):
        """Ažurira model Round kada se zove adut."""
        round_obj = Round.objects.get(id=event.round_id)
        round_obj.trump_suit = event.trump_suit
        round_obj.calling_team = event.calling_team
        round_obj.caller = User.objects.get(id=event.player_id)
        round_obj.save()
        
    def _handle_move_played(self, event, Move):
        """Stvara novi model Move kada igrač odigra potez."""
        # Logika za stvaranje novog poteza
        pass
        
    def _handle_trick_completed(self, event, Move):
        """Ažurira model Move za označavanje pobjedničkog poteza."""
        # Logika za označavanje pobjedničkog poteza
        pass
        
    def _handle_declaration_made(self, event, Declaration):
        """Stvara novi model Declaration kada igrač prijavi zvanje."""
        # Logika za stvaranje novog zvanja
        pass


class NotificationHandler(EventHandler):
    """
    Handler koji generira notifikacije za korisnike.
    
    Ove notifikacije mogu uključivati sistemske poruke u chatu,
    email obavijesti, ili push notifikacije.
    """
    
    def _register_handlers(self) -> None:
        """Registrira se na događaje koji generiraju notifikacije."""
        self._register('game.created')
        self._register('game.joined')
        self._register('game.started')
        self._register('game.finished')
        self._register('round.started')
        self._register('trump.called')
        self._register('declaration.made')
        self._register('bela.called')
    
    def handle_event(self, event: 'GameEvent') -> None:
        """
        Generira i šalje odgovarajuće obavijesti za događaj.
        
        Args:
            event: Objekt događaja koji pokreće notifikaciju
        """
        try:
            # Logika za slanje obavijesti (sistemske poruke, email, push)
            channel_layer = get_channel_layer()
            
            if hasattr(event, 'game_id'):
                group_name = f"game_{event.game_id}"
                
                # Generiranje poruke ovisno o tipu događaja
                message = self._create_notification_message(event)
                
                if message:
                    # Slanje sistemske poruke u chat
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'chat_message',
                            'message': {
                                'sender': 'Sustav',
                                'text': message,
                                'timestamp': timezone.now().isoformat(),
                                'is_system': True
                            }
                        }
                    )
                    
                    logger.debug(f"Poslana sistemska notifikacija: {message}")
            
        except Exception as e:
            logger.error(f"Greška pri slanju notifikacije: {str(e)}")
    
    def _create_notification_message(self, event: 'GameEvent') -> Optional[str]:
        """
        Stvara tekst notifikacije ovisno o tipu događaja.
        
        Args:
            event: Objekt događaja
            
        Returns:
            Tekst notifikacije ili None ako događaj ne generira notifikaciju
        """
        # Generiranje poruke ovisno o tipu događaja
        if event.event_type == 'game.joined':
            return f"Igrač {event.player_name} se pridružio igri."
            
        elif event.event_type == 'game.started':
            return "Igra je započela. Sretno svima!"
            
        elif event.event_type == 'game.finished':
            tim_ime = "A" if event.winner_team == 'a' else "B"
            return f"Igra je završena. Pobjednik je Tim {tim_ime}!"
            
        elif event.event_type == 'round.started':
            return f"Započela je runda {event.round_number}. Djelitelj je {event.dealer_name}."
            
        elif event.event_type == 'trump.called':
            suit_names = {
                'spades': 'Pik',
                'hearts': 'Herc',
                'diamonds': 'Karo',
                'clubs': 'Tref',
                'no_trump': 'Bez aduta',
                'all_trump': 'Sve boje su adut'
            }
            suit_name = suit_names.get(event.trump_suit, event.trump_suit)
            return f"Igrač {event.player_name} je zvao adut: {suit_name}."
            
        elif event.event_type == 'declaration.made':
            declaration_names = {
                'belot': 'Belot',
                'four_jacks': 'Četiri dečka',
                'four_nines': 'Četiri devetke',
                'four_aces': 'Četiri asa',
                'four_kings': 'Četiri kralja',
                'four_queens': 'Četiri dame',
                'sequence_5_plus': 'Kvinta i više',
                'sequence_4': 'Kvarta',
                'sequence_3': 'Terca'
            }
            decl_name = declaration_names.get(event.declaration_type, event.declaration_type)
            return f"Igrač {event.player_name} je prijavio zvanje: {decl_name} ({event.value} bodova)."
            
        elif event.event_type == 'bela.called':
            return f"Igrač {event.player_name} je prijavio belu (20 bodova)."
            
        return None


class StatisticsUpdateHandler(EventHandler):
    """
    Handler koji ažurira statistiku igre i igrača.
    
    Prati različite statističke podatke poput broja odigranih igara,
    pobjedničkih igara, prosječnog trajanja, itd.
    """
    
    def _register_handlers(self) -> None:
        """Registrira se na događaje koji utječu na statistiku."""
        self._register('game.finished')
        self._register('trick.completed')
        self._register('declaration.made')
    
    def handle_event(self, event: 'GameEvent') -> None:
        """
        Ažurira statistiku na temelju događaja.
        
        Args:
            event: Objekt događaja koji utječe na statistiku
        """
        try:
            # Uvoz modela statistike (ako postoji)
            from stats.models import PlayerStatistics, GameStatistics
            
            if event.event_type == 'game.finished':
                self._update_game_statistics(event, GameStatistics)
                self._update_player_statistics(event, PlayerStatistics)
                
        except ImportError:
            # Ako moduli statistike nisu dostupni, logger i ignoriraj
            logger.warning("Moduli statistike nisu dostupni, statistika nije ažurirana")
        except Exception as e:
            logger.error(f"Greška pri ažuriranju statistike: {str(e)}")
    
    def _update_game_statistics(self, event, GameStatistics):
        """Ažurira statistiku igre."""
        # Implementacija ažuriranja statistike igre
        pass
    
    def _update_player_statistics(self, event, PlayerStatistics):
        """Ažurira statistiku igrača."""
        # Implementacija ažuriranja statistike igrača
        pass