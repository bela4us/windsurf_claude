"""
Modul koji definira glavnu logiku Belot igre.

Ovaj modul pruža implementaciju klase Game koja sadrži središnju logiku
za igru Belot, upravljajući tijekom igre, potezima igrača, zvanjima,
bodovanjem i određivanjem pobjednika.
"""

import random
from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from game.game_logic.player import Player
from game.game_logic.validators.move_validator import MoveValidator
from game.game_logic.validators.call_validator import CallValidator


class Game:
    """
    Klasa koja implementira logiku Belot igre.
    
    Upravlja kompletnim tijekom igre, od dijeljenja karata do određivanja
    pobjednika, prateći stanje igre, zvanja, štihove i bodove.
    """
    
    # Konstante za igru
    POINTS_TO_WIN = 1001  # Broj bodova potreban za pobjedu
    CARDS_PER_PLAYER = 8  # Broj karata po igraču u jednoj rundi
    TRICKS_PER_ROUND = 8  # Broj štihova u jednoj rundi
    
    def __init__(self, points_to_win=POINTS_TO_WIN):
        """
        Inicijalizira novu igru Belota.
        
        Args:
            points_to_win: Broj bodova potreban za pobjedu (zadano 1001)
        """
        self.points_to_win = points_to_win
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
        
        self.game_status = 'waiting'  # Status igre (waiting, in_progress, finished)
        self.winner_team = None  # Pobjednički tim
    
    def add_player(self, player):
        """
        Dodaje igrača u igru.
        
        Args:
            player: Igrač koji se dodaje
            
        Returns:
            bool: True ako je igrač uspješno dodan, False inače
            
        Raises:
            ValueError: Ako već postoji 4 igrača
        """
        if len(self.players) >= 4:
            raise ValueError("Igra već ima maksimalan broj igrača (4)")
        
        self.players.append(player)
        return True
    
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
        if len(self.players) != 4:
            raise ValueError("Za formiranje timova potrebno je točno 4 igrača")
        
        # Tim A: igrači 0 i 2
        self.team_a = [self.players[0], self.players[2]]
        
        # Tim B: igrači 1 i 3
        self.team_b = [self.players[1], self.players[3]]
        
        return self.team_a, self.team_b
    
    def start_game(self):
        """
        Započinje igru.
        
        Ovo postavlja igru u stanje 'in_progress' i priprema prvu rundu.
        
        Returns:
            bool: True ako je igra uspješno započeta, False inače
            
        Raises:
            ValueError: Ako igra nema 4 igrača ili ako timovi nisu dodijeljeni
        """
        if len(self.players) != 4:
            raise ValueError("Za početak igre potrebno je točno 4 igrača")
        
        if not self.team_a or not self.team_b:
            self.assign_teams()
        
        self.game_status = 'in_progress'
        self.team_a_score = 0
        self.team_b_score = 0
        
        # Postavljanje prve runde
        self.start_new_round()
        
        return True
    
    def start_new_round(self):
        """
        Započinje novu rundu.
        
        Ovo uključuje miješanje špila, dijeljenje karata i određivanje
        početnog igrača.
        
        Returns:
            Round: Nova runda
        """
        self.round_number += 1
        
        # Određivanje djelitelja (rotiranje između igrača)
        dealer_index = (self.round_number - 1) % 4
        dealer = self.players[dealer_index]
        
        # Stvaranje nove runde
        self.current_round = Round(self.round_number, dealer, self)
        
        # Dijeljenje karata
        self.current_round.deal_cards()
        
        return self.current_round
    
    def play_move(self, player, card):
        """
        Izvršava potez igrača (igranje karte).
        
        Args:
            player: Igrač koji igra kartu
            card: Karta koja se igra (string ili Card objekt)
            
        Returns:
            dict: Rezultat poteza s informacijama o štihu
            
        Raises:
            ValueError: Ako potez nije valjan
        """
        # Provjera da je igra u tijeku
        if self.game_status != 'in_progress':
            raise ValueError("Igra nije u tijeku")
        
        # Provjera da postoji trenutna runda
        if not self.current_round:
            raise ValueError("Nema aktivne runde")
        
        # Delegiranje poteza trenutnoj rundi
        result = self.current_round.play_move(player, card)
        
        # Ako je runda završena, provjera pobjednika igre
        if self.current_round.is_completed:
            self._check_game_winner()
            
            # Ako igra nije završena, započni novu rundu
            if self.game_status != 'finished':
                self.start_new_round()
        
        return result
    
    def get_player_team(self, player):
        """
        Vraća tim kojem pripada igrač.
        
        Args:
            player: Igrač čiji se tim traži
            
        Returns:
            str: 'a' za tim A, 'b' za tim B, None ako igrač nije član igre
        """
        if player in self.team_a:
            return 'a'
        elif player in self.team_b:
            return 'b'
        else:
            return None
    
    def update_scores(self, team_a_points, team_b_points):
        """
        Ažurira ukupne bodove timova.
        
        Args:
            team_a_points: Bodovi za tim A
            team_b_points: Bodovi za tim B
            
        Returns:
            tuple: (ukupni_bodovi_tim_a, ukupni_bodovi_tim_b, pobjednički_tim)
        """
        self.team_a_score += team_a_points
        self.team_b_score += team_b_points
        
        # Provjera pobjednika
        winner_team = None
        if self.team_a_score >= self.points_to_win:
            winner_team = 'a'
        elif self.team_b_score >= self.points_to_win:
            winner_team = 'b'
        
        # Ažuriranje statusa igre ako imamo pobjednika
        if winner_team:
            self.game_status = 'finished'
            self.winner_team = winner_team
        
        return self.team_a_score, self.team_b_score, winner_team
    
    def _check_game_winner(self):
        """
        Provjerava postoji li pobjednik igre.
        
        Returns:
            str: 'a' za tim A, 'b' za tim B, None ako nema pobjednika
        """
        if self.team_a_score >= self.points_to_win:
            self.game_status = 'finished'
            self.winner_team = 'a'
            return 'a'
        elif self.team_b_score >= self.points_to_win:
            self.game_status = 'finished'
            self.winner_team = 'b'
            return 'b'
        
        return None
    
    def get_game_state(self):
        """
        Vraća trenutno stanje igre.
        
        Returns:
            dict: Stanje igre s informacijama o igračima, timovima, bodovima,
                  trenutnoj rundi itd.
        """
        state = {
            'status': self.game_status,
            'round_number': self.round_number,
            'team_a_score': self.team_a_score,
            'team_b_score': self.team_b_score,
            'winner_team': self.winner_team,
            'players': [str(player) for player in self.players],
            'team_a': [str(player) for player in self.team_a],
            'team_b': [str(player) for player in self.team_b]
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
        
        return state


class Round:
    """
    Klasa koja predstavlja jednu rundu Belot igre.
    
    Runda se sastoji od dijeljenja karata, zvanja aduta, odigravanja 8 štihova
    i računanja bodova na kraju.
    """
    
    def __init__(self, number, dealer, game):
        """
        Inicijalizira novu rundu.
        
        Args:
            number: Redni broj runde
            dealer: Igrač koji je djelitelj u ovoj rundi
            game: Referenca na igru kojoj runda pripada
        """
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
    
    def deal_cards(self):
        """
        Dijeli karte igračima.
        
        Returns:
            dict: Karte dodijeljene svakom igraču
        """
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
        
        return self.player_hands
    
    def call_trump(self, player, suit):
        """
        Postavlja adutsku boju na temelju zvanja igrača.
        
        Args:
            player: Igrač koji zove aduta
            suit: Adutska boja koju igrač zove
            
        Returns:
            bool: True ako je zvanje valjano, False inače
            
        Raises:
            ValueError: Ako je adut već određen ili ako je zvanje nevaljano
        """
        # Provjera je li adut već određen
        if self.trump_suit:
            raise ValueError("Adut je već određen")
        
        # Provjera valjanosti zvanja
        is_valid, message = self.game.call_validator.validate_trump_call(suit)
        if not is_valid:
            raise ValueError(f"Nevaljano zvanje aduta: {message}")
        
        # Postavljanje aduta
        self.trump_suit = suit
        self.calling_player = player
        self.calling_team = self.game.get_player_team(player)
        
        return True
    
    def play_move(self, player, card):
        """
        Izvršava potez igrača (igranje karte).
        
        Args:
            player: Igrač koji igra kartu
            card: Karta koja se igra (string ili Card objekt)
            
        Returns:
            dict: Rezultat poteza s informacijama o štihu
            
        Raises:
            ValueError: Ako potez nije valjan
        """
        # Provjera je li adut određen
        if not self.trump_suit:
            raise ValueError("Adut nije određen")
        
        # Provjera je li igrač na potezu
        current_player = self.game.players[self.current_player_index]
        if player != current_player:
            raise ValueError(f"Nije tvoj red za potez. Na potezu je {current_player}.")
        
        # Pretvaranje stringa u Card objekt ako je potrebno
        if isinstance(card, str):
            card = Card.from_code(card)
        
        # Provjera ima li igrač tu kartu
        if card not in self.player_hands[player]:
            raise ValueError("Igrač nema tu kartu u ruci")
        
        # Provjera je li potez valjan prema pravilima igre
        is_valid, message = self.game.move_validator.validate_move(
            card, self.player_hands[player], self.current_trick, self.trump_suit)
        
        if not is_valid:
            raise ValueError(f"Nevaljani potez: {message}")
        
        # Izvršavanje poteza
        self.current_trick.append(card)
        self.player_hands[player].remove(card)
        
        # Ažuriranje sljedećeg igrača
        self.current_player_index = (self.current_player_index + 1) % 4
        
        # Provjera je li štih završen
        trick_completed = len(self.current_trick) == 4
        
        result = {
            'player': str(player),
            'card': str(card),
            'trick_completed': trick_completed
        }
        
        # Ako je štih završen, odredi pobjednika i započni novi štih
        if trick_completed:
            winner_index = self.game.rules.determine_trick_winner(
                self.current_trick, self.trump_suit)
            
            # Određivanje pobjedničkog igrača i tima
            winner_player_index = (self.current_player_index - 4 + winner_index) % 4
            winner_player = self.game.players[winner_player_index]
            winner_team = self.game.get_player_team(winner_player)
            
            # Računanje bodova za štih
            is_last_trick = self.tricks_completed == 7  # Zadnji (8.) štih
            trick_points = self.game.scoring.calculate_trick_points(
                self.current_trick, self.trump_suit, is_last_trick)
            
            # Stvaranje podataka o štihu
            trick_data = {
                'cards': self.current_trick.copy(),
                'winner': winner_player,
                'winner_team': winner_team,
                'points': trick_points
            }
            
            # Dodavanje štiha odgovarajućem timu
            if winner_team == 'a':
                self.team_a_tricks.append(trick_data)
            else:
                self.team_b_tricks.append(trick_data)
            
            # Spremanje dovršenog štiha
            self.tricks.append(self.current_trick.copy())
            self.current_trick = []
            self.tricks_completed += 1
            self.current_trick_index += 1
            
            # Sljedeći igrač je pobjednik štiha
            self.current_player_index = winner_player_index
            
            # Dodavanje informacija o štihu u rezultat
            result.update({
                'winner': str(winner_player),
                'winner_team': winner_team,
                'trick_points': trick_points,
                'next_player': str(winner_player)
            })
            
            # Ako je ovo bio zadnji štih, završi rundu
            if self.tricks_completed == 8:
                self._complete_round()
                result['round_completed'] = True
                result['round_results'] = {
                    'team_a_points': self.team_a_points,
                    'team_b_points': self.team_b_points,
                    'winner_team': self.winner_team
                }
        else:
            # Ako štih nije završen, dodaj informaciju o sljedećem igraču
            result['next_player'] = str(self.game.players[self.current_player_index])
        
        return result
    
    def declare_combination(self, player, declaration_type, cards):
        """
        Prijavljuje zvanje (belot, četiri dečka, sekvenca, itd.).
        
        Args:
            player: Igrač koji prijavljuje zvanje
            declaration_type: Tip zvanja
            cards: Lista karata koje čine zvanje
            
        Returns:
            dict: Rezultat zvanja
            
        Raises:
            ValueError: Ako zvanje nije valjano
        """
        # Provjera valjanosti zvanja
        is_valid, message = self.game.call_validator.validate_declaration(
            declaration_type, cards, self.trump_suit)
        
        if not is_valid:
            raise ValueError(f"Nevaljano zvanje: {message}")
        
        # Provjer posjeduje li igrač te karte
        if isinstance(cards[0], str):
            card_objects = [Card.from_code(card) for card in cards]
        else:
            card_objects = cards
        
        if not all(card in self.player_hands[player] for card in card_objects):
            raise ValueError("Igrač nema sve karte za zvanje")
        
        # Izračunavanje bodovne vrijednosti zvanja
        points = self.game.scoring.get_declaration_value(declaration_type, cards)
        
        # Stvaranje podataka o zvanju
        declaration_data = {
            'type': declaration_type,
            'player': player,
            'cards': cards,
            'value': points
        }
        
        # Dodavanje zvanja odgovarajućem timu
        team = self.game.get_player_team(player)
        if team == 'a':
            self.team_a_declarations.append(declaration_data)
        else:
            self.team_b_declarations.append(declaration_data)
        
        return {
            'valid': True,
            'declaration_type': declaration_type,
            'player': str(player),
            'team': team,
            'value': points
        }
    
    def declare_bela(self, player):
        """
        Prijavljuje belu (kralj i dama aduta).
        
        Args:
            player: Igrač koji prijavljuje belu
            
        Returns:
            dict: Rezultat zvanja bele
            
        Raises:
            ValueError: Ako zvanje nije valjano
        """
        # Provjera je li adut određen
        if not self.trump_suit:
            raise ValueError("Adut nije određen, nije moguće prijaviti belu")
        
        # Određivanje koda adutske boje
        trump_code = self.game.rules._normalize_suit(self.trump_suit)
        
        # Provjera ima li igrač kralja i damu aduta
        king = Card('K', trump_code)
        queen = Card('Q', trump_code)
        
        has_king = king in self.player_hands[player]
        has_queen = queen in self.player_hands[player]
        
        if not (has_king and has_queen):
            raise ValueError("Igrač nema kralja i damu aduta za belu")
        
        # Izračunavanje bodovne vrijednosti bele
        points = self.game.scoring.get_declaration_value('bela')
        
        # Stvaranje podataka o zvanju
        declaration_data = {
            'type': 'bela',
            'player': player,
            'cards': [f"K{trump_code}", f"Q{trump_code}"],
            'value': points
        }
        
        # Dodavanje zvanja odgovarajućem timu
        team = self.game.get_player_team(player)
        if team == 'a':
            self.team_a_declarations.append(declaration_data)
        else:
            self.team_b_declarations.append(declaration_data)
        
        return {
            'valid': True,
            'declaration_type': 'bela',
            'player': str(player),
            'team': team,
            'value': points
        }
    
    def _complete_round(self):
        """
        Završava rundu i izračunava bodove.
        
        Returns:
            tuple: (team_a_points, team_b_points, winner_team)
        """
        # Izračunavanje bodova za rundu
        self.team_a_points, self.team_b_points, self.winner_team = self.game.scoring.calculate_round_points(
            self.team_a_tricks, self.team_b_tricks, 
            self.team_a_declarations, self.team_b_declarations,
            self.calling_team
        )
        
        # Ažuriranje ukupnih bodova igre
        self.game.update_scores(self.team_a_points, self.team_b_points)
        
        # Označavanje runde kao završene
        self.is_completed = True
        
        return self.team_a_points, self.team_b_points, self.winner_team