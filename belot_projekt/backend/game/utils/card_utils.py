"""
Utility funkcije za rad s kartama u Belot igri.

Ovaj modul sadrži pomoćne funkcije za rukovanje kartama,
normalizaciju boja, i druge uobičajene operacije s kartama.
"""

import logging
from functools import lru_cache
from game.utils.decorators import track_execution_time

# Postavljanje loggera za praćenje aktivnosti
logger = logging.getLogger(__name__)

# Konstante za boje
VALID_SUITS = ['S', 'H', 'D', 'C']

# Mapiranja za boje
SUIT_MAP = {
    'spades': 'S',
    'hearts': 'H',
    'diamonds': 'D',
    'clubs': 'C'
}

SUIT_NAMES_HR = {
    'S': 'pik',
    'H': 'herc',
    'D': 'karo',
    'C': 'tref'
}

SUIT_NAMES_EN = {
    'S': 'Spades',
    'H': 'Hearts',
    'D': 'Diamonds',
    'C': 'Clubs'
}

SUIT_SYMBOLS = {
    'S': '♠️',
    'H': '♥️',
    'D': '♦️',
    'C': '♣️'
}

SUIT_DISPLAY_NAMES = {
    'S': 'Pik',
    'H': 'Herc',
    'D': 'Karo',
    'C': 'Tref'
}

@lru_cache(maxsize=32)
@track_execution_time
def normalize_suit(suit):
    """
    Pretvara puno ime boje u kod boje.
    
    Args:
        suit (str): Boja (puno ime ili kod)
        
    Returns:
        str: Kod boje ('S', 'H', 'D', 'C')
        
    Raises:
        ValueError: Ako boja nije prepoznata ni kao kod niti kao puno ime
    """
    try:
        if not suit:
            logger.warning("Pokušaj normalizacije prazne vrijednosti boje")
            return None
            
        # Ako je već kod, vrati ga
        if suit in VALID_SUITS:
            return suit
        
        # Inače pokušaj mapirati iz punog imena
        normalized = SUIT_MAP.get(suit.lower())
        
        if normalized:
            logger.debug(f"Normalizirana boja: {suit} -> {normalized}")
            return normalized
        
        logger.warning(f"Nepoznata boja za normalizaciju: {suit}")
        return suit
        
    except Exception as e:
        logger.error(f"Greška prilikom normalizacije boje: {str(e)}")
        return suit


@lru_cache(maxsize=64)
@track_execution_time
def suit_name(suit_code, language='hr'):
    """
    Vraća čitljivo ime boje.
    
    Args:
        suit_code (str): Kod boje ('S', 'H', 'D', 'C')
        language (str, optional): Jezik za povrat imena (hr=hrvatski, en=engleski). Zadano je 'hr'.
        
    Returns:
        str: Čitljivo ime boje
    """
    try:
        if not suit_code:
            logger.warning("Pokušaj dohvaćanja imena za praznu vrijednost boje")
            return ""
            
        if language == 'hr':
            name = SUIT_NAMES_HR.get(suit_code)
        else:  # default je engleski
            name = SUIT_NAMES_EN.get(suit_code)
            
        if name:
            logger.debug(f"Dohvaćeno ime boje: {suit_code} -> {name} ({language})")
            return name
            
        logger.warning(f"Nepoznat kod boje: {suit_code}")
        return suit_code
        
    except Exception as e:
        logger.error(f"Greška prilikom dohvaćanja imena boje: {str(e)}")
        return suit_code


@lru_cache(maxsize=32)
@track_execution_time
def get_display_name(suit_code):
    """
    Vraća prikazno ime boje s Unicode simbolom.
    
    Args:
        suit_code (str): Kod boje ('S', 'H', 'D', 'C')
        
    Returns:
        str: Prikazno ime boje s Unicode simbolom
    """
    try:
        if not suit_code:
            logger.warning("Pokušaj dohvaćanja prikaznog imena za praznu vrijednost boje")
            return ""
            
        symbol = SUIT_SYMBOLS.get(suit_code)
        name = SUIT_DISPLAY_NAMES.get(suit_code)
        
        if symbol and name:
            display_name = f"{symbol} {name}"
            logger.debug(f"Dohvaćeno prikazno ime boje: {suit_code} -> {display_name}")
            return display_name
            
        logger.warning(f"Nepoznat kod boje za prikazno ime: {suit_code}")
        return suit_code
        
    except Exception as e:
        logger.error(f"Greška prilikom dohvaćanja prikaznog imena boje: {str(e)}")
        return suit_code