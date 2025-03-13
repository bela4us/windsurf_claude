"""
Repozitorij za Belot igru.

Ovaj modul implementira GameRepository klasu koja encapsulira svu logiku
za pristup i manipulaciju Game modelima. Repozitorij služi kao sloj
apstrakcije između modela podataka i poslovne logike, omogućujući
jednostavniji pristup i bolju organizaciju koda.
"""

import logging
import random
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Sum, F, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model

from game.models import Game, Round, Move

User = get_user_model()
logger = logging.getLogger('game.repositories')

class GameRepository:
    """
    Repozitorij za pristup i manipulaciju Game modelima.
    
    Ova klasa pruža metode za stvaranje, dohvaćanje, ažuriranje i brisanje
    igara, kao i za složenije operacije poput upravljanja igračima i timovima.
    """
    
    @staticmethod
    def get_by_id(game_id):
        """
        Dohvaća igru prema njenom ID-u.
        
        Args:
            game_id: UUID igre
            
        Returns:
            Game: Objekt igre ili None ako nije pronađena
        """
        try:
            return Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            logger.warning(f"Igra s ID-om {game_id} nije pronađena")
            return None
    
    @staticmethod
    def get_by_room_code(room_code):
        """
        Dohvaća igru prema kodu sobe.
        
        Args:
            room_code: Jedinstveni kod sobe za pridruživanje
            
        Returns:
            Game: Objekt igre ili None ako nije pronađena
        """
        try:
            return Game.objects.get(room_code=room_code)
        except Game.DoesNotExist:
            return None
    
    @staticmethod
    def get_active_games():
        """
        Dohvaća sve aktivne igre (one koje su u tijeku).
        
        Returns:
            QuerySet: Queryset s aktivnim igrama
        """
        return Game.objects.filter(status='in_progress')
    
    @staticmethod
    def get_waiting_games():
        """
        Dohvaća igre koje čekaju igrače ili su spremne za početak.
        
        Returns:
            QuerySet: Queryset s igrama koje čekaju
        """
        return Game.objects.filter(status__in=['waiting', 'ready'])
    
    @staticmethod
    def get_public_waiting_games():
        """
        Dohvaća javne igre koje čekaju igrače.
        
        Returns:
            QuerySet: Queryset s javnim igrama koje čekaju
        """
        return Game.objects.filter(
            status__in=['waiting', 'ready'],
            is_private=False
        ).annotate(
            player_count=Count('players')
        ).filter(
            player_count__lt=4
        ).order_by('-created_at')
    
    @staticmethod
    def get_games_for_player(user):
        """
        Dohvaća sve igre u kojima sudjeluje određeni igrač.
        
        Args:
            user: Korisnik za kojeg se traže igre
            
        Returns:
            QuerySet: Queryset s igrama korisnika
        """
        return Game.objects.filter(players=user).order_by('-created_at')
    
    @staticmethod
    def get_active_games_for_player(user):
        """
        Dohvaća aktivne igre u kojima sudjeluje određeni igrač.
        
        Args:
            user: Korisnik za kojeg se traže igre
            
        Returns:
            QuerySet: Queryset s aktivnim igrama korisnika
        """
        return Game.objects.filter(
            players=user,
            status__in=['in_progress', 'ready']
        ).order_by('-created_at')
    
    @staticmethod
    def create_game(creator, private=False, points_to_win=1001):
        """
        Stvara novu igru.
        
        Args:
            creator: Korisnik koji stvara igru
            private: Je li igra privatna (samo s pozivnicom)
            points_to_win: Broj bodova potreban za pobjedu
            
        Returns:
            Game: Stvorena igra
        """
        try:
            game = Game.objects.create(
                creator=creator,
                is_private=private,
                points_to_win=points_to_win,
                status='waiting'
            )
            # Dodaj kreatora kao prvog igrača
            game.players.add(creator)
            game.active_players.add(creator)
            
            logger.info(f"Stvorena nova igra: {game.id} (kreator: {creator.username})")
            return game
        except Exception as e:
            logger.error(f"Greška pri stvaranju igre: {str(e)}")
            raise
    
    @staticmethod
    def add_player_to_game(game, user):
        """
        Dodaje igrača u igru.
        
        Args:
            game: Igra u koju se dodaje igrač
            user: Korisnik koji se dodaje
            
        Returns:
            bool: True ako je igrač uspješno dodan, False inače
        """
        try:
            # Koristi metodu modela za dodavanje igrača
            result = game.add_player(user)
            
            if result:
                logger.info(f"Igrač {user.username} dodan u igru {game.id}")
            
            return result
        except ValueError as e:
            logger.warning(f"Nije moguće dodati igrača {user.username} u igru {game.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Greška pri dodavanju igrača u igru: {str(e)}")
            return False
    
    @staticmethod
    def remove_player_from_game(game, user):
        """
        Uklanja igrača iz igre.
        
        Args:
            game: Igra iz koje se uklanja igrač
            user: Korisnik koji se uklanja
            
        Returns:
            bool: True ako je igrač uspješno uklonjen, False inače
        """
        try:
            # Koristi metodu modela za uklanjanje igrača
            result = game.remove_player(user)
            
            if result:
                logger.info(f"Igrač {user.username} uklonjen iz igre {game.id}")
            
            return result
        except ValueError as e:
            logger.warning(f"Nije moguće ukloniti igrača {user.username} iz igre {game.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Greška pri uklanjanju igrača iz igre: {str(e)}")
            return False
    
    @staticmethod
    def delete_game(game):
        """
        Briše igru iz baze podataka.
        
        Args:
            game: Igra koja se briše
            
        Returns:
            bool: True ako je igra uspješno obrisana, False inače
        """
        try:
            game_id = str(game.id)
            game.delete()
            logger.info(f"Igra {game_id} uspješno obrisana")
            return True
        except Exception as e:
            logger.error(f"Greška pri brisanju igre {game.id}: {str(e)}")
            return False
    
    @staticmethod
    def start_game(game):
        """
        Započinje igru, postavlja status i formira timove.
        
        Args:
            game: Igra koja se započinje
            
        Returns:
            bool: True ako je igra uspješno započeta, False inače
        """
        with transaction.atomic():
            try:
                # Provjera ima li igra dovoljno igrača
                if game.players.count() != 4:
                    logger.warning(f"Pokušaj započinjanja igre {game.id} bez 4 igrača")
                    return False
                
                # Nasumično rasporedi igrače u timove
                if not game.team_a_players.exists() and not game.team_b_players.exists():
                    game.assign_teams()
                
                # Započni igru
                result = game.start_game()
                
                if result:
                    # Stvaranje prve runde
                    GameRepository.create_first_round(game)
                    logger.info(f"Igra {game.id} uspješno započeta")
                
                return result
            except ValueError as e:
                logger.warning(f"Nije moguće započeti igru {game.id}: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Greška pri započinjanju igre: {str(e)}")
                return False
    
    @staticmethod
    def create_first_round(game):
        """
        Stvara prvu rundu igre i određuje djelitelja.
        
        Args:
            game: Igra za koju se stvara prva runda
            
        Returns:
            Round: Stvorena runda
        """
        try:
            # Određivanje djelitelja - nasumično za prvu rundu
            dealer = random.choice(list(game.players.all()))
            
            # Stvaranje runde
            round_obj = Round.objects.create(
                game=game,
                number=1,
                dealer=dealer
            )
            
            logger.info(f"Stvorena prva runda za igru {game.id}, djelitelj: {dealer.username}")
            return round_obj
        except Exception as e:
            logger.error(f"Greška pri stvaranju prve runde: {str(e)}")
            raise
    
    @staticmethod
    def create_next_round(game):
        """
        Stvara sljedeću rundu igre nakon završetka prethodne.
        
        Args:
            game: Igra za koju se stvara sljedeća runda
            
        Returns:
            Round: Stvorena runda ili None ako nema prethodne runde
        """
        try:
            # Dohvaćanje trenutne runde
            current_round = game.get_current_round()
            
            if not current_round:
                # Ako nema prethodne runde, stvori prvu
                return GameRepository.create_first_round(game)
            
            # Provjera je li prethodna runda završena
            if not current_round.is_completed:
                logger.warning(f"Pokušaj stvaranja nove runde dok prethodna nije završena (igra {game.id})")
                return None
            
            # Određivanje sljedećeg djelitelja (igrač lijevo od prethodnog djelitelja)
            next_dealer = game.get_dealer_for_next_round()
            
            # Stvaranje nove runde
            new_round = Round.objects.create(
                game=game,
                number=current_round.number + 1,
                dealer=next_dealer
            )
            
            logger.info(f"Stvorena runda {new_round.number} za igru {game.id}, djelitelj: {next_dealer.username}")
            return new_round
        except Exception as e:
            logger.error(f"Greška pri stvaranju sljedeće runde: {str(e)}")
            raise
    
    @staticmethod
    def finish_game(game, winner_team=None):
        """
        Završava igru, postavlja pobjednika i bilježi vrijeme završetka.
        
        Args:
            game: Igra koja se završava
            winner_team: Pobjednički tim (a ili b), ako nije naveden, određuje se prema bodovima
            
        Returns:
            bool: True ako je igra uspješno završena, False inače
        """
        try:
            # Ako pobjednik nije naveden, odredi ga prema bodovima
            if winner_team is None:
                if game.team_a_score >= game.points_to_win:
                    winner_team = 'a'
                elif game.team_b_score >= game.points_to_win:
                    winner_team = 'b'
            
            # Koristi metodu modela za završavanje igre
            result = game.finish_game(winner_team=winner_team)
            
            if result:
                logger.info(f"Igra {game.id} završena, pobjednik: Tim {winner_team}")
            
            return result
        except ValueError as e:
            logger.warning(f"Nije moguće završiti igru {game.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Greška pri završavanju igre: {str(e)}")
            return False
    
    @staticmethod
    def abandon_game(game):
        """
        Označava igru kao napuštenu.
        
        Args:
            game: Igra koja se označava kao napuštena
            
        Returns:
            bool: True ako je igra uspješno označena kao napuštena, False inače
        """
        try:
            # Koristi metodu modela za napuštanje igre
            result = game.abandon_game()
            
            if result:
                logger.info(f"Igra {game.id} označena kao napuštena")
            
            return result
        except ValueError as e:
            logger.warning(f"Nije moguće označiti igru {game.id} kao napuštenu: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Greška pri označavanju igre kao napuštene: {str(e)}")
            return False
    
    @staticmethod
    def update_scores(game, team_a_points=0, team_b_points=0):
        """
        Ažurira rezultate timova dodavanjem novih bodova.
        
        Args:
            game: Igra čiji se rezultati ažuriraju
            team_a_points: Bodovi za tim A
            team_b_points: Bodovi za tim B
            
        Returns:
            str or None: ID pobjedničkog tima ('a' ili 'b') ako je igra završena, None inače
        """
        try:
            # Koristi metodu modela za ažuriranje rezultata
            winner = game.update_scores(team_a_points, team_b_points)
            
            logger.info(f"Ažurirani rezultati za igru {game.id}: Tim A: {game.team_a_score}, Tim B: {game.team_b_score}")
            
            return winner
        except Exception as e:
            logger.error(f"Greška pri ažuriranju rezultata: {str(e)}")
            raise
    
    @staticmethod
    def get_game_with_related_data(game_id):
        """
        Dohvaća igru s povezanim podacima (igrači, runde, potezi).
        Ovo je optimizirani upit koji smanjuje broj upita prema bazi.
        
        Args:
            game_id: UUID igre
            
        Returns:
            Game: Objekt igre s predučitanim vezama ili None ako nije pronađena
        """
        try:
            # Prefetch povezanih podataka za optimalnije upite
            return Game.objects.prefetch_related(
                'players',
                'team_a_players',
                'team_b_players',
                'active_players',
                Prefetch(
                    'rounds',
                    queryset=Round.objects.prefetch_related(
                        'moves',
                        'declarations'
                    ).order_by('number')
                )
            ).get(id=game_id)
        except Game.DoesNotExist:
            logger.warning(f"Igra s ID-om {game_id} nije pronađena")
            return None
    
    @staticmethod
    def get_game_state_for_player(game, user):
        """
        Dohvaća stanje igre prilagođeno za određenog igrača.
        Ovo uključuje podatke o trenutnoj rundi, kartama igrača, potezu, itd.
        
        Args:
            game: Igra čije se stanje dohvaća
            user: Korisnik za kojeg se dohvaća stanje
            
        Returns:
            dict: Rječnik s podacima o stanju igre za igrača
        """
        # Provjera je li korisnik član igre
        if not game.players.filter(id=user.id).exists():
            return {'error': 'Korisnik nije član ove igre'}
        
        try:
            # Dohvaćanje opće informacije o igri
            game_state = {
                'game_id': str(game.id),
                'status': game.status,
                'players': [],
                'teams': {
                    'team_a': [],
                    'team_b': []
                },
                'scores': {
                    'team_a': game.team_a_score,
                    'team_b': game.team_b_score
                },
                'your_team': game.get_team_for_player(user)
            }
            
            # Informacije o igračima
            for player in game.players.all():
                player_info = {
                    'id': player.id,
                    'username': player.username,
                    'is_active': game.is_player_active(player),
                    'team': game.get_team_for_player(player)
                }
                game_state['players'].append(player_info)
                
                # Dodaj igrača u odgovarajući tim
                if player_info['team'] == 'a':
                    game_state['teams']['team_a'].append(player_info)
                elif player_info['team'] == 'b':
                    game_state['teams']['team_b'].append(player_info)
            
            # Informacije o trenutnoj rundi
            current_round = game.get_current_round()
            if current_round:
                round_info = {
                    'id': current_round.id,
                    'number': current_round.number,
                    'dealer': current_round.dealer.username if current_round.dealer else None,
                    'trump_suit': current_round.trump_suit,
                    'calling_team': current_round.calling_team,
                    'is_completed': current_round.is_completed
                }
                game_state['round'] = round_info
                
                # Trenutni igrač na potezu
                current_player = current_round.get_current_player()
                game_state['your_turn'] = current_player and current_player.id == user.id
                
                # Informacije o trenutnom štihu
                current_trick = []
                for move in current_round.moves.filter(
                    order__gte=current_round.moves.count() // 4 * 4
                ).order_by('order'):
                    current_trick.append({
                        'player_id': move.player.id,
                        'player_name': move.player.username,
                        'card': move.card
                    })
                game_state['current_trick'] = current_trick
                
                # Zvanja u rundi
                declarations = []
                for decl in current_round.declarations.all():
                    declarations.append({
                        'type': decl.type,
                        'player_id': decl.player.id,
                        'player_name': decl.player.username,
                        'value': decl.value,
                        'team': game.get_team_for_player(decl.player)
                    })
                game_state['declarations'] = declarations
                
                # Povijest poteza (prethodni štihovi)
                history = []
                tricks = current_round.get_tricks()
                for i, trick in enumerate(tricks[:-1]):  # Izuzmi trenutni štih
                    trick_data = []
                    for move in trick:
                        trick_data.append({
                            'player_id': move.player.id,
                            'player_name': move.player.username,
                            'card': move.card,
                            'is_winner': move.is_winning
                        })
                    
                    history.append({
                        'trick_number': i + 1,
                        'moves': trick_data,
                        'winner': next((m['player_name'] for m in trick_data if m['is_winner']), None)
                    })
                game_state['history'] = history
                
                # Dohvaćanje karata igrača
                from game.models import Move
                
                # Uzimamo samo poteze gdje je karta izašla iz ruke igrača
                played_cards = set(Move.objects.filter(
                    round=current_round,
                    player=user,
                    is_valid=True
                ).values_list('card', flat=True))
                
                # Jednostavna simulacija karata u ruci igrača za demo svrhe
                try:
                    from game.game_logic.card import Card
                    from game.game_logic.deck import Deck
                    import random
                    
                    # Ako postoji aktivna runda koja nije završena
                    if not current_round.is_completed:
                        # Simuliraj dijeljenje karata (u stvarnoj implementaciji, to bi bilo u bazi)
                        # Fiksni seed za konzistentnost u demo svrhe
                        random.seed(hash(f"{user.id}_{game.id}_{current_round.number}"))
                        
                        # Kreiraj špil
                        deck = Deck()
                        all_cards = [card.code for card in deck.cards]
                        random.shuffle(all_cards)
                        
                        # Simuliraj karte dodijeljene ovom igraču
                        player_cards = all_cards[:8]
                        
                        # Ukloni karte koje su već odigrane
                        player_hand = [card for card in player_cards if card not in played_cards]
                        
                        # Sortiraj karte za bolji prikaz
                        player_hand.sort(key=lambda c: (c[-1], c[:-1]))
                        
                        game_state['your_cards'] = player_hand
                    else:
                        game_state['your_cards'] = []
                except Exception as e:
                    logger.error(f"Greška pri simulaciji karata igrača: {str(e)}", exc_info=True)
                    game_state['your_cards'] = []
            
            return game_state
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju stanja igre: {str(e)}", exc_info=True)
            return {'error': f'Interna greška: {str(e)}'}