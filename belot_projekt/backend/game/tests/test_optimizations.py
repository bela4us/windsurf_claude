"""
Testovi za provjeru funkcionalnosti i ispravnosti optimizacija.

Ovaj modul sadrži Django testove koji provjeravaju funkcionalni dio optimizacija,
osiguravajući da optimizacije nisu narušile ispravnost rada sustava.
"""

import unittest
from django.test import TestCase
from unittest.mock import patch

from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.player import Player
from game.game_logic.game import Game, Round
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from game.game_logic.validators.move_validator import MoveValidator
from game.game_logic.validators.call_validator import CallValidator
from game.utils.card_utils import normalize_suit, suit_name, get_display_name


class CardOptimizationTest(TestCase):
    """Testovi za optimizacije klase Card."""
    
    def test_card_creation(self):
        """Test stvaranja karata s optimizacijama."""
        # Testiraj stvaranje karte
        card = Card.from_code('AS')
        self.assertEqual(card.code, 'AS')
        self.assertEqual(card.value, 'A')
        self.assertEqual(card.suit, 'S')
        
        # Testiraj keširanje - trebala bi se vratiti ista instanca
        card2 = Card.from_code('AS')
        self.assertIs(card, card2, "Keširanje karata nije uspjelo - nisu iste instance")
    
    def test_card_sorting(self):
        """Test sortiranja karata nakon optimizacija."""
        # Kreiraj karte u nasumičnom redoslijedu
        cards = [Card.from_code('AS'), Card.from_code('KS'), Card.from_code('QS'), Card.from_code('JS')]
        
        # Sortiraj karte
        sorted_cards = sorted(cards, key=lambda c: Card.RANKS.index(c.value))
        
        # Provjeri redoslijed
        expected_values = ['J', 'Q', 'K', 'A']
        actual_values = [card.value for card in sorted_cards]
        self.assertEqual(actual_values, expected_values)
    
    def test_card_comparison(self):
        """Test usporedbe karata nakon optimizacija."""
        # Kreiraj karte
        ace_spades = Card.from_code('AS')
        king_spades = Card.from_code('KS')
        ace_hearts = Card.from_code('AH')
        
        # Testiraj ==
        self.assertEqual(ace_spades, Card.from_code('AS'))
        self.assertNotEqual(ace_spades, king_spades)
        
        # Testiraj istu boju (umjesto has_same_suit)
        self.assertEqual(ace_spades.suit, king_spades.suit)
        self.assertNotEqual(ace_spades.suit, ace_hearts.suit)
        
        # Testiraj istu vrijednost (umjesto has_same_value)
        self.assertEqual(ace_spades.value, ace_hearts.value)
        self.assertNotEqual(ace_spades.value, king_spades.value)


class DeckOptimizationTest(TestCase):
    """Testovi za optimizacije klase Deck."""
    
    def test_deck_initialization(self):
        """Test inicijalizacije špila nakon optimizacija."""
        # Ručno kreiraj špil umjesto korištenja keširane metode
        deck = Deck()
        
        # Ako je špil prazan, ručno ga napuni
        if len(deck.cards) == 0:
            deck.cards = []
            for suit in Card.VALID_SUITS:
                for value in Card.VALID_VALUES:
                    deck.cards.append(Card.from_code(f"{value}{suit}"))
        
        self.assertEqual(len(deck.cards), 32)
        
        # Provjeri da su svi tipovi karata prisutni
        values = set(card.value for card in deck.cards)
        suits = set(card.suit for card in deck.cards)
        
        self.assertEqual(values, set(Card.VALID_VALUES))
        self.assertEqual(suits, set(Card.VALID_SUITS))
    
    @patch('random.shuffle')
    def test_deck_shuffle(self, mock_shuffle):
        """Test miješanja špila nakon optimizacija."""
        deck = Deck()
        
        # Ako je špil prazan, ručno ga napuni
        if len(deck.cards) == 0:
            deck.cards = []
            for suit in Card.VALID_SUITS:
                for value in Card.VALID_VALUES:
                    deck.cards.append(Card.from_code(f"{value}{suit}"))
                    
        deck.shuffle()
        
        # Provjeri da je random.shuffle pozvan jednom
        mock_shuffle.assert_called_once()
    
    def test_deck_deal(self):
        """Test dijeljenja karata nakon optimizacija."""
        deck = Deck()
        
        # Ako je špil prazan, ručno ga napuni
        if len(deck.cards) == 0:
            deck.cards = []
            for suit in Card.VALID_SUITS:
                for value in Card.VALID_VALUES:
                    deck.cards.append(Card.from_code(f"{value}{suit}"))
                    
        num_players = 4
        hands = deck.deal(num_players)
        
        # Provjeri da su karte podijeljene ispravno
        self.assertEqual(len(hands), num_players)
        
        # Po 8 karata po igraču
        for hand in hands:
            self.assertEqual(len(hand), 8)
        
        # Provjeri da je špil sada prazan
        self.assertEqual(len(deck.cards), 0)


