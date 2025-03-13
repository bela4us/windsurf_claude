"""
Testovi za osnovnu logiku Belot igre.

Ovaj modul testira osnovne logičke komponente igre Belot, uključujući
karte, špil, pravila igre, bodovanje i validaciju poteza.
"""

import unittest
from django.test import TestCase

from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from game.game_logic.validators.move_validator import MoveValidator
from game.game_logic.validators.call_validator import CallValidator


class CardTest(unittest.TestCase):
    """Testovi za Card klasu."""
    
    def test_card_creation(self):
        """Test stvaranja karte."""
        card = Card('A', 'S')  # As pik
        
        self.assertEqual(card.value, 'A')
        self.assertEqual(card.suit, 'S')
        self.assertEqual(card.code, 'AS')
        
        # Test stvaranja karte iz koda
        card2 = Card.from_code('KH')  # Kralj herc
        
        self.assertEqual(card2.value, 'K')
        self.assertEqual(card2.suit, 'H')
        self.assertEqual(card2.code, 'KH')
    
    def test_card_comparisons(self):
        """Test usporedbe karata."""
        # Iste karte su jednake
        card1 = Card('J', 'D')
        card2 = Card('J', 'D')
        
        self.assertEqual(card1, card2)
        
        # Različite karte nisu jednake
        card3 = Card('Q', 'D')
        
        self.assertNotEqual(card1, card3)
        
        # Test hash funkcije (za korištenje karata kao ključeva rječnika)
        card_set = {card1, card2, card3}
        self.assertEqual(len(card_set), 2)  # card1 i card2 su jednake, pa imamo 2 jedinstvene karte
    
    def test_card_representation(self):
        """Test string reprezentacije karte."""
        card = Card('10', 'H')
        
        self.assertEqual(str(card), '10 of Hearts')
        self.assertEqual(repr(card), "Card('10', 'H')")
    
    def test_is_valid_code(self):
        """Test provjere valjanosti koda karte."""
        # Valjani kodovi
        self.assertTrue(Card.is_valid_code('AS'))  # As pik
        self.assertTrue(Card.is_valid_code('10H'))  # Desetka herc
        self.assertTrue(Card.is_valid_code('JD'))  # Dečko karo
        self.assertTrue(Card.is_valid_code('QC'))  # Dama tref
        
        # Nevaljani kodovi
        self.assertFalse(Card.is_valid_code(''))  # Prazan string
        self.assertFalse(Card.is_valid_code('A'))  # Samo vrijednost
        self.assertFalse(Card.is_valid_code('S'))  # Samo boja
        self.assertFalse(Card.is_valid_code('AX'))  # Nepoznata boja
        self.assertFalse(Card.is_valid_code('1S'))  # Nepoznata vrijednost
        self.assertFalse(Card.is_valid_code('ASX'))  # Previše znakova
    
    def test_get_suit_name(self):
        """Test dohvaćanja punog imena boje."""
        self.assertEqual(Card.get_suit_name('S'), 'Spades')
        self.assertEqual(Card.get_suit_name('H'), 'Hearts')
        self.assertEqual(Card.get_suit_name('D'), 'Diamonds')
        self.assertEqual(Card.get_suit_name('C'), 'Clubs')
        
        # Nepoznata boja
        self.assertEqual(Card.get_suit_name('X'), 'Unknown')
    
    def test_get_value_name(self):
        """Test dohvaćanja punog imena vrijednosti."""
        self.assertEqual(Card.get_value_name('A'), 'Ace')
        self.assertEqual(Card.get_value_name('K'), 'King')
        self.assertEqual(Card.get_value_name('Q'), 'Queen')
        self.assertEqual(Card.get_value_name('J'), 'Jack')
        self.assertEqual(Card.get_value_name('10'), 'Ten')
        self.assertEqual(Card.get_value_name('9'), 'Nine')
        self.assertEqual(Card.get_value_name('8'), 'Eight')
        self.assertEqual(Card.get_value_name('7'), 'Seven')
        
        # Nepoznata vrijednost
        self.assertEqual(Card.get_value_name('X'), 'Unknown')


