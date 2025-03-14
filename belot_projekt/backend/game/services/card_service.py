"""
Modul koji pruža servis za rad s kartama u Belot igri.

Ovaj modul sadrži klasu CardService koja pruža funkcionalnosti za
miješanje, dijeljenje i validaciju karata u igri Belot.
"""
import random
import logging
from functools import lru_cache
from django.db import transaction

from game.game_logic.card import Card
from game.models import Move
from game.repositories.move_repository import MoveRepository

logger = logging.getLogger(__name__)

class CardService:
    """
    Servis za rad s kartama u Belot igri.
    
    Pruža funkcionalnosti za miješanje, dijeljenje i validaciju karata.
    """
    
    @staticmethod
    def shuffle_deck():
        """
        Stvara i miješa novi špil karata.
        
        Returns:
            list: Promiješani špil karata
        """
        try:
            deck = Card.create_deck()
            random.shuffle(deck)
            return deck
        except Exception as e:
            logger.error(f"Greška pri miješanju špila: {e}", exc_info=True)
            return []
    
    @staticmethod
    def deal_cards(game_round, players, cards_per_player=8):
        """
        Dijeli karte igračima za novu rundu.
        
        Args:
            game_round: Instanca runde za koju se dijele karte
            players: Lista igrača kojima se dijele karte
            cards_per_player: Broj karata po igraču (default: 8)
            
        Returns:
            dict: Karte podijeljene po igračima (id_igrača -> lista karti)
        """
        try:
            # Stvori i promiješaj špil
            deck = CardService.shuffle_deck()
            if not deck:
                logger.error("Nije moguće stvoriti špil karata")
                return {}
            
            # Provjeri broj igrača
            if not players or len(players) != 4:
                logger.error(f"Nevažeći broj igrača za dijeljenje karata: {len(players) if players else 0}")
                return {}
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Podijeli svakom igraču određeni broj karata
                player_cards = {}
                
                for i, player in enumerate(players):
                    start_idx = i * cards_per_player
                    end_idx = start_idx + cards_per_player
                    player_deck = deck[start_idx:end_idx]
                    
                    # Spremi karte u bazu
                    for card in player_deck:
                        MoveRepository.add_card_to_player(game_round, player, card)
                    
                    # Spremi za povratak
                    player_cards[str(player.id)] = [card.get_code() for card in player_deck]
                
                return player_cards
                
        except Exception as e:
            logger.error(f"Greška pri dijeljenju karata: {e}", exc_info=True)
            return {}
    
    @staticmethod
    def get_player_cards(game_round, player):
        """
        Dohvaća karte koje igrač ima u ruci.
        
        Args:
            game_round: Instanca runde
            player: Igrač čije karte se dohvaćaju
            
        Returns:
            list: Lista karata koje igrač ima u ruci
        """
        try:
            return MoveRepository.get_player_cards(game_round, player)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju karata igrača {player.id}: {e}", exc_info=True)
            return []
    
    @staticmethod
    def remove_card_from_player(game_round, player, card):
        """
        Uklanja kartu iz ruke igrača.
        
        Args:
            game_round: Instanca runde
            player: Igrač od kojeg se uklanja karta
            card: Karta koja se uklanja
            
        Returns:
            bool: True ako je karta uspješno uklonjena, False inače
        """
        try:
            return MoveRepository.remove_card_from_player(game_round, player, card)
        except Exception as e:
            logger.error(f"Greška pri uklanjanju karte {card.get_code()} od igrača {player.id}: {e}", exc_info=True)
            return False
    
    @staticmethod
    @lru_cache(maxsize=128)
    def is_valid_move(card, player_cards, trick_cards, trump_suit=None, must_follow_suit=True):
        """
        Provjerava je li potez valjan prema pravilima belota.
        
        Args:
            card: Karta koja se igra
            player_cards: Karte koje igrač ima u ruci
            trick_cards: Karte već odigrane u trenutnom štihu
            trump_suit: Adutska boja
            must_follow_suit: Treba li pratiti boju (True po defaultu)
            
        Returns:
            tuple: (je_valjan, poruka_o_pogrešci)
        """
        try:
            # Provjeri je li karta string i pretvori je u objekt Card ako jest
            if isinstance(card, str):
                try:
                    card = Card.from_code(card)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return False, f"Nevažeći kod karte: {str(e)}"
            
            # Provjeri je li potez karta koju igrač ima
            if card.get_code() not in [c.get_code() if isinstance(c, Card) else c for c in player_cards]:
                return False, "Igrač nema tu kartu u ruci"
                
            # Ako je prvi potez u štihu, sve karte su valjane
            if not trick_cards:
                return True, ""
                
            # Dohvati boju prvog poteza
            first_card = trick_cards[0]
            if isinstance(first_card, str):
                try:
                    first_card = Card.from_code(first_card)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return False, f"Nevažeći kod karte: {str(e)}"
            elif isinstance(first_card, dict) and 'card' in first_card:
                try:
                    first_card = Card.from_code(first_card['card'])
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return False, f"Nevažeći kod karte: {str(e)}"
            
            lead_suit = first_card.suit
            
            # Ako igrač prati boju, potez je valjan
            if card.suit == lead_suit:
                return True, ""
                
            # Ako igrač ne mora pratiti boju, potez je valjan
            if not must_follow_suit:
                return True, ""
                
            # Provjeri ima li igrač karte u boji prvog poteza
            has_lead_suit = any(
                (c.suit == lead_suit if isinstance(c, Card) else Card.from_code(c).suit == lead_suit)
                for c in player_cards
            )
            
            # Ako igrač ima karte u boji prvog poteza, mora ih igrati
            if has_lead_suit:
                return False, "Igrač mora pratiti boju prvog poteza"
                
            # Ako igrač nema karte u boji prvog poteza, može igrati bilo koju kartu
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška pri provjeri valjanosti poteza: {e}", exc_info=True)
            return False, f"Greška pri provjeri valjanosti poteza: {str(e)}"
    
    @staticmethod
    @lru_cache(maxsize=128)
    def calculate_trick_winner(trick_cards, trump_suit=None):
        """
        Određuje pobjednika štiha na temelju odigranih karata.
        
        Args:
            trick_cards: Lista karata u štihu
            trump_suit: Adutska boja
            
        Returns:
            dict: Informacije o pobjedničkoj karti i igraču
        """
        try:
            if not trick_cards or len(trick_cards) == 0:
                logger.error("Pokušaj određivanja pobjednika štiha bez karata")
                return None
                
            # Provjeri jesu li karte u formatu objekta, stringa ili rječnika
            is_dict_format = isinstance(trick_cards[0], dict)
            
            # Dohvati prvu kartu
            first_card_data = trick_cards[0]
            if is_dict_format:
                first_card_code = first_card_data.get('card')
                first_player = first_card_data.get('player')
            else:
                first_card_code = first_card_data
                first_player = None
            
            # Pretvori kod karte u objekt Card
            try:
                first_card = Card.from_code(first_card_code) if isinstance(first_card_code, str) else first_card_code
            except ValueError as e:
                logger.error(f"Nevažeći kod karte: {e}")
                return None
            
            # Odredi boju prvog poteza
            lead_suit = first_card.suit
            
            # Inicijaliziraj pobjedničku kartu kao prvu kartu
            winning_card = first_card
            winning_card_data = first_card_data
            
            # Prođi kroz ostale karte i pronađi pobjednika
            for card_data in trick_cards[1:]:
                if is_dict_format:
                    card_code = card_data.get('card')
                else:
                    card_code = card_data
                
                # Pretvori kod karte u objekt Card
                try:
                    card = Card.from_code(card_code) if isinstance(card_code, str) else card_code
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    continue
                
                # Usporedi karte prema pravilima belota
                if CardService._is_card_stronger(card, winning_card, lead_suit, trump_suit):
                    winning_card = card
                    winning_card_data = card_data
            
            # Vrati informacije o pobjedničkoj karti
            if is_dict_format:
                return {
                    'card': winning_card,
                    'card_code': winning_card.get_code(),
                    'player': winning_card_data.get('player'),
                    'index': trick_cards.index(winning_card_data)
                }
            else:
                return {
                    'card': winning_card,
                    'card_code': winning_card.get_code(),
                    'index': trick_cards.index(winning_card_data)
                }
                
        except Exception as e:
            logger.error(f"Greška pri određivanju pobjednika štiha: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _is_card_stronger(card1, card2, lead_suit, trump_suit=None):
        """
        Uspoređuje dvije karte i određuje je li prva karta jača od druge.
        
        Args:
            card1: Prva karta (Card objekt)
            card2: Druga karta (Card objekt)
            lead_suit: Boja prvog poteza u štihu
            trump_suit: Adutska boja (opcionalno)
            
        Returns:
            bool: True ako je prva karta jača, False inače
        """
        try:
            # Ako su obje karte aduti, usporedi ih prema vrijednosti aduta
            if trump_suit and card1.is_trump(trump_suit) and card2.is_trump(trump_suit):
                return CardService._get_trump_card_strength(card1) > CardService._get_trump_card_strength(card2)
                
            # Ako je samo prva karta adut, ona je jača
            if trump_suit and card1.is_trump(trump_suit) and not card2.is_trump(trump_suit):
                return True
                
            # Ako je samo druga karta adut, ona je jača
            if trump_suit and not card1.is_trump(trump_suit) and card2.is_trump(trump_suit):
                return False
                
            # Ako nijedna karta nije adut, usporedi ih prema boji prvog poteza
            if card1.suit == lead_suit and card2.suit != lead_suit:
                return True
                
            if card1.suit != lead_suit and card2.suit == lead_suit:
                return False
                
            # Ako su obje karte iste boje (i to nije adut), usporedi ih prema vrijednosti
            if card1.suit == card2.suit:
                if card1.suit == lead_suit:
                    return CardService._get_card_strength(card1) > CardService._get_card_strength(card2)
                else:
                    # Ako nijedna karta nije boje prvog poteza niti adut, pobjeđuje prva odigrana
                    return False
                    
            # Ako su različite boje i nijedna nije adut niti boja prvog poteza, pobjeđuje prva odigrana
            return False
            
        except Exception as e:
            logger.error(f"Greška pri usporedbi karata: {e}", exc_info=True)
            return False
    
    @staticmethod
    @lru_cache(maxsize=32)
    def _get_card_strength(card):
        """
        Vraća relativnu snagu karte u neadutskoj boji.
        
        Args:
            card: Karta (Card objekt)
            
        Returns:
            int: Relativna snaga karte (veći broj znači jača karta)
        """
        strength_map = {
            '7': 1,
            '8': 2,
            '9': 3,
            'J': 4,
            'Q': 5,
            'K': 6,
            '10': 7,
            'A': 8
        }
        return strength_map.get(card.value, 0)
    
    @staticmethod
    @lru_cache(maxsize=32)
    def _get_trump_card_strength(card):
        """
        Vraća relativnu snagu karte u adutskoj boji.
        
        Args:
            card: Karta (Card objekt)
            
        Returns:
            int: Relativna snaga karte u adutu (veći broj znači jača karta)
        """
        strength_map = {
            '7': 1,
            '8': 2,
            'Q': 3,
            'K': 4,
            '10': 5,
            'A': 6,
            '9': 7,
            'J': 8
        }
        return strength_map.get(card.value, 0)
    
    @staticmethod
    def validate_declaration(declaration_type, cards, round_obj=None):
        """
        Provjerava je li zvanje valjano prema pravilima Belota.
        
        Args:
            declaration_type: Tip zvanja (npr. 'belot', 'four_jacks', 'sequence_3')
            cards: Lista karata koje čine zvanje
            round_obj: Opcionalno, objekt runde za dodatnu validaciju
            
        Returns:
            tuple: (je_valjano, poruka_o_pogrešci)
        """
        try:
            from game.services.scoring_service import ScoringService
            return ScoringService.validate_declaration(declaration_type, cards, round_obj)
        except Exception as e:
            logger.error(f"Greška pri validaciji zvanja: {e}", exc_info=True)
            return False, f"Greška pri validaciji zvanja: {str(e)}" 