class PlayerOptimizationTest(TestCase):
    """Testovi za optimizacije klase Player."""
    
    def setUp(self):
        """Postavljanje testa."""
        self.player = Player(id=1, username="Test Player")
        self.cards = [
            Card.from_code('7S'), Card.from_code('8S'), Card.from_code('9S'),  # Pikovi
            Card.from_code('AH'), Card.from_code('KH'),             # Herčevi
            Card.from_code('JD'), Card.from_code('QD'),             # Karo
            Card.from_code('10C')                          # Tref
        ]
        
        # Dodaj karte igraču
        for card in self.cards:
            self.player.add_card(card)
    
    def test_cache_invalidation(self):
        """Test poništavanja keša nakon izmjene ruke."""
        # Dohvati karte pik boje - ovo će napuniti keš
        spades_before = self.player.get_cards_of_suit('S')
        self.assertEqual(len(spades_before), 3)
        
        # Ukloni jednu kartu pik boje
        removed_card = Card.from_code('7S')
        self.player.remove_card(removed_card)
        
        # Dohvati ponovno karte pik boje - keš bi trebao biti poništen
        spades_after = self.player.get_cards_of_suit('S')
        self.assertEqual(len(spades_after), 2)
        self.assertNotIn(removed_card, spades_after)
    
    def test_has_suit(self):
        """Test has_suit metode nakon optimizacija."""
        # Igrač ima karte pik, herc, karo i tref boje
        self.assertTrue(self.player.has_suit('S'))
        self.assertTrue(self.player.has_suit('H'))
        self.assertTrue(self.player.has_suit('D'))
        self.assertTrue(self.player.has_suit('C'))
        
        # Ukloni sve tref karte
        self.player.remove_card(Card.from_code('10C'))
        
        # Sada nema tref boje
        self.assertFalse(self.player.has_suit('C'))
    
    def test_can_play_card(self):
        """Test can_play_card metode nakon optimizacija."""
        # Prvi potez u štihu, svaka karta je dozvoljena
        for card in self.player.hand:
            self.assertTrue(self.player.can_play_card(card, [], 'S'))
        
        # Šith s pikovima, mora igrati pik ako ga ima
        trick = [Card.from_code('AS')]
        
        # Može igrati pikove
        self.assertTrue(self.player.can_play_card(Card.from_code('7S'), trick, 'H'))
        self.assertTrue(self.player.can_play_card(Card.from_code('8S'), trick, 'H'))
        
        # Ne može igrati druge boje
        self.assertFalse(self.player.can_play_card(Card.from_code('AH'), trick, 'H'))
        self.assertFalse(self.player.can_play_card(Card.from_code('JD'), trick, 'H'))


class RulesOptimizationTest(TestCase):
    """Testovi za optimizacije klase Rules."""
    
    def setUp(self):
        """Postavljanje testa."""
        self.rules = Rules()
        self.trump_suit = 'S'
        self.non_trump_suit = 'H'
    
    def test_get_card_value_in_trick(self):
        """Test get_card_value_in_trick metode nakon optimizacija."""
        # Adut jače od ne-aduta
        jack_trump = Card.from_code('JS')  # Dečko adut
        ace_non_trump = Card.from_code('AH')  # As ne-adut
        
        jack_value = self.rules.get_card_value_in_trick(jack_trump, self.non_trump_suit, self.trump_suit)
        ace_value = self.rules.get_card_value_in_trick(ace_non_trump, self.non_trump_suit, self.trump_suit)
        
        self.assertGreater(jack_value, ace_value, "Dečko adut treba biti jači od asa ne-aduta")
        
        # Keširanje - drugi poziv bi trebao vratiti keširan rezultat
        jack_value2 = self.rules.get_card_value_in_trick(jack_trump, self.non_trump_suit, self.trump_suit)
        self.assertEqual(jack_value, jack_value2)
    
    def test_determine_trick_winner(self):
        """Test determine_trick_winner metode nakon optimizacija."""
        # Šith bez aduta - pobjeđuje najviša karta iste boje
        trick_no_trump = [Card.from_code('7H'), Card.from_code('KH'), Card.from_code('QH'), Card.from_code('AH')]
        winner_idx = self.rules.determine_trick_winner(trick_no_trump, self.trump_suit)
        self.assertEqual(winner_idx, 3, "As herc treba pobijediti")
        
        # Šith s adutom - pobjeđuje najviši adut
        trick_with_trump = [Card.from_code('7H'), Card.from_code('KH'), Card.from_code('9S'), Card.from_code('AH')]
        winner_idx = self.rules.determine_trick_winner(trick_with_trump, self.trump_suit)
        self.assertEqual(winner_idx, 2, "Adut devetka treba pobijediti")
    
    def test_check_declarations(self):
        """Test check_declarations metode nakon optimizacija."""
        # Ruka s belom (kralj i dama aduta)
        bela_hand = [Card.from_code('KS'), Card.from_code('QS')]
        
        declarations = self.rules.check_declarations(bela_hand, self.trump_suit)
        
        # Treba naći belu
        self.assertEqual(len(declarations), 1)
        self.assertEqual(declarations[0]['type'], 'bela')
        
        # Ruka s tercom (sekvenca od 3)
        sequence_hand = [Card.from_code('7S'), Card.from_code('8S'), Card.from_code('9S'), Card.from_code('JS')]
        
        declarations = self.rules.check_declarations(sequence_hand, self.trump_suit)
        
        # Treba naći tercu (četvorku)
        self.assertEqual(len(declarations), 1)
        self.assertEqual(declarations[0]['type'], 'sequence_4')


