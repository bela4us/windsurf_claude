"""
Servis za upravljanje igrom belota.

Ovaj modul implementira servisni sloj za operacije vezane uz igru,
odvajajući poslovnu logiku od ostalih komponenti aplikacije i pružajući
jedinstveno sučelje za repository i API/consumer komponente.
"""

import logging
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from game.models import Game, Round, Move, Declaration
from game.repositories.game_repository import GameRepository
from game.repositories.move_repository import MoveRepository
from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring

# Inicijalizacija loggera
logger = logging.getLogger('game.services')
User = get_user_model()

class GameService:
    """
    Servisni sloj za Belot igru koji enkapsulira poslovnu logiku igre.
    
    Pruža metode za upravljanje stanjem igre, obradu poteza i
    implementaciju pravila igre. Koristi repository sloj za pristup podacima.
    """
    
    def __init__(self, game_id=None, room_code=None):
        """
        Inicijalizira GameService za određenu igru.
        
        Args:
            game_id: ID igre ako je poznato
            room_code: Kod sobe ako se igra dohvaća prema kodu
        """
        self.game_id = game_id
        self.room_code = room_code
        self.rules = Rules()
        self.scoring = Scoring()
    
    def get_game(self, check_exists=True):
        """
        Dohvaća instancu igre prema ID-u ili kodu sobe.
        
        Args:
            check_exists: Ako je True, baca iznimku ako igra ne postoji
            
        Returns:
            Game: Instanca igre ili None ako ne postoji
        """
        if self.game_id:
            return GameRepository.get_by_id(self.game_id)
        elif self.room_code:
            try:
                return Game.objects.get(room_code=self.room_code)
            except Game.DoesNotExist:
                if check_exists:
                    raise ValueError(f"Igra s kodom {self.room_code} ne postoji")
                return None
        if check_exists:
            raise ValueError("Nije naveden ID igre ili kod sobe")
        return None
    
    def create_game(self, creator_id, is_private=False, points_to_win=1001):
        """
        Stvara novu igru.
        
        Args:
            creator_id: ID korisnika koji stvara igru
            is_private: Označava je li igra privatna
            points_to_win: Broj bodova potrebnih za pobjedu
            
        Returns:
            dict: Rezultat s ID-om stvorene igre i ostalim podacima
        """
        try:
            creator = User.objects.get(id=creator_id)
            
            # Stvaranje igre
            game = GameRepository.create_game(
                creator=creator, 
                private=is_private, 
                points_to_win=points_to_win
            )
            self.game_id = str(game.id)
            
            return {
                'valid': True,
                'game_id': str(game.id),
                'room_code': game.room_code
            }
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri stvaranju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri stvaranju igre: {str(e)}"}
    
    def join_game(self, user_id, room_code=None):
        """
        Pridružuje korisnika igri.
        
        Args:
            user_id: ID korisnika koji se pridružuje
            room_code: Kod sobe (opcija) ako nije prethodno postavljen
            
        Returns:
            dict: Rezultat s podacima o igri i pozicijom igrača
        """
        try:
            # Ako je naveden novi kod sobe, postavi ga
            if room_code:
                self.room_code = room_code
            
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Provjeri je li već član igre
            if game.players.filter(id=user_id).exists():
                return {
                    'valid': True,
                    'message': 'Već ste član ove igre',
                    'game_id': str(game.id),
                    'status': game.status
                }
            
            # Provjeri može li se pridružiti
            if game.status != 'waiting' or game.players.count() >= 4:
                return {
                    'valid': False,
                    'message': 'Nije moguće pridružiti se igri'
                }
            
            # Dodaj igrača
            GameRepository.add_player_to_game(game, user)
            
            # Označi ga kao aktivnog
            game.active_players.add(user)
            
            # Ako je igra puna, automatski dodijeli timove ako već nisu dodijeljeni
            if game.players.count() == 4 and (game.team_a_players.count() == 0 or game.team_b_players.count() == 0):
                game.assign_teams()
            
            return {
                'valid': True, 
                'game_id': str(game.id),
                'room_code': game.room_code,
                'status': game.status,
                'player_count': game.players.count()
            }
            
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri pridruživanju igri: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri pridruživanju igri: {str(e)}"}
    
    def leave_game(self, user_id, reason="voluntary"):
        """
        Uklanja korisnika iz igre.
        
        Args:
            user_id: ID korisnika koji napušta igru
            reason: Razlog napuštanja (voluntary/inactivity/disconnected)
            
        Returns:
            dict: Rezultat s podacima o igri nakon napuštanja
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Provjeri je li član igre
            if not game.players.filter(id=user_id).exists():
                return {
                    'valid': False,
                    'message': 'Niste član ove igre'
                }
            
            # Ako je igra u tijeku, to je predaja i rezultira pobjedom drugog tima
            if game.status == 'in_progress':
                # Odredi tim igrača koji napušta
                player_team = None
                if user in game.team_a_players.all():
                    player_team = 'a'
                    # Tim B pobjeđuje
                    game.winner_team = 'b'
                elif user in game.team_b_players.all():
                    player_team = 'b'
                    # Tim A pobjeđuje
                    game.winner_team = 'a'
                
                game.status = 'completed'
                game.ended_at = timezone.now()
                game.save()
                
                return {
                    'valid': True,
                    'game_status': 'completed',
                    'winner_team': game.winner_team,
                    'reason': reason
                }
            
            # Ako igra nije u tijeku, samo ukloni igrača
            GameRepository.remove_player_from_game(game, user)
            
            # Označi ga kao neaktivnog
            game.active_players.remove(user)
            
            # Ako je kreator napustio igru, a nitko nije ostao, izbriši igru
            if user == game.creator and game.players.count() == 0:
                GameRepository.delete_game(game)
                return {
                    'valid': True, 
                    'game_status': 'deleted',
                    'reason': reason
                }
            # Ako je kreator napustio igru, a ima još igrača, prebaci vlasništvo
            elif user == game.creator and game.players.count() > 0:
                game.creator = game.players.first()
                game.save()
            
            return {
                'valid': True, 
                'game_status': game.status,
                'reason': reason
            }
            
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri napuštanju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri napuštanju igre: {str(e)}"}
    
    def start_game(self, user_id):
        """
        Pokreće igru.
        
        Args:
            user_id: ID korisnika koji pokreće igru
            
        Returns:
            dict: Rezultat s podacima o pokrenutoj igri
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Provjeri je li kreator igre
            if user != game.creator:
                return {
                    'valid': False,
                    'message': 'Samo kreator igre može pokrenuti igru'
                }
            
            # Provjeri može li se igra pokrenuti
            if game.status != 'waiting' or game.players.count() != 4:
                return {
                    'valid': False,
                    'message': 'Nije moguće pokrenuti igru'
                }
            
            with transaction.atomic():
                # Pokreni igru
                GameRepository.start_game(game)
                
                # Dohvati trenutnu rundu
                current_round = GameRepository.get_current_round(game)
                
                # Podijeli karte
                self._deal_cards(current_round)
                
                dealer = current_round.dealer
                
                # Odredi prvog igrača za zvanje aduta (nakon djelitelja)
                players = list(game.players.all())
                dealer_index = players.index(dealer)
                first_bidder_index = (dealer_index + 1) % 4
                first_bidder = players[first_bidder_index]
                
                current_round.current_player = first_bidder
                current_round.save()
                
                # Pripremi karte za svakog igrača
                player_cards = {}
                for player in players:
                    cards = MoveRepository.get_player_cards(current_round, player)
                    player_cards[str(player.id)] = [card.get_code() for card in cards]
                
                return {
                    'valid': True,
                    'dealer': {
                        'id': str(dealer.id),
                        'username': dealer.username
                    },
                    'next_player': {
                        'id': str(first_bidder.id),
                        'username': first_bidder.username
                    },
                    'player_cards': player_cards,
                    'round_number': current_round.round_number
                }
                
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri pokretanju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri pokretanju igre: {str(e)}"}
    
    def mark_player_ready(self, user_id):
        """
        Označava igrača kao spremnog za početak igre.
        
        Args:
            user_id: ID korisnika koji se označava kao spreman
            
        Returns:
            dict: Rezultat s podacima o spremnosti svih igrača
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Provjeri je li član igre
            if not game.players.filter(id=user_id).exists():
                return {
                    'valid': False,
                    'message': 'Niste član ove igre'
                }
            
            # Provjeri je li igra u statusu čekanja
            if game.status != 'waiting':
                return {
                    'valid': False,
                    'message': 'Igra nije u statusu čekanja'
                }
            
            # Označi igrača kao spremnog
            game.ready_players.add(user)
            
            # Provjeri jesu li svi igrači spremni
            all_ready = game.ready_players.count() == game.players.count()
            
            # Ako su svi spremni, automatski pokreni igru
            if all_ready and game.players.count() == 4:
                return self.start_game(game.creator.id)
            
            return {
                'valid': True,
                'all_ready': all_ready,
                'ready_count': game.ready_players.count(),
                'player_count': game.players.count()
            }
            
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri označavanju spremnosti: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri označavanju spremnosti: {str(e)}"}
    
    def process_move(self, user_id, card):
        """
        Obrađuje potez igrača (igranje karte).
        
        Args:
            user_id: ID korisnika koji igra potez
            card: Instanca Card ili string kod karte
            
        Returns:
            dict: Rezultat s podacima o potrezu i sljedećem igraču
        """
        try:
            # Pretvori string kod karte u Card instancu ako je potrebno
            if isinstance(card, str):
                card = Card.from_code(card)
            
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li igrač na potezu
            if current_round.current_player != user:
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za potez'
                }
            
            # Provjeri je li status runde 'playing'
            if current_round.status != 'playing':
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi igranja'
                }
            
            # Dohvati igračeve karte
            player_cards = MoveRepository.get_player_cards(current_round, user)
            
            # Provjeri ima li igrač tu kartu
            if not any(c.get_code() == card.get_code() for c in player_cards):
                return {
                    'valid': False,
                    'message': 'Nemaš tu kartu u ruci'
                }
            
            # Dohvati trenutni štih
            current_trick_cards = current_round.current_trick_cards or []
            trick_cards = [
                Card.from_code(trick_card['card']) for trick_card in current_trick_cards
            ]
            
            # Provjeri je li potez valjan prema pravilima
            if not self.rules.validate_move(card, player_cards, trick_cards, current_round.trump_suit):
                return {
                    'valid': False,
                    'message': 'Nevažeći potez prema pravilima igre'
                }
            
            with transaction.atomic():
                # Izračunaj trenutni broj štiha i redoslijed poteza unutar štiha
                trick_number = current_round.trick_number or 0
                trick_move_count = len(current_trick_cards)
                
                # Ako je prvi potez u novom štihu, povećaj broj štiha
                if trick_move_count == 0:
                    trick_number += 1
                
                # Stvori novi potez
                move = Move.objects.create(
                    round=current_round,
                    player=user,
                    card_code=card.get_code(),
                    trick_number=trick_number,
                    order=trick_move_count + 1,
                    is_winning_card=False  # Postavit će se kasnije ako je pobjednički
                )
                
                # Dodaj kartu u trenutni štih
                current_trick_cards.append({
                    'player': str(user.id),
                    'card': card.get_code(),
                    'username': user.username
                })
                
                # Ažuriraj rundu s novim štihom
                current_round.current_trick_cards = current_trick_cards
                current_round.trick_number = trick_number
                
                # Rezultat poteza
                result = {
                    'valid': True,
                    'card': card.get_code(),
                    'trick_number': trick_number,
                    'trick_completed': False,
                    'round_completed': False,
                    'game_completed': False
                }
                
                # Ako je štih završen (4 karte odigrane)
                if len(current_trick_cards) == 4:
                    result['trick_completed'] = True
                    
                    # Odredi pobjednika štiha
                    led_suit = Card.from_code(current_trick_cards[0]['card']).suit
                    
                    # Pripremi podatke za određivanje pobjednika
                    trick = [
                        {'player': i, 'card': Card.from_code(card_data['card'])}
                        for i, card_data in enumerate(current_trick_cards)
                    ]
                    
                    winner_index = self.rules.determine_trick_winner(trick, current_round.trump_suit, led_suit)
                    winning_player_id = current_trick_cards[winner_index]['player']
                    winning_player = User.objects.get(id=winning_player_id)
                    
                    # Označi pobjednički potez
                    winning_move = Move.objects.get(
                        round=current_round,
                        player__id=winning_player_id,
                        trick_number=trick_number
                    )
                    winning_move.is_winning_card = True
                    winning_move.save()
                    
                    # Dodaj podatke o pobjedniku u rezultat
                    result['trick_winner'] = {
                        'id': winning_player_id,
                        'username': winning_player.username
                    }
                    
                    # Sljedeći igrač je pobjednik štiha
                    current_round.current_player = winning_player
                    
                    # Očisti trenutni štih
                    current_round.current_trick_cards = []
                    
                    # Provjeri je li runda završena (odigrano 8 štihova)
                    if trick_number == 8:
                        result['round_completed'] = True
                        
                        # Izračunaj rezultat runde
                        round_result = self._calculate_round_result(current_round)
                        result['round_results'] = round_result
                        
                        # Ažuriraj bodove igre
                        game.team_a_score += round_result['team_a_points']
                        game.team_b_score += round_result['team_b_points']
                        game.save()
                        
                        # Provjeri je li igra završena
                        if game.team_a_score >= game.points_to_win or game.team_b_score >= game.points_to_win:
                            result['game_completed'] = True
                            
                            # Odredi pobjednika
                            if game.team_a_score >= game.points_to_win:
                                game.winner_team = 'a'
                            else:
                                game.winner_team = 'b'
                            
                            game.status = 'completed'
                            game.ended_at = timezone.now()
                            game.save()
                            
                            result['game_results'] = {
                                'winner_team': game.winner_team,
                                'team_a_score': game.team_a_score,
                                'team_b_score': game.team_b_score
                            }
                        else:
                            # Stvori novu rundu
                            new_dealer = self._get_next_dealer(current_round.dealer, game)
                            new_round = Round.objects.create(
                                game=game,
                                round_number=current_round.round_number + 1,
                                dealer=new_dealer,
                                status='dealing'
                            )
                            
                            # Podijeli karte za novu rundu
                            self._deal_cards(new_round)
                            
                            # Odredi prvog igrača za zvanje aduta (nakon djelitelja)
                            players = list(game.players.all())
                            dealer_index = players.index(new_dealer)
                            first_bidder_index = (dealer_index + 1) % 4
                            first_bidder = players[first_bidder_index]
                            
                            new_round.current_player = first_bidder
                            new_round.status = 'bidding'
                            new_round.save()
                            
                            result['next_round'] = {
                                'number': new_round.round_number,
                                'dealer': {
                                    'id': str(new_dealer.id),
                                    'username': new_dealer.username
                                },
                                'next_player': {
                                    'id': str(first_bidder.id),
                                    'username': first_bidder.username
                                }
                            }
                        
                        # Završi trenutnu rundu
                        current_round.status = 'completed'
                        current_round.completed_at = timezone.now()
                    
                else:
                    # Odredi sljedećeg igrača
                    players = list(game.players.all())
                    current_index = players.index(user)
                    next_index = (current_index + 1) % 4
                    next_player = players[next_index]
                    
                    current_round.current_player = next_player
                    
                    result['next_player'] = {
                        'id': str(next_player.id),
                        'username': next_player.username
                    }
                
                # Spremi promjene na rundi
                current_round.save()
                
                return result
                
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri obradi poteza: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri obradi poteza: {str(e)}"}
    
    def process_trump_call(self, user_id, suit):
        """
        Obrađuje zvanje aduta.
        
        Args:
            user_id: ID korisnika koji zove aduta
            suit: Boja aduta ('S', 'H', 'D', 'C')
            
        Returns:
            dict: Rezultat s podacima o zvanom adutu i sljedećem igraču
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li igrač na potezu
            if current_round.current_player != user:
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za zvanje aduta'
                }
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi zvanja aduta'
                }
            
            # Provjeri je li boja aduta valjana
            if suit not in ['S', 'H', 'D', 'C']:
                return {
                    'valid': False,
                    'message': 'Nevažeća boja aduta'
                }
            
            with transaction.atomic():
                # Postavi adut i status
                current_round.trump_suit = suit
                current_round.caller = user
                current_round.status = 'playing'
                
                # Odredi tim koji je zvao adut
                calling_team = 'a' if user in game.team_a_players.all() else 'b'
                current_round.calling_team = calling_team
                
                # Prvi igrač nakon djelitelja započinje igru
                players = list(game.players.all())
                dealer_index = players.index(current_round.dealer)
                first_player_index = (dealer_index + 1) % 4
                first_player = players[first_player_index]
                
                current_round.current_player = first_player
                current_round.save()
                
                # Pripremi karte za svakog igrača (možda ima novih)
                player_cards = {}
                for player in players:
                    cards = MoveRepository.get_player_cards(current_round, player)
                    player_cards[str(player.id)] = [card.get_code() for card in cards]
                
                return {
                    'valid': True,
                    'suit': suit,
                    'calling_team': calling_team,
                    'caller': {
                        'id': str(user.id),
                        'username': user.username
                    },
                    'round_number': current_round.round_number,
                    'next_player': {
                        'id': str(first_player.id),
                        'username': first_player.username
                    },
                    'player_cards': player_cards
                }
                
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri zvanju aduta: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri zvanju aduta: {str(e)}"}
    
    def process_trump_pass(self, user_id):
        """
        Obrađuje propuštanje zvanja aduta.
        
        Args:
            user_id: ID korisnika koji propušta zvanje
            
        Returns:
            dict: Rezultat s podacima o sljedećem igraču za zvanje
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li igrač na potezu
            if current_round.current_player != user:
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za zvanje aduta'
                }
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi zvanja aduta'
                }
            
            with transaction.atomic():
                # Odredi sljedećeg igrača
                players = list(game.players.all())
                current_index = players.index(user)
                next_index = (current_index + 1) % 4
                next_player = players[next_index]
                
                # Označi da je korisnik propustio zvanje
                if not hasattr(current_round, 'passed_players'):
                    current_round.passed_players = []
                
                passed_players = current_round.passed_players or []
                passed_players.append(str(user.id))
                current_round.passed_players = passed_players
                
                # Provjeri je li ovaj igrač zadnji koji može zvati
                dealer = current_round.dealer
                dealer_index = players.index(dealer)
                last_bidder_index = (dealer_index + 3) % 4  # 3 mjesta od dealera u smjeru zvanja
                must_call = (current_index == last_bidder_index)
                
                # Ako su svi propustili zvanje i dosli do zadnjeg koji mora zvati
                if must_call:
                    return {
                        'valid': False,
                        'message': 'Moraš zvati aduta, ne možeš reći dalje'
                    }
                
                # Postavi sljedećeg igrača
                current_round.current_player = next_player
                current_round.save()
                
                # Provjeri je li sljedeći igrač mora zvati
                next_must_call = False
                if next_index == (dealer_index + 3) % 4 and len(passed_players) == 3:
                    next_must_call = True
                
                return {
                    'valid': True,
                    'next_player': {
                        'id': str(next_player.id),
                        'username': next_player.username
                    },
                    'must_call': next_must_call
                }
                
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri propuštanju aduta: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri propuštanju aduta: {str(e)}"}
    
    def process_declaration(self, user_id, declaration_type, cards):
        """
        Obrađuje zvanje (niz, 4 dečka, itd.).
        
        Args:
            user_id: ID korisnika koji prijavljuje zvanje
            declaration_type: Tip zvanja
            cards: Lista kodova karata koje čine zvanje
            
        Returns:
            dict: Rezultat s podacima o zvanju
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li status runde 'playing'
            if current_round.status != 'playing':
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi igranja'
                }
            
            # Dohvati igračeve karte
            player_cards = MoveRepository.get_player_cards(current_round, user)
            player_card_codes = [card.get_code() for card in player_cards]
            
            # Provjeri ima li igrač sve karte koje prijavljuje
            for card_code in cards:
                if card_code not in player_card_codes:
                    return {
                        'valid': False,
                        'message': f'Nemaš kartu {card_code} u ruci'
                    }
            
            # Provjeri je li zvanje valjano prema pravilima
            card_objs = [Card.from_code(code) for code in cards]
            if declaration_type == 'four_of_kind':
                # Provjeri jesu li 4 karte istog ranga
                ranks = [card.rank for card in card_objs]
                if len(set(ranks)) != 1:
                    return {
                        'valid': False,
                        'message': 'Karte moraju biti istog ranga za četverku'
                    }
                
                # Odredi vrijednost zvanja
                rank = ranks[0]
                if rank == 'J':
                    value = 200
                    declaration_type = 'four_jacks'
                elif rank == '9':
                    value = 150
                    declaration_type = 'four_nines'
                elif rank == 'A':
                    value = 100
                    declaration_type = 'four_aces'
                elif rank == 'K':
                    value = 100
                    declaration_type = 'four_kings'
                elif rank == 'Q':
                    value = 100
                    declaration_type = 'four_queens'
                else:
                    return {
                        'valid': False,
                        'message': f'Nevažeće zvanje četvorke ranga {rank}'
                    }
                
            elif declaration_type.startswith('sequence_'):
                # Provjeri je li niz valjan
                try:
                    seq_length = int(declaration_type.split('_')[1])
                    
                    if len(cards) != seq_length:
                        return {
                            'valid': False,
                            'message': f'Niz mora imati točno {seq_length} karata'
                        }
                    
                    # Provjeri jesu li sve karte iste boje
                    suits = set(card.suit for card in card_objs)
                    if len(suits) != 1:
                        return {
                            'valid': False,
                            'message': 'Sve karte u nizu moraju biti iste boje'
                        }
                    
                    # Sortiraj karte po rangu
                    sorted_cards = sorted(card_objs, key=lambda c: Card.RANKS.index(c.rank))
                    
                    # Provjeri je li sekvenca
                    for i in range(1, len(sorted_cards)):
                        if Card.RANKS.index(sorted_cards[i].rank) != Card.RANKS.index(sorted_cards[i-1].rank) + 1:
                            return {
                                'valid': False,
                                'message': 'Karte moraju biti u nizu'
                            }
                    
                    # Odredi vrijednost zvanja
                    if seq_length == 3:
                        value = 20
                    elif seq_length == 4:
                        value = 50
                    elif seq_length >= 5:
                        value = 100
                    else:
                        return {
                            'valid': False,
                            'message': f'Nevažeća duljina niza: {seq_length}'
                        }
                    
                    # Ako je niz 8 karata, to je belot
                    if seq_length == 8:
                        value = 1001  # Odmah pobjeđuje
                        declaration_type = 'belot'
                        
                except ValueError:
                    return {
                        'valid': False,
                        'message': 'Nevažeći format zvanja niza'
                    }
            else:
                return {
                    'valid': False,
                    'message': f'Nevažeći tip zvanja: {declaration_type}'
                }
            
            # Stvori zvanje
            declaration = Declaration.objects.create(
                round=current_round,
                player=user,
                declaration_type=declaration_type,
                value=value,
                cards_json=cards
            )
            
            # Vrati rezultat
            return {
                'valid': True,
                'declaration_id': str(declaration.id),
                'declaration_type': declaration_type,
                'value': value,
                'cards': cards
            }
            
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri prijavi zvanja: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri prijavi zvanja: {str(e)}"}
    
    def process_bela(self, user_id):
        """
        Obrađuje zvanje bele (kralj i dama u adutu).
        
        Args:
            user_id: ID korisnika koji prijavljuje belu
            
        Returns:
            dict: Rezultat s podacima o zvanju bele
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li status runde 'playing'
            if current_round.status != 'playing':
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi igranja'
                }
            
            # Provjeri postoji li adut
            if not current_round.trump_suit:
                return {
                    'valid': False,
                    'message': 'Adut nije određen'
                }
            
            # Dohvati igračeve karte
            player_cards = MoveRepository.get_player_cards(current_round, user)
            
            # Provjeri ima li igrač kralja i damu u adutu
            suit = current_round.trump_suit
            king = next((card for card in player_cards if card.rank == 'K' and card.suit == suit), None)
            queen = next((card for card in player_cards if card.rank == 'Q' and card.suit == suit), None)
            
            if not king or not queen:
                return {
                    'valid': False,
                    'message': 'Nemaš kralja i damu u adutu'
                }
            
            # Stvori zvanje
            declaration = Declaration.objects.create(
                round=current_round,
                player=user,
                declaration_type='belot',
                value=20,
                cards_json=[king.get_code(), queen.get_code()]
            )
            
            # Vrati rezultat
            return {
                'valid': True,
                'declaration_id': str(declaration.id),
                'declaration_type': 'belot',
                'value': 20,
                'suit': suit,
                'cards': [king.get_code(), queen.get_code()]
            }
            
        except User.DoesNotExist:
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri prijavi bele: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri prijavi bele: {str(e)}"}
    
    def is_player_turn(self, user_id):
        """
        Provjerava je li igrač na potezu.
        
        Args:
            user_id: ID korisnika
            
        Returns:
            bool: True ako je igrač na potezu, inače False
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return False
            
            # Provjeri je li igrač na potezu
            return current_round.current_player_id == user_id
            
        except Exception:
            return False
    
    def can_call_trump(self, user_id):
        """
        Provjerava može li igrač zvati aduta.
        
        Args:
            user_id: ID korisnika
            
        Returns:
            bool: True ako igrač može zvati aduta, inače False
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                return False
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                return False
            
            # Provjeri je li igrač na potezu
            return current_round.current_player_id == user_id
            
        except Exception:
            return False
    
    def can_start_game(self, user_id):
        """
        Provjerava može li igrač pokrenuti igru.
        
        Args:
            user_id: ID korisnika
            
        Returns:
            bool: True ako igrač može pokrenuti igru, inače False
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Provjeri je li kreator igre
            if game.creator_id != user_id:
                return False
            
            # Provjeri je li status igre 'waiting'
            if game.status != 'waiting':
                return False
            
            # Provjeri ima li dovoljno igrača
            return game.players.count() == 4
            
        except Exception:
            return False
    
    def get_game_state(self, user_id):
        """
        Dohvaća trenutno stanje igre za specifičnog igrača.
        
        Args:
            user_id: ID korisnika za kojeg se dohvaća stanje
            
        Returns:
            dict: Stanje igre prilagođeno za igrača
        """
        try:
            # Dohvati igru
            game = self.get_game()
            
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Provjeri je li korisnik član igre
            if not game.players.filter(id=user_id).exists():
                return {'error': 'Nisi član ove igre'}
            
            # Osnovni podaci o igri
            game_state = {
                'game_id': str(game.id),
                'status': game.status,
                'scores': {
                    'team_a': game.team_a_score,
                    'team_b': game.team_b_score
                },
                'created_at': game.created_at.isoformat(),
                'started_at': game.started_at.isoformat() if game.started_at else None,
                'finished_at': game.finished_at.isoformat() if game.finished_at else None
            }
            
            # Podaci o igračima
            players_data = []
            for player in game.players.all():
                is_active = player in game.active_players.all()
                is_ready = hasattr(game, 'ready_players') and player in game.ready_players.all()
                
                player_data = {
                    'id': str(player.id),
                    'username': player.username,
                    'is_active': is_active,
                    'is_ready': is_ready,
                    'is_you': player.id == user_id
                }
                players_data.append(player_data)
            
            game_state['players'] = players_data
            
            # Podaci o timovima
            teams = {}
            for player in game.team_a_players.all():
                teams[str(player.id)] = 'a'
            for player in game.team_b_players.all():
                teams[str(player.id)] = 'b'
            
            game_state['teams'] = teams
            game_state['your_team'] = teams.get(str(user_id))
            
            # Trenutna runda
            current_round = GameRepository.get_current_round(game)
            if current_round:
                round_data = {
                    'id': str(current_round.id),
                    'number': current_round.round_number,
                    'status': current_round.status,
                    'trump_suit': current_round.trump_suit,
                    'calling_team': current_round.calling_team,
                    'current_player': str(current_round.current_player_id) if current_round.current_player else None
                }
                
                game_state['round'] = round_data
                game_state['your_turn'] = current_round.current_player_id == user_id
                
                # Karte igrača
                user_cards = MoveRepository.get_player_cards(current_round, user)
                game_state['your_cards'] = [card.get_code() for card in user_cards]
                
                # Trenutni štih
                game_state['current_trick'] = current_round.current_trick_cards or []
                
                # Zvanja u rundi
                declarations = []
                for declaration in Declaration.objects.filter(round=current_round).order_by('-created_at'):
                    declaration_data = {
                        'id': str(declaration.id),
                        'player_id': str(declaration.player_id),
                        'player_username': declaration.player.username,
                        'type': declaration.declaration_type,
                        'value': declaration.value,
                        'cards': declaration.cards_json
                    }
                    declarations.append(declaration_data)
                
                game_state['declarations'] = declarations
                
                # Povijest poteza u rundi
                moves_history = []
                for move in Move.objects.filter(round=current_round).order_by('trick_number', 'order'):
                    move_data = {
                        'player_id': str(move.player_id),
                        'player_username': move.player.username,
                        'card': move.card_code,
                        'trick_number': move.trick_number,
                        'order': move.order,
                        'is_winning': move.is_winning_card
                    }
                    moves_history.append(move_data)
                
                game_state['history'] = moves_history
            else:
                game_state['round'] = None
                game_state['your_turn'] = False
                game_state['your_cards'] = []
                game_state['current_trick'] = []
                game_state['declarations'] = []
                game_state['history'] = []
            
            return game_state
            
        except User.DoesNotExist:
            return {'error': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju stanja igre: {str(e)}", exc_info=True)
            return {'error': f"Greška pri dohvaćanju stanja igre: {str(e)}"}
    
    # Pomoćne metode
    
    def _deal_cards(self, round_obj):
        """
        Dijeli karte za novu rundu.
        
        Args:
            round_obj: Runda za koju se dijele karte
        """
        # Stvori novi špil
        deck = Deck()
        deck.shuffle()
        
        # Dohvati igrače
        game = round_obj.game
        players = list(game.players.all())
        
        # Prilagodi redoslijed igrača tako da djelitelj bude zadnji
        dealer_index = players.index(round_obj.dealer)
        ordered_players = players[dealer_index+1:] + players[:dealer_index+1]
        
        # Podijeli karte
        hands = deck.deal(4)
        
        # Dodaj karte u repozitorij
        for i, player in enumerate(ordered_players):
            for card in hands[i]:
                # Pretpostavka da MoveRepository ima metodu store_card
                MoveRepository.store_card(round_obj, player, card)
    
    def _get_next_dealer(self, current_dealer, game):
        """
        Određuje sljedećeg djelitelja.
        
        Args:
            current_dealer: Trenutni djelitelj
            game: Instanca igre
            
        Returns:
            User: Sljedeći djelitelj
        """
        players = list(game.players.all())
        current_index = players.index(current_dealer)
        next_index = (current_index + 1) % 4
        return players[next_index]
    
    def _calculate_round_result(self, round_obj):
        """
        Izračunava rezultat runde.
        
        Args:
            round_obj: Runda za koju se računa rezultat
            
        Returns:
            dict: Rezultat runde s bodovima za oba tima
        """
        game = round_obj.game
        
        # Dohvati poteze i zvanja
        moves = Move.objects.filter(round=round_obj)
        declarations = Declaration.objects.filter(round=round_obj)
        
        # Grupiraj poteze po štihu
        tricks = {}
        for move in moves:
            trick_num = move.trick_number
            if trick_num not in tricks:
                tricks[trick_num] = []
            tricks[trick_num].append(move)
        
        # Izračunaj bodove za štihove
        team_a_trick_points = 0
        team_b_trick_points = 0
        
        for trick_num, trick_moves in tricks.items():
            # Odredi pobjednika štiha
            winning_move = next((move for move in trick_moves if move.is_winning_card), None)
            
            if winning_move:
                winning_player = winning_move.player
                winning_team = 'a' if winning_player in game.team_a_players.all() else 'b'
                
                # Izračunaj bodove za štih
                trick_points = sum(self._get_card_value(move.card_code, round_obj.trump_suit) for move in trick_moves)
                
                # Dodatni bodovi za zadnji štih
                if trick_num == 8:
                    trick_points += 10
                
                # Dodaj bodove pobjedničkom timu
                if winning_team == 'a':
                    team_a_trick_points += trick_points
                else:
                    team_b_trick_points += trick_points
        
        # Izračunaj bodove za zvanja
        team_a_declarations = []
        team_b_declarations = []
        
        for declaration in declarations:
            declaring_player = declaration.player
            declaring_team = 'a' if declaring_player in game.team_a_players.all() else 'b'
            
            if declaring_team == 'a':
                team_a_declarations.append(declaration)
            else:
                team_b_declarations.append(declaration)
        
        # Odredi koji tim ima prioritet za zvanja
        if team_a_declarations and team_b_declarations:
            max_team_a = max(team_a_declarations, key=lambda d: d.value)
            max_team_b = max(team_b_declarations, key=lambda d: d.value)
            
            if max_team_a.value > max_team_b.value:
                declaration_winner = 'a'
            elif max_team_b.value > max_team_a.value:
                declaration_winner = 'b'
            else:
                # Ako su jednake vrijednosti, prednost ima tim koji je bliži djelitelju
                # (Tim koji je zvao aduta ima prednost)
                declaration_winner = round_obj.calling_team
        elif team_a_declarations:
            declaration_winner = 'a'
        elif team_b_declarations:
            declaration_winner = 'b'
        else:
            declaration_winner = None
        
        # Izračunaj bodove za zvanja
        team_a_declaration_points = 0
        team_b_declaration_points = 0
        
        if declaration_winner == 'a':
            for declaration in team_a_declarations:
                team_a_declaration_points += declaration.value
        elif declaration_winner == 'b':
            for declaration in team_b_declarations:
                team_b_declaration_points += declaration.value
        
        # Izračunaj ukupne bodove
        team_a_total = team_a_trick_points + team_a_declaration_points
        team_b_total = team_b_trick_points + team_b_declaration_points
        
        # Odredi je li tim koji je zvao aduta prošao
        calling_team = round_obj.calling_team
        
        if calling_team == 'a':
            if team_a_total <= team_b_total:
                # Tim A je pao, svi bodovi idu timu B
                team_b_final = team_a_total + team_b_total
                team_a_final = 0
            else:
                # Tim A je prošao
                team_a_final = team_a_total
                team_b_final = team_b_total
        else:  # calling_team == 'b'
            if team_b_total <= team_a_total:
                # Tim B je pao, svi bodovi idu timu A
                team_a_final = team_a_total + team_b_total
                team_b_final = 0
            else:
                # Tim B je prošao
                team_a_final = team_a_total
                team_b_final = team_b_total
        
        # Ažuriraj bodove runde
        round_obj.team_a_score = team_a_final
        round_obj.team_b_score = team_b_final
        round_obj.save(update_fields=['team_a_score', 'team_b_score'])
        
        # Vrati detaljan rezultat
        return {
            'team_a_points': team_a_final,
            'team_b_points': team_b_final,
            'team_a_trick_points': team_a_trick_points,
            'team_b_trick_points': team_b_trick_points,
            'team_a_declaration_points': team_a_declaration_points,
            'team_b_declaration_points': team_b_declaration_points,
            'calling_team': calling_team,
            'declaration_winner': declaration_winner,
            'passed': (calling_team == 'a' and team_a_total > team_b_total) or
                     (calling_team == 'b' and team_b_total > team_a_total)
        }
    
    def _get_card_value(self, card_code, trump_suit):
        """
        Vraća vrijednost karte u bodovima.
        
        Args:
            card_code: Kod karte (npr. 'AH')
            trump_suit: Boja aduta
            
        Returns:
            int: Vrijednost karte u bodovima
        """
        card = Card.from_code(card_code)
        return card.get_value(trump_suit)