class DeckTest(unittest.TestCase):
    """Testovi za Deck klasu."""
    
    def test_deck_creation(self):
        """Test stvaranja špila."""
        deck = Deck()
        
        # Špil Belota ima 32 karte
        self.assertEqual(len(deck.cards), 32)
        
        # Provjera da su sve karte jedinstvene
        card_codes = [card.code for card in deck.cards]
        self.assertEqual(len(card_codes), len(set(card_codes)))
        
        # Provjera da špil sadrži sve očekivane karte
        expected_values = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        expected_suits = ['S', 'H', 'D', 'C']
        
        for value in expected_values:
            for suit in expected_suits:
                card_code = value + suit
                self.assertIn(card_code, card_codes)
    
    def test_shuffle(self):
        """Test miješanja špila."""
        deck = Deck()
        original_order = deck.cards.copy()
        
        # Miješanje špila
        deck.shuffle()
        
        # Špil bi trebao imati isti broj karata
        self.assertEqual(len(deck.cards), 32)
        
        # Ali bi redoslijed trebao biti drugačiji (u većini slučajeva)
        self.assertNotEqual(deck.cards, original_order)
        
        # Provjera da su iste karte u špilu nakon miješanja
        original_codes = sorted([card.code for card in original_order])
        shuffled_codes = sorted([card.code for card in deck.cards])
        self.assertEqual(original_codes, shuffled_codes)
    
    def test_draw(self):
        """Test vučenja karte iz špila."""
        deck = Deck()
        initial_count = len(deck.cards)
        
        # Izvlačenje karte
        card = deck.draw()
        
        # Špil bi trebao imati jednu kartu manje
        self.assertEqual(len(deck.cards), initial_count - 1)
        
        # Izvučena karta ne bi trebala biti u špilu
        self.assertNotIn(card, deck.cards)
        
        # Izvlačenje svih karata
        for _ in range(initial_count - 1):
            deck.draw()
        
        # Špil bi trebao biti prazan
        self.assertEqual(len(deck.cards), 0)
        
        # Pokušaj izvlačenja iz praznog špila
        with self.assertRaises(ValueError):
            deck.draw()
    
    def test_deal(self):
        """Test dijeljenja karata igračima."""
        deck = Deck()
        
        # Dijeljenje 8 karata za 4 igrača
        hands = deck.deal(4, 8)
        
        # Provjera da su sve ruke ispravne veličine
        self.assertEqual(len(hands), 4)
        for hand in hands:
            self.assertEqual(len(hand), 8)
        
        # Provjera da su karte jedinstvene (nijedna karta se ne pojavljuje dvaput)
        all_cards = []
        for hand in hands:
            all_cards.extend(hand)
        
        self.assertEqual(len(all_cards), 32)
        self.assertEqual(len(set([card.code for card in all_cards])), 32)
        
        # Špil bi trebao biti prazan nakon dijeljenja svih karata
        self.assertEqual(len(deck.cards), 0)


