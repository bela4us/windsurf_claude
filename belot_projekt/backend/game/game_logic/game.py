"""
Modul koji definira glavnu logiku Belot igre.

Ovaj modul pruža implementaciju klase Game koja sadrži središnju logiku
za igru Belot, upravljajući tijekom igre, potezima igrača, zvanjima,
bodovanjem i određivanjem pobjednika.
"""

import random
import logging
from functools import lru_cache

from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from game.game_logic.player import Player
from game.game_logic.validators.move_validator import MoveValidator
from game.game_logic.validators.call_validator import CallValidator
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class Game:
    """
    Klasa koja implementira logiku Belot igre.
    
    Upravlja kompletnim tijekom igre, od dijeljenja karata do određivanja
    pobjednika, prateći stanje igre, zvanja, štihove i bodove.
    
    Attributes:
        points_to_win (int): Broj bodova potreban za pobjedu
        players (list): Lista igrača u igri
        team_a (list): Igrači u timu A
        team_b (list): Igrači u timu B
        team_a_score (int): Ukupni bodovi tima A
        team_b_score (int): Ukupni bodovi tima B
        current_round (Round): Trenutna runda u igri
        round_number (int): Redni broj trenutne runde
        rules (Rules): Pravila igre
        scoring (Scoring): Sustav bodovanja
        move_validator (MoveValidator): Validator poteza
        call_validator (CallValidator): Validator zvanja
        game_status (str): Status igre ('waiting', 'in_progress', 'finished')
        winner_team (str): Pobjednički tim ('a', 'b' ili None)
        _cache_timestamp (float): Vremenska oznaka za invalidaciju keša
    """
    
    # Konstante za igru
    POINTS_TO_WIN = 1001  # Broj bodova potreban za pobjedu
    CARDS_PER_PLAYER = 8  # Broj karata po igraču u jednoj rundi
    TRICKS_PER_ROUND = 8  # Broj štihova u jednoj rundi
    
    # Konstante za status igre
    STATUS_WAITING = 'waiting'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_FINISHED = 'finished'
    
    @track_execution_time
    def __init__(self, points_to_win=POINTS_TO_WIN, game_id=None):
        """
        Inicijalizira novu igru Belota.
        
        Args:
            points_to_win (int): Broj bodova potreban za pobjedu (zadano 1001)
            game_id (str, optional): Jedinstveni identifikator igre
        """
        try:
            self.points_to_win = points_to_win
            self.game_id = game_id
            self.players = []  # Lista igrača
            self.team_a = []  # Igrači u timu A
            self.team_b = []  # Igrači u timu B
            
            self.team_a_score = 0  # Ukupni bodovi tima A
            self.team_b_score = 0  # Ukupni bodovi tima B
            
            self.current_round = None  # Trenutna runda
            self.round_number = 0  # Broj trenutne runde
            
            self.rules = Rules()  # Pravila igre
            self.scoring = Scoring()  # Bodovanje
            self.move_validator = MoveValidator()  # Validator poteza
            self.call_validator = CallValidator()  # Validator zvanja
            
            self.game_status = self.STATUS_WAITING  # Status igre
            self.winner_team = None  # Pobjednički tim
            
            # Timestamp za invalidaciju keša
            self._cache_timestamp = 0.0
            
            logger.info(f"Nova igra Belot stvorena (ID: {game_id}, bodovi za pobjedu: {points_to_win})")
        except Exception as e:
            logger.error(f"Greška pri inicijalizaciji igre: {str(e)}", exc_info=True)
            raise
    
    def _invalidate_cache(self):
        """Invalidira keširanje igre inkrementiranjem timestampa."""
        import time
        self._cache_timestamp = time.time()
    
    @track_execution_time
    def add_player(self, player):
        """
        Dodaje igrača u igru.
        
        Args:
            player (Player): Igrač koji se dodaje
            
        Returns:
            bool: True ako je igrač uspješno dodan, False inače
            
        Raises:
            ValueError: Ako već postoji 4 igrača ili igra nije u stanju čekanja
        """
        try:
            # Provjera statusa igre
            if self.game_status != self.STATUS_WAITING:
                error_msg = f"Nije moguće dodati igrača - igra nije u stanju čekanja (status: {self.game_status})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera broja igrača
            if len(self.players) >= 4:
                error_msg = "Igra već ima maksimalan broj igrača (4)"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera je li igrač već u igri
            if player in self.players:
                logger.warning(f"Igrač {player} već je dodan u igru")
                return False
            
            # Dodavanje igrača
            self.players.append(player)
            logger.info(f"Igrač {player} dodan u igru (ID: {self.game_id})")
            
            # Invalidacija keša jer je došlo do promjene
            self._invalidate_cache()
            
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri dodavanju igrača: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def assign_teams(self):
        """
        Dodjeljuje igrače u timove.
        
        U Belotu su timovi od po 2 igrača, a suprotno smješteni igrači
        su u istom timu.
        
        Returns:
            tuple: (tim_a, tim_b) - liste igrača u svakom timu
            
        Raises:
            ValueError: Ako ne postoje točno 4 igrača
        """
        try:
            if len(self.players) != 4:
                error_msg = "Za formiranje timova potrebno je točno 4 igrača"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Tim A: igrači 0 i 2
            self.team_a = [self.players[0], self.players[2]]
            
            # Tim B: igrači 1 i 3
            self.team_b = [self.players[1], self.players[3]]
            
            logger.info(f"Timovi formirani - Tim A: {self.team_a}, Tim B: {self.team_b}")
            
            # Invalidacija keša
            self._invalidate_cache()
            
            return self.team_a, self.team_b
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri dodjeljivanju timova: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def start_game(self):
        """
        Započinje igru.
        
        Ovo postavlja igru u stanje 'in_progress' i priprema prvu rundu.
        
        Returns:
            bool: True ako je igra uspješno započeta, False inače
            
        Raises:
            ValueError: Ako igra nema 4 igrača ili ako timovi nisu dodijeljeni
        """
        try:
            if self.game_status != self.STATUS_WAITING:
                error_msg = f"Igra nije u stanju čekanja (status: {self.game_status})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            if len(self.players) != 4:
                error_msg = "Za početak igre potrebno je točno 4 igrača"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            if not self.team_a or not self.team_b:
                logger.info("Timovi nisu dodijeljeni - automatsko dodjeljivanje")
                self.assign_teams()
            
            self.game_status = self.STATUS_IN_PROGRESS
            self.team_a_score = 0
            self.team_b_score = 0
            
            # Postavljanje prve runde
            self.start_new_round()
            
            logger.info(f"Igra Belot započela (ID: {self.game_id})")
            
            # Invalidacija keša
            self._invalidate_cache()
            
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri započinjanju igre: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def start_new_round(self):
        """
        Započinje novu rundu.
        
        Ovo uključuje miješanje špila, dijeljenje karata i određivanje
        početnog igrača.
        
        Returns:
            Round: Nova runda
            
        Raises:
            ValueError: Ako igra nije u tijeku
        """
        try:
            if self.game_status != self.STATUS_IN_PROGRESS:
                error_msg = f"Igra nije u tijeku (status: {self.game_status})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            self.round_number += 1
            
            # Određivanje djelitelja (rotiranje između igrača)
            dealer_index = (self.round_number - 1) % 4
            dealer = self.players[dealer_index]
            
            # Stvaranje nove runde
            self.current_round = Round(self.round_number, dealer, self)
            
            # Dijeljenje karata
            self.current_round.deal_cards()
            
            logger.info(f"Nova runda započeta (runda: {self.round_number}, djelitelj: {dealer})")
            
            # Invalidacija keša
            self._invalidate_cache()
            
            return self.current_round
        except Exception as e:
            logger.error(f"Greška pri započinjanju nove runde: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def play_move(self, player, card):
        """
        Izvršava potez igrača (igranje karte).
        
        Args:
            player (Player): Igrač koji igra kartu
            card (str or Card): Karta koja se igra (string ili Card objekt)
            
        Returns:
            dict: Rezultat poteza s informacijama o štihu
            
        Raises:
            ValueError: Ako potez nije valjan
        """
        try:
            # Provjera da je igra u tijeku
            if self.game_status != self.STATUS_IN_PROGRESS:
                error_msg = f"Igra nije u tijeku (status: {self.game_status})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera da postoji trenutna runda
            if not self.current_round:
                error_msg = "Nema aktivne runde"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Pretvaranje stringa u objekt Card ako je potrebno
            if isinstance(card, str):
                try:
                    card = Card.from_code(card)
                except ValueError as e:
                    logger.warning(f"Nevažeći kod karte: {card}, {str(e)}")
                    raise ValueError(f"Nevažeći kod karte: {card}, {str(e)}")
            
            # Delegiranje poteza trenutnoj rundi
            result = self.current_round.play_move(player, card)
            
            # Ako je runda završena, provjera pobjednika igre
            if self.current_round.is_completed:
                logger.info(f"Runda {self.round_number} završena")
                self._check_game_winner()
                
                # Ako igra nije završena, započni novu rundu
                if self.game_status != self.STATUS_FINISHED:
                    self.start_new_round()
            
            # Invalidacija keša
            self._invalidate_cache()
            
            return result
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri igranju poteza: {str(e)}", exc_info=True)
            raise
    
    @lru_cache(maxsize=32)
    def get_player_team(self, player):
        """
        Vraća tim kojem pripada igrač.
        
        Args:
            player (Player): Igrač čiji se tim traži
            
        Returns:
            str: 'a' za tim A, 'b' za tim B, None ako igrač nije član igre
        """
        try:
            if player in self.team_a:
                return 'a'
            elif player in self.team_b:
                return 'b'
            else:
                logger.warning(f"Igrač {player} nije član ni jednog tima")
                return None
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju tima igrača: {str(e)}", exc_info=True)
            return None
    
    @track_execution_time
    def update_scores(self, team_a_points, team_b_points):
        """
        Ažurira ukupne bodove timova.
        
        Args:
            team_a_points (int): Bodovi za tim A
            team_b_points (int): Bodovi za tim B
            
        Returns:
            tuple: (ukupni_bodovi_tim_a, ukupni_bodovi_tim_b, pobjednički_tim)
            
        Raises:
            ValueError: Ako su bodovi negativni
        """
        try:
            # Validacija bodova
            if team_a_points < 0 or team_b_points < 0:
                error_msg = f"Bodovi ne mogu biti negativni (A: {team_a_points}, B: {team_b_points})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Ažuriranje bodova
            self.team_a_score += team_a_points
            self.team_b_score += team_b_points
            
            logger.info(f"Bodovi ažurirani - Tim A: {self.team_a_score}, Tim B: {self.team_b_score}")
            
            # Provjera pobjednika
            winner_team = None
            if self.team_a_score >= self.points_to_win:
                winner_team = 'a'
                logger.info(f"Tim A pobijedio s {self.team_a_score} bodova")
            elif self.team_b_score >= self.points_to_win:
                winner_team = 'b'
                logger.info(f"Tim B pobijedio s {self.team_b_score} bodova")
            
            # Ažuriranje statusa igre ako imamo pobjednika
            if winner_team:
                self.game_status = self.STATUS_FINISHED
                self.winner_team = winner_team
            
            # Invalidacija keša
            self._invalidate_cache()
            
            return self.team_a_score, self.team_b_score, winner_team
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri ažuriranju bodova: {str(e)}", exc_info=True)
            raise
    
    def _check_game_winner(self):
        """
        Provjerava postoji li pobjednik igre.
        
        Returns:
            str: 'a' za tim A, 'b' za tim B, None ako nema pobjednika
        """
        try:
            if self.team_a_score >= self.points_to_win:
                self.game_status = self.STATUS_FINISHED
                self.winner_team = 'a'
                logger.info(f"Tim A pobijedio s {self.team_a_score} bodova")
                return 'a'
            elif self.team_b_score >= self.points_to_win:
                self.game_status = self.STATUS_FINISHED
                self.winner_team = 'b'
                logger.info(f"Tim B pobijedio s {self.team_b_score} bodova")
                return 'b'
            
            return None
        except Exception as e:
            logger.error(f"Greška pri provjeri pobjednika igre: {str(e)}", exc_info=True)
            return None
    
    @track_execution_time
    def get_game_state(self, include_hands=False):
        """
        Vraća trenutno stanje igre.
        
        Args:
            include_hands (bool): Uključuje ruke igrača u rezultat ako je True
            
        Returns:
            dict: Stanje igre s informacijama o igračima, timovima, bodovima,
                  trenutnoj rundi itd.
        """
        try:
            state = {
                'status': self.game_status,
                'round_number': self.round_number,
                'team_a_score': self.team_a_score,
                'team_b_score': self.team_b_score,
                'winner_team': self.winner_team,
                'players': [str(player) for player in self.players],
                'team_a': [str(player) for player in self.team_a],
                'team_b': [str(player) for player in self.team_b],
                'timestamp': self._cache_timestamp
            }
            
            # Dodavanje informacija o trenutnoj rundi ako postoji
            if self.current_round:
                state['current_round'] = {
                    'number': self.current_round.number,
                    'dealer': str(self.current_round.dealer),
                    'trump_suit': self.current_round.trump_suit,
                    'calling_player': str(self.current_round.calling_player) if self.current_round.calling_player else None,
                    'calling_team': self.current_round.calling_team,
                    'is_completed': self.current_round.is_completed,
                    'current_trick': self.current_round.current_trick_index,
                    'tricks_completed': self.current_round.tricks_completed
                }
                
                # Dodaj informacije o rukama ako je zatraženo
                if include_hands:
                    state['current_round']['player_hands'] = {}
                    for player, hand in self.current_round.player_hands.items():
                        state['current_round']['player_hands'][str(player)] = [
                            card.get_code() if hasattr(card, 'get_code') else str(card) 
                            for card in hand
                        ]
            
            return state
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju stanja igre: {str(e)}", exc_info=True)
            # Vrati minimalno stanje u slučaju greške
            return {
                'status': self.game_status,
                'error': str(e)
            }


class Round:
    """
    Klasa koja predstavlja jednu rundu Belot igre.
    
    Runda se sastoji od dijeljenja karata, zvanja aduta, odigravanja 8 štihova
    i računanja bodova na kraju.
    
    Attributes:
        number (int): Redni broj runde
        dealer (Player): Igrač koji je djelitelj u ovoj rundi
        game (Game): Referenca na igru kojoj runda pripada
        trump_suit (str): Adutska boja ('S', 'H', 'D', 'C' ili None)
        calling_player (Player): Igrač koji je zvao aduta
        calling_team (str): Tim koji je zvao aduta ('a', 'b' ili None)
        player_hands (dict): Karte u rukama igrača
        tricks (list): Odigrani štihovi
        current_trick (list): Trenutni štih
        current_trick_index (int): Indeks trenutnog štiha
        tricks_completed (int): Broj dovršenih štihova
        team_a_tricks (list): Štihovi koje je osvojio tim A
        team_b_tricks (list): Štihovi koje je osvojio tim B
        team_a_declarations (list): Zvanja tima A
        team_b_declarations (list): Zvanja tima B
        is_completed (bool): Je li runda završena
        current_player_index (int): Indeks trenutnog igrača
    """
    
    @track_execution_time
    def __init__(self, number, dealer, game):
        """
        Inicijalizira novu rundu.
        
        Args:
            number (int): Redni broj runde
            dealer (Player): Igrač koji je djelitelj u ovoj rundi
            game (Game): Referenca na igru kojoj runda pripada
        """
        try:
            self.number = number
            self.dealer = dealer
            self.game = game
            
            self.trump_suit = None  # Adutska boja
            self.calling_player = None  # Igrač koji je zvao aduta
            self.calling_team = None  # Tim koji je zvao aduta
            
            self.player_hands = {}  # Karte u rukama igrača
            self.tricks = []  # Odigrani štihovi
            self.current_trick = []  # Trenutni štih
            self.current_trick_index = 0  # Indeks trenutnog štiha
            self.tricks_completed = 0  # Broj dovršenih štihova
            
            self.team_a_tricks = []  # Štihovi koje je osvojio tim A
            self.team_b_tricks = []  # Štihovi koje je osvojio tim B
            
            self.team_a_declarations = []  # Zvanja tima A
            self.team_b_declarations = []  # Zvanja tima B
            
            self.is_completed = False  # Je li runda završena
            
            # Određivanje igrača nakon djelitelja (prvi za zvanje aduta)
            all_players = self.game.players
            dealer_index = all_players.index(dealer)
            self.current_player_index = (dealer_index + 1) % 4
            
            # Validacija
            if number <= 0:
                raise ValueError(f"Nevažeći broj runde: {number}")
            if dealer not in all_players:
                raise ValueError(f"Djelitelj {dealer} nije dio igre")
                
            logger.info(f"Nova runda stvorena (broj: {number}, djelitelj: {dealer})")
        except Exception as e:
            logger.error(f"Greška pri inicijalizaciji runde: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def deal_cards(self):
        """
        Dijeli karte igračima.
        
        Returns:
            dict: Karte dodijeljene svakom igraču
            
        Raises:
            RuntimeError: Ako dođe do greške pri dijeljenju
        """
        try:
            # Korištenje CardService ako je dostupan, inače standardno dijeljenje
            try:
                from game.services.card_service import CardService
                has_card_service = True
            except ImportError:
                has_card_service = False
                logger.info("CardService nije dostupan, korištenje standardnog dijeljenja")
            
            if has_card_service:
                try:
                    # Korištenje CardService za dijeljenje
                    logger.debug("Korištenje CardService za dijeljenje karata")
                    
                    # Simulacija runde za CardService
                    round_data = {
                        'number': self.number,
                        'dealer': self.dealer
                    }
                    
                    self.player_hands = CardService.deal_cards_to_players(round_data, self.game.players)
                    logger.info(f"Karte podijeljene s CardService (runda: {self.number})")
                    return self.player_hands
                except Exception as e:
                    logger.warning(f"Greška pri korištenju CardService: {str(e)}. Nastavak sa standardnim dijeljenjem.")
            
            # Standardno dijeljenje
            # Stvaranje i miješanje špila
            deck = Deck()
            deck.shuffle()
            
            # Inicijalizacija ruku igrača
            for player in self.game.players:
                self.player_hands[player] = []
            
            # Dijeljenje karata - u Belotu se dijeli 3-3-2
            # Prvi krug: 3 karte svakom igraču
            for player in self.game.players:
                for _ in range(3):
                    self.player_hands[player].append(deck.draw())
            
            # Drugi krug: 3 karte svakom igraču
            for player in self.game.players:
                for _ in range(3):
                    self.player_hands[player].append(deck.draw())
            
            # Treći krug: 2 karte svakom igraču
            for player in self.game.players:
                for _ in range(2):
                    self.player_hands[player].append(deck.draw())
            
            logger.info(f"Karte podijeljene standardnim načinom (runda: {self.number})")
            return self.player_hands
        except Exception as e:
            logger.error(f"Greška pri dijeljenju karata: {str(e)}", exc_info=True)
            raise RuntimeError(f"Greška pri dijeljenju karata: {str(e)}")
    
    @track_execution_time
    def call_trump(self, player, suit):
        """
        Postavlja adutsku boju na temelju zvanja igrača.
        
        Args:
            player (Player): Igrač koji zove aduta
            suit (str): Adutska boja koju igrač zove
            
        Returns:
            bool: True ako je zvanje valjano, False inače
            
        Raises:
            ValueError: Ako je adut već određen ili ako je zvanje nevaljano
        """
        try:
            # Provjera je li adut već određen
            if self.trump_suit:
                error_msg = "Adut je već određen"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera je li igrač na redu
            current_player = self.game.players[self.current_player_index]
            if player != current_player:
                error_msg = f"Igrač {player} nije na redu (trenutni igrač: {current_player})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera valjanosti zvanja
            is_valid, message = self.game.call_validator.validate_trump_call(suit)
            if not is_valid:
                error_msg = f"Nevaljano zvanje aduta: {message}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Postavljanje aduta
            self.trump_suit = suit
            self.calling_player = player
            self.calling_team = self.game.get_player_team(player)
            
            logger.info(f"Adut postavljen: {suit} (igrač: {player}, tim: {self.calling_team})")
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri zvanju aduta: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def play_move(self, player, card):
        """
        Izvršava potez igrača (igranje karte).
        
        Args:
            player (Player): Igrač koji igra kartu
            card (Card): Karta koja se igra
            
        Returns:
            dict: Rezultat poteza s informacijama o štihu
            
        Raises:
            ValueError: Ako potez nije valjan
        """
        try:
            # Provjera je li adut određen
            if not self.trump_suit:
                error_msg = "Adut nije određen"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera je li igrač na redu
            current_player = self.game.players[self.current_player_index]
            if player != current_player:
                error_msg = f"Igrač {player} nije na redu (trenutni igrač: {current_player})"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera ima li igrač kartu u ruci
            player_cards = self.player_hands[player]
            
            # Pronalaženje karte u ruci (usporedba po kodu)
            card_in_hand = None
            for c in player_cards:
                if (isinstance(c, Card) and c.get_code() == card.get_code()) or str(c) == str(card):
                    card_in_hand = c
                    break
            
            if not card_in_hand:
                error_msg = f"Igrač {player} nema kartu {card} u ruci"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera valjanosti poteza
            first_card_in_trick = self.current_trick[0][1] if self.current_trick else None
            is_valid, error_message = self.game.move_validator.validate_move(
                card, 
                player_cards, 
                first_card_in_trick, 
                self.trump_suit
            )
            
            if not is_valid:
                error_msg = f"Nevaljani potez: {error_message}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Uklanjanje karte iz ruke
            self.player_hands[player].remove(card_in_hand)
            
            # Dodavanje poteza u trenutni štih
            self.current_trick.append((player, card))
            
            logger.debug(f"Igrač {player} odigrao kartu {card} (runda: {self.number}, štih: {self.current_trick_index})")
            
            # Ako je štih završen (4 karte), određivanje pobjednika
            if len(self.current_trick) == 4:
                trick_result = self._complete_trick()
                logger.info(f"Štih {self.current_trick_index} završen, pobjednik: {trick_result['winner']}")
                
                # Provjera je li runda završena
                if len(self.player_hands[player]) == 0:
                    self._complete_round()
                    logger.info(f"Runda {self.number} završena")
                
                return trick_result
            else:
                # Prelazak na sljedećeg igrača
                self.current_player_index = (self.current_player_index + 1) % 4
                
                return {
                    'played_card': str(card),
                    'player': str(player),
                    'next_player': str(self.game.players[self.current_player_index]),
                    'trick_completed': False
                }
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri igranju poteza: {str(e)}", exc_info=True)
            raise
    
    def _complete_trick(self):
        """
        Završava trenutni štih i određuje pobjednika.
        
        Returns:
            dict: Informacije o završenom štihu
        """
        try:
            trick = self.current_trick
            
            # Određivanje pobjednika štiha
            winner, winning_card = self._determine_trick_winner(trick)
            winner_team = self.game.get_player_team(winner)
            
            # Spremanje završenog štiha
            self.tricks.append(trick)
            
            # Dodavanje štiha pobjedničkom timu
            if winner_team == 'a':
                self.team_a_tricks.append(trick)
            else:
                self.team_b_tricks.append(trick)
            
            # Ažuriranje statusa
            self.tricks_completed += 1
            self.current_trick_index += 1
            self.current_trick = []
            
            # Sljedeći igrač je pobjednik štiha
            winner_index = self.game.players.index(winner)
            self.current_player_index = winner_index
            
            # Bodovi za štih
            trick_points = self._calculate_trick_points(trick)
            
            logger.debug(f"Štih {self.current_trick_index-1} završen - pobjednik: {winner}, tim: {winner_team}, bodovi: {trick_points}")
            
            return {
                'trick_completed': True,
                'trick_index': self.current_trick_index - 1,
                'winner': str(winner),
                'winner_team': winner_team,
                'cards': [str(card) for _, card in trick],
                'points': trick_points,
                'next_player': str(winner)
            }
        except Exception as e:
            logger.error(f"Greška pri završavanju štiha: {str(e)}", exc_info=True)
            raise
    
    def _determine_trick_winner(self, trick):
        """
        Određuje pobjednika štiha.
        
        Args:
            trick (list): Lista poteza u štihu
            
        Returns:
            tuple: (pobjednik, pobjednička_karta)
        """
        try:
            # Korištenje CardService ako je dostupan
            try:
                from game.services.card_service import CardService
                has_card_service = True
            except ImportError:
                has_card_service = False
            
            if has_card_service:
                try:
                    trick_data = {
                        'moves': [{'player': p, 'card': c.get_code() if hasattr(c, 'get_code') else str(c)} for p, c in trick],
                        'trump_suit': self.trump_suit
                    }
                    result = CardService.calculate_trick_winner(trick_data)
                    winner_index = result['winner_index']
                    winner = trick[winner_index][0]
                    winning_card = trick[winner_index][1]
                    
                    return winner, winning_card
                except Exception as e:
                    logger.warning(f"Greška pri korištenju CardService za određivanje pobjednika: {str(e)}. Nastavak sa standardnim određivanjem.")
            
            # Standardno određivanje pobjednika
            first_player, first_card = trick[0]
            lead_suit = first_card.suit
            
            highest_card_value = -1
            winner = first_player
            winning_card = first_card
            
            for player, card in trick:
                card_value = self._get_card_value(card, lead_suit)
                
                if card_value > highest_card_value:
                    highest_card_value = card_value
                    winner = player
                    winning_card = card
            
            return winner, winning_card
        except Exception as e:
            logger.error(f"Greška pri određivanju pobjednika štiha: {str(e)}", exc_info=True)
            raise
    
    def _get_card_value(self, card, lead_suit):
        """
        Određuje vrijednost karte za usporedbu pri određivanju pobjednika štiha.
        
        Args:
            card (Card): Karta koja se vrednuje
            lead_suit (str): Boja koja je prva odigrana u štihu
            
        Returns:
            int: Vrijednost karte za usporedbu
        """
        try:
            # Prioritet aduta nad drugim bojama
            if card.suit == self.trump_suit:
                # Vrijednosti adutskih karata
                ranks = ['7', '8', 'Q', 'K', '10', 'A', '9', 'J']
                return 100 + ranks.index(card.value)
            elif card.suit == lead_suit:
                # Vrijednosti karata u traženoj boji
                ranks = ['7', '8', '9', 'J', 'Q', 'K', '10', 'A']
                return ranks.index(card.value)
            else:
                # Karte druge boje nemaju vrijednost
                return -1
        except Exception as e:
            logger.error(f"Greška pri određivanju vrijednosti karte: {str(e)}", exc_info=True)
            return -1
    
    def _calculate_trick_points(self, trick):
        """
        Računa bodove za štih.
        
        Args:
            trick (list): Lista poteza u štihu
            
        Returns:
            int: Bodovi za štih
        """
        try:
            # Korištenje CardService ako je dostupan
            try:
                from game.services.card_service import CardService
                has_card_service = True
            except ImportError:
                has_card_service = False
            
            if has_card_service:
                try:
                    trick_data = {
                        'moves': [{'player': p, 'card': c.get_code() if hasattr(c, 'get_code') else str(c)} for p, c in trick],
                        'trump_suit': self.trump_suit
                    }
                    result = CardService.calculate_trick_points(trick_data)
                    return result['points']
                except Exception as e:
                    logger.warning(f"Greška pri korištenju CardService za računanje bodova: {str(e)}. Nastavak sa standardnim računanjem.")
            
            # Standardno računanje bodova
            total_points = 0
            
            for _, card in trick:
                # Bodovanje ovisi o tome je li karta adut
                if card.suit == self.trump_suit:
                    if card.value == 'J':
                        total_points += 20
                    elif card.value == '9':
                        total_points += 14
                    elif card.value == 'A':
                        total_points += 11
                    elif card.value == '10':
                        total_points += 10
                    elif card.value == 'K':
                        total_points += 4
                    elif card.value == 'Q':
                        total_points += 3
                else:
                    if card.value == 'A':
                        total_points += 11
                    elif card.value == '10':
                        total_points += 10
                    elif card.value == 'K':
                        total_points += 4
                    elif card.value == 'Q':
                        total_points += 3
                    elif card.value == 'J':
                        total_points += 2
            
            return total_points
        except Exception as e:
            logger.error(f"Greška pri računanju bodova za štih: {str(e)}", exc_info=True)
            return 0
    
    @track_execution_time
    def declare_combination(self, player, declaration_type, cards):
        """
        Prijavljuje zvanje (kombinaciju karata).
        
        Args:
            player (Player): Igrač koji prijavljuje zvanje
            declaration_type (str): Tip zvanja ('four_of_kind', 'sequence_3', itd.)
            cards (list): Karte koje čine zvanje
            
        Returns:
            dict: Rezultat zvanja s bodovima
            
        Raises:
            ValueError: Ako zvanje nije valjano
        """
        try:
            # Provjera je li zvanje valjano
            is_valid, error_message = self.game.call_validator.validate_declaration(
                declaration_type, cards, self.player_hands[player], self.trump_suit
            )
            
            if not is_valid:
                error_msg = f"Nevaljano zvanje: {error_message}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Određivanje vrijednosti zvanja
            points = self._calculate_declaration_points(declaration_type, cards)
            
            # Spremanje zvanja
            declaration = {
                'player': player,
                'type': declaration_type,
                'cards': cards,
                'points': points
            }
            
            # Dodavanje zvanja odgovarajućem timu
            player_team = self.game.get_player_team(player)
            if player_team == 'a':
                self.team_a_declarations.append(declaration)
            else:
                self.team_b_declarations.append(declaration)
            
            logger.info(f"Igrač {player} prijavio zvanje {declaration_type} ({points} bodova)")
            
            return {
                'valid': True,
                'player': str(player),
                'team': player_team,
                'declaration_type': declaration_type,
                'cards': [str(card) for card in cards],
                'points': points
            }
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri prijavljivanju zvanja: {str(e)}", exc_info=True)
            raise
    
    def _calculate_declaration_points(self, declaration_type, cards):
        """
        Računa bodove za zvanje.
        
        Args:
            declaration_type (str): Tip zvanja
            cards (list): Karte u zvanju
            
        Returns:
            int: Bodovi za zvanje
        """
        try:
            # Korištenje CardService ako je dostupan
            try:
                from game.services.card_service import CardService
                has_card_service = True
            except ImportError:
                has_card_service = False
            
            if has_card_service:
                try:
                    declaration_data = {
                        'type': declaration_type,
                        'cards': [c.get_code() if hasattr(c, 'get_code') else str(c) for c in cards]
                    }
                    result = CardService.calculate_declaration_points(declaration_data)
                    return result['points']
                except Exception as e:
                    logger.warning(f"Greška pri korištenju CardService za računanje bodova zvanja: {str(e)}. Nastavak sa standardnim računanjem.")
            
            # Standardno računanje bodova
            if declaration_type == 'four_jacks':
                return 200
            elif declaration_type == 'four_nines':
                return 150
            elif declaration_type == 'four_aces':
                return 100
            elif declaration_type == 'four_kings':
                return 100
            elif declaration_type == 'four_queens':
                return 100
            elif declaration_type == 'four_tens':
                return 100
            elif declaration_type.startswith('sequence_'):
                seq_length = int(declaration_type.split('_')[1])
                if seq_length == 3:
                    return 20
                elif seq_length == 4:
                    return 50
                elif seq_length == 5:
                    return 100
                elif seq_length == 6:
                    return 500
                elif seq_length == 7:
                    return 750
                elif seq_length == 8:
                    return 1000
            elif declaration_type == 'belot':
                return 20
            
            return 0
        except Exception as e:
            logger.error(f"Greška pri računanju bodova za zvanje: {str(e)}", exc_info=True)
            return 0
    
    @track_execution_time
    def declare_bela(self, player):
        """
        Prijavljuje belu (kralj i kraljica aduta).
        
        Args:
            player (Player): Igrač koji prijavljuje belu
            
        Returns:
            dict: Rezultat prijave s bodovima
            
        Raises:
            ValueError: Ako bela nije valjana
        """
        try:
            # Provjera je li adut postavljen
            if not self.trump_suit:
                error_msg = "Adut nije postavljen"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Provjera ima li igrač kralja i kraljicu aduta
            player_cards = self.player_hands[player]
            has_king = False
            has_queen = False
            
            for card in player_cards:
                if card.suit == self.trump_suit:
                    if card.value == 'K':
                        has_king = True
                    elif card.value == 'Q':
                        has_queen = True
            
            if not (has_king and has_queen):
                error_msg = f"Igrač {player} nema kralja i kraljicu aduta"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Bodovi za belu
            points = 20
            
            # Spremanje zvanja
            declaration = {
                'player': player,
                'type': 'belot',
                'points': points
            }
            
            # Dodavanje zvanja odgovarajućem timu
            player_team = self.game.get_player_team(player)
            if player_team == 'a':
                self.team_a_declarations.append(declaration)
            else:
                self.team_b_declarations.append(declaration)
            
            logger.info(f"Igrač {player} prijavio belu ({points} bodova)")
            
            return {
                'valid': True,
                'player': str(player),
                'team': player_team,
                'declaration_type': 'belot',
                'points': points
            }
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri prijavljivanju bele: {str(e)}", exc_info=True)
            raise
    
    def _complete_round(self):
        """
        Završava rundu i računa rezultate.
        
        Returns:
            dict: Rezultati runde
        """
        try:
            # Obilježavanje runde kao završene
            self.is_completed = True
            
            # Računanje bodova za štihove
            team_a_trick_points = sum(self._calculate_trick_points(trick) for trick in self.team_a_tricks)
            team_b_trick_points = sum(self._calculate_trick_points(trick) for trick in self.team_b_tricks)
            
            # Dodavanje bodova za zadnji štih
            if self.team_a_tricks and self.team_a_tricks[-1] == self.tricks[-1]:
                team_a_trick_points += 10
            elif self.team_b_tricks and self.team_b_tricks[-1] == self.tricks[-1]:
                team_b_trick_points += 10
            
            # Računanje bodova za zvanja
            team_a_declaration_points = sum(decl['points'] for decl in self.team_a_declarations)
            team_b_declaration_points = sum(decl['points'] for decl in self.team_b_declarations)
            
            # Ukupni bodovi
            team_a_total = team_a_trick_points + team_a_declaration_points
            team_b_total = team_b_trick_points + team_b_declaration_points
            
            # Provjera ispunjavanja najavljenog aduta
            if self.calling_team:
                calling_team_points = team_a_total if self.calling_team == 'a' else team_b_total
                opposing_team_points = team_b_total if self.calling_team == 'a' else team_a_total
                
                # Ako zovući tim nije skupio više bodova, protivnički tim dobiva sve bodove
                if calling_team_points <= opposing_team_points:
                    if self.calling_team == 'a':
                        team_a_total = 0
                        team_b_total = team_a_trick_points + team_b_trick_points + team_a_declaration_points + team_b_declaration_points
                    else:
                        team_a_total = team_a_trick_points + team_b_trick_points + team_a_declaration_points + team_b_declaration_points
                        team_b_total = 0
            
            # Ažuriranje bodova u igri
            self.game.update_scores(team_a_total, team_b_total)
            
            logger.info(f"Runda {self.number} završena - Tim A: {team_a_total} bodova, Tim B: {team_b_total} bodova")
            
            return {
                'round_number': self.number,
                'team_a_trick_points': team_a_trick_points,
                'team_b_trick_points': team_b_trick_points,
                'team_a_declaration_points': team_a_declaration_points,
                'team_b_declaration_points': team_b_declaration_points,
                'team_a_total': team_a_total,
                'team_b_total': team_b_total,
                'calling_team': self.calling_team,
                'trump_suit': self.trump_suit
            }
        except Exception as e:
            logger.error(f"Greška pri završavanju runde: {str(e)}", exc_info=True)
            raise