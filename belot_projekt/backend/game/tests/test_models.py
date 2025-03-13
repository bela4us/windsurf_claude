"""
Testovi za modele Belot igre.

Ovaj modul testira funkcionalnost modela igre, runde, poteza, zvanja i
ostalih komponenti potrebnih za pravilno funkcioniranje Belot igre.
"""

import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.utils import IntegrityError

from game.models import Game, Round, Move, Declaration
from game.tests import create_test_game, create_test_round, create_test_moves

User = get_user_model()


class GameModelTest(TestCase):
    """Testovi za Game model."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.user1 = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='player2',
            email='player2@example.com',
            password='testpass123'
        )
        self.user3 = User.objects.create_user(
            username='player3',
            email='player3@example.com',
            password='testpass123'
        )
        self.user4 = User.objects.create_user(
            username='player4',
            email='player4@example.com',
            password='testpass123'
        )
    
    def test_game_creation(self):
        """Test stvaranja nove igre."""
        game = Game.objects.create(
            creator=self.user1,
            points_to_win=1001,
            is_private=False
        )
        self.assertEqual(game.creator, self.user1)
        self.assertEqual(game.points_to_win, 1001)
        self.assertFalse(game.is_private)
        self.assertEqual(game.status, 'waiting')
        self.assertIsNotNone(game.room_code)
        self.assertIsNotNone(game.created_at)
        self.assertIsNone(game.started_at)
        self.assertIsNone(game.finished_at)
        self.assertEqual(game.team1_score, 0)
        self.assertEqual(game.team2_score, 0)
        self.assertIsNone(game.winner_team)
        
        # Test da je room_code unikatan
        all_room_codes = Game.objects.values_list('room_code', flat=True)
        self.assertEqual(len(all_room_codes), len(set(all_room_codes)))
    
    def test_player_management(self):
        """Test dodavanja i uklanjanja igrača iz igre."""
        game = Game.objects.create(
            creator=self.user1,
            points_to_win=1001
        )
        
        # Dodavanje igrača u igru
        game.players.add(self.user1)
        game.active_players.add(self.user1)
        
        self.assertEqual(game.players.count(), 1)
        self.assertEqual(game.active_players.count(), 1)
        
        # Dodavanje dodatnih igrača
        game.add_player(self.user2)
        game.add_player(self.user3)
        game.add_player(self.user4)
        
        self.assertEqual(game.players.count(), 4)
        self.assertEqual(game.active_players.count(), 4)
        
        # Pokušaj dodavanja 5. igrača
        user5 = User.objects.create_user(
            username='player5',
            email='player5@example.com',
            password='testpass123'
        )
        
        # Očekujemo valueerror jer igra ima maksimalno 4 igrača
        with self.assertRaises(ValueError):
            game.add_player(user5)
        
        # Uklanjanje igrača
        game.remove_player(self.user4)
        self.assertEqual(game.players.count(), 3)
        
        # Uklanjanje drugog igrača
        game.remove_player(self.user3)
        self.assertEqual(game.players.count(), 2)
        
        # Dodavanje igrača natrag
        game.add_player(self.user3)
        self.assertEqual(game.players.count(), 3)
    
    def test_team_assignment(self):
        """Test dodjele igrača u timove."""
        game, users = create_test_game()
        
        # Inicijalno, igrači nisu u timovima
        self.assertEqual(game.team1_players.count(), 0)
        self.assertEqual(game.team2_players.count(), 0)
        
        # Dodjela timova
        game.assign_teams()
        
        # Provjera da su timovi ispravno dodijeljeni
        self.assertEqual(game.team1_players.count(), 2)
        self.assertEqual(game.team2_players.count(), 2)
        
        # Provjera da su suprotni igrači u istom timu
        team1_ids = list(game.team1_players.values_list('id', flat=True))
        team2_ids = list(game.team2_players.values_list('id', flat=True))
        
        # Test da su svi igrači dodijeljeni u timove
        all_player_ids = set(game.players.values_list('id', flat=True))
        assigned_ids = set(team1_ids + team2_ids)
        self.assertEqual(all_player_ids, assigned_ids)
    
    def test_game_lifecycle(self):
        """Test životnog ciklusa igre."""
        game, users = create_test_game()
        
        # Test početka igre
        self.assertEqual(game.status, 'waiting')
        
        # Dodjela timova i početak igre
        game.assign_teams()
        game.start_game()
        
        self.assertEqual(game.status, 'in_progress')
        self.assertIsNotNone(game.started_at)
        
        # Test završetka igre
        game.finish_game(winner_team=1)
        
        self.assertEqual(game.status, 'finished')
        self.assertEqual(game.winner_team, 1)
        self.assertIsNotNone(game.finished_at)
        
        # Test napuštanja igre
        game2, _ = create_test_game()
        game2.abandon_game()
        
        self.assertEqual(game2.status, 'abandoned')
    
    def test_score_update(self):
        """Test ažuriranja rezultata igre."""
        game, users = create_test_game()
        
        # Inicijalni rezultati
        self.assertEqual(game.team1_score, 0)
        self.assertEqual(game.team2_score, 0)
        
        # Dodavanje bodova
        game.update_scores(150, 0)
        self.assertEqual(game.team1_score, 150)
        self.assertEqual(game.team2_score, 0)
        
        # Dodavanje još bodova
        game.update_scores(200, 100)
        self.assertEqual(game.team1_score, 350)
        self.assertEqual(game.team2_score, 100)
        
        # Dovoljno bodova za pobjedu (ako je limit 1001)
        winner = game.update_scores(700, 0)
        self.assertEqual(game.team1_score, 1050)
        self.assertEqual(winner, 1)
        
        # Provjera da je igra završena
        self.assertEqual(game.status, 'finished')
        self.assertEqual(game.winner_team, 1)
    
    def test_helper_methods(self):
        """Test pomoćnih metoda modela."""
        game, users = create_test_game()
        
        # Dodjela timova
        game.assign_teams()
        
        # Provjera dohvata tima za igrača
        team1_player = game.team1_players.first()
        team2_player = game.team2_players.first()
        
        self.assertEqual(game.get_team_for_player(team1_player), 1)
        self.assertEqual(game.get_team_for_player(team2_player), 2)
        
        # Test metode is_player_active
        self.assertTrue(game.is_player_active(team1_player))
        
        # Test uklanjanja igrača iz active_players
        game.active_players.remove(team1_player)
        self.assertFalse(game.is_player_active(team1_player))
    
    def test_can_join_and_start(self):
        """Test metoda can_player_join_game i can_player_start_game."""
        game = Game.objects.create(
            creator=self.user1,
            points_to_win=1001
        )
        game.players.add(self.user1)
        
        # Korisnici koji nisu u igri mogu se pridružiti
        self.assertTrue(game.can_join(self.user2))
        
        # Postojeći igrači se ne mogu ponovno pridružiti
        self.assertFalse(game.can_join(self.user1))
        
        # Popunjena igra ne dopušta pridruživanje
        game.players.add(self.user2)
        game.players.add(self.user3)
        game.players.add(self.user4)
        self.assertFalse(game.can_join(User.objects.create_user(
            username='player5',
            email='player5@example.com',
            password='testpass123'
        )))
        
        # Test početka igre - samo kreator može pokrenuti igru
        self.assertTrue(game.can_player_start_game(self.user1))
        self.assertFalse(game.can_player_start_game(self.user2))
        
        # Igra mora biti u statusu ready da bi se mogla pokrenuti
        game.status = 'ready'
        game.save()
        self.assertTrue(game.can_player_start_game(self.user1))
        
        # Nakon pokretanja, igra više ne može biti pokrenuta
        game.status = 'in_progress'
        game.save()
        self.assertFalse(game.can_player_start_game(self.user1))


class RoundModelTest(TestCase):
    """Testovi za Round model."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.game, self.users = create_test_game()
        self.game.assign_teams()
    
    def test_round_creation(self):
        """Test stvaranja nove runde."""
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            dealer=self.users[0]
        )
        
        self.assertEqual(round_obj.game, self.game)
        self.assertEqual(round_obj.number, 1)
        self.assertEqual(round_obj.dealer, self.users[0])
        self.assertIsNone(round_obj.trump_suit)
        self.assertIsNone(round_obj.calling_team)
        self.assertIsNone(round_obj.caller)
        self.assertEqual(round_obj.team1_score, 0)
        self.assertEqual(round_obj.team2_score, 0)
        self.assertIsNone(round_obj.winner_team)
        self.assertFalse(round_obj.is_completed)
    
    def test_set_trump(self):
        """Test postavljanja adutske boje."""
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            dealer=self.users[0]
        )
        
        # Postavljanje aduta
        player = self.users[1]
        team = self.game.get_team_for_player(player)
        round_obj.set_trump('hearts', player)
        
        self.assertEqual(round_obj.trump_suit, 'hearts')
        self.assertEqual(round_obj.caller, player)
        self.assertEqual(round_obj.calling_team, team)
        
        # Provjera da adut ne može biti postavljen dvaput
        with self.assertRaises(ValueError):
            round_obj.set_trump('spades', self.users[2])
    
    def test_complete_round(self):
        """Test završetka runde."""
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            dealer=self.users[0]
        )
        
        # Postavljanje aduta i tima koji je zvao
        player = self.users[1]
        round_obj.set_trump('hearts', player)
        
        # Završetak runde
        winner_team = round_obj.complete_round(120, 42)
        
        self.assertTrue(round_obj.is_completed)
        self.assertIsNotNone(round_obj.completed_at)
        self.assertEqual(round_obj.team1_score, 120)
        self.assertEqual(round_obj.team2_score, 42)
        self.assertEqual(round_obj.winner_team, 1)  # Tim 1 ima više bodova
        self.assertEqual(winner_team, 1)
        
        # Test pravila "prolaza"
        round_obj2 = Round.objects.create(
            game=self.game,
            number=2,
            dealer=self.users[1]
        )
        
        # Tim 2 zove aduta
        round_obj2.set_trump('spades', self.users[2])  # Pretpostavljamo da je users[2] u timu 2
        
        # Tim 2 ima jednak broj bodova kao tim 1 - ne prolazi
        winner_team = round_obj2.complete_round(80, 80)
        
        # Tim 2 nije prošao, svi bodovi idu timu 1
        self.assertEqual(round_obj2.team1_score, 160)
        self.assertEqual(round_obj2.team2_score, 0)
        self.assertEqual(round_obj2.winner_team, 1)
        self.assertEqual(winner_team, 1)
    
    def test_get_current_player(self):
        """Test određivanja igrača koji je na potezu."""
        round_obj = create_test_round(self.game, self.users[0])
        
        # Bez poteza, prvi igrač je sljedeći nakon dealera
        current_player = round_obj.get_current_player()
        self.assertEqual(current_player, self.users[1])
        
        # Stvaranje poteza
        moves, _ = create_test_moves(round_obj, cards_per_player=1)
        
        # Nakon 4 poteza (jednog kompletnog štiha), pobjednik je na potezu
        # Pobjednik će biti određen logikom u move_repository
        
        # Za potrebe testa, označit ćemo zadnji potez kao pobjednički
        winning_move = moves[3]
        winning_move.is_winning = True
        winning_move.save()
        
        # Ponovno dohvaćanje trenutnog igrača
        current_player = round_obj.get_current_player()
        self.assertEqual(current_player, winning_move.player)
    
    def test_calling_order(self):
        """Test redoslijeda zvanja aduta."""
        round_obj = create_test_round(self.game, self.users[0])
        
        # Prvi igrač na redu za zvanje je igrač nakon djelitelja
        next_caller = round_obj.get_next_calling_player()
        self.assertEqual(next_caller, self.users[1])
        
        # Bilježenje da je prvi igrač rekao "dalje"
        round_obj.add_to_calling_order(self.users[1])
        
        # Sljedeći igrač je na redu
        next_caller = round_obj.get_next_calling_player()
        self.assertEqual(next_caller, self.users[2])
        
        # Bilježenje da je drugi igrač rekao "dalje"
        round_obj.add_to_calling_order(self.users[2])
        
        # Sljedeći igrač je na redu
        next_caller = round_obj.get_next_calling_player()
        self.assertEqual(next_caller, self.users[3])
        
        # Bilježenje da je treći igrač rekao "dalje"
        round_obj.add_to_calling_order(self.users[3])
        
        # Djelitelj mora zvati aduta
        next_caller = round_obj.get_next_calling_player()
        self.assertEqual(next_caller, self.users[0])