class RulesTest(TestCase):
    """Testovi za Rules klasu."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.rules = Rules()
    
    def test_card_value_in_trick(self):
        """Test određivanja jačine karte u štihu."""
        # Karte istog aduta
        card1 = Card('J', 'H')  # Dečko herc
        card2 = Card('9', 'H')  # Devetka herc
        
        # U adutu, dečko je jači od devetke
        self.assertGreater(
            self.rules.get_card_value_in_trick(card1, 'H', 'H'),
            self.rules.get_card_value_in_trick(card2, 'H', 'H')
        )
        
        # Karte iste boje, ali nisu adut
        card3 = Card('A', 'S')  # As pik
        card4 = Card('10', 'S')  # Desetka pik
        
        # Izvan aduta, as je jači od desetke
        self.assertGreater(
            self.rules.get_card_value_in_trick(card3, 'S', 'H'),
            self.rules.get_card_value_in_trick(card4, 'S', 'H')
        )
        
        # Karte različitih boja
        card5 = Card('7', 'H')  # Sedmica herc (adut)
        card6 = Card('A', 'S')  # As pik (nije adut)
        
        # Adut pobjeđuje ne-adut
        self.assertGreater(
            self.rules.get_card_value_in_trick(card5, 'S', 'H'),
            self.rules.get_card_value_in_trick(card6, 'S', 'H')
        )
    
    def test_is_card_playable(self):
        """Test provjere može li se karta odigrati prema pravilima."""
        hand = [
            Card('A', 'S'), Card('K', 'S'),  # As i kralj pik
            Card('10', 'H'), Card('J', 'H'),  # Desetka i dečko herc
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        
        # Scenario 1: Prvi potez - bilo koja karta je dozvoljena
        for card in hand:
            self.assertTrue(self.rules.is_card_playable(card, hand, [], 'H'))
        
        # Scenario 2: Štih je započet, igrač mora pratiti boju
        trick = [Card('7', 'S')]  # Prvi potez je sedmica pik
        
        # Igračeve karte pik su dozvoljene
        self.assertTrue(self.rules.is_card_playable(Card('A', 'S'), hand, trick, 'H'))
        self.assertTrue(self.rules.is_card_playable(Card('K', 'S'), hand, trick, 'H'))
        
        # Ostale karte nisu dozvoljene jer igrač ima pik
        self.assertFalse(self.rules.is_card_playable(Card('10', 'H'), hand, trick, 'H'))
        self.assertFalse(self.rules.is_card_playable(Card('9', 'D'), hand, trick, 'H'))
        self.assertFalse(self.rules.is_card_playable(Card('7', 'C'), hand, trick, 'H'))
        
        # Scenario 3: Štih je započet, igrač nema traženu boju, mora igrati adut
        hand2 = [
            Card('10', 'H'), Card('J', 'H'),  # Desetka i dečko herc (adut)
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        trick = [Card('7', 'S')]  # Prvi potez je sedmica pik
        
        # Igračeve karte aduta su dozvoljene (herc)
        self.assertTrue(self.rules.is_card_playable(Card('10', 'H'), hand2, trick, 'H'))
        self.assertTrue(self.rules.is_card_playable(Card('J', 'H'), hand2, trick, 'H'))
        
        # Ostale karte nisu dozvoljene jer igrač ima adut
        self.assertFalse(self.rules.is_card_playable(Card('9', 'D'), hand2, trick, 'H'))
        self.assertFalse(self.rules.is_card_playable(Card('7', 'C'), hand2, trick, 'H'))
        
        # Scenario 4: Štih je započet, igrač nema ni traženu boju ni adut
        hand3 = [
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        trick = [Card('7', 'S')]  # Prvi potez je sedmica pik
        
        # Bilo koja karta je dozvoljena
        for card in hand3:
            self.assertTrue(self.rules.is_card_playable(card, hand3, trick, 'H'))
    
    def test_must_play_higher_card(self):
        """Test provjere mora li igrač igrati jaču kartu."""
        # Stvaranje ruku i poteza
        hand = [
            Card('A', 'S'), Card('K', 'S'),  # As i kralj pik
            Card('10', 'H'), Card('J', 'H'),  # Desetka i dečko herc
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        
        # Scenario 1: Igrač ima jaču kartu iste boje
        trick = [Card('7', 'S')]  # Prvi potez je sedmica pik
        
        # Igrač mora igrati jaču kartu (kralj ili as)
        self.assertTrue(self.rules.must_play_higher_card(Card('K', 'S'), hand, trick, 'H'))
        self.assertTrue(self.rules.must_play_higher_card(Card('A', 'S'), hand, trick, 'H'))
        
        # Scenario 2: Igrač nema jaču kartu iste boje
        hand2 = [
            Card('7', 'S'),  # Sedmica pik
            Card('10', 'H'), Card('J', 'H'),  # Desetka i dečko herc
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        trick = [Card('K', 'S')]  # Prvi potez je kralj pik
        
        # Igrač ne mora igrati jaču kartu (jer nema jaču)
        self.assertFalse(self.rules.must_play_higher_card(Card('7', 'S'), hand2, trick, 'H'))
        
        # Scenario 3: Netko je već igrao adut
        trick = [Card('7', 'S'), Card('9', 'H')]  # Prvi potez sedmica pik, drugi adut 9 herc
        
        # Igrač ne mora igrati jaču kartu jer je adut već igran
        self.assertFalse(self.rules.must_play_higher_card(Card('K', 'S'), hand, trick, 'H'))
    
    def test_determine_trick_winner(self):
        """Test određivanja pobjednika štiha."""
        # Scenario 1: Štih bez aduta
        trick = [
            Card('7', 'S'),  # Sedmica pik
            Card('K', 'S'),  # Kralj pik
            Card('A', 'S'),  # As pik
            Card('10', 'S')  # Desetka pik
        ]
        
        winner_index = self.rules.determine_trick_winner(trick, 'H')
        self.assertEqual(winner_index, 2)  # As pik je najjača karta
        
        # Scenario 2: Štih s adutom
        trick = [
            Card('A', 'S'),  # As pik
            Card('9', 'H'),  # Devetka herc (adut)
            Card('J', 'H'),  # Dečko herc (adut)
            Card('10', 'S')  # Desetka pik
        ]
        
        winner_index = self.rules.determine_trick_winner(trick, 'H')
        self.assertEqual(winner_index, 2)  # Dečko herc je najjača karta (adut)
        
        # Scenario 3: Štih s više aduta
        trick = [
            Card('7', 'H'),  # Sedmica herc (adut)
            Card('9', 'H'),  # Devetka herc (adut)
            Card('8', 'H'),  # Osmica herc (adut)
            Card('A', 'H')  # As herc (adut)
        ]
        
        winner_index = self.rules.determine_trick_winner(trick, 'H')
        self.assertEqual(winner_index, 1)  # Devetka herc je najjača adut karta


class ScoringTest(TestCase):
    """Testovi za Scoring klasu."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.scoring = Scoring()
    
    def test_card_point_value(self):
        """Test izračuna bodovne vrijednosti karata."""
        # Vrijednosti karata kada nisu adut
        self.assertEqual(self.scoring.get_card_point_value(Card('A', 'S'), 'H'), 11)
        self.assertEqual(self.scoring.get_card_point_value(Card('10', 'S'), 'H'), 10)
        self.assertEqual(self.scoring.get_card_point_value(Card('K', 'S'), 'H'), 4)
        self.assertEqual(self.scoring.get_card_point_value(Card('Q', 'S'), 'H'), 3)
        self.assertEqual(self.scoring.get_card_point_value(Card('J', 'S'), 'H'), 2)
        self.assertEqual(self.scoring.get_card_point_value(Card('9', 'S'), 'H'), 0)
        self.assertEqual(self.scoring.get_card_point_value(Card('8', 'S'), 'H'), 0)
        self.assertEqual(self.scoring.get_card_point_value(Card('7', 'S'), 'H'), 0)
        
        # Vrijednosti karata kada su adut
        self.assertEqual(self.scoring.get_card_point_value(Card('J', 'H'), 'H'), 20)
        self.assertEqual(self.scoring.get_card_point_value(Card('9', 'H'), 'H'), 14)
        self.assertEqual(self.scoring.get_card_point_value(Card('A', 'H'), 'H'), 11)
        self.assertEqual(self.scoring.get_card_point_value(Card('10', 'H'), 'H'), 10)
        self.assertEqual(self.scoring.get_card_point_value(Card('K', 'H'), 'H'), 4)
        self.assertEqual(self.scoring.get_card_point_value(Card('Q', 'H'), 'H'), 3)
        self.assertEqual(self.scoring.get_card_point_value(Card('8', 'H'), 'H'), 0)
        self.assertEqual(self.scoring.get_card_point_value(Card('7', 'H'), 'H'), 0)
    
    def test_trick_points(self):
        """Test izračuna bodova za štih."""
        # Štih bez aduta
        trick = [
            Card('A', 'S'),  # 11 bodova
            Card('K', 'S'),  # 4 boda
            Card('Q', 'S'),  # 3 boda
            Card('J', 'S')   # 2 boda
        ]
        
        points = self.scoring.calculate_trick_points(trick, 'H')
        self.assertEqual(points, 20)  # 11 + 4 + 3 + 2 = 20
        
        # Štih s adutom
        trick = [
            Card('J', 'H'),  # 20 bodova (adut)
            Card('9', 'H'),  # 14 bodova (adut)
            Card('A', 'S'),  # 11 bodova
            Card('10', 'S')  # 10 bodova
        ]
        
        points = self.scoring.calculate_trick_points(trick, 'H')
        self.assertEqual(points, 55)  # 20 + 14 + 11 + 10 = 55
    
    def test_last_trick_bonus(self):
        """Test dodatnih bodova za zadnji štih."""
        trick = [
            Card('7', 'S'),  # 0 bodova
            Card('8', 'S'),  # 0 bodova
            Card('9', 'S'),  # 0 bodova
            Card('J', 'S')   # 2 boda
        ]
        
        # Bez označavanja zadnjeg štiha
        points = self.scoring.calculate_trick_points(trick, 'H')
        self.assertEqual(points, 2)  # 0 + 0 + 0 + 2 = 2
        
        # S označavanjem zadnjeg štiha
        points = self.scoring.calculate_trick_points(trick, 'H', is_last_trick=True)
        self.assertEqual(points, 12)  # 0 + 0 + 0 + 2 + 10 = 12
    
    def test_declarations_points(self):
        """Test izračuna bodova za zvanja."""
        # Četiri dečka
        points = self.scoring.get_declaration_value('four_jacks', ['JS', 'JH', 'JD', 'JC'])
        self.assertEqual(points, 200)
        
        # Četiri devetke
        points = self.scoring.get_declaration_value('four_nines', ['9S', '9H', '9D', '9C'])
        self.assertEqual(points, 150)
        
        # Četiri asa
        points = self.scoring.get_declaration_value('four_aces', ['AS', 'AH', 'AD', 'AC'])
        self.assertEqual(points, 100)
        
        # Kvarta (četiri karte u nizu)
        points = self.scoring.get_declaration_value('sequence_4', ['7S', '8S', '9S', '10S'])
        self.assertEqual(points, 50)
        
        # Terca (tri karte u nizu)
        points = self.scoring.get_declaration_value('sequence_3', ['JS', 'QS', 'KS'])
        self.assertEqual(points, 20)
        
        # Bela (kralj i dama aduta)
        points = self.scoring.get_declaration_value('bela', ['KH', 'QH'])
        self.assertEqual(points, 20)