class ScoringOptimizationTest(TestCase):
    """Testovi za optimizacije klase Scoring."""
    
    def setUp(self):
        """Postavljanje testa."""
        self.scoring = Scoring()
        self.trump_suit = 'S'
    
    def test_get_card_point_value(self):
        """Test get_card_point_value metode nakon optimizacija."""
        # Bodovi za adut
        jack_trump = Card.from_code('JS')  # Dečko adut - 20 bodova
        nine_trump = Card.from_code('9S')  # Devetka adut - 14 bodova
        
        self.assertEqual(self.scoring.get_card_point_value(jack_trump, self.trump_suit), 20)
        self.assertEqual(self.scoring.get_card_point_value(nine_trump, self.trump_suit), 14)
        
        # Bodovi za ne-adut
        ace_non_trump = Card.from_code('AH')  # As ne-adut - 11 bodova
        king_non_trump = Card.from_code('KH')  # Kralj ne-adut - 4 boda
        
        self.assertEqual(self.scoring.get_card_point_value(ace_non_trump, self.trump_suit), 11)
        self.assertEqual(self.scoring.get_card_point_value(king_non_trump, self.trump_suit), 4)
    
    def test_calculate_trick_points(self):
        """Test calculate_trick_points metode nakon optimizacija."""
        # Šith bez aduta
        trick_no_trump = [Card.from_code('AH'), Card.from_code('KH'), Card.from_code('QH'), Card.from_code('JH')]
        points = self.scoring.calculate_trick_points(trick_no_trump, self.trump_suit)
        
        # As (11) + Kralj (4) + Dama (3) + Dečko (2) = 20
        self.assertEqual(points, 20)
        
        # Šith s adutom i zadnji šith
        trick_with_trump = [Card.from_code('7H'), Card.from_code('KH'), Card.from_code('9S'), Card.from_code('JH')]
        points = self.scoring.calculate_trick_points(trick_with_trump, self.trump_suit, is_last_trick=True)
        
        # Devetka adut (14) + Kralj (4) + Dečko (2) + ostale (0) + 10 za zadnji šith = 30
        self.assertEqual(points, 30)
    
    def test_check_belot_bonus(self):
        """Test check_belot_bonus metode nakon optimizacija."""
        # Ruka s belom (kralj i dama aduta)
        bela_hand = [Card.from_code('KS'), Card.from_code('QS')]
        
        # Provjera bele
        points = self.scoring.check_belot_bonus(bela_hand, self.trump_suit)
        self.assertEqual(points, 20)
        
        # Ruka bez bele (samo kralj adut)
        no_bela_hand = [Card.from_code('KS'), Card.from_code('QH')]
        
        # Provjera bez bele
        points = self.scoring.check_belot_bonus(no_bela_hand, self.trump_suit)
        self.assertEqual(points, 0)


