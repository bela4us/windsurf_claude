"""
Testovi za servisni sloj Belot igre.

Ovaj modul testira servisne klase koje implementiraju poslovnu logiku igre,
uključujući GameService i ScoringService.
"""

from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from game.models import Game, Round, Move, Declaration
from game.services.game_service import GameService
from game.services.scoring_service import ScoringService
from game.repositories.game_repository import GameRepository
from game.repositories.move_repository import MoveRepository
from game.tests import create_test_game, create_test_round, create_test_moves

User = get_user_model()


class GameServiceTest(TestCase):
    """Testovi za GameService."""
    
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
        
        # Stvaranje igre za testiranje
        self.game, self.users = create_test_game()
        
        # Inicijalizacija servisa
        self.service = GameService(game_id=str(self.game.id))
    
    def test_create_game(self):
        """Test stvaranja nove igre putem servisa."""
        # Stvaranje novog servisa bez game_id
        service = GameService()
        
        # Stvaranje igre
        result = service.create_game(
            creator_id=self.user1.id,
            private=False,
            points_to_win=1001
        )
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        self.assertIn('game_id', result)
        
        # Provjera stvorene igre
        game_id = result['game_id']
        game = Game.objects.get(id=game_id)
        
        self.assertEqual(game.creator, self.user1)
        self.assertEqual(game.points_to_win, 1001)
        self.assertFalse(game.is_private)
        
        # Provjera da je kreator automatski dodan kao igrač
        self.assertTrue(game.players.filter(id=self.user1.id).exists())
    
    def test_join_game(self):
        """Test pridruživanja igri putem servisa."""
        # Dodjeli game_id postojećoj instanci servisa
        self.service.game_id = str(self.game.id)
        
        # Korisnik 2 se pridružuje igri
        result = self.service.join_game(user_id=self.user2.id)
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        
        # Provjera da se korisnik pridružio igri
        self.game.refresh_from_db()
        self.assertTrue(self.game.players.filter(id=self.user2.id).exists())
        
        # Test pridruživanja putem room_code
        service = GameService()  # Nova instanca bez game_id
        result = service.join_game(
            user_id=self.user3.id,
            room_code=self.game.room_code
        )
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        
        # Provjera da se korisnik pridružio igri
        self.game.refresh_from_db()
        self.assertTrue(self.game.players.filter(id=self.user3.id).exists())
    
    def test_leave_game(self):
        """Test napuštanja igre putem servisa."""
        # Prvo dodaj korisnika u igru
        self.game.players.add(self.user2)
        self.game.active_players.add(self.user2)
        
        # Korisnik napušta igru
        result = self.service.leave_game(user_id=self.user2.id)
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        
        # Provjera da je korisnik uklonjen iz igre
        self.game.refresh_from_db()
        self.assertFalse(self.game.players.filter(id=self.user2.id).exists())
    
    def test_start_game(self):
        """Test pokretanja igre putem servisa."""
        # Dodavanje još igrača i postavljanje igre u stanje ready
        self.game.players.add(self.user2, self.user3, self.user4)
        self.game.active_players.add(self.user2, self.user3, self.user4)
        self.game.status = 'ready'
        self.game.save()
        
        # Pokretanje igre
        result = self.service.start_game(user_id=self.user1.id)  # Korisnik 1 je kreator
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        
        # Provjera da je igra pokrenuta
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, 'in_progress')
        
        # Provjera da je stvorena runda
        self.assertGreater(self.game.rounds.count(), 0)
        
        # Provjera da postoje informacije o kartama u odgovoru
        self.assertIn('player_cards', result)
        
        # Provjera da su timovi dodijeljeni
        self.assertGreater(self.game.team1_players.count(), 0)
        self.assertGreater(self.game.team2_players.count(), 0)
    
    @patch('game.repositories.move_repository.MoveRepository.validate_card_playable')
    def test_process_move(self, mock_validate):
        """Test obrade poteza igrača putem servisa."""
        # Postavi igru u stanje za testiranje poteza
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde i postavljanje aduta
        round_obj = create_test_round(self.game, self.users[0])
        round_obj.trump_suit = 'hearts'
        round_obj.caller = self.users[1]
        round_obj.calling_team = 1
        round_obj.save()
        
        # Mock validaciju poteza da uvijek prođe
        mock_validate.return_value = (True, "")
        
        # Mock MoveRepository.create_move da ne pokušava stvarno stvoriti potez
        with patch('game.repositories.move_repository.MoveRepository.create_move') as mock_create:
            mock_move = Move(
                round=round_obj,
                player=self.users[1],
                card='AS',
                order=0,
                is_winning=False
            )
            mock_create.return_value = mock_move
            
            # Obrada poteza
            result = self.service.process_move(
                user_id=self.users[1].id,
                card='AS'
            )
            
            # Provjera da je servis pozvao validaciju
            mock_validate.assert_called_once()
            
            # Provjera da je servis pokušao stvoriti potez
            mock_create.assert_called_once()
            
            # Provjera rezultata
            self.assertTrue(result.get('valid', False))
            self.assertIn('trick_completed', result)
            
    def test_process_trump_call(self):
        """Test zvanja aduta putem servisa."""
        # Postavi igru u stanje za testiranje
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde
        round_obj = create_test_round(self.game, self.users[0])
        
        # Zvanje aduta
        result = self.service.process_trump_call(
            user_id=self.users[1].id,
            suit='hearts'
        )
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        self.assertEqual(result.get('suit'), 'hearts')
        
        # Provjera da je adut postavljen
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.trump_suit, 'hearts')
        self.assertEqual(round_obj.caller, self.users[1])
    
    def test_process_trump_pass(self):
        """Test propuštanja zvanja aduta putem servisa."""
        # Postavi igru u stanje za testiranje
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde
        round_obj = create_test_round(self.game, self.users[0])
        
        # Propuštanje zvanja
        result = self.service.process_trump_pass(
            user_id=self.users[1].id
        )
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        self.assertIn('next_player', result)
        
        # Provjera da je sljedeći igrač na redu
        next_player_name = result.get('next_player')
        self.assertEqual(next_player_name, self.users[2].username)
    
    def test_process_declaration(self):
        """Test prijave zvanja putem servisa."""
        # Postavi igru u stanje za testiranje
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde i postavljanje aduta
        round_obj = create_test_round(self.game, self.users[0])
        round_obj.trump_suit = 'hearts'
        round_obj.caller = self.users[1]
        round_obj.calling_team = 1
        round_obj.save()
        
        # Prijava zvanja (terca)
        with patch('game.models.Declaration.validate_declaration') as mock_validate:
            # Mock validaciju da uvijek prođe
            mock_validate.return_value = (True, "")
            
            # Stvaranje zvanja
            result = self.service.process_declaration(
                user_id=self.users[1].id,
                declaration_type='sequence_3',
                cards=['JH', 'QH', 'KH']
            )
            
            # Provjera rezultata
            self.assertTrue(result.get('valid', False))
            self.assertEqual(result.get('declaration_type'), 'sequence_3')
            
            # Provjera da je zvanje stvoreno
            declaration = Declaration.objects.first()
            self.assertIsNotNone(declaration)
            self.assertEqual(declaration.type, 'sequence_3')
            self.assertEqual(declaration.player, self.users[1])
    
    def test_process_bela(self):
        """Test prijave bele putem servisa."""
        # Postavi igru u stanje za testiranje
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde i postavljanje aduta
        round_obj = create_test_round(self.game, self.users[0])
        round_obj.trump_suit = 'hearts'
        round_obj.caller = self.users[1]
        round_obj.calling_team = 1
        round_obj.save()
        
        # Prijava bele
        result = self.service.process_bela(
            user_id=self.users[1].id
        )
        
        # Provjera rezultata
        self.assertTrue(result.get('valid', False))
        self.assertEqual(result.get('suit'), 'H')
        
        # Provjera da je bela stvorena
        declaration = Declaration.objects.first()
        self.assertIsNotNone(declaration)
        self.assertEqual(declaration.type, 'bela')
        self.assertEqual(declaration.player, self.users[1])
    
    def test_get_game_state(self):
        """Test dohvaćanja stanja igre putem servisa."""
        # Postavi igru u stanje za testiranje
        self.game.status = 'in_progress'
        self.game.save()
        
        # Provjera da GameRepository.get_game_state_for_player vraća stanje
        with patch('game.repositories.game_repository.GameRepository.get_game_state_for_player') as mock_get_state:
            # Mock stanje igre
            mock_state = {
                'game_id': str(self.game.id),
                'status': 'in_progress',
                'players': [],
                'teams': {'team1': [], 'team2': []},
                'scores': {'team1': 0, 'team2': 0},
                'your_team': 1
            }
            mock_get_state.return_value = mock_state
            
            # Dohvat stanja
            result = self.service.get_game_state(user_id=self.users[1].id)
            
            # Provjera da je repository pozvan
            mock_get_state.assert_called_once()
            
            # Provjera rezultata
            self.assertEqual(result, mock_state)