class MoveValidatorTest(TestCase):
    """Testovi za MoveValidator klasu."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.validator = MoveValidator()
    
    def test_validate_move(self):
        """Test validacije poteza."""
        # Stvaranje ruke i poteza
        hand = [
            Card('A', 'S'), Card('K', 'S'),  # As i kralj pik
            Card('10', 'H'), Card('J', 'H'),  # Desetka i dečko herc
            Card('9', 'D'), Card('Q', 'D'),  # Devetka i dama karo
            Card('7', 'C'), Card('8', 'C')   # Sedmica i osmica tref
        ]
        
        # Scenario 1: Prvi potez, bilo koja karta je dozvoljena
        result, _ = self.validator.validate_move(Card('A', 'S'), hand, [], 'H')
        self.assertTrue(result)
        
        # Scenario 2: Igrač mora pratiti boju
        trick = [Card('7', 'D')]  # Prvi potez je sedmica karo
        
        # Karte karo su dozvoljene
        result, _ = self.validator.validate_move(Card('9', 'D'), hand, trick, 'H')
        self.assertTrue(result)
        result, _ = self.validator.validate_move(Card('Q', 'D'), hand, trick, 'H')
        self.assertTrue(result)
        
        # Ostale karte nisu dozvoljene
        result, _ = self.validator.validate_move(Card('A', 'S'), hand, trick, 'H')
        self.assertFalse(result)
        result, _ = self.validator.validate_move(Card('10', 'H'), hand, trick, 'H')
        self.assertFalse(result)
        
        # Scenario 3: Igrač mora "übati" (igrati višu kartu)
        trick = [Card('7', 'S')]  # Prvi potez je sedmica pik
        
        # Igrač mora igrati višu kartu od sedmice pik
        result, _ = self.validator.validate_move(Card('K', 'S'), hand, trick, 'H')
        self.assertTrue(result)
        result, _ = self.validator.validate_move(Card('A', 'S'), hand, trick, 'H')
        self.assertTrue(result)
        
        # Igrač ne smije igrati nižu kartu ako ima višu
        result, message = self.validator.validate_move(Card('7', 'S'), hand, trick, 'H')
        self.assertFalse(result)  # 7S je niža od već odigrane 7S i igrač ima više karte
        
        # Provjera poruke o grešci
        self.assertIn("viši", message.lower())


class CallValidatorTest(TestCase):
    """Testovi za CallValidator klasu."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.validator = CallValidator()
    
    def test_validate_trump_call(self):
        """Test validacije zvanja aduta."""
        # Test valjanih zvanja aduta
        result, _ = self.validator.validate_trump_call('hearts')
        self.assertTrue(result)
        
        result, _ = self.validator.validate_trump_call('spades')
        self.assertTrue(result)
        
        result, _ = self.validator.validate_trump_call('diamonds')
        self.assertTrue(result)
        
        result, _ = self.validator.validate_trump_call('clubs')
        self.assertTrue(result)
        
        # Test nevaljanih zvanja aduta
        result, message = self.validator.validate_trump_call('invalid')
        self.assertFalse(result)
        self.assertIn("nepoznat", message.lower())
        
        result, message = self.validator.validate_trump_call('')
        self.assertFalse(result)
        self.assertIn("prazno", message.lower())
    
    def test_validate_bela(self):
        """Test validacije bele (kralj i dama aduta)."""
        # Valjana bela
        result, _ = self.validator.validate_bela(['KH', 'QH'], 'hearts')
        self.assertTrue(result)
        
        # Nevaljana bela - pogrešne karte
        result, message = self.validator.validate_bela(['AH', 'QH'], 'hearts')
        self.assertFalse(result)
        self.assertIn("kralj i dama", message.lower())
        
        # Nevaljana bela - karte nisu adut
        result, message = self.validator.validate_bela(['KS', 'QS'], 'hearts')
        self.assertFalse(result)
        self.assertIn("adut", message.lower())
    
    def test_validate_sequence(self):
        """Test validacije sekvence karata."""
        # Valjana terca
        result, _ = self.validator.validate_sequence(['7H', '8H', '9H'], 'sequence_3')
        self.assertTrue(result)
        
        # Valjana kvarta
        result, _ = self.validator.validate_sequence(['7H', '8H', '9H', '10H'], 'sequence_4')
        self.assertTrue(result)
        
        # Valjana kvinta
        result, _ = self.validator.validate_sequence(['7H', '8H', '9H', '10H', 'JH'], 'sequence_5_plus')
        self.assertTrue(result)
        
        # Nevaljana sekvenca - premalo karata
        result, message = self.validator.validate_sequence(['7H', '8H'], 'sequence_3')
        self.assertFalse(result)
        self.assertIn("barem 3", message.lower())
        
        # Nevaljana sekvenca - karte nisu u nizu
        result, message = self.validator.validate_sequence(['7H', '8H', '10H'], 'sequence_3')
        self.assertFalse(result)
        self.assertIn("nizu", message.lower())
        
        # Nevaljana sekvenca - karte nisu iste boje
        result, message = self.validator.validate_sequence(['7H', '8H', '9S'], 'sequence_3')
        self.assertFalse(result)
        self.assertIn("boje", message.lower())