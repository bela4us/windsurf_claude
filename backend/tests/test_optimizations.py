from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.db import connection
import time
import json
from unittest.mock import patch, MagicMock
from channels.testing import WebsocketCommunicator
from ..utils.db_optimizations import db_optimizer
from ..utils.api_optimizations import api_optimizer
from ..middleware.websocket_middleware import WebSocketOptimizer
from ..cache.redis_cache import cache_manager
from ..game.models import Game, Player, Move
from ..game.serializers import GameSerializer

class DatabaseOptimizationsTest(TestCase):
    def setUp(self):
        self.test_data = [
            {'name': f'Test Game {i}', 'status': 'active'}
            for i in range(100)
        ]

    def test_bulk_create(self):
        start_time = time.time()
        games = db_optimizer.bulk_create(Game, self.test_data)
        bulk_time = time.time() - start_time

        start_time = time.time()
        for data in self.test_data:
            Game.objects.create(**data)
        individual_time = time.time() - start_time

        self.assertEqual(len(games), 100)
        self.assertLess(bulk_time, individual_time)

    def test_bulk_update(self):
        games = db_optimizer.bulk_create(Game, self.test_data)
        start_time = time.time()
        updated = db_optimizer.bulk_update(
            Game.objects.filter(status='active'),
            fields=['status']
        )
        bulk_time = time.time() - start_time

        start_time = time.time()
        for game in games:
            game.status = 'completed'
            game.save()
        individual_time = time.time() - start_time

        self.assertEqual(updated, 100)
        self.assertLess(bulk_time, individual_time)

    def test_optimize_query(self):
        game = Game.objects.create(name='Test Game')
        player = Player.objects.create(name='Test Player', game=game)
        
        start_time = time.time()
        optimized = db_optimizer.optimize_query(Player.objects.all())
        optimized_time = time.time() - start_time

        start_time = time.time()
        unoptimized = Player.objects.all()
        unoptimized_time = time.time() - start_time

        self.assertLess(optimized_time, unoptimized_time)

class CacheOptimizationsTest(TestCase):
    def setUp(self):
        self.test_data = {'key': 'value'}
        cache_manager.delete('test_key')

    def test_cache_set_get(self):
        start_time = time.time()
        cache_manager.set('test_key', self.test_data)
        cached_data = cache_manager.get('test_key')
        cache_time = time.time() - start_time

        start_time = time.time()
        db_data = Game.objects.create(name='Test Game')
        db_time = time.time() - start_time

        self.assertEqual(cached_data, self.test_data)
        self.assertLess(cache_time, db_time)

    def test_cache_invalidation(self):
        cache_manager.set('test_key', self.test_data)
        cache_manager.invalidate_pattern('test_*')
        self.assertIsNone(cache_manager.get('test_key'))

    def test_cache_batch_operations(self):
        test_data = {f'key_{i}': f'value_{i}' for i in range(10)}
        
        start_time = time.time()
        cache_manager.set_many(test_data)
        cached_data = cache_manager.get_many(list(test_data.keys()))
        batch_time = time.time() - start_time

        start_time = time.time()
        for key, value in test_data.items():
            cache_manager.set(key, value)
            cache_manager.get(key)
        individual_time = time.time() - start_time

        self.assertEqual(cached_data, test_data)
        self.assertLess(batch_time, individual_time)

class WebSocketOptimizationsTest(TestCase):
    async def test_rate_limiting(self):
        optimizer = WebSocketOptimizer()
        consumer_id = 'test_consumer'
        
        # Test rate limiting
        for _ in range(100):
            self.assertFalse(optimizer.should_rate_limit(consumer_id))
        
        self.assertTrue(optimizer.should_rate_limit(consumer_id))

    async def test_message_batching(self):
        optimizer = WebSocketOptimizer()
        consumer_id = 'test_consumer'
        message = {'type': 'websocket.send', 'text': 'test'}
        
        # Test batching
        for _ in range(5):
            self.assertFalse(optimizer.add_to_batch(consumer_id, message))
        
        self.assertTrue(optimizer.add_to_batch(consumer_id, message))
        batch = optimizer.get_batch(consumer_id)
        self.assertEqual(len(batch), 6)

class APIOptimizationsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_data = {'name': 'Test Game'}

    @patch('django.core.cache.cache')
    def test_api_caching(self, mock_cache):
        # Test cache hit
        mock_cache.get.return_value = self.test_data
        start_time = time.time()
        response = self.client.get(reverse('game-list'))
        cache_time = time.time() - start_time

        # Test cache miss
        mock_cache.get.return_value = None
        start_time = time.time()
        response = self.client.get(reverse('game-list'))
        db_time = time.time() - start_time

        self.assertLess(cache_time, db_time)

    def test_request_batching(self):
        # Test batch request
        batch_data = [self.test_data for _ in range(5)]
        response = self.client.post(
            reverse('game-batch'),
            data=json.dumps(batch_data),
            content_type='application/json',
            HTTP_X_BATCH_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        results = json.loads(response.content)['results']
        self.assertEqual(len(results), 5)

    def test_serialization_optimization(self):
        game = Game.objects.create(name='Test Game')
        player = Player.objects.create(name='Test Player', game=game)
        
        start_time = time.time()
        serializer = GameSerializer(game)
        optimized_time = time.time() - start_time

        start_time = time.time()
        serializer = GameSerializer(Game.objects.get(id=game.id))
        unoptimized_time = time.time() - start_time

        self.assertLess(optimized_time, unoptimized_time)

class IntegrationTest(TestCase):
    async def test_full_optimization_flow(self):
        # Test database optimizations
        games = db_optimizer.bulk_create(Game, [
            {'name': f'Test Game {i}', 'status': 'active'}
            for i in range(10)
        ])

        # Test cache optimizations
        cache_manager.set('test_games', games)
        cached_games = cache_manager.get('test_games')
        self.assertEqual(len(cached_games), 10)

        # Test API optimizations
        response = self.client.get(reverse('game-list'))
        self.assertEqual(response.status_code, 200)

        # Test WebSocket optimizations
        optimizer = WebSocketOptimizer()
        consumer_id = 'test_consumer'
        message = {'type': 'websocket.send', 'text': 'test'}
        
        for _ in range(5):
            optimizer.add_to_batch(consumer_id, message)
        
        batch = optimizer.get_batch(consumer_id)
        self.assertEqual(len(batch), 5) 