class ScoringServiceTest(TestCase):
    """Testovi za ScoringService."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        # Stvaranje igre za testiranje
        self.game, self.users = create_test_game()
        self.game.status = 'in_progress'
        self.game.save()
        
        # Dodjela timova
        self.game.assign_teams()
        
        # Stvaranje runde
        self.round = create_test_round(self.game, self.users[0])
        self.round.trump_suit = 'hearts'
        self.round.caller = self.users[1]
        self.round.calling_team = 1
        self.round.save()
    
    def test_calculate_card_value(self):
        """Test izračuna vrijednosti karata."""
        # Karta koja nije adut
        value = ScoringService.calculate_card_value('AS', 'hearts')  # As pik, adut herc
        self.assertEqual(value, 11)  # As vrijedi 11 bodova
        
        value = ScoringService.calculate_card_value('JS', 'hearts')  # Dečko pik, adut herc
        self.assertEqual(value, 2)  # Dečko vrijedi 2 boda kad nije adut
        
        # Karta koja je adut
        value = ScoringService.calculate_card_value('JH', 'hearts')  # Dečko herc, adut herc
        self.assertEqual(value, 20)  # Dečko adut vrijedi 20 bodova
        
        value = ScoringService.calculate_card_value('9H', 'hearts')  # Devetka herc, adut herc
        self.assertEqual(value, 14)  # Devetka adut vrijedi 14 bodova
    
    def test_validate_declaration(self):
        """Test validacije zvanja."""
        # Zvanje četiri dečka
        valid, _ = ScoringService.validate_declaration(
            'four_jacks',
            ['JS', 'JH', 'JD', 'JC']
        )
        self.assertTrue(valid)
        
        # Nevažeće zvanje (nedostaje karta)
        valid, _ = ScoringService.validate_declaration(
            'four_jacks',
            ['JS', 'JH', 'JD']
        )
        self.assertFalse(valid)
        
        # Validacija sekvence
        valid, _ = ScoringService.validate_declaration(
            'sequence_3',
            ['7H', '8H', '9H']
        )
        self.assertTrue(valid)
        
        # Nevažeća sekvenca (karte nisu u nizu)
        valid, _ = ScoringService.validate_declaration(
            'sequence_3',
            ['7H', '9H', '10H']
        )
        self.assertFalse(valid)
    
    def test_compare_declarations(self):
        """Test usporedbe zvanja po jačini."""
        # Stvaranje zvanja za usporedbu
        decl1 = Declaration(
            round=self.round,
            player=self.users[1],
            type='sequence_3',
            value=20
        )
        
        decl2 = Declaration(
            round=self.round,
            player=self.users[2],
            type='four_jacks',
            value=200
        )
        
        # Usporedba - četiri dečka jače od terce
        result = ScoringService.compare_declarations(decl1, decl2)
        self.assertEqual(result, -1)  # decl1 < decl2
        
        # Obrnuta usporedba
        result = ScoringService.compare_declarations(decl2, decl1)
        self.assertEqual(result, 1)  # decl2 > decl1
        
        # Jednaka zvanja
        decl3 = Declaration(
            round=self.round,
            player=self.users[3],
            type='sequence_3',
            value=20
        )
        
        result = ScoringService.compare_declarations(decl1, decl3)
        self.assertEqual(result, 0)  # decl1 == decl3
    
    def test_calculate_trick_points(self):
        """Test izračuna bodova za štih."""
        # Stvaranje poteza za štih
        trick_moves = [
            Move(round=self.round, player=self.users[0], card='10S'),
            Move(round=self.round, player=self.users[1], card='AS'),
            Move(round=self.round, player=self.users[2], card='KS'),
            Move(round=self.round, player=self.users[3], card='QS')
        ]
        
        # Izračun bodova - karte nisu adut
        points = ScoringService.calculate_trick_points(trick_moves, 'hearts')
        
        # Bodovi: 10 (desetka) + 11 (as) + 4 (kralj) + 3 (dama) = 28
        self.assertEqual(points, 28)
        
        # Štih s adutom
        trick_moves = [
            Move(round=self.round, player=self.users[0], card='7S'),
            Move(round=self.round, player=self.users[1], card='8S'),
            Move(round=self.round, player=self.users[2], card='JH'),  # Dečko adut
            Move(round=self.round, player=self.users[3], card='9S')
        ]
        
        # Izračun bodova
        points = ScoringService.calculate_trick_points(trick_moves, 'hearts')
        
        # Bodovi: 0 (sedmica) + 0 (osmica) + 20 (dečko adut) + 0 (devetka) = 20
        self.assertEqual(points, 20)
    
    def test_check_game_winner(self):
        """Test provjere pobjednika igre."""
        # Prvi tim dostigao bodove za pobjedu
        self.game.team1_score = 1001
        self.game.team2_score = 900
        self.game.save()
        
        is_finished, winner = ScoringService.check_game_winner(self.game)
        
        self.assertTrue(is_finished)
        self.assertEqual(winner, 1)
        
        # Drugi tim dostigao bodove za pobjedu
        self.game.team1_score = 900
        self.game.team2_score = 1050
        self.game.save()
        
        is_finished, winner = ScoringService.check_game_winner(self.game)
        
        self.assertTrue(is_finished)
        self.assertEqual(winner, 2)
        
        # Nijedan tim nije dostigao bodove za pobjedu
        self.game.team1_score = 800
        self.game.team2_score = 700
        self.game.save()
        
        is_finished, winner = ScoringService.check_game_winner(self.game)
        
        self.assertFalse(is_finished)
        self.assertIsNone(winner)