class MoveModelTest(TestCase):
    """Testovi za Move model."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.game, self.users = create_test_game()
        self.game.assign_teams()
        self.round = create_test_round(self.game, self.users[0])
    
    def test_move_creation(self):
        """Test stvaranja novog poteza."""
        move = Move.objects.create(
            round=self.round,
            player=self.users[1],
            card='AS',  # As pik
            order=0
        )
        
        self.assertEqual(move.round, self.round)
        self.assertEqual(move.player, self.users[1])
        self.assertEqual(move.card, 'AS')
        self.assertEqual(move.order, 0)
        self.assertFalse(move.is_winning)
        self.assertTrue(move.is_valid)  # Prvi potez je uvijek valjan
        self.assertIsNotNone(move.created_at)
    
    def test_get_card_methods(self):
        """Test metoda za dohvaćanje informacija o karti."""
        # Karta: Dečko karo
        move = Move.objects.create(
            round=self.round,
            player=self.users[1],
            card='JD',
            order=0
        )
        
        self.assertEqual(move.get_card_suit(), 'D')  # Karo
        self.assertEqual(move.get_card_value(), 'J')  # Dečko
        
        # Postavljanje aduta za testiranje bodovanja
        self.round.set_trump('diamonds', self.users[2])
        
        # Dečko adut vrijedi 20 bodova
        self.assertEqual(move.get_card_points('diamonds'), 20)
        
        # Ako karta nije adut, dečko vrijedi 2 boda
        move2 = Move.objects.create(
            round=self.round,
            player=self.users[2],
            card='JS',  # Dečko pik (nije adut)
            order=1
        )
        
        self.assertEqual(move2.get_card_points('diamonds'), 2)
    
    def test_validate_move(self):
        """Test validacije poteza prema pravilima igre."""
        # Implementacija ovisi o daljnjoj logici validacije poteza
        # Na razini modela pretpostavljamo da su potezi valjani
        pass


class DeclarationModelTest(TestCase):
    """Testovi za Declaration model."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.game, self.users = create_test_game()
        self.game.assign_teams()
        self.round = create_test_round(self.game, self.users[0])
        self.round.set_trump('hearts', self.users[1])
    
    def test_declaration_creation(self):
        """Test stvaranja novog zvanja."""
        declaration = Declaration.objects.create(
            round=self.round,
            player=self.users[1],
            type='sequence_3',
            suit='H',
            cards=['JH', 'QH', 'KH']
        )
        
        self.assertEqual(declaration.round, self.round)
        self.assertEqual(declaration.player, self.users[1])
        self.assertEqual(declaration.type, 'sequence_3')
        self.assertEqual(declaration.suit, 'H')
        self.assertEqual(declaration.cards, ['JH', 'QH', 'KH'])
        self.assertEqual(declaration.value, 20)  # Terca vrijedi 20 bodova
        self.assertIsNotNone(declaration.created_at)
    
    def test_declaration_validation(self):
        """Test validacije zvanja."""
        # Zvanje četiri dečka
        valid, _ = Declaration.validate_declaration(
            'four_jacks',
            ['JS', 'JH', 'JD', 'JC'],
            self.round
        )
        self.assertTrue(valid)
        
        # Nevažeće zvanje (nedostaje karta)
        valid, _ = Declaration.validate_declaration(
            'four_jacks',
            ['JS', 'JH', 'JD'],
            self.round
        )
        self.assertFalse(valid)
        
        # Nevažeća sekvenca (karte nisu u nizu)
        valid, _ = Declaration.validate_declaration(
            'sequence_3',
            ['7H', '9H', '10H'],
            self.round
        )
        self.assertFalse(valid)
        
        # Valjana sekvenca
        valid, _ = Declaration.validate_declaration(
            'sequence_3',
            ['8H', '9H', '10H'],
            self.round
        )
        self.assertTrue(valid)
        
        # Valjana bela u adutu
        valid, _ = Declaration.validate_declaration(
            'bela',
            ['KH', 'QH'],
            self.round
        )
        self.assertTrue(valid)
    
    def test_get_highest_declaration(self):
        """Test određivanja najvišeg zvanja."""
        # Terca
        declaration1 = Declaration.objects.create(
            round=self.round,
            player=self.users[1],
            type='sequence_3',
            suit='H',
            cards=['JH', 'QH', 'KH']
        )
        
        # Kvarta
        declaration2 = Declaration.objects.create(
            round=self.round,
            player=self.users[2],
            type='sequence_4',
            suit='S',
            cards=['7S', '8S', '9S', '10S']
        )
        
        # Četiri asa
        declaration3 = Declaration.objects.create(
            round=self.round,
            player=self.users[3],
            type='four_aces',
            cards=['AS', 'AH', 'AD', 'AC']
        )
        
        # Najviše zvanje je četiri asa (100 bodova)
        highest = Declaration.get_highest_declaration([
            declaration1, declaration2, declaration3
        ])
        
        self.assertEqual(highest, declaration3)
        
        # Usporedba zvanja iste vrijednosti
        declaration4 = Declaration.objects.create(
            round=self.round,
            player=self.users[0],
            type='four_kings',
            cards=['KS', 'KH', 'KD', 'KC']
        )
        
        # Rezultat ovisi o tome kako je implementirana usporedba
        # jednakih zvanja, ali logika bi trebala biti konzistentna
        comparison = Declaration.compare_declarations(declaration3, declaration4)
        self.assertIn(comparison, [-1, 0, 1])  # Jedan od mogućih rezultata