"""
Servis za bodovanje Belot igre.

Ovaj modul implementira ScoringService klasu koja sadrži svu logiku
vezanu uz bodovanje u Belot igri, uključujući bodovanje karata, zvanja,
izračun rezultata rundi i određivanje pobjednika.
"""

import logging
from collections import defaultdict
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from game.models import Game, Round, Move, Declaration
from game.game_logic.card import Card

User = get_user_model()
logger = logging.getLogger('game.services')

class ScoringService:
    """
    Servis koji upravlja bodovanjem Belot igre.
    
    Ova klasa sadrži metode za sve aspekte bodovanja igre, uključujući
    izračun vrijednosti karata, bodovanje zvanja, izračun rezultata rundi
    i određivanje pobjednika igre.
    """
    
    # Konstante za bodovanje karata
    NON_TRUMP_CARD_VALUES = {
        'A': 11,
        '10': 10,
        'K': 4,
        'Q': 3,
        'J': 2,
        '9': 0,
        '8': 0,
        '7': 0
    }
    
    TRUMP_CARD_VALUES = {
        'J': 20,
        '9': 14,
        'A': 11,
        '10': 10,
        'K': 4,
        'Q': 3,
        '8': 0,
        '7': 0
    }
    
    # Konstante za bodovanje zvanja
    DECLARATION_VALUES = {
        'belot': 1001,  # Osam karata u istoj boji u nizu
        'four_jacks': 200,  # Četiri dečka
        'four_nines': 150,  # Četiri devetke
        'four_aces': 100,  # Četiri asa
        'four_tens': 100,  # Četiri desetke
        'four_kings': 100,  # Četiri kralja
        'four_queens': 100,  # Četiri dame
        'sequence_5_plus': 100,  # Pet, šest ili sedam karata u nizu iste boje
        'sequence_4': 50,  # Četiri karte u nizu iste boje
        'sequence_3': 20,  # Tri karte u nizu iste boje
        'bela': 20,  # Kralj i dama iste boje u adutu
    }
    
    # Ukupan broj bodova u jednoj rundi (bez zvanja)
    TOTAL_ROUND_POINTS = 162  # 152 bodova za karte + 10 za zadnji štih
    
    # Bodovi za štih-mač (štilju)
    CLEAN_SWEEP_BONUS = 90
    
    # Dodatni bodovi za zadnji štih
    LAST_TRICK_BONUS = 10
    
    @staticmethod
    def calculate_card_value(card_code, trump_suit):
        """
        Izračunava bodovnu vrijednost karte ovisno o tome je li adut.
        
        Args:
            card_code: Kod karte (npr. "7S", "AH", "JD")
            trump_suit: Adutska boja (S, H, D, C) ili None za bez aduta
            
        Returns:
            int: Bodovna vrijednost karte
        """
        if not card_code or len(card_code) < 2:
            return 0
        
        value = card_code[:-1]  # Npr. "7", "10", "A"
        suit = card_code[-1]  # Npr. "S", "H", "D", "C"
        
        # U varijanti "sve adut" sve boje su adut
        # U varijanti "bez aduta" nijedna boja nije adut
        is_trump = False
        if trump_suit:
            if trump_suit == 'all_trump':
                is_trump = True
            elif trump_suit != 'no_trump':
                # Pretvori trump_suit iz "spades" u "S" itd.
                suit_map = {
                    'spades': 'S',
                    'hearts': 'H',
                    'diamonds': 'D',
                    'clubs': 'C'
                }
                is_trump = (suit == suit_map.get(trump_suit, ''))
        
        if is_trump:
            return ScoringService.TRUMP_CARD_VALUES.get(value, 0)
        else:
            return ScoringService.NON_TRUMP_CARD_VALUES.get(value, 0)
    
    @staticmethod
    def calculate_trick_points(trick_moves, trump_suit):
        """
        Izračunava ukupnu bodovnu vrijednost štiha.
        
        Args:
            trick_moves: Lista poteza u štihu
            trump_suit: Adutska boja
            
        Returns:
            int: Ukupni bodovi za štih
        """
        total = 0
        for move in trick_moves:
            total += ScoringService.calculate_card_value(move.card, trump_suit)
        return total
    
    @staticmethod
    def calculate_tricks_points(round_obj):
        """
        Izračunava bodove za štihove osvojene u rundi za oba tima.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2)
        """
        game = round_obj.game
        team1_points = 0
        team2_points = 0
        
        # Dobavi sve poteze u rundi, sortirane po redoslijedu
        moves = Move.objects.filter(round=round_obj).order_by('order')
        
        # Grupiraj poteze u štihove (svaki štih ima 4 poteza)
        tricks = []
        current_trick = []
        
        for move in moves:
            current_trick.append(move)
            if len(current_trick) == 4:
                tricks.append(current_trick)
                current_trick = []
        
        # Izračunaj bodove za svaki štih
        for i, trick in enumerate(tricks):
            # Nađi pobjednički potez
            winning_move = next((move for move in trick if move.is_winning), None)
            if not winning_move:
                continue
            
            # Izračunaj bodove za štih
            trick_points = ScoringService.calculate_trick_points(trick, round_obj.trump_suit)
            
            # Dodaj dodatne bodove za zadnji štih
            if i == len(tricks) - 1:  # Zadnji štih
                trick_points += ScoringService.LAST_TRICK_BONUS
            
            # Dodaj bodove odgovarajućem timu
            winner_team = game.get_team_for_player(winning_move.player)
            if winner_team == 1:
                team1_points += trick_points
            elif winner_team == 2:
                team2_points += trick_points
        
        # Provjeri štih-mač (štilju)
        if team1_points == 0:
            # Tim 2 je osvojio sve štihove
            team2_points += ScoringService.CLEAN_SWEEP_BONUS
        elif team2_points == 0:
            # Tim 1 je osvojio sve štihove
            team1_points += ScoringService.CLEAN_SWEEP_BONUS
        
        return team1_points, team2_points
    
    @staticmethod
    def validate_declaration(declaration_type, cards, round_obj=None):
        """
        Provjerava je li zvanje valjano prema pravilima Belota.
        
        Args:
            declaration_type: Tip zvanja (jedna od ključeva u DECLARATION_VALUES)
            cards: Lista karata koje čine zvanje
            round_obj: Opcionalno, objekt runde za dodatnu validaciju
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        if declaration_type not in ScoringService.DECLARATION_VALUES:
            return False, f"Nevažeći tip zvanja: {declaration_type}"
        
        # Različita validacija ovisno o tipu zvanja
        if declaration_type == 'bela':
            # Bela zahtijeva kralja i damu iste boje u adutu
            if len(cards) != 2:
                return False, "Bela mora sadržavati točno dvije karte"
            
            # Provjeri jesu li karte kralj i dama
            values = [card[:-1] for card in cards]
            if sorted(values) != ['K', 'Q']:
                return False, "Bela mora sadržavati kralja i damu"
            
            # Provjeri jesu li iste boje
            suits = [card[-1] for card in cards]
            if len(set(suits)) != 1:
                return False, "Karte u beli moraju biti iste boje"
            
            # Provjeri je li ta boja adut (ako je runda navedena)
            if round_obj and round_obj.trump_suit:
                suit = suits[0]
                trump_suit_map = {
                    'spades': 'S',
                    'hearts': 'H',
                    'diamonds': 'D',
                    'clubs': 'C'
                }
                
                if round_obj.trump_suit in trump_suit_map:
                    if suit != trump_suit_map[round_obj.trump_suit]:
                        return False, "Bela mora biti u adutskoj boji"
                elif round_obj.trump_suit == 'no_trump':
                    return False, "Bela nije moguća u varijanti bez aduta"
        
        elif declaration_type.startswith('four_'):
            # Četiri iste karte (npr. četiri dečka)
            if len(cards) != 4:
                return False, f"{declaration_type} mora sadržavati točno četiri karte"
            
            # Provjeri jesu li sve karte iste vrijednosti
            value_map = {
                'four_jacks': 'J',
                'four_nines': '9',
                'four_aces': 'A',
                'four_tens': '10',
                'four_kings': 'K',
                'four_queens': 'Q'
            }
            
            expected_value = value_map.get(declaration_type)
            if not expected_value:
                return False, f"Nevažeći tip zvanja: {declaration_type}"
            
            values = [card[:-1] for card in cards]
            if not all(v == expected_value for v in values):
                return False, f"Sve karte moraju biti {expected_value}"
            
            # Provjeri jesu li sve boje zastupljene
            suits = [card[-1] for card in cards]
            if len(set(suits)) != 4:
                return False, "Sve četiri boje moraju biti zastupljene"
        
        elif declaration_type.startswith('sequence_'):
            # Sekvenca karata iste boje
            # Dobavi minimalnu duljinu sekvence
            min_length = 0
            if declaration_type == 'sequence_3':
                min_length = 3
            elif declaration_type == 'sequence_4':
                min_length = 4
            elif declaration_type == 'sequence_5_plus':
                min_length = 5
            else:
                return False, f"Nevažeći tip sekvence: {declaration_type}"
            
            if len(cards) < min_length:
                return False, f"Sekvenca mora sadržavati najmanje {min_length} karata"
            
            # Provjeri jesu li sve karte iste boje
            suits = [card[-1] for card in cards]
            if len(set(suits)) != 1:
                return False, "Sve karte u sekvenci moraju biti iste boje"
            
            # Provjeri jesu li karte u nizu
            values = [card[:-1] for card in cards]
            value_order = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            
            # Pretvori vrijednosti u njihove indekse u value_order
            try:
                indices = [value_order.index(v) for v in values]
                indices.sort()
            except ValueError:
                return False, "Nevažeća vrijednost karte u sekvenci"
            
            # Provjeri jesu li indeksi u nizu
            for i in range(1, len(indices)):
                if indices[i] != indices[i-1] + 1:
                    return False, "Karte u sekvenci moraju biti u nizu"
        
        elif declaration_type == 'belot':
            # Belot (8 karata u nizu iste boje)
            if len(cards) != 8:
                return False, "Belot mora sadržavati točno 8 karata"
            
            # Provjeri jesu li sve karte iste boje
            suits = [card[-1] for card in cards]
            if len(set(suits)) != 1:
                return False, "Sve karte u belotu moraju biti iste boje"
            
            # Provjeri jesu li sve vrijednosti zastupljene
            values = [card[:-1] for card in cards]
            expected_values = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            for ev in expected_values:
                if ev not in values:
                    return False, f"Belot mora sadržavati kartu {ev}"
        
        return True, ""
    
    @staticmethod
    def get_declaration_value(declaration_type, cards=None):
        """
        Vraća bodovnu vrijednost zvanja.
        
        Args:
            declaration_type: Tip zvanja
            cards: Opcionalno, lista karata za zvanja koja imaju varijabilnu vrijednost
            
        Returns:
            int: Bodovna vrijednost zvanja
        """
        return ScoringService.DECLARATION_VALUES.get(declaration_type, 0)
    
    @staticmethod
    def compare_declarations(decl1, decl2):
        """
        Uspoređuje dva zvanja prema snazi.
        
        Args:
            decl1: Prvo zvanje (Declaration objekt)
            decl2: Drugo zvanje (Declaration objekt)
            
        Returns:
            int: 1 ako je decl1 jače, -1 ako je decl2 jače, 0 ako su jednaka
        """
        if not decl1 and not decl2:
            return 0
        if not decl1:
            return -1
        if not decl2:
            return 1
        
        # Usporedi po vrijednosti
        if decl1.value > decl2.value:
            return 1
        elif decl1.value < decl2.value:
            return -1
        
        # Ako su jednake vrijednosti, usporedi po tipu
        declaration_strength = {
            'belot': 8,
            'four_jacks': 7,
            'four_nines': 6,
            'four_aces': 5,
            'four_tens': 4,
            'four_kings': 3,
            'four_queens': 2,
            'sequence_5_plus': 1,
            'sequence_4': 0,
            'sequence_3': -1,
            'bela': -2
        }
        
        type1_strength = declaration_strength.get(decl1.type, -999)
        type2_strength = declaration_strength.get(decl2.type, -999)
        
        if type1_strength > type2_strength:
            return 1
        elif type1_strength < type2_strength:
            return -1
        
        # Ako su isti tipovi i vrijednosti, za sekvence usporedi po najvišoj karti
        if decl1.type.startswith('sequence_') and decl2.type.startswith('sequence_'):
            value_order = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            
            # Dobavi najvišu kartu u svakoj sekvenci
            decl1_values = [card[:-1] for card in decl1.cards]
            decl2_values = [card[:-1] for card in decl2.cards]
            
            highest1 = max(decl1_values, key=lambda v: value_order.index(v))
            highest2 = max(decl2_values, key=lambda v: value_order.index(v))
            
            if value_order.index(highest1) > value_order.index(highest2):
                return 1
            elif value_order.index(highest1) < value_order.index(highest2):
                return -1
        
        # Ako su potpuno jednaka zvanja, treba provjeriti koji je igrač bliži djelitelju
        # To se obično radi u Round modelu jer ovdje nemamo informaciju o položaju igrača
        return 0
    
    @staticmethod
    def calculate_declarations_points(round_obj):
        """
        Izračunava bodove za zvanja u rundi za oba tima.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2)
        """
        game = round_obj.game
        team1_points = 0
        team2_points = 0
        
        # Dobavi sva zvanja u rundi
        declarations = Declaration.objects.filter(round=round_obj)
        
        # Grupiraj zvanja po timovima
        team1_declarations = []
        team2_declarations = []
        
        for decl in declarations:
            team = game.get_team_for_player(decl.player)
            if team == 1:
                team1_declarations.append(decl)
            elif team == 2:
                team2_declarations.append(decl)
        
        # Pronađi najviše zvanje za svaki tim
        highest_team1 = None
        highest_team2 = None
        
        if team1_declarations:
            highest_team1 = max(team1_declarations, key=lambda d: d.value)
        if team2_declarations:
            highest_team2 = max(team2_declarations, key=lambda d: d.value)
        
        # Ako oba tima imaju zvanja, usporedi njihove vrijednosti
        if highest_team1 and highest_team2:
            comparison = ScoringService.compare_declarations(highest_team1, highest_team2)
            
            # Ako tim 1 ima jače zvanje, samo tim 1 dobiva bodove
            if comparison > 0:
                team1_points = sum(d.value for d in team1_declarations)
            # Ako tim 2 ima jače zvanje, samo tim 2 dobiva bodove
            elif comparison < 0:
                team2_points = sum(d.value for d in team2_declarations)
            # Ako su zvanja jednake vrijednosti, provjeri koji je igrač bliži djelitelju
            else:
                # U tom slučaju, obično pravilo je da prednost ima igrač koji je "stariji" (bliži djelitelju)
                # Ovo bi trebalo implementirati u Round modelu
                
                # Za sada, pretpostavimo da oba tima dobivaju bodove
                team1_points = sum(d.value for d in team1_declarations)
                team2_points = sum(d.value for d in team2_declarations)
        else:
            # Samo jedan tim ima zvanja ili nijedan nema
            if highest_team1:
                team1_points = sum(d.value for d in team1_declarations)
            if highest_team2:
                team2_points = sum(d.value for d in team2_declarations)
        
        return team1_points, team2_points
    
    @staticmethod
    def calculate_round_points(round_obj):
        """
        Izračunava ukupne bodove za rundu za oba tima, uključujući sve komponente.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2, pobjednički_tim)
        """
        # Izračunaj bodove za štihove
        trick_points_team1, trick_points_team2 = ScoringService.calculate_tricks_points(round_obj)
        
        # Izračunaj bodove za zvanja
        decl_points_team1, decl_points_team2 = ScoringService.calculate_declarations_points(round_obj)
        
        # Ukupni bodovi
        total_team1 = trick_points_team1 + decl_points_team1
        total_team2 = trick_points_team2 + decl_points_team2
        
        # Primijeni pravilo "prolaza"
        # Tim koji je zvao aduta mora imati više bodova od protivnika da bi "prošao"
        calling_team = round_obj.calling_team
        if calling_team == 1:
            if total_team1 <= total_team2:
                # Tim 1 nije prošao, svi bodovi idu timu 2
                total_team2 = total_team1 + total_team2
                total_team1 = 0
                winner_team = 2
            else:
                winner_team = 1
        elif calling_team == 2:
            if total_team2 <= total_team1:
                # Tim 2 nije prošao, svi bodovi idu timu 1
                total_team1 = total_team1 + total_team2
                total_team2 = 0
                winner_team = 1
            else:
                winner_team = 2
        else:
            # Ako nema zvanja aduta (što je neuobičajeno), pobjednik je tim s više bodova
            winner_team = 1 if total_team1 > total_team2 else 2
        
        return total_team1, total_team2, winner_team
    
    @staticmethod
    def check_game_winner(game):
        """
        Provjerava je li igra završena i određuje pobjednika.
        
        Args:
            game: Objekt igre (Game)
            
        Returns:
            tuple: (je_li_završeno, pobjednički_tim)
        """
        # Provjeri je li neki tim dostigao bodove potrebne za pobjedu
        if game.team1_score >= game.points_to_win:
            return True, 1
        elif game.team2_score >= game.points_to_win:
            return True, 2
        
        # Provjeri imaju li oba tima više od pola potrebnih bodova
        # U tom slučaju, pobjednik je tim s više bodova
        half_points = game.points_to_win / 2
        if game.team1_score > half_points and game.team2_score > half_points:
            if game.team1_score > game.team2_score:
                return True, 1
            elif game.team2_score > game.team1_score:
                return True, 2
        
        # Provjeri ima li zvanja "belot" koje automatski završava igru
        current_round = game.get_current_round()
        if current_round:
            belot_declaration = Declaration.objects.filter(
                round=current_round,
                type='belot'
            ).first()
            
            if belot_declaration:
                team = game.get_team_for_player(belot_declaration.player)
                return True, team
        
        return False, None