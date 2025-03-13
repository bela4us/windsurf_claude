"""
Utility funkcije za rad s kartama u Belot igri.

Ovaj modul sadrži pomoćne funkcije za rukovanje kartama,
normalizaciju boja, i druge uobičajene operacije s kartama.
"""

def normalize_suit(suit):
    """
    Pretvara puno ime boje u kod boje.
    
    Args:
        suit: Boja (puno ime ili kod)
        
    Returns:
        str: Kod boje ('S', 'H', 'D', 'C')
    """
    # Mapiranje punih imena boja na kodove
    suit_map = {
        'spades': 'S',
        'hearts': 'H',
        'diamonds': 'D',
        'clubs': 'C'
    }
    
    # Ako je već kod, vrati ga
    valid_suits = ['S', 'H', 'D', 'C']
    if suit in valid_suits:
        return suit
    
    # Inače pokušaj mapirati iz punog imena
    return suit_map.get(suit.lower(), suit)


def suit_name(suit_code, language='hr'):
    """
    Vraća čitljivo ime boje.
    
    Args:
        suit_code: Kod boje ('S', 'H', 'D', 'C')
        language: Jezik za povrat imena (hr=hrvatski, en=engleski)
        
    Returns:
        str: Čitljivo ime boje
    """
    if language == 'hr':
        suit_names = {
            'S': 'pik',
            'H': 'herc',
            'D': 'karo',
            'C': 'tref'
        }
    else:  # default je engleski
        suit_names = {
            'S': 'Spades',
            'H': 'Hearts',
            'D': 'Diamonds',
            'C': 'Clubs'
        }
        
    return suit_names.get(suit_code, suit_code)


def get_display_name(suit_code):
    """
    Vraća prikazno ime boje s Unicode simbolom.
    
    Args:
        suit_code: Kod boje ('S', 'H', 'D', 'C')
        
    Returns:
        str: Prikazno ime boje s Unicode simbolom
    """
    symbols = {
        'S': '♠️',
        'H': '♥️',
        'D': '♦️',
        'C': '♣️'
    }
    
    names = {
        'S': 'Pik',
        'H': 'Herc',
        'D': 'Karo',
        'C': 'Tref'
    }
    
    if suit_code in symbols:
        return f"{symbols[suit_code]} {names[suit_code]}"
    return suit_code