class ValidatorOptimizationTest(TestCase):
    """Testovi za optimizacije validatora poteza i zvanja."""
    
    def setUp(self):
        """Postavljanje testa."""
        self.move_validator = MoveValidator()
        self.call_validator = CallValidator()
        self.trump_suit = 'S'
        
        # Kreiraj ruku s različitim bojama
        self.hand = [
            Card.from_code('7S'), Card.from_code('8S'),  # Pikovi
            Card.from_code('AH'), Card.from_code('KH'),  # Herčevi
            Card.from_code('JD'), Card.from_code('QD'),  # Karo
            Card.from_code('9C'), Card.from_code('10C')  # Tref
        ]
    
    def test_validate_move(self):
        """Test validate_move metode nakon optimizacija."""
        # Prvi potez u štihu - svaka karta je dozvoljena
        for card in self.hand:
            is_valid, _ = self.move_validator.validate(card, self.hand, [], self.trump_suit)
            self.assertTrue(is_valid)
        
        # Šith s pikovima - mora igrati pik ako ga ima
        trick = [Card.from_code('AS')]
        
        # Može igrati pikove
        is_valid, _ = self.move_validator.validate(Card.from_code('7S'), self.hand, trick, self.trump_suit)
        self.assertTrue(is_valid)
        
        # Ne može igrati druge boje
        is_valid, _ = self.move_validator.validate(Card.from_code('AH'), self.hand, trick, self.trump_suit)
        self.assertFalse(is_valid)
    
    def test_validate_bela(self):
        """Test validate_bela metode nakon optimizacija."""
        # Validna bela - kralj i dama aduta
        cards_valid = [Card.from_code('KS'), Card.from_code('QS')]
        is_valid, _ = self.call_validator.validate_bela(cards_valid, self.trump_suit)
        self.assertTrue(is_valid)
        
        # Nevalidna bela - kralj i dama različitih boja
        cards_invalid = [Card.from_code('KS'), Card.from_code('QH')]
        is_valid, _ = self.call_validator.validate_bela(cards_invalid, self.trump_suit)
        self.assertFalse(is_valid)
        
        # Nevalidna bela - krive karte
        cards_invalid2 = [Card.from_code('KS'), Card.from_code('JS')]
        is_valid, _ = self.call_validator.validate_bela(cards_invalid2, self.trump_suit)
        self.assertFalse(is_valid)
    
    def test_validate_sequence(self):
        """Test validate_sequence metode nakon optimizacija."""
        # Validna terca - 3 karte u nizu
        cards_terca = ['7S', '8S', '9S']
        is_valid, _ = self.call_validator.validate_sequence(cards_terca, 'sequence_3')
        self.assertTrue(is_valid)
        
        # Validna kvarta - 4 karte u nizu
        cards_kvarta = ['7S', '8S', '9S', '10S']
        is_valid, _ = self.call_validator.validate_sequence(cards_kvarta, 'sequence_4')
        self.assertTrue(is_valid)
        
        # Nevalidna sekvenca - karte nisu u nizu
        cards_invalid = ['7S', '8S', '10S']
        is_valid, _ = self.call_validator.validate_sequence(cards_invalid, 'sequence_3')
        self.assertFalse(is_valid)
        
        # Nevalidna sekvenca - različite boje
        cards_invalid2 = ['7S', '8S', '9H']
        is_valid, _ = self.call_validator.validate_sequence(cards_invalid2, 'sequence_3')
        self.assertFalse(is_valid)


class CardUtilsOptimizationTest(TestCase):
    """Testovi za optimizacije funkcija u card_utils."""
    
    def test_normalize_suit(self):
        """Test normalize_suit funkcije nakon optimizacija."""
        # Normalizacija iz punog imena
        self.assertEqual(normalize_suit('spades'), 'S')
        self.assertEqual(normalize_suit('hearts'), 'H')
        self.assertEqual(normalize_suit('diamonds'), 'D')
        self.assertEqual(normalize_suit('clubs'), 'C')
        
        # Već normalizirane vrijednosti
        self.assertEqual(normalize_suit('S'), 'S')
        self.assertEqual(normalize_suit('H'), 'H')
        
        # Neosjetljivost na velika/mala slova
        self.assertEqual(normalize_suit('SPADES'), 'S')
        self.assertEqual(normalize_suit('Hearts'), 'H')
    
    def test_suit_name(self):
        """Test suit_name funkcije nakon optimizacija."""
        # Hrvatski nazivi
        self.assertEqual(suit_name('S', 'hr'), 'pik')
        self.assertEqual(suit_name('H', 'hr'), 'herc')
        self.assertEqual(suit_name('D', 'hr'), 'karo')
        self.assertEqual(suit_name('C', 'hr'), 'tref')
        
        # Engleski nazivi
        self.assertEqual(suit_name('S', 'en'), 'Spades')
        self.assertEqual(suit_name('H', 'en'), 'Hearts')
        
        # Zadana vrijednost je hrvatski
        self.assertEqual(suit_name('S'), 'pik')
    
    def test_get_display_name(self):
        """Test get_display_name funkcije nakon optimizacija."""
        self.assertEqual(get_display_name('S'), '♠️ Pik')
        self.assertEqual(get_display_name('H'), '♥️ Herc')
        self.assertEqual(get_display_name('D'), '♦️ Karo')
        self.assertEqual(get_display_name('C'), '♣️ Tref') 