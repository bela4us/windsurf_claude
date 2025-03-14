#!/usr/bin/env python
"""
Skripta za testiranje performansi optimiziranih funkcija i klasa u Belot projektu.

Ova skripta izvodi niz testova za mjerenje performansi ključnih komponenti,
uključujući funkcije za rad s kartama, pravilima igre i validacije poteza.
Glavni fokus je na utjecaju keširanja i drugih optimizacija na brzinu izvršavanja.
"""

import os
import sys
import time
import django
import random
import logging
import statistics
from datetime import datetime
from functools import wraps

# Postavljanje Django okruženja
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')
django.setup()

# Konfiguracija logging sustava
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Uvoz svih optimiziranih modula za testiranje
from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.player import Player
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from game.game_logic.validators.move_validator import MoveValidator
from game.game_logic.validators.call_validator import CallValidator
from game.utils.card_utils import normalize_suit, suit_name, get_display_name

def measure_time(func):
    """Dekorator za mjerenje vremena izvršavanja funkcije."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time
    return wrapper

def warm_up_function(func, *args, **kwargs):
    """Zagrijava funkciju kako bi se napunio keš."""
    for _ in range(10):
        func(*args, **kwargs)

def test_cache_impact(func, *args, iterations=1000, **kwargs):
    """
    Testira utjecaj keša na performanse funkcije.
    
    Args:
        func: Funkcija koja se testira
        iterations: Broj ponavljanja testa
        args, kwargs: Argumenti za funkciju
        
    Returns:
        dict: Rezultati testa (vremena s kešom i bez njega)
    """
    # Prvo mjerenje - bez čišćenja keša (koristi keš)
    warm_up_function(func, *args, **kwargs)
    cached_times = []
    
    for _ in range(iterations):
        _, execution_time = measure_time(func)(*args, **kwargs)
        cached_times.append(execution_time)
    
    # Drugo mjerenje - s čišćenjem keša prije svakog poziva
    uncached_times = []
    
    for _ in range(iterations):
        if hasattr(func, 'cache_clear'):
            func.cache_clear()
        _, execution_time = measure_time(func)(*args, **kwargs)
        uncached_times.append(execution_time)
    
    return {
        'cached_mean': statistics.mean(cached_times),
        'cached_median': statistics.median(cached_times),
        'uncached_mean': statistics.mean(uncached_times),
        'uncached_median': statistics.median(uncached_times),
        'improvement_factor': statistics.mean(uncached_times) / statistics.mean(cached_times) if statistics.mean(cached_times) > 0 else 0,
        'cached_min': min(cached_times),
        'uncached_min': min(uncached_times),
    }

def run_card_tests():
    """Izvodi testove optimizacije za funkcije rada s kartama."""
    logger.info("=== TEST OPTIMIZACIJA KARATA ===")
    
    # Test 1: Kreiranje karata
    def test_create_cards():
        cards = []
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                cards.append(Card.from_code(f"{value}{suit}"))
        return cards
    
    result, time_taken = measure_time(test_create_cards)()
    logger.info(f"Kreiranje 32 karte: {time_taken:.6f} sekundi")
    
    # Test 2: Usporedba karata
    cards = test_create_cards()
    
    def test_card_comparison():
        sorted_cards = sorted(cards, key=lambda c: (c.suit, c.get_rank_index()))
        return sorted_cards
    
    result, time_taken = measure_time(test_card_comparison)()
    logger.info(f"Sortiranje 32 karte: {time_taken:.6f} sekundi")
    
    # Test 3: Utjecaj keša na normalize_suit
    suits = ['spades', 'hearts', 'diamonds', 'clubs', 'S', 'H', 'D', 'C']
    cache_results = test_cache_impact(normalize_suit, random.choice(suits), iterations=10000)
    
    logger.info(f"normalize_suit s kešom (median): {cache_results['cached_median']:.6f} sekundi")
    logger.info(f"normalize_suit bez keša (median): {cache_results['uncached_median']:.6f} sekundi")
    logger.info(f"Poboljšanje: {cache_results['improvement_factor']:.2f}x")
    
    return {
        'card_creation': time_taken,
        'card_sorting': time_taken,
        'normalize_suit_impact': cache_results,
    }

def run_deck_tests():
    """Izvodi testove optimizacije za klasu Deck."""
    logger.info("=== TEST OPTIMIZACIJA ŠPILA ===")
    
    # Test 1: Kreiranje i miješanje špila
    @measure_time
    def create_and_shuffle_deck():
        deck = Deck()
        deck.shuffle()
        return deck
    
    deck, creation_time = create_and_shuffle_deck()
    logger.info(f"Kreiranje i miješanje špila: {creation_time:.6f} sekundi")
    
    # Test 2: Dijeljenje karata
    @measure_time
    def deal_cards(deck):
        hands = deck.deal(4)
        return hands
    
    hands, deal_time = deal_cards(deck)
    logger.info(f"Dijeljenje karata za 4 igrača: {deal_time:.6f} sekundi")
    
    return {
        'deck_creation': creation_time,
        'deal_time': deal_time,
    }

def run_rules_tests():
    """Izvodi testove optimizacije za klasu Rules."""
    logger.info("=== TEST OPTIMIZACIJA PRAVILA ===")
    
    rules = Rules()
    # Kreiranje špila i dijeljenje karata za testove
    deck = Deck()
    
    # Osiguravamo da špil ima karte
    if len(deck.cards) == 0:
        # Ručno stvaramo karte za špil
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                deck.cards.append(Card.from_code(f"{value}{suit}"))
    
    deck.shuffle()
    hand = deck.cards[:8]  # Uzimamo 8 karata za ruku
    trump_suit = 'S'
    
    # Test 1: Mjerenje vremena za get_card_value_in_trick s kešom i bez njega
    test_card = hand[0]
    lead_suit = 'H'
    
    cache_results = test_cache_impact(
        rules.get_card_value_in_trick, 
        test_card, lead_suit, trump_suit,
        iterations=5000
    )
    
    logger.info(f"get_card_value_in_trick s kešom (median): {cache_results['cached_median']:.6f} sekundi")
    logger.info(f"get_card_value_in_trick bez keša (median): {cache_results['uncached_median']:.6f} sekundi")
    logger.info(f"Poboljšanje: {cache_results['improvement_factor']:.2f}x")
    
    # Test 2: Mjerenje vremena za is_card_playable
    trick = [Card.from_code('AH'), Card.from_code('KH'), Card.from_code('QH')]
    
    @measure_time
    def test_is_card_playable():
        results = []
        for card in hand:
            results.append(rules.is_card_playable(card, hand, trick, trump_suit))
        return results
    
    results, playable_time = test_is_card_playable()
    logger.info(f"Provjera 8 karata je li playable: {playable_time:.6f} sekundi")
    
    # Test 3: Mjerenje vremena za determine_trick_winner
    @measure_time
    def test_determine_winner():
        return rules.determine_trick_winner(trick, trump_suit)
    
    winner, winner_time = test_determine_winner()
    logger.info(f"Određivanje pobjednika štiha: {winner_time:.6f} sekundi")
    
    return {
        'card_value_cache_impact': cache_results,
        'playable_check_time': playable_time,
        'winner_determination_time': winner_time,
    }

def run_validator_tests():
    """Izvodi testove optimizacije za validatore poteza i zvanja."""
    logger.info("=== TEST OPTIMIZACIJA VALIDATORA ===")
    
    move_validator = MoveValidator()
    call_validator = CallValidator()
    
    # Kreiranje špila i dijeljenje karata za testove
    deck = Deck()
    
    # Osiguravamo da špil ima karte
    if len(deck.cards) == 0:
        # Ručno stvaramo karte za špil
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                deck.cards.append(Card.from_code(f"{value}{suit}"))
    
    deck.shuffle()
    hand = deck.cards[:8]  # Uzimamo 8 karata za ruku
    trick = [Card.from_code('AH'), Card.from_code('KH')]
    trump_suit = 'S'
    
    # Test 1: Mjerenje vremena za validate_move
    @measure_time
    def test_validate_move():
        results = []
        for card in hand:
            results.append(move_validator.validate(card, hand, trick, trump_suit))
        return results
    
    results, validate_time = test_validate_move()
    logger.info(f"Validacija 8 poteza: {validate_time:.6f} sekundi")
    
    # Test 2: Utjecaj keša na _normalize_suit
    suits = ['spades', 'hearts', 'diamonds', 'clubs', 'S', 'H', 'D', 'C']
    cache_results = test_cache_impact(
        move_validator._normalize_suit, 
        random.choice(suits),
        iterations=10000
    )
    
    logger.info(f"_normalize_suit s kešom (median): {cache_results['cached_median']:.6f} sekundi")
    logger.info(f"_normalize_suit bez keša (median): {cache_results['uncached_median']:.6f} sekundi")
    logger.info(f"Poboljšanje: {cache_results['improvement_factor']:.2f}x")
    
    # Test 3: Mjerenje vremena za validaciju zvanja
    cards_for_declaration = [Card.from_code('KS'), Card.from_code('QS')]
    
    @measure_time
    def test_validate_bela():
        return call_validator.validate_bela(cards_for_declaration, 'S')
    
    bela_result, bela_time = test_validate_bela()
    logger.info(f"Validacija zvanja bele: {bela_time:.6f} sekundi")
    
    return {
        'move_validation_time': validate_time,
        'normalize_suit_impact': cache_results,
        'bela_validation_time': bela_time,
    }

def run_performance_tests():
    """Izvodi kompletne testove performansi za sve optimizirane komponente."""
    logger.info("=== POČETAK TESTIRANJA PERFORMANSI OPTIMIZACIJA ===")
    start_time = time.time()
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'cards': run_card_tests(),
        'deck': run_deck_tests(),
        'rules': run_rules_tests(),
        'validators': run_validator_tests(),
    }
    
    end_time = time.time()
    total_time = end_time - start_time
    
    logger.info(f"=== TESTIRANJE ZAVRŠENO (ukupno vrijeme: {total_time:.2f}s) ===")
    
    # Ispis sažetka rezultata
    logger.info("\n=== SAŽETAK REZULTATA ===")
    
    # Utjecaj keša
    cache_impacts = [
        results['cards']['normalize_suit_impact']['improvement_factor'],
        results['rules']['card_value_cache_impact']['improvement_factor'],
        results['validators']['normalize_suit_impact']['improvement_factor'],
    ]
    avg_cache_impact = statistics.mean(cache_impacts)
    logger.info(f"Prosječno poboljšanje zbog keširanja: {avg_cache_impact:.2f}x")
    
    # Najbrže i najsporije operacije
    operations = [
        ('Normalizacija boje (keširana)', results['cards']['normalize_suit_impact']['cached_min']),
        ('Normalizacija boje (nekeširana)', results['cards']['normalize_suit_impact']['uncached_min']),
        ('Kreiranje špila', results['deck']['deck_creation']),
        ('Dijeljenje karata', results['deck']['deal_time']),
        ('Vrijednost karte u štihu (keširana)', results['rules']['card_value_cache_impact']['cached_min']),
        ('Vrijednost karte u štihu (nekeširana)', results['rules']['card_value_cache_impact']['uncached_min']),
        ('Provjera valjanosti poteza', results['validators']['move_validation_time']),
    ]
    
    operations.sort(key=lambda x: x[1])
    
    logger.info("\nNajbrže operacije:")
    for name, time_taken in operations[:3]:
        logger.info(f"- {name}: {time_taken:.6f}s")
    
    logger.info("\nNajsporije operacije:")
    for name, time_taken in operations[-3:]:
        logger.info(f"- {name}: {time_taken:.6f}s")
    
    return results

def main():
    """Glavna funkcija za pokretanje testova performansi."""
    try:
        results = run_performance_tests()
        logger.info("Testiranje performansi uspješno završeno")
        return 0
    except Exception as e:
        logger.error(f"Greška pri testiranju performansi: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 