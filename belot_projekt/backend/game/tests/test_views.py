"""
Testovi za poglede (views) Belot igre.

Ovaj modul testira web i API poglede za Belot igru,
uključujući prikaz igre, pridruživanje igri, igranje poteza, itd.
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from game.models import Game, Round, Move, Declaration
from game.tests import create_test_game, create_test_round, create_test_moves

User = get_user_model()


class WebViewsTest(TestCase):
    """Testovi za web poglede igre."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.client = Client()
        
        # Stvaranje test korisnika
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
        
        # Prijava korisnika
        self.client.login(username='player1', password='testpass123')
        
        # Stvaranje test igre
        self.game = Game.objects.create(
            creator=self.user1,
            points_to_win=1001,
            is_private=False
        )
        self.game.players.add(self.user1)
    
    def test_lobby_view(self):
        """Test prikaza predvorja igre."""
        url = reverse('game:lobby')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/lobby.html')
        
        # Provjera da li predvorje prikazuje igre koje čekaju
        self.assertContains(response, 'Dostupne igre')
        
        # Provjera da li predvorje prikazuje igračeve igre
        self.assertContains(response, 'Moje igre')
    
    def test_game_create_view(self):
        """Test stvaranja nove igre putem web sučelja."""
        url = reverse('game:create')
        data = {
            'points_to_win': 1001,
            'is_private': False
        }
        
        response = self.client.post(url, data)
        
        # Provjera preusmjeravanja na detalje igre nakon stvaranja
        self.assertEqual(response.status_code, 302)
        
        # Provjera da je igra stvorena
        latest_game = Game.objects.latest('created_at')
        self.assertEqual(latest_game.creator, self.user1)
        self.assertEqual(latest_game.points_to_win, 1001)
        self.assertFalse(latest_game.is_private)
    
    def test_game_join_view(self):
        """Test pridruživanja igri putem web sučelja."""
        url = reverse('game:join')
        data = {
            'room_code': self.game.room_code
        }
        
        # Odjava prvog korisnika i prijava drugog
        self.client.logout()
        self.client.login(username='player2', password='testpass123')
        
        response = self.client.post(url, data)
        
        # Provjera preusmjeravanja na detalje igre nakon pridruživanja
        self.assertEqual(response.status_code, 302)
        
        # Provjera da se igrač pridružio igri
        self.game.refresh_from_db()
        self.assertTrue(self.game.players.filter(id=self.user2.id).exists())
    
    def test_game_detail_view(self):
        """Test prikaza detalja igre."""
        url = reverse('game:detail', args=[self.game.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/game_detail.html')
        
        # Provjera prikazanih informacija o igri
        self.assertContains(response, self.game.room_code)
        self.assertContains(response, str(self.game.points_to_win))
        
        # Provjera da samo kreator vidi gumb za pokretanje igre
        self.assertContains(response, 'start_game')
    
    def test_game_play_view(self):
        """Test prikaza sučelja za igranje."""
        # Dodavanje još 3 igrača, timova i pokretanje igre
        self.game.players.add(self.user2)
        self.game.active_players.add(self.user2)
        
        user3 = User.objects.create_user(
            username='player3',
            email='player3@example.com',
            password='testpass123'
        )
        user4 = User.objects.create_user(
            username='player4',
            email='player4@example.com',
            password='testpass123'
        )
        
        self.game.players.add(user3, user4)
        self.game.active_players.add(user3, user4)
        
        self.game.assign_teams()
        self.game.team1_players.add(self.user1, user3)
        self.game.team2_players.add(self.user2, user4)
        
        self.game.status = 'in_progress'
        self.game.save()
        
        # Stvaranje runde
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            dealer=self.user1
        )
        
        url = reverse('game:play', args=[self.game.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/game_play.html')
        
        # Provjera da li stranica sadrži ključne elemente sučelja za igru
        self.assertContains(response, 'game_state')
        self.assertContains(response, 'websocket_url')
    
    def test_game_action_start(self):
        """Test akcije pokretanja igre."""
        # Dodavanje još 3 igrača i postavljanje igre u stanje 'ready'
        self.game.players.add(self.user2)
        self.game.active_players.add(self.user2)
        
        user3 = User.objects.create_user(
            username='player3',
            email='player3@example.com',
            password='testpass123'
        )
        user4 = User.objects.create_user(
            username='player4',
            email='player4@example.com',
            password='testpass123'
        )
        
        self.game.players.add(user3, user4)
        self.game.active_players.add(user3, user4)
        
        self.game.status = 'ready'
        self.game.save()
        
        url = reverse('game:detail', args=[self.game.id])
        data = {
            'action': 'start_game'
        }
        
        response = self.client.post(url, data)
        
        # Provjera preusmjeravanja na sučelje za igranje
        self.assertEqual(response.status_code, 302)
        
        # Provjera da je igra pokrenuta
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, 'in_progress')
    
    def test_unauthorized_access(self):
        """Test neautoriziranog pristupa stranicama igre."""
        # Stvaranje igre koja nije dostupna korisniku
        game2 = Game.objects.create(
            creator=self.user2,
            points_to_win=1001,
            is_private=True
        )
        game2.players.add(self.user2)
        
        url = reverse('game:detail', args=[game2.id])
        response = self.client.get(url)
        
        # Provjera preusmjeravanja na početnu stranicu (lobby)
        self.assertEqual(response.status_code, 302)


class ApiViewsTest(TestCase):
    """Testovi za API poglede igre."""
    
    def setUp(self):
        """Postavljanje podataka za testove."""
        self.client = APIClient()
        
        # Stvaranje test korisnika
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
        
        # Prijava korisnika
        self.client.force_authenticate(user=self.user1)
    
    def test_game_list_api(self):
        """Test API-ja za dohvat liste igara."""
        # Stvaranje nekoliko test igara
        game1 = Game.objects.create(
            creator=self.user1,
            points_to_win=1001,
            is_private=False
        )
        game1.players.add(self.user1)
        
        game2 = Game.objects.create(
            creator=self.user2,
            points_to_win=701,
            is_private=True
        )
        game2.players.add(self.user2)
        
        url = reverse('api:game-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_game_create_api(self):
        """Test API-ja za stvaranje igre."""
        url = reverse('api:game-list')
        data = {
            'points_to_win': 1001,
            'is_private': False
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Provjera da je igra stvorena
        game_id = response.data['id']
        game = Game.objects.get(id=game_id)
        
        self.assertEqual(game.creator, self.user1)
        self.assertEqual(game.points_to_win, 1001)
        self.assertFalse(game.is_private)
        
        # Provjera da je kreator automatski dodan kao igrač
        self.assertTrue(game.players.filter(id=self.user1.id).exists())
    
    def test_game_join_api(self):
        """Test API-ja za pridruživanje igri."""
        game = Game.objects.create(
            creator=self.user1,
            points_to_win=1001,
            is_private=False
        )
        game.players.add(self.user1)
        
        url = reverse('api:game-join', args=[game.id])
        
        # Odjava prvog korisnika i prijava drugog
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Provjera da se igrač pridružio igri
        game.refresh_from_db()
        self.assertTrue(game.players.filter(id=self.user2.id).exists())
    
    def test_game_start_api(self):
        """Test API-ja za pokretanje igre."""
        game, users = create_test_game()
        game.status = 'ready'
        game.save()
        
        url = reverse('api:game-start', args=[game.id])
        
        # Prijava kreatora igre
        self.client.force_authenticate(user=game.creator)
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Provjera da je igra pokrenuta
        game.refresh_from_db()
        self.assertEqual(game.status, 'in_progress')
    
    def test_game_state_api(self):
        """Test API-ja za dohvat stanja igre."""
        game, users = create_test_game()
        game.assign_teams()
        game.status = 'in_progress'
        game.save()
        
        round_obj = create_test_round(game, users[0])
        
        url = reverse('api:game-state', args=[game.id])
        
        # Prijava igrača u igri
        self.client.force_authenticate(user=users[0])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Provjera osnovnih podataka o stanju igre
        self.assertEqual(response.data['game_id'], str(game.id))
        self.assertEqual(response.data['status'], game.status)
    
    def test_game_action_api(self):
        """Test API-ja za izvršavanje akcija u igri."""
        game, users = create_test_game()
        game.assign_teams()
        game.status = 'in_progress'
        game.save()
        
        round_obj = create_test_round(game, users[0])
        
        url = reverse('api:game-action', args=[game.id])
        
        # Prijava igrača na potezu (prvi nakon dealera)
        self.client.force_authenticate(user=users[1])
        
        # Test zvanja aduta
        data = {
            'action': 'call_trump',
            'trump_suit': 'hearts'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Provjera da je adut postavljen
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.trump_suit, 'hearts')
    
    def test_move_create_api(self):
        """Test API-ja za stvaranje poteza."""
        game, users = create_test_game()
        game.assign_teams()
        game.status = 'in_progress'
        game.save()
        
        round_obj = create_test_round(game, users[0])
        round_obj.trump_suit = 'hearts'
        round_obj.caller = users[1]
        round_obj.calling_team = game.get_team_for_player(users[1])
        round_obj.save()
        
        url = reverse('api:move-list')
        
        # Prijava igrača na potezu (prvi nakon dealera)
        self.client.force_authenticate(user=users[1])
        
        # Odigravanje karte
        data = {
            'round': round_obj.id,
            'card': 'AS'  # As pik
        }
        
        response = self.client.post(url, data)
        
        # Zbog složene validacije poteza, možda će trebati mockati GameService
        # Za jednostavnost testa, pretpostavljamo da je potez valjan
        
        # Provjera da je potez stvoren
        self.assertEqual(Move.objects.count(), 1)
        move = Move.objects.first()
        self.assertEqual(move.round, round_obj)
        self.assertEqual(move.player, users[1])
        self.assertEqual(move.card, 'AS')
    
    def test_declaration_create_api(self):
        """Test API-ja za stvaranje zvanja."""
        game, users = create_test_game()
        game.assign_teams()
        game.status = 'in_progress'
        game.save()
        
        round_obj = create_test_round(game, users[0])
        round_obj.trump_suit = 'hearts'
        round_obj.caller = users[1]
        round_obj.calling_team = game.get_team_for_player(users[1])
        round_obj.save()
        
        url = reverse('api:declaration-list')
        
        # Prijava igrača
        self.client.force_authenticate(user=users[1])
        
        # Prijava zvanja (terca)
        data = {
            'round': round_obj.id,
            'type': 'sequence_3',
            'suit': 'H',
            'cards': ['JH', 'QH', 'KH']
        }
        
        response = self.client.post(url, data)
        
        # Zbog složene validacije zvanja, možda će trebati mockati GameService
        # Za jednostavnost testa, pretpostavljamo da je zvanje valjano
        
        # Provjera da je zvanje stvoreno
        self.assertEqual(Declaration.objects.count(), 1)
        declaration = Declaration.objects.first()
        self.assertEqual(declaration.round, round_obj)
        self.assertEqual(declaration.player, users[1])
        self.assertEqual(declaration.type, 'sequence_3')