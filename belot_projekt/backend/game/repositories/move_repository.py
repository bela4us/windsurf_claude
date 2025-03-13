"""
Repozitorij za poteze u Belot igri.

Ovaj modul implementira MoveRepository klasu koja encapsulira svu logiku
za pristup i manipulaciju Move modelima. Repozitorij služi kao sloj
apstrakcije između modela podataka i poslovne logike, omogućujući
jednostavniji pristup i bolju organizaciju koda vezanog uz poteze u igri.
"""

import logging
from django.db import transaction
from django.db.models import F, Q, Count, Max, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model

from game.models import Game, Round, Move, Declaration
from game.game_logic.card import Card

User = get_user_model()
logger = logging.getLogger('game.repositories')

class MoveRepository:
    """
    Repozitorij za pristup i manipulaciju Move modelima.
    
    Ova klasa pruža metode za stvaranje, dohvaćanje i validaciju poteza
    u Belot igri, kao i za određivanje pobjednika štihova i praćenje
    redoslijeda igranja.
    """
    
    @staticmethod
    def get_by_id(move_id):
        """
        Dohvaća potez prema njegovom ID-u.
        
        Args:
            move_id: ID poteza
            
        Returns:
            Move: Objekt poteza ili None ako nije pronađen
        """
        try:
            return Move.objects.get(id=move_id)
        except Move.DoesNotExist:
            logger.warning(f"Potez s ID-om {move_id} nije pronađen")
            return None
    
    @staticmethod
    def get_moves_for_round(round_obj):
        """
        Dohvaća sve poteze za određenu rundu.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            QuerySet: Queryset s potezima za rundu
        """
        return Move.objects.filter(round=round_obj).order_by('order')
    
    @staticmethod
    def get_moves_for_player(user, round_obj=None):
        """
        Dohvaća poteze određenog igrača, opcionalno filtrirano po rundi.
        
        Args:
            user: Korisnik čiji se potezi dohvaćaju
            round_obj: Opcionalno, objekt runde za filtriranje
            
        Returns:
            QuerySet: Queryset s potezima igrača
        """
        query = Move.objects.filter(player=user)
        if round_obj:
            query = query.filter(round=round_obj)
        return query.order_by('round', 'order')
    
    @staticmethod
    def get_last_move(round_obj):
        """
        Dohvaća posljednji potez u rundi.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            Move: Objekt posljednjeg poteza ili None ako nema poteza
        """
        return Move.objects.filter(round=round_obj).order_by('-order').first()
    
    @staticmethod
    def get_current_trick(round_obj):
        """
        Dohvaća trenutni (nedovršeni) štih u rundi.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            list: Lista poteza u trenutnom štihu
        """
        # Izračunaj broj već dovršenih štihova
        total_moves = Move.objects.filter(round=round_obj).count()
        completed_tricks = total_moves // 4
        
        # Dohvati poteze trenutnog štiha
        start_order = completed_tricks * 4
        
        return list(Move.objects.filter(
            round=round_obj,
            order__gte=start_order
        ).order_by('order'))
    
    @staticmethod
    def get_next_player(round_obj):
        """
        Određuje koji je igrač sljedeći na potezu.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            User: Korisnik koji je sljedeći na potezu
        """
        # Ako nema poteza, prvi potez ima igrač lijevo od djelitelja
        moves_count = Move.objects.filter(round=round_obj).count()
        
        if moves_count == 0:
            # U Belotu, prvi potez ima igrač nakon djelitelja
            game = round_obj.game
            all_players = list(game.players.all())
            dealer_index = all_players.index(round_obj.dealer)
            # Prvi potez ima igrač nakon djelitelja (u smjeru suprotnom od kazaljke na satu)
            first_player_index = (dealer_index + 1) % 4
            return all_players[first_player_index]
        
        # Ako je dovršen kompletan štih (4 poteza), sljedeći potez ima pobjednik štiha
        if moves_count > 0 and moves_count % 4 == 0:
            # Dohvati posljednji dovršeni štih
            last_trick_end = moves_count - 1
            last_trick_start = last_trick_end - 3
            
            # Nađi pobjednički potez
            winning_move = Move.objects.filter(
                round=round_obj,
                order__gte=last_trick_start,
                order__lte=last_trick_end,
                is_winning=True
            ).first()
            
            if winning_move:
                return winning_move.player
        
        # U nedovršenom štihu, sljedeći je igrač nakon posljednjeg koji je igrao
        last_move = Move.objects.filter(round=round_obj).order_by('-order').first()
        
        if last_move:
            game = round_obj.game
            all_players = list(game.players.all())
            last_player_index = all_players.index(last_move.player)
            next_player_index = (last_player_index + 1) % 4
            return all_players[next_player_index]
        
        # Ako iz nekog razloga ne možemo odrediti, vraćamo None
        logger.error(f"Nije moguće odrediti sljedećeg igrača za rundu {round_obj.id}")
        return None
    
    @staticmethod
    def create_move(round_obj, player, card, order=None):
        """
        Stvara novi potez (igranje karte).
        
        Args:
            round_obj: Runda u kojoj se stvara potez
            player: Igrač koji igra kartu
            card: Karta koja se igra (string format, npr. "7S")
            order: Opcionalno, redni broj poteza (ako nije naveden, automatski se određuje)
            
        Returns:
            Move: Stvoreni potez
        """
        try:
            # Ako redni broj nije naveden, odredi ga kao sljedeći u nizu
            if order is None:
                last_move = Move.objects.filter(round=round_obj).aggregate(max_order=Max('order'))
                order = (last_move['max_order'] or -1) + 1
            
            # Stvaranje poteza
            move = Move.objects.create(
                round=round_obj,
                player=player,
                card=card,
                order=order
            )
            
            logger.info(f"Stvoren potez {move.id}: Igrač {player.username} igra {card} u rundi {round_obj.id}")
            
            # Validacija poteza i određivanje pobjednika štiha ako je potrebno
            move.validate_move()
            
            # Ako je ovaj potez kompletan štih, odredi pobjednika
            moves_count = Move.objects.filter(round=round_obj).count()
            if moves_count % 4 == 0:
                MoveRepository.determine_trick_winner(round_obj, moves_count // 4 - 1)
            
            return move
        except Exception as e:
            logger.error(f"Greška pri stvaranju poteza: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def determine_trick_winner(round_obj, trick_number):
        """
        Određuje pobjednika štiha i označava pobjednički potez.
        
        Args:
            round_obj: Objekt runde
            trick_number: Redni broj štiha (0-bazirano)
            
        Returns:
            Move: Pobjednički potez
        """
        try:
            # Izračunaj redne brojeve poteza u štihu
            start_order = trick_number * 4
            end_order = start_order + 3
            
            # Dohvati poteze štiha
            trick_moves = list(Move.objects.filter(
                round=round_obj,
                order__gte=start_order,
                order__lte=end_order
            ).order_by('order'))
            
            if len(trick_moves) != 4:
                logger.error(f"Nepotpun štih {trick_number} u rundi {round_obj.id}")
                return None
            
            # Prvo resetiraj pobjednički status svih poteza u štihu
            for move in trick_moves:
                move.is_winning = False
                move.save()
            
            # Dohvati adutsku boju
            trump_suit_code = round_obj.trump_suit
            if trump_suit_code == 'spades':
                trump_suit = 'S'
            elif trump_suit_code == 'hearts':
                trump_suit = 'H'
            elif trump_suit_code == 'diamonds':
                trump_suit = 'D'
            elif trump_suit_code == 'clubs':
                trump_suit = 'C'
            else:
                trump_suit = None  # No trump ili all trump
            
            # Dohvati početnu boju
            first_move = trick_moves[0]
            lead_suit = first_move.get_card_suit()
            
            # Poredak jačine karata u adutskoj i ne-adutskoj boji
            non_trump_order = {'7': 0, '8': 1, '9': 2, 'J': 3, 'Q': 4, 'K': 5, '10': 6, 'A': 7}
            trump_order = {'7': 0, '8': 1, 'Q': 2, 'K': 3, '10': 4, 'A': 5, '9': 6, 'J': 7}
            
            winning_move = first_move
            highest_value = 0
            is_trump_played = False
            
            # Prolazak kroz sve poteze u štihu
            for move in trick_moves:
                move_suit = move.get_card_suit()
                move_value = move.get_card_value()
                
                # Provjeri je li potez adut
                is_move_trump = False
                if trump_suit and move_suit == trump_suit:
                    is_move_trump = True
                elif trump_suit_code == 'all_trump':
                    is_move_trump = True
                
                # Ako je već igran adut, samo drugi adut može pobijediti
                if is_trump_played and not is_move_trump:
                    continue
                
                # Ako je ovo prvi adut u štihu, on postaje pobjednički
                if is_move_trump and not is_trump_played:
                    winning_move = move
                    highest_value = trump_order.get(move_value, 0)
                    is_trump_played = True
                    continue
                
                # Ako su oba adut, usporedi vrijednosti
                if is_move_trump and is_trump_played:
                    move_rank = trump_order.get(move_value, 0)
                    if move_rank > highest_value:
                        winning_move = move
                        highest_value = move_rank
                    continue
                
                # Ako nema aduta, usporedi s početnom bojom
                if not is_trump_played:
                    # Samo karte početne boje mogu pobijediti
                    if move_suit == lead_suit:
                        move_rank = non_trump_order.get(move_value, 0)
                        if move == first_move or move_rank > highest_value:
                            winning_move = move
                            highest_value = move_rank
            
            # Označi pobjednički potez
            winning_move.is_winning = True
            winning_move.save()
            
            # Ako je ovo posljednji štih u rundi, dodaj 10 bodova
            if trick_number == 7:  # 8 štihova po rundi, 0-bazirani indeks
                # Ovo bi se trebalo bilježiti za bodovanje runde
                logger.info(f"Posljednji štih u rundi {round_obj.id} osvojio igrač {winning_move.player.username}, +10 bodova")
            
            logger.info(f"Štih {trick_number} u rundi {round_obj.id} osvojio igrač {winning_move.player.username}")
            
            return winning_move
        except Exception as e:
            logger.error(f"Greška pri određivanju pobjednika štiha: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def validate_card_playable(round_obj, player, card_code):
        """
        Provjerava je li igrač na potezu i može li odigrati određenu kartu.
        
        Args:
            round_obj: Objekt runde
            player: Igrač koji želi odigrati kartu
            card_code: Kod karte koja se želi odigrati
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
        """
        # Provjera je li igrač na potezu
        next_player = MoveRepository.get_next_player(round_obj)
        if next_player != player:
            return False, "Nije tvoj red za potez"
        
        # Provjera pravila bacanja karata
        # - Prvi potez u štihu može biti bilo koja karta
        # - Sljedeći potezi moraju pratiti boju ako je moguće
        # - Ako ne mogu pratiti boju, moraju baciti aduta ako ga imaju
        # - Ako ne mogu ni jedno ni drugo, mogu baciti bilo koju kartu
        
        # Ova provjera zahtijeva znanje o kartama u rukama igrača, što bi trebalo biti
        # implementirano u game_service koji ima širi kontekst o stanju igre
        
        # Za sada, pretpostavljamo da je potez valjan
        return True, ""

    @staticmethod
    def get_valid_moves(round_obj, player, hand):
        """
        Vraća listu karata koje igrač može odigrati prema pravilima Belota.
        
        Args:
            round_obj: Objekt runde
            player: Igrač koji je na potezu
            hand: Lista karata u ruci igrača
            
        Returns:
            list: Lista karata koje su valjani potezi
        """
        try:
            # Ako igrač nije na potezu, ne može igrati kartu
            next_player = MoveRepository.get_next_player(round_obj)
            if next_player != player:
                return []
            
            # Ako nema poteza u štihu, igrač može igrati bilo koju kartu
            trick_moves = MoveRepository.get_current_trick(round_obj)
            if not trick_moves:
                return hand
            
            # Dohvaćanje adutske boje
            trump_suit_code = round_obj.trump_suit
            if trump_suit_code == 'spades':
                trump_suit = 'S'
            elif trump_suit_code == 'hearts':
                trump_suit = 'H'
            elif trump_suit_code == 'diamonds':
                trump_suit = 'D'
            elif trump_suit_code == 'clubs':
                trump_suit = 'C'
            else:
                trump_suit = None  # No trump ili all trump
            
            # Dohvaćanje boje prvog poteza u štihu
            first_move = trick_moves[0]
            lead_suit = first_move.get_card_suit()
            
            # Provjera karata koje prate boju
            same_suit_cards = [card for card in hand if card[-1] == lead_suit]
            
            # Ako igrač ima karte tražene boje, mora ih igrati
            if same_suit_cards:
                return same_suit_cards
            
            # Ako igrač nema karte tražene boje, mora igrati aduta ako ga ima
            # (osim ako već netko nije odigrao aduta)
            has_trump_been_played = any(move.get_card_suit() == trump_suit for move in trick_moves)
            
            if not has_trump_been_played and trump_suit != lead_suit:
                trump_cards = [card for card in hand if card[-1] == trump_suit]
                if trump_cards:
                    return trump_cards
            
            # Ako nema karata tražene boje ili aduta, može igrati bilo koju kartu
            return hand
        except Exception as e:
            logger.error(f"Greška pri određivanju valjanih poteza: {str(e)}", exc_info=True)
            # U slučaju greške, vraćamo sve karte (sigurniji pristup)
            return hand
    
    @staticmethod
    def get_player_cards(round_obj, player):
        """
        Dohvaća karte igrača u trenutnoj rundi.
        
        U stvarnoj implementaciji, ovo bi dohvaćalo podatke iz baze.
        Za demo svrhe, simuliramo karte na temelju seediranog random generatora.
        
        Args:
            round_obj: Objekt runde
            player: Igrač čije karte dohvaćamo
            
        Returns:
            list: Lista karata u ruci igrača
        """
        try:
            game = round_obj.game
            
            # Dohvaćanje odigranih karata
            played_cards = set(Move.objects.filter(
                round=round_obj,
                player=player,
                is_valid=True
            ).values_list('card', flat=True))
            
            # Simulacija karata u ruci igrača (kao u get_game_state_for_player)
            import random
            from game.game_logic.deck import Deck
            
            # Fiksni seed za konzistentnost
            random.seed(hash(f"{player.id}_{game.id}_{round_obj.number}"))
            
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
            
            return player_hand
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju karata igrača: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def count_trick_points(trick_moves, trump_suit):
        """
        Izračunava bodovnu vrijednost štiha na temelju vrijednosti karata.
        
        Args:
            trick_moves: Lista poteza u štihu
            trump_suit: Adutska boja
            
        Returns:
            int: Ukupni bodovi za štih
        """
        total_points = 0
        
        for move in trick_moves:
            total_points += move.get_card_points(trump_suit)
        
        return total_points
    
    @staticmethod
    def calculate_round_points(round_obj):
        """
        Izračunava bodove timova za rundu, uključujući štihove i zvanja.
        
        Args:
            round_obj: Objekt runde
            
        Returns:
            tuple: (team_a_points, team_b_points)
        """
        game = round_obj.game
        team_a_trick_points = 0
        team_b_trick_points = 0
        
        # Bodovi za štihove
        for trick_number in range(8):  # 8 štihova po rundi
            start_order = trick_number * 4
            end_order = start_order + 3
            
            trick_moves = list(Move.objects.filter(
                round=round_obj,
                order__gte=start_order,
                order__lte=end_order
            ).order_by('order'))
            
            if len(trick_moves) != 4:
                continue  # Preskočimo nepotpune štihove
            
            # Nađi pobjednički potez
            winning_move = next((move for move in trick_moves if move.is_winning), None)
            if not winning_move:
                continue
            
            # Odredi tim pobjednika
            winner_team = game.get_team_for_player(winning_move.player)
            if not winner_team:
                continue
            
            # Izračunaj bodove za štih
            trick_points = MoveRepository.count_trick_points(trick_moves, round_obj.trump_suit)
            
            # Dodatnih 10 bodova za posljednji štih
            if trick_number == 7:
                trick_points += 10
            
            # Dodaj bodove odgovarajućem timu
            if winner_team == 'a':
                team_a_trick_points += trick_points
            else:
                team_b_trick_points += trick_points
        
        # Provjera štih-mača (štiglje)
        if team_a_trick_points == 0:
            team_b_trick_points += 90  # Dodatnih 90 bodova za štih-mač
        elif team_b_trick_points == 0:
            team_a_trick_points += 90  # Dodatnih 90 bodova za štih-mač
        
        # Bodovi za zvanja
        team_a_declarations = Declaration.objects.filter(
            round=round_obj,
            player__in=game.team_a_players.all()
        )
        
        team_b_declarations = Declaration.objects.filter(
            round=round_obj,
            player__in=game.team_b_players.all()
        )
        
        # Pronađi najviše zvanje za svaki tim
        highest_team_a = Declaration.get_highest_declaration(list(team_a_declarations))
        highest_team_b = Declaration.get_highest_declaration(list(team_b_declarations))
        
        # Usporedi najviša zvanja i dodijeli bodove
        if highest_team_a and highest_team_b:
            comparison = Declaration.compare_declarations(highest_team_a, highest_team_b)
            if comparison > 0:  # Tim A ima jače zvanje
                team_a_trick_points += sum(decl.value for decl in team_a_declarations)
            elif comparison < 0:  # Tim B ima jače zvanje
                team_b_trick_points += sum(decl.value for decl in team_b_declarations)
            else:  # Jednaka zvanja, provjeriti koji je igrač bliži djelitelju
                # Ova logika bi trebala biti implementirana u servisnom sloju
                # Za sada, pretpostavljamo da oba tima dobivaju svoje bodove
                team_a_trick_points += sum(decl.value for decl in team_a_declarations)
                team_b_trick_points += sum(decl.value for decl in team_b_declarations)
        elif highest_team_a:  # Samo tim A ima zvanja
            team_a_trick_points += sum(decl.value for decl in team_a_declarations)
        elif highest_team_b:  # Samo tim B ima zvanja
            team_b_trick_points += sum(decl.value for decl in team_b_declarations)
        
        return team_a_trick_points, team_b_trick_points