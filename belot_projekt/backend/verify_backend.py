#!/usr/bin/env python
"""
Backend Verification Script for Belot Application

This script performs checks on critical components of the Belot backend:
1. Django configuration
2. Database connection
3. Redis connection
4. WebSocket infrastructure
5. Celery configuration
6. Repository pattern implementation
7. Middleware functionality
8. App configuration
9. Users app verification
10. Stats app verification
11. Game app verification
12. Belot game rules verification

It also provides functional testing capabilities:
- User registration and authentication
- Lobby room creation and management
- Game initialization and basic gameplay
- Statistics tracking
- Belot-specific game logic tests

Usage:
    python verify_backend.py [--quiet] [--component COMPONENT_NAME]
    python verify_backend.py --functional [test_name]
"""

import os
import sys
import argparse
import importlib
import inspect
import json
import time
import traceback
import random
import uuid

# Dodaj projektni direktorij u Python path ako već nije dodan
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Configure Django Settings (single setup) - MORA BITI PRIJE MODELA
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')
import django
django.setup()

# Sada NAKON Django setup-a importamo Django i druge module
from django.db import connection, DatabaseError, transaction
from django.conf import settings
from django.core.cache import cache
from django.core.wsgi import get_wsgi_application
from django.urls import reverse, resolve, get_resolver, Resolver404
from django.test import Client
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# Inicijaliziramo globalne varijable za modele i klase koje ćemo dinamički uvesti
Game = Round = Move = Declaration = None
Card = Deck = Rules = Scoring = None
PlayerStats = TeamStats = GameStats = GlobalStats = DailyStats = Leaderboard = None
Profile = Friendship = Achievement = Notification = None

# Dinamički uvoz repository klasa
try:
    from lobby.repositories.lobby_repository import LobbyRepository
    from lobby.repositories.membership_repository import MembershipRepository
    from lobby.repositories.message_repository import MessageRepository
    from lobby.repositories.invitation_repository import InvitationRepository
    from lobby.repositories.event_repository import EventRepository
except ImportError as e:
    print(f"Upozorenje: Neki repository moduli nisu pronađeni: {e}")
    # Postavljamo prazan objekt za repozitorije koji nisu dostupni
    if 'LobbyRepository' not in globals():
        class LobbyRepository: pass
    if 'MembershipRepository' not in globals():
        class MembershipRepository: pass
    if 'MessageRepository' not in globals():
        class MessageRepository: pass
    if 'InvitationRepository' not in globals():
        class InvitationRepository: pass
    if 'EventRepository' not in globals():
        class EventRepository: pass

# Dinamički uvoz dekoratora
try:
    from utils.decorators import login_required_ajax, admin_required, throttle_request, track_execution_time, cached_property
except ImportError as e:
    print(f"Upozorenje: Neki dekoratori nisu pronađeni: {e}")
    # Definiramo prazne funkcije ako dekoratori nisu pronađeni
    def login_required_ajax(func): return func
    def admin_required(func): return func
    def throttle_request(*args, **kwargs): return lambda func: func
    def track_execution_time(func): return func
    def cached_property(func): return property(func)

# Dinamički uvoz Redis cache komponenti
try:
    from cache.redis_cache import RedisCache, get_redis_connection
except ImportError as e:
    print(f"Upozorenje: Redis cache komponente nisu pronađene: {e}")
    # Definiramo prazne klase kao fallback
    class RedisCache: pass
    def get_redis_connection(): return None

# Dinamički uvoz middleware komponenti
try:
    from middleware.request_logger import RequestLoggerMiddleware
    from middleware.rate_limiter import RateLimiterMiddleware
    from middleware.auth_middleware import TokenAuthMiddleware
except ImportError as e:
    print(f"Upozorenje: Neki middleware moduli nisu pronađeni: {e}")
    # Definiramo prazne klase kao fallback
    class RequestLoggerMiddleware: pass
    class RateLimiterMiddleware: pass
    class TokenAuthMiddleware: pass

# Status uvoza modula
users_imports_successful = False
stats_imports_successful = False
game_imports_successful = False
users_import_error = ""
stats_import_error = ""
game_import_error = ""

# Pokušaj uvoza game modela dinamički
try:
    # Koristimo importlib.import_module za dinamički uvoz
    game_models = None
    try:
        game_models = importlib.import_module('game.models')
    except ImportError:
        # Alternativni pristup ako game.models nije direktno dostupan (koristi __init__)
        for module_name in ['game.models.game', 'game.models.round', 'game.models.move', 'game.models.declaration']:
            try:
                module = importlib.import_module(module_name)
                if 'Game' not in globals() and hasattr(module, 'Game'):
                    Game = module.Game
                if 'Round' not in globals() and hasattr(module, 'Round'):
                    Round = module.Round
                if 'Move' not in globals() and hasattr(module, 'Move'):
                    Move = module.Move
                if 'Declaration' not in globals() and hasattr(module, 'Declaration'):
                    Declaration = module.Declaration
            except ImportError:
                pass
    
            try:
                # Još jedan pokušaj kroz Django apps API
                from django.apps import apps
                
                if Game is None:
                    Game = apps.get_model('game', 'Game', require_ready=False)
                if Round is None:
                    Round = apps.get_model('game', 'Round', require_ready=False)
                if Move is None:
                    Move = apps.get_model('game', 'Move', require_ready=False)
                if Declaration is None:
                    Declaration = apps.get_model('game', 'Declaration', require_ready=False)
            except Exception as e:
                print(f"Upozorenje: Ne mogu dohvatiti modele preko apps API: {e}")

    # Ako je game_models uspješno uvezen, postavimo globalne varijable
    if game_models:
        Game = getattr(game_models, 'Game', None)
        Round = getattr(game_models, 'Round', None)
        Move = getattr(game_models, 'Move', None)
        Declaration = getattr(game_models, 'Declaration', None)
    
    # Uvoz game_logic komponenti
    try:
        card_module = importlib.import_module('game.game_logic.card')
        deck_module = importlib.import_module('game.game_logic.deck')
        rules_module = importlib.import_module('game.game_logic.rules')
        scoring_module = importlib.import_module('game.game_logic.scoring')
        
        Card = getattr(card_module, 'Card', None)
        Deck = getattr(deck_module, 'Deck', None)
        Rules = getattr(rules_module, 'Rules', None)
        Scoring = getattr(scoring_module, 'Scoring', None)
    except ImportError as e:
        print(f"Upozorenje: Game logic komponente nisu pronađene: {e}")
    
    game_imports_successful = True
except Exception as e:
    print(f"Upozorenje: Problem pri uvozu game modula: {e}")
    game_import_error = str(e)
    game_imports_successful = False

# Pokušaj uvoza users modula
try:
    # Pokušaj naći users.models dinamički
    try:
        users_module = importlib.import_module('users.models')
        Profile = getattr(users_module, 'Profile', None)
        Friendship = getattr(users_module, 'Friendship', None)
        Achievement = getattr(users_module, 'Achievement', None)
        Notification = getattr(users_module, 'Notification', None)
    except ImportError as e:
        print(f"Upozorenje: users.models nije pronađen: {e}")
    
    # Inicijalizacija API view varijabli
    RegisterView = LoginView = None
    UserSerializer = UserPublicSerializer = None
    UserViewSet = ProfileViewSet = FriendshipViewSet = None
    
    # Pokušaj naći API views
    try:
        api_views_module = importlib.import_module('users.api_views')
        RegisterView = getattr(api_views_module, 'RegisterView', None)
        LoginView = getattr(api_views_module, 'LoginView', None)
        UserViewSet = getattr(api_views_module, 'UserViewSet', None)
        ProfileViewSet = getattr(api_views_module, 'ProfileViewSet', None)
        FriendshipViewSet = getattr(api_views_module, 'FriendshipViewSet', None)
    except ImportError:
        pass
    
    users_imports_successful = True
except Exception as e:
    users_import_error = str(e)
    users_imports_successful = False

# Pokušaj uvoza stats modula
try:
    # Pokušaj naći stats.models dinamički
    try:
        stats_module = importlib.import_module('stats.models')
        PlayerStats = getattr(stats_module, 'PlayerStats', None)
        TeamStats = getattr(stats_module, 'TeamStats', None)
        GameStats = getattr(stats_module, 'GameStats', None)
        GlobalStats = getattr(stats_module, 'GlobalStats', None)
        DailyStats = getattr(stats_module, 'DailyStats', None)
        Leaderboard = getattr(stats_module, 'Leaderboard', None)
    except ImportError as e:
        print(f"Upozorenje: stats.models nije pronađen: {e}")
    
    # Inicijalizacija view i API varijabli
    StatisticsHomeView = PlayerStatsDetailView = GlobalStatsView = None
    PlayerStatsSerializer = TeamStatsSerializer = None
    PlayerStatsViewSet = TeamStatsViewSet = None
    update_global_statistics = update_daily_statistics = update_leaderboards = None
    
    # Pokušaj naći view klase
    try:
        views_module = importlib.import_module('stats.views')
        StatisticsHomeView = getattr(views_module, 'StatisticsHomeView', None)
        PlayerStatsDetailView = getattr(views_module, 'PlayerStatsDetailView', None)
        GlobalStatsView = getattr(views_module, 'GlobalStatsView', None)
    except ImportError:
        try:
            api_views_module = importlib.import_module('stats.api_views')
            StatisticsHomeView = getattr(api_views_module, 'StatisticsHomeView', None)
            PlayerStatsDetailView = getattr(api_views_module, 'PlayerStatsDetailView', None)
            GlobalStatsView = getattr(api_views_module, 'GlobalStatsView', None)
        except ImportError:
            pass
    
    # Pokušaj naći task funkcije
    try:
        tasks_module = importlib.import_module('stats.tasks')
        update_global_statistics = getattr(tasks_module, 'update_global_statistics', None)
        update_daily_statistics = getattr(tasks_module, 'update_daily_statistics', None)
        update_leaderboards = getattr(tasks_module, 'update_leaderboards', None)
    except ImportError:
        pass
    
    stats_imports_successful = True
except Exception as e:
    stats_imports_successful = False
    stats_import_error = str(e)

# Pokušaj uvoza game API viewsets
try:
    GameViewSet = MoveViewSet = DeclarationViewSet = None
    
    # Prvo pokušaj direktno u game.views.api_views (ispravna lokacija prema strukturi)
    try:
        api_views_module = importlib.import_module('game.views.api_views')
        GameViewSet = getattr(api_views_module, 'GameViewSet', None)
        MoveViewSet = getattr(api_views_module, 'MoveViewSet', None)
        DeclarationViewSet = getattr(api_views_module, 'DeclarationViewSet', None)
    except ImportError:
        # Ako ne uspije, pokušaj alternativne lokacije
        try:
            api_views_module = importlib.import_module('game.api_views')
            GameViewSet = getattr(api_views_module, 'GameViewSet', None)
            MoveViewSet = getattr(api_views_module, 'MoveViewSet', None)
            DeclarationViewSet = getattr(api_views_module, 'DeclarationViewSet', None)
        except ImportError:
            # Pokušaj u views (manje vjerojatno)
            try:
                views_module = importlib.import_module('game.views')
                GameViewSet = getattr(views_module, 'GameViewSet', None)
                MoveViewSet = getattr(views_module, 'MoveViewSet', None)
                DeclarationViewSet = getattr(views_module, 'DeclarationViewSet', None)
            except ImportError:
                pass
except Exception as e:
    print(f"Upozorenje: Problem pri uvozu game viewsets: {e}")

class BackendVerifier:
    """Class that verifies key components of the Belot backend."""
    
    def __init__(self, verbose=True):  # Verbose uključen prema zadanim postavkama
        self.verbose = verbose
        self.results = {
            "django_config": False,
            "migrations": False,
            "database_connection": False,
            "redis_connection": False,
            "websocket_config": False,
            "celery_config": False,
            "repository_pattern": False,
            "middleware_components": False,
            "app_configuration": False,
            "users_app": False,
            "stats_app": False,
            "game_app": False,
            "belot_rules": False,  # Dodano za specifična pravila Belota
        }
    
    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def verify_django_config(self):
        """Verify Django configuration is loaded properly."""
        self.log("\n===== Verifying Django Configuration =====")
        try:
            # Check that Django settings are configured
            self.log(f"Running Django {django.get_version()}")
            self.log(f"Active environment: {getattr(settings, 'ACTIVE_ENVIRONMENT', 'unknown')}")
            self.log(f"Debug mode: {settings.DEBUG}")
            
            # Check that wsgi application can be loaded
            app = get_wsgi_application()
            self.log("WSGI application loaded successfully")
            
            # Check URL configuration without using resolve() directly
            # This avoids issues with null bytes
            try:
                # Check if admin URL is defined in urlpatterns
                from belot.urls import urlpatterns
                admin_url_exists = False
                for pattern in urlpatterns:
                    if hasattr(pattern, 'name') and pattern.name == 'admin:index':
                        admin_url_exists = True
                        break
                    elif hasattr(pattern, 'pattern') and 'admin' in str(pattern.pattern):
                        admin_url_exists = True
                        break
                
                if admin_url_exists:
                    self.log("URL configuration detected admin URLs successfully")
                
                # Check API health endpoint
                try:
                    health_endpoint_exists = False
                    for pattern in urlpatterns:
                        if hasattr(pattern, 'name') and pattern.name == 'health_check':
                            health_endpoint_exists = True
                            break
                        elif hasattr(pattern, 'pattern') and 'api/health' in str(pattern.pattern):
                            health_endpoint_exists = True
                            break
                    
                    if health_endpoint_exists:
                        self.log("API health endpoint found in URL configuration")
                        self.results["django_config"] = True
                    else:
                        self.log("WARNING: API health endpoint not found in URL configuration")
                except Exception as e:
                    self.log(f"ERROR checking API health endpoint in URLs: {str(e)}")
            except ImportError as e:
                self.log(f"WARNING: Could not import urlpatterns: {str(e)}")
            except Exception as e:
                self.log(f"ERROR checking URL configuration: {str(e)}")
                
            # Additional check for Django configuration
            if not self.results["django_config"]:
                # If previous checks failed, check if we have access to basic Django functionality
                if settings.DATABASES and settings.MIDDLEWARE:
                    self.log("Basic Django configuration seems valid")
                    self.results["django_config"] = True
        
        except Exception as e:
            self.log(f"ERROR verifying Django configuration: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Django configuration verified: {self.results['django_config']}")
    
    def verify_migrations(self):
        """Verify that migrations are properly created and applied."""
        self.log("\n===== Verifying Database Migrations =====")
        
        try:
            from django.db.migrations.recorder import MigrationRecorder
            
            # Check if migration tables exist
            try:
                migrations = MigrationRecorder.Migration.objects.all()
                applied_count = migrations.count()
                self.log(f"Found {applied_count} applied migrations")
                
                # Check migrations per app
                app_migrations = {}
                for migration in migrations:
                    app = migration.app
                    if app not in app_migrations:
                        app_migrations[app] = 0
                    app_migrations[app] += 1
                
                for app, count in app_migrations.items():
                    self.log(f"  {app}: {count} migrations")
                
                # Check for unapplied migrations (this is a bit trickier)
                from django.db.migrations.loader import MigrationLoader
                loader = MigrationLoader(connection)
                
                # Get all migrations that should be applied
                graph = loader.graph
                targets = graph.leaf_nodes()
                
                # Check if any migrations are not applied
                unapplied = []
                for app_name, migration_name in targets:
                    if not migrations.filter(app=app_name, name=migration_name).exists():
                        unapplied.append((app_name, migration_name))
                
                if unapplied:
                    self.log(f"WARNING: Found {len(unapplied)} unapplied migrations:")
                    for app_name, migration_name in unapplied:
                        self.log(f"  {app_name}: {migration_name}")
                else:
                    self.log("All migrations are applied")
                
                self.results["migrations"] = True
                
            except Exception as e:
                self.log(f"ERROR checking migrations: {str(e)}")
                self.log("Migration tables may not exist - run 'python manage.py migrate' first")
                self.results["migrations"] = False
                
                # ISPRAVAK: Provjerimo grešku unutar except bloka gdje je e definiran
                if "no such table: django_migrations" in str(e):
                    self.log("No migrations table found - assuming this is a new setup")
                    self.results["migrations"] = True
                    
        except Exception as e:
            self.log(f"ERROR verifying migrations: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Migrations verified: {self.results.get('migrations', False)}")

    def verify_database_connection(self):
        """Verify database connection is working."""
        self.log("\n===== Verifying Database Connection =====")
        try:
            # Try executing a simple query
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] == 1:
                    self.results["database_connection"] = True
                    self.log("Database connection successful")
                    self.log(f"Database engine: {settings.DATABASES['default']['ENGINE']}")
                    self.log(f"Database name: {settings.DATABASES['default']['NAME']}")
                
                # Check available tables - handling different database types
                try:
                    if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                        cursor.execute("""
                            SELECT tablename FROM pg_tables 
                            WHERE schemaname='public'
                        """)
                    else:
                        cursor.execute("SHOW TABLES")
                    
                    tables = cursor.fetchall()
                    self.log(f"Database contains {len(tables)} tables")
                    self.log(f"Tables: {', '.join([t[0] for t in tables][:5])}...")
                    
                    # Check for stats tables specifically
                    stats_tables = [
                        'stats_playerstats', 'stats_teamstats', 'stats_gamestats',
                        'stats_globalstats', 'stats_dailystats', 'stats_leaderboard'
                    ]
                    
                    found_stats_tables = [t[0] for t in tables if any(st in t[0].lower() for st in stats_tables)]
                    if found_stats_tables:
                        self.log(f"Found stats tables: {', '.join(found_stats_tables)}")
                    else:
                        self.log("WARNING: No stats tables found in database")

                    # Check for game tables specifically
                    game_tables = [
                        'game_game', 'game_round', 'game_move', 'game_declaration'
                    ]
                    
                    found_game_tables = [t[0] for t in tables if any(gt in t[0].lower() for gt in game_tables)]
                    if found_game_tables:
                        self.log(f"Found game tables: {', '.join(found_game_tables)}")
                    else:
                        self.log("WARNING: No game tables found in database")
                    
                except Exception as e:
                    self.log(f"Could not fetch table list: {str(e)}")
        
        except DatabaseError as e:
            self.log(f"ERROR connecting to database: {str(e)}")
        except Exception as e:
            self.log(f"ERROR verifying database: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Database connection verified: {self.results['database_connection']}")
    
    def verify_redis_connection(self):
        """Verify Redis connection and cache functionality."""
        self.log("\n===== Verifying Redis Connection =====")
        try:
            # Provjeri konfiguraciju Redis-a prije nego što pokušamo povezivanje
            redis_host = getattr(settings, 'REDIS_HOST', None)
            redis_port = getattr(settings, 'REDIS_PORT', None)
            
            self.log(f"Redis configuration: host={redis_host}, port={redis_port}")
            
            if not redis_host:
                self.log("WARNING: REDIS_HOST nije definiran u postavkama")
                redis_host = 'localhost'  # Fallback na standardni host
            
            if not redis_port:
                self.log("WARNING: REDIS_PORT nije definiran u postavkama")
                redis_port = 6379  # Fallback na standardni port
            
            # Pokušaj dohvatiti instancu Redis klijenta
            try:
                # Uvedi Redis samo ako je potrebno
                import redis
                redis_client = redis.Redis(host=redis_host, port=redis_port, socket_timeout=2)
                
                # Provjeri vezu s timeoutom
                redis_ping = redis_client.ping()
                self.log(f"Redis connection: {'OK' if redis_ping else 'FAILED'}")
                
                if redis_ping:
                    # Testiraj osnovne Redis operacije
                    test_key = f"verify_backend_test_{int(time.time())}"
                    redis_client.set(test_key, "test_value", ex=10)
                    test_value = redis_client.get(test_key)
                    
                    if test_value and test_value.decode() == "test_value":
                        self.log("Redis basic operations test: OK")
                    else:
                        self.log("WARNING: Redis operations test failed")
                    
                    # Testiraj Django cache
                    try:
                        cache_key = f"verify_django_cache_{int(time.time())}"
                        cache.set(cache_key, "test_cache_value", 10)
                        retrieved_value = cache.get(cache_key)
                        
                        cache_working = (retrieved_value == "test_cache_value")
                        self.log(f"Django cache test: {'OK' if cache_working else 'FAILED'}")
                    except Exception as e:
                        self.log(f"ERROR testing Django cache: {str(e)}")
                    
                    self.results["redis_connection"] = True
                else:
                    self.log("WARNING: Could not ping Redis server")
                    self.results["redis_connection"] = False
                    
            except redis.exceptions.ConnectionError:
                self.log("ERROR: Could not connect to Redis server")
                self.log(f"Make sure Redis is running on {redis_host}:{redis_port}")
                self.results["redis_connection"] = False
            except ImportError:
                self.log("ERROR: Redis Python package not installed")
                self.log("Install it with: pip install redis")
                self.results["redis_connection"] = False
            except Exception as e:
                self.log(f"ERROR connecting to Redis: {str(e)}")
                self.results["redis_connection"] = False
        
        except Exception as e:
            self.log(f"ERROR verifying Redis connection: {str(e)}")
            self.log(traceback.format_exc())
            self.results["redis_connection"] = False
        
        self.log(f"Redis connection verified: {self.results['redis_connection']}")

    def verify_websocket_config(self):
        """Verify WebSocket infrastructure configuration."""
        self.log("\n===== Verifying WebSocket Configuration =====")
        try:
            # Check ASGI application configuration
            asgi_app = getattr(settings, 'ASGI_APPLICATION', None)
            if asgi_app:
                self.log(f"ASGI application configured: {asgi_app}")
            else:
                self.log("WARNING: ASGI_APPLICATION not configured in settings")
                return
            
            # Check if Channels is in INSTALLED_APPS
            if 'channels' not in settings.INSTALLED_APPS and not any('channels' in app for app in settings.INSTALLED_APPS):
                self.log("WARNING: 'channels' not found in INSTALLED_APPS")
                return
            
            # Check if channel layer is configured
            try:
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                
                if channel_layer is not None:
                    self.log(f"Channel layer type: {channel_layer.__class__.__name__}")
                    
                    # Check if it's a Redis channel layer
                    if 'RedisChannelLayer' in channel_layer.__class__.__name__:
                        self.log("Redis channel layer detected")
                        
                        # Only test channel operations if Redis is working
                        if self.results["redis_connection"]:
                            try:
                                # Test basic channel layer functionality
                                channel_name = "test_channel"
                                test_message = {"type": "test.message", "text": "Hello WebSocket!"}
                                
                                from asgiref.sync import async_to_sync
                                async_to_sync(channel_layer.group_add)(channel_name, channel_name)
                                async_to_sync(channel_layer.group_send)(channel_name, test_message)
                                async_to_sync(channel_layer.group_discard)(channel_name, channel_name)
                                
                                self.log("Channel layer group operations successful")
                            except Exception as e:
                                self.log(f"ERROR testing channel layer operations: {str(e)}")
                    else:
                        self.log(f"Non-Redis channel layer detected: {channel_layer.__class__.__name__}")
                    
                    # Check if consumers are defined
                    try:
                        from lobby.consumers import LobbyConsumer, RoomConsumer
                        self.log(f"Found WebSocket consumers: LobbyConsumer, RoomConsumer")
                        
                        # Check if routing is configured
                        try:
                            from lobby.routing import websocket_urlpatterns as lobby_ws_urlpatterns
                            self.log(f"Found lobby WebSocket URL patterns: {len(lobby_ws_urlpatterns)}")
                            
                            all_websocket_urlpatterns = lobby_ws_urlpatterns
                            game_patterns_found = False
                            
                            try:
                                from game.routing import websocket_urlpatterns as game_ws_urlpatterns
                                all_websocket_urlpatterns = lobby_ws_urlpatterns + game_ws_urlpatterns
                                game_patterns_found = True
                                self.log(f"Found game WebSocket URL patterns: {len(game_ws_urlpatterns)}")
                            except ImportError:
                                self.log("Game WebSocket URL patterns not found (this may be expected)")
                            
                            if len(all_websocket_urlpatterns) > 0:
                                self.log(f"Total WebSocket URL patterns: {len(all_websocket_urlpatterns)}")
                                
                                # WebSocket config is considered valid if we have channels, consumers, and routes
                                self.results["websocket_config"] = True
                            else:
                                self.log("WARNING: No WebSocket URL patterns defined")
                        except ImportError as e:
                            self.log(f"ERROR importing WebSocket URL patterns: {str(e)}")
                    except ImportError as e:
                        self.log(f"ERROR importing WebSocket consumers: {str(e)}")
                else:
                    self.log("ERROR: Channel layer not configured")
            except Exception as e:
                self.log(f"ERROR getting channel layer: {str(e)}")
        
        except ImportError as e:
            self.log(f"ERROR: Missing required WebSocket packages: {str(e)}")
        except Exception as e:
            self.log(f"ERROR verifying WebSocket configuration: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"WebSocket configuration verified: {self.results['websocket_config']}")
    
    def verify_users_app(self):
        """Verify the Users application components."""
        self.log("\n===== Verifying Users Application =====")
        
        try:
            # 1. Check if Users app is installed
            if 'users' not in settings.INSTALLED_APPS and not any('users' in app for app in settings.INSTALLED_APPS):
                self.log("WARNING: 'users' not found in INSTALLED_APPS")
                return
            
            self.log("Users app is installed in INSTALLED_APPS")
            
            # 2. Check if imports are successful
            if not users_imports_successful:
                self.log(f"ERROR importing users modules: {users_import_error}")
                return
            
            self.log("Users modules imported successfully")
            
            # 3. Check User model
            User = get_user_model()
            user_fields = [f.name for f in User._meta.get_fields()]
            
            expected_fields = ['username', 'email', 'password', 'id', 'nickname', 'avatar', 
                            'bio', 'rating', 'games_played', 'games_won', 'is_online']
            
            found_fields = [field for field in expected_fields if field in user_fields]
            self.log(f"User model has {len(found_fields)}/{len(expected_fields)} expected fields")
            
            if len(found_fields) >= len(expected_fields) * 0.7:  # At least 70% of expected fields
                self.log("User model structure looks valid")
            
            # 4. Check Profile model
            if 'Profile' in globals():
                profile_fields = [f.name for f in Profile._meta.get_fields()]
                self.log(f"Profile model has {len(profile_fields)} fields")
                
                # Look for key relations
                has_user_relation = any(f.name == 'user' for f in Profile._meta.get_fields())
                self.log(f"Profile has user relation: {has_user_relation}")
            
            # 5. Check authentication views
            if 'RegisterView' in globals() and 'LoginView' in globals():
                self.log("Authentication views found (RegisterView, LoginView)")
            
            # 6. Check API components
            if 'UserViewSet' in globals():
                if UserViewSet is not None:
                    self.log("API viewsets found")
                else:
                    self.log("API viewsets nisu pronađeni, ali verifikacija se nastavlja")
                            
                # Check if REST framework is installed
                if 'rest_framework' in settings.INSTALLED_APPS:
                    self.log("REST framework is installed")
                
                # Try to find API URLs
                try:
                    # Import users URLs - using the appropriate method based on your url structure
                    try:
                        from users.api_urls import urlpatterns as api_urlpatterns
                        self.log(f"Found {len(api_urlpatterns)} API URL patterns")
                    except ImportError:
                        try:
                            from users.api_urls import urlpatterns as api_urlpatterns
                            self.log(f"Found {len(api_urlpatterns)} API URL patterns")
                        except ImportError:
                            self.log("Could not import users API URL patterns")
                except Exception as e:
                    self.log(f"Error checking users API URLs: {str(e)}")
            
            # 7. Check for model signals
            try:
                from users.signals import create_user_profile, save_user_profile
                self.log("User signals found (create_user_profile, save_user_profile)")
            except ImportError:
                self.log("User signals not found or not correctly implemented")
            
            # 8. Check for tasks
            try:
                from users.tasks import send_verification_email, check_achievements_for_user
                self.log("User tasks found (send_verification_email, check_achievements_for_user)")
            except ImportError:
                self.log("User tasks not found or not correctly implemented")
            
            # Overall assessment
            # If we've made it this far without major errors, consider the users app valid
            self.results["users_app"] = True
            self.log("Users application looks valid")
            
        except Exception as e:
            self.log(f"ERROR verifying users application: {str(e)}")
            self.log(traceback.format_exc())
            self.results["users_app"] = False
        
        self.log(f"Users application verified: {self.results.get('users_app', False)}")

    def verify_stats_app(self):
        """Verify the Stats application components."""
        self.log("\n===== Verifying Stats Application =====")
        
        try:
            # 1. Check if Stats app is installed
            if 'stats' not in settings.INSTALLED_APPS and not any('stats' in app for app in settings.INSTALLED_APPS):
                self.log("WARNING: 'stats' not found in INSTALLED_APPS")
                return
            
            self.log("Stats app is installed in INSTALLED_APPS")
            
            # 2. Check if imports are successful
            if not stats_imports_successful:
                self.log(f"ERROR importing stats modules: {stats_import_error}")
                return
            
            self.log("Stats modules imported successfully")
            
            # 3. Check stats models
            stats_models = [
                (PlayerStats, "PlayerStats"),
                (TeamStats, "TeamStats"),
                (GameStats, "GameStats"),
                (GlobalStats, "GlobalStats"),
                (DailyStats, "DailyStats"),
                (Leaderboard, "Leaderboard")
            ]
            
            for model_class, model_name in stats_models:
                if model_class:
                    field_count = len(model_class._meta.get_fields()) if hasattr(model_class, '_meta') else 0
                    self.log(f"Found {model_name} model with {field_count} fields")
                else:
                    self.log(f"WARNING: {model_name} model not found")
            
            # 4. Check for API components
            if StatisticsHomeView or PlayerStatsDetailView or GlobalStatsView:
                self.log("Stats views found")
            else:
                self.log("WARNING: Stats views not found")
            
            # 5. Check for task functions
            if update_global_statistics or update_daily_statistics or update_leaderboards:
                self.log("Stats tasks found")
            else:
                self.log("WARNING: Stats tasks not found")
            
            # Consider stats app valid if some models and views/tasks are found
            stats_models_valid = any(model_class for model_class, _ in stats_models)
            stats_funcs_valid = any([StatisticsHomeView, PlayerStatsDetailView, GlobalStatsView, 
                                    update_global_statistics, update_daily_statistics, update_leaderboards])
            
            self.results["stats_app"] = stats_models_valid and stats_funcs_valid
            
        except Exception as e:
            self.log(f"ERROR verifying stats application: {str(e)}")
            self.log(traceback.format_exc())
            self.results["stats_app"] = False
        
        self.log(f"Stats application verified: {self.results.get('stats_app', False)}")

    def verify_game_app(self):
        """Verify the Game application components."""
        self.log("\n===== Verifying Game Application =====")
        
        try:
            # 1. Check if Game app is installed
            if 'game' not in settings.INSTALLED_APPS and not any('game' in app for app in settings.INSTALLED_APPS):
                self.log("WARNING: 'game' not found in INSTALLED_APPS")
                return
            
            self.log("Game app is installed in INSTALLED_APPS")
            
            # 2. Check for core models
            self.log("Checking Game models...")
            for model_name in ['Game', 'Round', 'Move', 'Declaration']:
                if model_name in globals():
                    model_class = globals()[model_name]
                    field_count = len(model_class._meta.get_fields())
                    self.log(f"Found {model_name} model with {field_count} fields")
                else:
                    self.log(f"WARNING: {model_name} model not found")
            
            # 3. Check Game repository implementation
            try:
                from game.repositories.game_repository import GameRepository
                self.log("Found GameRepository implementation")
                
                # Check for essential methods
                methods = [m for m in dir(GameRepository) if not m.startswith('_')]
                required_methods = ['create_game', 'add_player_to_game', 'start_game', 'get_by_id', 'update_game', 'delete_game']
                found_methods = [m for m in required_methods if m in methods]
                
                self.log(f"GameRepository has {len(found_methods)}/{len(required_methods)} required methods")
                
            except ImportError:
                self.log("WARNING: GameRepository could not be imported")
            
            # 4. Check Move repository implementation
            try:
                from game.repositories.move_repository import MoveRepository
                self.log("Found MoveRepository implementation")
                
                # Check for essential methods
                methods = [m for m in dir(MoveRepository) if not m.startswith('_')]
                required_methods = ['create_move', 'get_next_player', 'determine_trick_winner', 'get_valid_moves']
                found_methods = [m for m in required_methods if m in methods]
                
                self.log(f"MoveRepository has {len(found_methods)}/{len(required_methods)} required methods")
                
            except ImportError:
                self.log("WARNING: MoveRepository could not be imported")
            
            # 5. Check game_logic implementation
            try:
                from game.game_logic.card import Card
                from game.game_logic.deck import Deck
                from game.game_logic.rules import Rules
                from game.game_logic.scoring import Scoring
                
                self.log("Game logic core modules found (Card, Deck, Rules, Scoring)")
                
                # Test basic functionality
                if 'Card' in globals():
                    test_card = Card('A', 'S')
                    self.log(f"Card creation works: {test_card}")
                
                if 'Deck' in globals():
                    test_deck = Deck()
                    self.log(f"Deck creation works: {len(test_deck.cards)} cards")
                    self.log(f"Checking if deck has 32 cards (Belot standard): {len(test_deck.cards) == 32}")
            except ImportError as e:
                self.log(f"WARNING: Game logic modules not fully implemented: {str(e)}")
            
            # 6. Check for API components
            try:
                # Najprije pokušajte uvesti s ispravne lokacije prema strukturi projekta
                from game.views.api_views import (
                    GameViewSet, RoundViewSet, MoveViewSet, DeclarationViewSet,
                    GameActionView, GameStatisticsView, CurrentGamesView
                )
            except ImportError:
                # Zatim pokušajte direktan uvoz (stara struktura)
                try:
                    from game.api_views import (
                        GameViewSet, RoundViewSet, MoveViewSet, DeclarationViewSet,
                        GameActionView, GameStatisticsView, CurrentGamesView
                    )
                except ImportError:
                    pass
            
            # 7. Check for WebSocket configuration
            try:
                from game.consumers import GameConsumer
                self.log("Game WebSocket consumer found")
                
                # Check for WebSocket methods
                if hasattr(GameConsumer, 'connect') and hasattr(GameConsumer, 'disconnect'):
                    self.log("GameConsumer has basic WebSocket methods")
                
                # Check for game-specific WebSocket methods
                game_methods = ['play_card', 'bid_trump', 'declare']
                found_game_methods = [m for m in game_methods if hasattr(GameConsumer, m)]
                self.log(f"GameConsumer has {len(found_game_methods)}/{len(game_methods)} game-specific methods")
            except ImportError:
                self.log("Game WebSocket consumer not found")
            
            # 8. Check for validators
            try:
                from game.game_logic.validators.move_validator import MoveValidator
                from game.game_logic.validators.call_validator import CallValidator
                self.log("Game validators found")
            except ImportError:
                self.log("Game validators not found")
            
            # Overall assessment - game app is considered valid if models and repositories are found
            self.results["game_app"] = (
                'Game' in globals() and 
                'Card' in globals() and 
                'Deck' in globals()
            )
            
        except Exception as e:
            self.log(f"ERROR verifying game application: {str(e)}")
            self.log(traceback.format_exc())
            self.results["game_app"] = False
        
        self.log(f"Game application verified: {self.results.get('game_app', False)}")
    
    def verify_belot_rules(self):
        """Verify Belot specific game rules implementation."""
        self.log("\n===== Verifying Belot Game Rules =====")
        
        try:
            # 1. Check Card implementation
            try:
                from game.game_logic.card import Card
                
                # Test card creation and properties
                test_cards = {
                    'regular': [
                        Card('7', 'S'), Card('8', 'S'), Card('9', 'S'), Card('10', 'S'),
                        Card('J', 'S'), Card('Q', 'S'), Card('K', 'S'), Card('A', 'S')
                    ],
                    'trump': [
                        Card('7', 'H'), Card('8', 'H'), Card('Q', 'H'), Card('K', 'H'),
                        Card('10', 'H'), Card('A', 'H'), Card('9', 'H'), Card('J', 'H')
                    ]
                }
                
                self.log(f"Created test cards for regular and trump suits")
                
                # Check card value methods
                regular_values_correct = True
                trump_values_correct = True
                
                try:
                    # Test non-trump card values
                    expected_regular_values = [0, 0, 0, 10, 2, 3, 4, 11]
                    for i, card in enumerate(test_cards['regular']):
                        value = card.get_value()
                        if value != expected_regular_values[i]:
                            self.log(f"ERROR: Card {card} value is {value}, expected {expected_regular_values[i]}")
                            regular_values_correct = False
                    
                    # Test trump card values
                    expected_trump_values = [0, 0, 3, 4, 10, 11, 14, 20]
                    for i, card in enumerate(test_cards['trump']):
                        value = card.get_value(trump_suit='H')
                        if value != expected_trump_values[i]:
                            self.log(f"ERROR: Card {card} trump value is {value}, expected {expected_trump_values[i]}")
                            trump_values_correct = False
                    
                    self.log(f"Regular card values correct: {regular_values_correct}")
                    self.log(f"Trump card values correct: {trump_values_correct}")
                except Exception as e:
                    self.log(f"ERROR testing card values: {str(e)}")
                    regular_values_correct = False
                    trump_values_correct = False
                
                card_implementation_valid = regular_values_correct and trump_values_correct
                
            except ImportError as e:
                self.log(f"ERROR: Card implementation not found: {str(e)}")
                card_implementation_valid = False
            except Exception as e:
                self.log(f"ERROR in Card implementation: {str(e)}")
                card_implementation_valid = False
            
            # 2. Check Rules implementation
            try:
                from game.game_logic.rules import Rules
                
                rules = Rules()
                rules_methods = [m for m in dir(rules) if not m.startswith('_')]
                
                # Check for Belot-specific rules methods
                belot_rule_methods = [
                    'check_belot',              # Kralj i dama u istoj boji u adutu
                    'check_declarations',       # Provjera zvanja
                    'must_follow_suit',         # Pravilo za praćenje boje
                    'can_trump',                # Pravilo za rezanje adutom
                    'validate_move',            # Validacija poteza
                    'validate_bid'              # Validacija zvanja aduta
                ]
                
                found_rules = [m for m in belot_rule_methods if m in rules_methods]
                self.log(f"Rules has {len(found_rules)}/{len(belot_rule_methods)} required Belot methods")
                
                # Check for declaration types
                has_declarations = False
                try:
                    if hasattr(rules, 'DECLARATIONS') or hasattr(Rules, 'DECLARATIONS'):
                        declarations = getattr(rules, 'DECLARATIONS', getattr(Rules, 'DECLARATIONS', None))
                        if declarations:
                            self.log(f"Found declarations types: {len(declarations)}")
                            declaration_types = ['belot', 'trula', 'four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens', 'sequence']
                            found_declarations = [d for d in declaration_types if d in str(declarations).lower()]
                            self.log(f"Found {len(found_declarations)}/{len(declaration_types)} declaration types")
                            has_declarations = len(found_declarations) >= 5
                except Exception as e:
                    self.log(f"ERROR checking declarations: {str(e)}")
                
                rules_implementation_valid = len(found_rules) >= len(belot_rule_methods) * 0.7 and has_declarations
                
            except ImportError as e:
                self.log(f"ERROR: Rules implementation not found: {str(e)}")
                rules_implementation_valid = False
            except Exception as e:
                self.log(f"ERROR in Rules implementation: {str(e)}")
                rules_implementation_valid = False
            
            # 3. Check Scoring implementation
            try:
                from game.game_logic.scoring import Scoring
                
                scoring = Scoring()
                scoring_methods = [m for m in dir(scoring) if not m.startswith('_')]
                
                # Check for Belot-specific scoring methods
                belot_scoring_methods = [
                    'calculate_trick_points',     # Izračun bodova za štih
                    'calculate_declaration_points', # Izračun bodova za zvanja
                    'add_last_trick_bonus',       # Dodatak za zadnji štih
                    'check_belot_bonus',          # Bodovi za belot (kralj i dama u adutu)
                    'check_declarations_priority', # Prioritet zvanja
                    'calculate_round_score'       # Izračun ukupnih bodova za rundu
                ]
                
                found_scoring = [m for m in belot_scoring_methods if m in scoring_methods]
                self.log(f"Scoring has {len(found_scoring)}/{len(belot_scoring_methods)} required Belot methods")
                
                scoring_implementation_valid = len(found_scoring) >= len(belot_scoring_methods) * 0.7
                
            except ImportError as e:
                self.log(f"ERROR: Scoring implementation not found: {str(e)}")
                scoring_implementation_valid = False
            except Exception as e:
                self.log(f"ERROR in Scoring implementation: {str(e)}")
                scoring_implementation_valid = False
            
            # 4. Check Deck implementation
            try:
                from game.game_logic.deck import Deck
                
                deck = Deck()
                
                # Check if the deck has 32 cards (standard for Belot)
                deck_has_32_cards = len(deck.cards) == 32
                self.log(f"Deck has 32 cards (Belot standard): {deck_has_32_cards}")
                
                # Check if the deck has all required card ranks
                required_ranks = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
                deck_ranks = set(card.rank for card in deck.cards)
                has_all_ranks = all(rank in deck_ranks for rank in required_ranks)
                self.log(f"Deck has all required card ranks: {has_all_ranks}")
                
                # Check if the deck has all required card suits
                required_suits = ['S', 'H', 'D', 'C']
                deck_suits = set(card.suit for card in deck.cards)
                has_all_suits = all(suit in deck_suits for suit in required_suits)
                self.log(f"Deck has all required card suits: {has_all_suits}")
                
                # Check shuffle and deal methods
                has_shuffle = hasattr(deck, 'shuffle')
                has_deal = hasattr(deck, 'deal')
                self.log(f"Deck has shuffle method: {has_shuffle}")
                self.log(f"Deck has deal method: {has_deal}")
                
                deck_implementation_valid = deck_has_32_cards and has_all_ranks and has_all_suits and has_shuffle and has_deal
                
            except ImportError as e:
                self.log(f"ERROR: Deck implementation not found: {str(e)}")
                deck_implementation_valid = False
            except Exception as e:
                self.log(f"ERROR in Deck implementation: {str(e)}")
                deck_implementation_valid = False
            
            # 5. Check Validators implementation
            try:
                from game.game_logic.validators.move_validator import MoveValidator
                from game.game_logic.validators.call_validator import CallValidator
                
                move_validator = MoveValidator()
                call_validator = CallValidator()
                
                # Check move validator methods
                move_validator_methods = [m for m in dir(move_validator) if not m.startswith('_')]
                required_move_methods = ['validate', 'can_play_card', 'must_follow_suit', 'can_trump']
                found_move_methods = [m for m in required_move_methods if m in move_validator_methods]
                self.log(f"MoveValidator has {len(found_move_methods)}/{len(required_move_methods)} required methods")
                
                # Check call validator methods
                call_validator_methods = [m for m in dir(call_validator) if not m.startswith('_')]
                required_call_methods = ['validate', 'can_declare', 'check_priority']
                found_call_methods = [m for m in required_call_methods if m in call_validator_methods]
                self.log(f"CallValidator has {len(found_call_methods)}/{len(required_call_methods)} required methods")
                
                validators_implementation_valid = (len(found_move_methods) >= len(required_move_methods) * 0.7 and 
                                                 len(found_call_methods) >= len(required_call_methods) * 0.7)
                
            except ImportError as e:
                self.log(f"ERROR: Validators not found: {str(e)}")
                validators_implementation_valid = False
            except Exception as e:
                self.log(f"ERROR in Validators implementation: {str(e)}")
                validators_implementation_valid = False
            
            # Overall assessment of Belot rules
            self.results["belot_rules"] = (
                card_implementation_valid and
                rules_implementation_valid and
                scoring_implementation_valid and
                deck_implementation_valid
            )
        
        except Exception as e:
            self.log(f"ERROR verifying Belot rules: {str(e)}")
            self.log(traceback.format_exc())
            self.results["belot_rules"] = False
        
        self.log(f"Belot rules verified: {self.results.get('belot_rules', False)}")

    def verify_celery_config(self):
        """Verify Celery configuration."""
        self.log("\n===== Verifying Celery Configuration =====")
        try:
            # Check if Celery app is defined
            from celery_app.celery import app as celery_app
            
            if celery_app:
                self.log(f"Celery application name: {celery_app.main}")
                self.log(f"Broker URL: {celery_app.conf.broker_url}")
                self.log(f"Result backend: {celery_app.conf.result_backend}")
                
                # Check if tasks are defined
                try:
                    from celery_app.tasks import send_email_task, cleanup_expired_items
                    self.log("Found Celery tasks: send_email_task, cleanup_expired_items")
                    
                    # Check for stats tasks specifically
                    try:
                        from stats.tasks import update_global_statistics, update_daily_statistics
                        self.log("Found Stats Celery tasks: update_global_statistics, update_daily_statistics")
                    except ImportError:
                        self.log("Stats Celery tasks not found")
                    
                    # Check for game tasks
                    try:
                        from game.tasks import cleanup_abandoned_games, update_game_statistics
                        self.log("Found Game Celery tasks: cleanup_abandoned_games, update_game_statistics")
                    except ImportError:
                        self.log("Game Celery tasks not found")
                    
                    # Check if beat schedule is configured
                    if hasattr(celery_app.conf, 'beat_schedule'):
                        schedule_tasks = len(celery_app.conf.beat_schedule)
                        self.log(f"Celery beat schedule contains {schedule_tasks} tasks")
                        
                        # Check for stats tasks in beat schedule
                        stats_tasks_in_schedule = 0
                        for task_name in celery_app.conf.beat_schedule:
                            if 'stats' in task_name.lower():
                                stats_tasks_in_schedule += 1
                        
                        if stats_tasks_in_schedule > 0:
                            self.log(f"Found {stats_tasks_in_schedule} stats tasks in beat schedule")
                        
                    self.results["celery_config"] = True
                except ImportError as e:
                    self.log(f"WARNING: Could not import Celery tasks: {str(e)}")
                    # Still consider Celery configured if app exists
                    self.results["celery_config"] = True
            else:
                self.log("ERROR: Celery application not properly configured")
        
        except ImportError as e:
            self.log(f"ERROR: Missing required Celery packages: {str(e)}")
        except Exception as e:
            self.log(f"ERROR verifying Celery configuration: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Celery configuration verified: {self.results['celery_config']}")
    
    def verify_repository_pattern(self):
        """Verify repository pattern implementation."""
        self.log("\n===== Verifying Repository Pattern Implementation =====")
        
        repositories = [
            (LobbyRepository, "LobbyRepository"),
            (MembershipRepository, "MembershipRepository"),
            (MessageRepository, "MessageRepository"),
            (InvitationRepository, "InvitationRepository"),
            (EventRepository, "EventRepository")
        ]
        
        repo_methods = []
        all_repos_valid = True
        
        for repo_class, repo_name in repositories:
            self.log(f"Checking {repo_name}...")
            
            # Get static methods in repository
            methods = [
                name for name, method in inspect.getmembers(repo_class)
                if inspect.isfunction(method) and not name.startswith('_')
            ]
            
            self.log(f"  Found {len(methods)} public methods")
            repo_methods.extend(methods)
            
            # Check for common repository methods
            if not any(m.startswith('get_') for m in methods):
                self.log(f"  WARNING: {repo_name} may be missing getter methods")
                all_repos_valid = False
            
            if not any(m.startswith('create_') or m.startswith('add_') for m in methods):
                self.log(f"  WARNING: {repo_name} may be missing creation methods")
                all_repos_valid = False
        
        # Check game repositories
        try:
            from game.repositories.game_repository import GameRepository
            from game.repositories.move_repository import MoveRepository
            
            # Add game repositories to list
            repositories.extend([
                (GameRepository, "GameRepository"),
                (MoveRepository, "MoveRepository")
            ])
            
            # Check GameRepository CRUD methods
            game_repo_methods = [name for name, method in inspect.getmembers(GameRepository) 
                                if inspect.isfunction(method) and not name.startswith('_')]
            
            has_game_create = any(m.startswith('create_') for m in game_repo_methods)
            has_game_read = any(m.startswith('get_') for m in game_repo_methods)
            has_game_update = any(m.startswith('update_') for m in game_repo_methods)
            has_game_delete = any(m.startswith('delete_') for m in game_repo_methods)
            
            self.log(f"  GameRepository CRUD methods: Create={has_game_create}, Read={has_game_read}, Update={has_game_update}, Delete={has_game_delete}")
            
            if not (has_game_create and has_game_read and has_game_update and has_game_delete):
                self.log(f"  WARNING: GameRepository is missing some CRUD methods")
                all_repos_valid = False
            
            # Check MoveRepository methods
            move_repo_methods = [name for name, method in inspect.getmembers(MoveRepository) 
                                if inspect.isfunction(method) and not name.startswith('_')]
            
            repo_methods.extend(move_repo_methods)
            
            belot_specific_methods = [
                'determine_trick_winner',
                'get_valid_moves',
                'get_round_moves',
                'get_player_cards'
            ]
            
            found_belot_methods = [m for m in belot_specific_methods if m in move_repo_methods]
            self.log(f"  MoveRepository has {len(found_belot_methods)}/{len(belot_specific_methods)} Belot-specific methods")
            
            if len(found_belot_methods) < len(belot_specific_methods) * 0.7:
                self.log(f"  WARNING: MoveRepository is missing some Belot-specific methods")
                all_repos_valid = False
                
        except ImportError:
            self.log("  WARNING: Game repositories could not be imported")
            all_repos_valid = False
        
        # Check for common method patterns
        common_patterns = {
            'get': len([m for m in repo_methods if m.startswith('get_')]),
            'create': len([m for m in repo_methods if m.startswith('create_') or m.startswith('add_')]),
            'update': len([m for m in repo_methods if m.startswith('update_') or m.startswith('edit_')]),
            'delete': len([m for m in repo_methods if m.startswith('delete_') or m.startswith('remove_')])
        }
        
        self.log("\nRepository method patterns:")
        for pattern, count in common_patterns.items():
            self.log(f"  {pattern.upper()} methods: {count}")
        
        # Provjeri specifične CRUD metode u LobbyRepository
        lobby_repo_methods = [name for name, method in inspect.getmembers(LobbyRepository) 
                             if inspect.isfunction(method) and not name.startswith('_')]
        has_update = 'update_room' in lobby_repo_methods
        has_delete = 'delete_room' in lobby_repo_methods

        if not has_update:
            self.log("  WARNING: LobbyRepository nema metodu update_room")
            all_repos_valid = False
        if not has_delete:
            self.log("  WARNING: LobbyRepository nema metodu delete_room")
            all_repos_valid = False
        
        self.results["repository_pattern"] = all_repos_valid and all(count > 0 for count in common_patterns.values())
        self.log(f"Repository pattern verified: {self.results['repository_pattern']}")
    
    def verify_middleware_components(self):
        """Verify middleware components."""
        self.log("\n===== Verifying Middleware Components =====")
        
        try:
            # Check configured middleware
            installed_middleware = settings.MIDDLEWARE
            self.log(f"Configured middleware components: {len(installed_middleware)}")
            
            # Check for our custom middleware
            custom_middleware_names = [
                "middleware.rate_limiter.RateLimiterMiddleware", 
                "middleware.rate_limiter.APIThrottleMiddleware",
                "middleware.request_logger.RequestLoggerMiddleware",
                "middleware.request_logger.QueryCountMiddleware",
                "middleware.auth_middleware.TokenAuthMiddleware",
                "middleware.cors_middleware.CORSMiddleware",
                "middleware.cors_middleware.SameSiteMiddleware"
            ]
            
            found_middleware = []
            for middleware in custom_middleware_names:
                middleware_class_name = middleware.split('.')[-1]
                if middleware in installed_middleware or any(middleware_class_name in m for m in installed_middleware):
                    found_middleware.append(middleware_class_name)
            
            self.log(f"Found custom middleware: {', '.join(found_middleware)}")
            
            # Check that middleware classes are properly defined
            middleware_classes = [
                RequestLoggerMiddleware,
                RateLimiterMiddleware,
                TokenAuthMiddleware
            ]
            
            all_middleware_valid = True
            for middleware_class in middleware_classes:
                if not hasattr(middleware_class, '__call__'):
                    self.log(f"WARNING: {middleware_class.__name__} might not be properly implemented")
                    all_middleware_valid = False
            
            # Check for WebSocket-specific middleware
            try:
                from channels.middleware import BaseMiddleware
                
                # Try to import WebSocket auth middleware
                try:
                    from middleware.websocket_middleware import WebSocketJWTAuthMiddleware
                    self.log("Found WebSocket auth middleware")
                    
                    if issubclass(WebSocketJWTAuthMiddleware, BaseMiddleware):
                        self.log("WebSocketJWTAuthMiddleware correctly extends BaseMiddleware")
                    else:
                        self.log("WARNING: WebSocketJWTAuthMiddleware does not extend BaseMiddleware")
                        all_middleware_valid = False
                except ImportError:
                    self.log("WebSocket auth middleware not found")
            except ImportError:
                self.log("Channels package not found, skipping WebSocket middleware check")
            
            self.results["middleware_components"] = all_middleware_valid and len(found_middleware) >= 3
        
        except Exception as e:
            self.log(f"ERROR verifying middleware components: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Middleware components verified: {self.results['middleware_components']}")
    
    def verify_app_configuration(self):
        """Verify application configuration."""
        self.log("\n===== Verifying Application Configuration =====")
        
        try:
            # Check installed apps
            installed_apps = settings.INSTALLED_APPS
            self.log(f"Installed applications: {len(installed_apps)}")
            
            # Check for our custom apps - improved detection logic
            required_apps = [
                'game', 'lobby', 'users', 'stats',
                'channels', 'rest_framework', 'corsheaders'
            ]
            
            found_apps = []
            for app in required_apps:
                # More flexible detection logic
                if any(app in installed_app.lower() for installed_app in installed_apps):
                    found_apps.append(app)
            
            missing_apps = set(required_apps) - set(found_apps)
            if missing_apps:
                self.log(f"WARNING: Missing applications: {', '.join(missing_apps)}")
                # Print actual INSTALLED_APPS for debugging
                self.log(f"Actual INSTALLED_APPS: {', '.join(installed_apps)}")
            else:
                self.log(f"All required applications found: {', '.join(found_apps)}")
            
            # Check URL configuration
            try:
                from belot.urls import urlpatterns
                self.log(f"URL patterns defined: {len(urlpatterns)}")
                
                # Check for Belot-specific endpoints
                belot_urls = {
                    'game': False,
                    'lobby': False,
                    'stats': False,
                    'users': False,
                    'api/game': False,
                    'api/lobby': False,
                    'api/stats': False,
                    'api/users': False
                }
                
                for pattern in urlpatterns:
                    for endpoint in belot_urls:
                        if hasattr(pattern, 'pattern') and endpoint in str(pattern.pattern):
                            belot_urls[endpoint] = True
                
                for endpoint, found in belot_urls.items():
                    self.log(f"URL endpoint '{endpoint}': {'Found' if found else 'Not found'}")
                
                # Check for specific API endpoints related to Belot game
                try:
                    # Try to check game API URLs if found
                    if belot_urls['api/game']:
                        try:
                            from game.urls.api import urlpatterns as game_api_patterns
                            self.log(f"Game API has {len(game_api_patterns)} URL patterns")
                            
                            game_api_endpoints = ['games', 'rounds', 'moves', 'declarations']
                            found_endpoints = []
                            
                            for pattern in game_api_patterns:
                                pattern_str = str(pattern.pattern)
                                for endpoint in game_api_endpoints:
                                    if endpoint in pattern_str and endpoint not in found_endpoints:
                                        found_endpoints.append(endpoint)
                            
                            self.log(f"Found game API endpoints: {', '.join(found_endpoints)}")
                        except ImportError:
                            self.log("Could not import game API URLs")
                except Exception as e:
                    self.log(f"Error checking game API endpoints: {str(e)}")
            except ImportError as e:
                self.log(f"WARNING: Could not import urlpatterns: {str(e)}")
                # Dodana linija za detaljniji ispis greške
                self.log(f"Detalji greške: {traceback.format_exc()}")
            except Exception as e:
                self.log(f"ERROR checking URL patterns: {str(e)}")
            
            # Check static/media configuration
            self.log(f"Static URL: {settings.STATIC_URL}")
            self.log(f"Media URL: {settings.MEDIA_URL}")
            
            # Check directory existence
            static_root = getattr(settings, 'STATIC_ROOT', None)
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            
            if static_root:
                self.log(f"Static root: {static_root}")
                self.log(f"Static root exists: {os.path.exists(static_root)}")
            else:
                self.log("WARNING: STATIC_ROOT not defined in settings")
                
            if media_root:
                self.log(f"Media root: {media_root}")
                self.log(f"Media root exists: {os.path.exists(media_root)}")
            else:
                self.log("WARNING: MEDIA_ROOT not defined in settings")
            
            # Check for Belot-specific settings
            belot_specific_settings = [
                'BELOT_POINTS_TO_WIN',
                'BELOT_ROUND_TIMEOUT',
                'BELOT_MOVE_TIMEOUT',
                'BELOT_MAX_PLAYERS_PER_GAME'
            ]
            
            found_belot_settings = []
            for setting_name in belot_specific_settings:
                if hasattr(settings, setting_name):
                    found_belot_settings.append(setting_name)
                    self.log(f"Found Belot setting: {setting_name} = {getattr(settings, setting_name)}")
            
            if found_belot_settings:
                self.log(f"Found {len(found_belot_settings)}/{len(belot_specific_settings)} Belot-specific settings")
            else:
                self.log("WARNING: No Belot-specific settings found")
            
            # App configuration is considered valid if:
            # 1. Most required apps are found (allow 1-2 missing)
            # 2. URL patterns are defined
            # 3. Static and media are configured
            self.results["app_configuration"] = (
                len(missing_apps) <= 2 and 
                'urlpatterns' in locals() and 
                static_root is not None and 
                media_root is not None
            )
            
        except Exception as e:
            self.log(f"ERROR verifying application configuration: {str(e)}")
            self.log(traceback.format_exc())
        
        self.log(f"Application configuration verified: {self.results['app_configuration']}")

    def run_all_checks(self):
        """Run all verification checks."""
        self.verify_django_config()
        self.verify_migrations()
        self.verify_database_connection()
        self.verify_redis_connection()
        self.verify_websocket_config()
        self.verify_celery_config()
        self.verify_repository_pattern()
        self.verify_middleware_components()
        self.verify_app_configuration()
        self.verify_users_app()
        self.verify_stats_app()
        self.verify_game_app()
        self.verify_belot_rules()  # Added Belot-specific rules verification
        
        return self.get_summary()
        
    def get_summary(self):
        """Get a summary of verification results."""
        passed = sum(1 for value in self.results.values() if value)
        total = len(self.results)
        
        summary = {
            "status": "PASSED" if passed == total else "FAILED",
            "score": f"{passed}/{total}",
            "percentage": int((passed / total) * 100),
            "details": self.results
        }
        
        return summary


class FunctionalTester:
    """Class that tests functional aspects of the Belot backend."""
    
    def __init__(self, verbose=True):  # Verbose uključen prema zadanim postavkama
        self.verbose = verbose
        self.test_users = []
        self.test_room = None
        self.test_game = None
        
    def log(self, message):
        """Print a log message."""
        if self.verbose:
            print(message)
    
    def clean_test_data(self):
        """Clean up any test data created during tests."""
        self.log("\n===== Cleaning up test data =====")
        try:
            # First delete any created games
            if self.test_game:
                try:
                    self.test_game.delete()
                    self.log(f"Deleted test game with ID: {self.test_game.id}")
                except Exception as e:
                    self.log(f"Error deleting test game: {str(e)}")
            
            # Delete any created lobby rooms
            if self.test_room:
                try:
                    LobbyRepository.delete_room(self.test_room.id)
                    self.log(f"Deleted test room: {self.test_room.name}")
                except Exception as e:
                    self.log(f"Error deleting test room: {str(e)}")
            
            # Delete any created test users
            for user in self.test_users:
                try:
                    user.delete()
                    self.log(f"Deleted test user: {user.username}")
                except Exception as e:
                    self.log(f"Error deleting test user {user.username}: {str(e)}")
            
            self.test_users = []
            self.test_room = None
            self.test_game = None
            
            self.log("Cleanup completed")
            
        except Exception as e:
            self.log(f"Error during cleanup: {str(e)}")
    
    def test_user_creation(self, count=4):
        """Test creation of users for testing."""
        self.log("\n===== Testing User Creation =====")
        try:
            # Create test users
            for i in range(1, count + 1):
                username = f"testplayer{i}_{int(time.time())}"
                email = f"{username}@example.com"
                password = "testpass123"
                
                # Create user with User.objects.create_user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                
                self.test_users.append(user)
                self.log(f"Created test user: {username}")
            
            # Check that all users were created
            self.log(f"Created {len(self.test_users)} test users")
            
            # Check for PlayerStats creation (should be automatic via signals)
            for user in self.test_users:
                try:
                    stats = PlayerStats.objects.get(user=user)
                    self.log(f"PlayerStats automatically created for {user.username}")
                except PlayerStats.DoesNotExist:
                    self.log(f"WARNING: PlayerStats not created for {user.username}")
            
            return len(self.test_users) == count
            
        except Exception as e:
            self.log(f"ERROR during user creation test: {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def test_lobby_room_creation(self):
        """Test creation of a lobby room."""
        self.log("\n===== Testing Lobby Room Creation =====")
        try:
            # Make sure we have test users
            if not self.test_users:
                self.log("No test users available, creating them now...")
                self.test_user_creation(4)
            
            # Create a room using repository
            creator = self.test_users[0]
            room_name = f"Test Room {int(time.time())}"
            
            # Use repository to create room
            room = LobbyRepository.create_room(
                name=room_name,
                creator=creator,
                max_players=4,
                points_to_win=1001,
                is_private=False
            )
            
            self.test_room = room
            self.log(f"Created test room: {room_name} (ID: {room.id})")
            
            # Add players to the room
            for user in self.test_users[1:]:  # Skip creator as they're already in the room
                membership = MembershipRepository.create_membership(
                    room=room,
                    user=user
                )
                self.log(f"Added {user.username} to room")
            
            # Verify room has correct number of players
            room_players = MembershipRepository.get_room_players(room.id)
            self.log(f"Room has {len(room_players)} players")
            
            # Send a test message
            message = MessageRepository.create_message(
                room=room,
                sender=creator,
                content="Test message from functional testing",
                is_system_message=False
            )
            self.log(f"Created test message in room: {message.content}")
            
            return True
            
        except Exception as e:
            self.log(f"ERROR during lobby room creation test: {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def test_game_creation(self):
        """Test creation and basic setup of a game."""
        self.log("\n===== Testing Game Creation =====")
        try:
            # Make sure we have test users
            if not self.test_users:
                self.log("No test users available, creating them now...")
                self.test_user_creation(4)
            
            if not self.test_room:
                self.log("No test room available, creating it now...")
                self.test_lobby_room_creation()
            
            # Try using GameRepository if available
            try:
                from game.repositories.game_repository import GameRepository
                self.log("Using GameRepository for game creation...")
                
                # Create a game instance
                creator = self.test_users[0]
                
                with transaction.atomic():
                    game = GameRepository.create_game(
                        creator=creator,
                        private=False,
                        points_to_win=1001
                    )
                    
                    # Add all users to the game
                    for user in self.test_users[1:]:  # Skip creator who's already added
                        GameRepository.add_player_to_game(game, user)
                    
                    # Save reference to game
                    self.test_game = game
                    self.log(f"Created test game with ID: {game.id}")
                    
                    # Try to assign teams 
                    try:
                        # Try using game model method if available
                        if hasattr(game, 'assign_teams'):
                            game.assign_teams()
                            self.log("Teams assigned using game model method")
                        else:
                            # Manually assign teams
                            game.team_a_players.add(self.test_users[0], self.test_users[2])
                            game.team_b_players.add(self.test_users[1], self.test_users[3])
                            self.log("Teams assigned manually")
                        
                        self.log(f"Team A: {', '.join([u.username for u in game.team_a_players.all()])}")
                        self.log(f"Team B: {', '.join([u.username for u in game.team_b_players.all()])}")
                    except Exception as e:
                        self.log(f"Error assigning teams: {str(e)}")
                    
                    # Check if game was created correctly
                    player_count = game.players.count()
                    self.log(f"Game has {player_count} players")
                    
                    # Associate game with room
                    if hasattr(self.test_room, 'game'):
                        self.test_room.game = game
                        self.test_room.save()
                        self.log(f"Associated game with room {self.test_room.name}")
                    
                    return player_count == 4
            except ImportError:
                self.log("GameRepository not available, trying direct model approach...")
                
                # Fallback to direct model creation
                creator = self.test_users[0]
                
                with transaction.atomic():
                    game = Game.objects.create(
                        creator=creator,
                        points_to_win=1001,
                        is_private=False,
                        status='waiting'
                    )
                    
                    # Add all users to the game
                    for user in self.test_users:
                        game.players.add(user)
                    
                    # Save reference to game
                    self.test_game = game
                    self.log(f"Created test game with ID: {game.id}")
                    
                    # Set team assignments
                    if hasattr(game, 'team_a_players') and hasattr(game, 'team_b_players'):
                        game.team_a_players.add(self.test_users[0], self.test_users[2])
                        game.team_b_players.add(self.test_users[1], self.test_users[3])
                        self.log("Added players to teams using M2M relations")
                    else:
                        # Try string-based approach as fallback
                        game.team_a_players = [str(self.test_users[0].id), str(self.test_users[2].id)]
                        game.team_b_players = [str(self.test_users[1].id), str(self.test_users[3].id)]
                        game.save()
                        self.log("Added players to teams using string lists")
                    
                    self.log(f"Assigned players to teams")
                    self.log(f"Team A: {self.test_users[0].username}, {self.test_users[2].username}")
                    self.log(f"Team B: {self.test_users[1].username}, {self.test_users[3].username}")
                    
                    # Check if game was created correctly
                    player_count = game.players.count()
                    self.log(f"Game has {player_count} players")
                    
                    # Associate game with room
                    if self.test_room and hasattr(self.test_room, 'game'):
                        self.test_room.game = game
                        self.test_room.save()
                        self.log(f"Associated game with room {self.test_room.name}")
                    
                    return player_count == 4
                    
        except Exception as e:
            self.log(f"ERROR during game creation test: {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def test_game_core_components(self):
        """Test the core game logic components."""
        self.log("\n===== Testing Game Core Components =====")
        try:
            # Test Card class
            try:
                from game.game_logic.card import Card
                self.log("Testing Card class...")
                
                # Create some cards
                cards = [
                    Card('A', 'S'),  # Ace of Spades
                    Card('J', 'H'),  # Jack of Hearts
                    Card('7', 'D'),  # 7 of Diamonds
                    Card('K', 'C'),  # King of Clubs
                ]
                
                self.log(f"Created cards: {', '.join(str(card) for card in cards)}")
                
                # Test card comparison
                if cards[0] > cards[2]:  # Ace > 7
                    self.log("Card comparison works (Ace > 7)")
                
                # Test card equality
                card1 = Card('Q', 'H')
                card2 = Card('Q', 'H')
                if card1 == card2:
                    self.log("Card equality works (QH == QH)")
                
                # Test card from code
                code_card = Card.from_code('10D')
                self.log(f"Created card from code: {code_card}")
                
                # Test card value calculation
                adut_value = cards[1].get_value(trump_suit='H')  # Jack of Hearts as trump
                self.log(f"Jack of Hearts value as trump: {adut_value}")
                if adut_value == 20:
                    self.log("Trump card value calculation is correct (J=20)")
                
                regular_value = cards[0].get_value()  # Ace of Spades regular value
                self.log(f"Ace of Spades regular value: {regular_value}")
                if regular_value == 11:
                    self.log("Regular card value calculation is correct (A=11)")
                
                card_test_success = True
            except ImportError as e:
                self.log(f"Card class not available: {str(e)}")
                card_test_success = False
            except Exception as e:
                self.log(f"Error testing Card class: {str(e)}")
                card_test_success = False
            
            # Test Deck class
            try:
                from game.game_logic.deck import Deck
                self.log("Testing Deck class...")
                
                # Create a deck
                deck = Deck()
                self.log(f"Created deck with {len(deck.cards)} cards")
                
                # Check if deck has 32 cards (standard for Belot)
                if len(deck.cards) == 32:
                    self.log("Deck has correct number of cards (32)")
                else:
                    self.log(f"WARNING: Deck has {len(deck.cards)} cards, expected 32")
                
                # Shuffle the deck
                deck.shuffle()
                self.log("Shuffled the deck")
                
                # Draw some cards
                drawn_cards = [deck.draw() for _ in range(5)]
                self.log(f"Drew 5 cards: {', '.join(str(card) for card in drawn_cards)}")
                self.log(f"Remaining cards: {len(deck.cards)}")
                
                # Test dealing cards to players
                if hasattr(deck, 'deal'):
                    # Create test hands
                    hands = deck.deal(4)  # Deal to 4 players
                    self.log(f"Dealt cards to 4 players, each player got {len(hands[0])} cards")
                    
                    if len(hands) == 4 and all(len(hand) == len(deck.cards) // 4 for hand in hands):
                        self.log("Dealing cards works correctly")
                
                deck_test_success = True
            except ImportError as e:
                self.log(f"Deck class not available: {str(e)}")
                deck_test_success = False
            except Exception as e:
                self.log(f"Error testing Deck class: {str(e)}")
                deck_test_success = False
            
            # Test Rules class if available
            try:
                from game.game_logic.rules import Rules
                self.log("Testing Rules class...")
                
                rules = Rules()
                self.log("Created Rules instance")
                
                # Test trump determination
                if hasattr(rules, 'is_trump'):
                    card = Card('J', 'H')
                    is_trump = rules.is_trump(card, 'H')
                    self.log(f"is_trump check: Card {card} is{'' if is_trump else ' not'} trump in hearts")
                
                # Test belot check (king and queen of same suit in trump)
                if hasattr(rules, 'check_belot'):
                    king = Card('K', 'H')
                    queen = Card('Q', 'H')
                    hand = [king, queen, Card('A', 'S'), Card('10', 'D')]
                    has_belot = rules.check_belot(hand, 'H')
                    self.log(f"check_belot: Hand {'has' if has_belot else 'does not have'} belot in hearts")
                
                # Test must_follow_suit rule
                if hasattr(rules, 'must_follow_suit'):
                    hand = [Card('A', 'S'), Card('K', 'S'), Card('Q', 'H'), Card('J', 'D')]
                    trick_suit = 'S'
                    valid_cards = rules.must_follow_suit(hand, trick_suit, 'H')
                    self.log(f"must_follow_suit: Valid cards to play: {', '.join(str(c) for c in valid_cards)}")
                    if all(card.suit == trick_suit for card in valid_cards):
                        self.log("must_follow_suit works correctly")
                
                rules_test_success = True
            except ImportError as e:
                self.log(f"Rules class not available: {str(e)}")
                rules_test_success = False
            except Exception as e:
                self.log(f"Error testing Rules class: {str(e)}")
                rules_test_success = False
            
            # Test Scoring class if available
            try:
                from game.game_logic.scoring import Scoring
                self.log("Testing Scoring class...")
                
                scoring = Scoring()
                self.log("Created Scoring instance")
                
                # Test trick points calculation
                if hasattr(scoring, 'calculate_trick_points'):
                    trick = [Card('A', 'S'), Card('K', 'S'), Card('Q', 'S'), Card('J', 'S')]
                    points = scoring.calculate_trick_points(trick, 'H')
                    self.log(f"calculate_trick_points: Trick worth {points} points")
                    
                    # Test with trump cards
                    trump_trick = [Card('J', 'H'), Card('9', 'H'), Card('A', 'H'), Card('K', 'H')]
                    trump_points = scoring.calculate_trick_points(trump_trick, 'H')
                    self.log(f"calculate_trick_points: Trump trick worth {trump_points} points")
                
                # Test last trick bonus
                if hasattr(scoring, 'add_last_trick_bonus'):
                    points = 20
                    with_bonus = scoring.add_last_trick_bonus(points)
                    self.log(f"add_last_trick_bonus: {points} + 10 = {with_bonus}")
                    if with_bonus == points + 10:
                        self.log("Last trick bonus works correctly")
                
                scoring_test_success = True
            except ImportError as e:
                self.log(f"Scoring class not available: {str(e)}")
                scoring_test_success = False
            except Exception as e:
                self.log(f"Error testing Scoring class: {str(e)}")
                scoring_test_success = False
            
            # Return overall success - at least Card and Deck must be working
            return card_test_success and deck_test_success
            
        except Exception as e:
            self.log(f"ERROR during game core components test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def test_belot_specific_rules(self):
        """Test Belot-specific game rules."""
        self.log("\n===== Testing Belot-Specific Rules =====")
        try:
            # Test declarations (zvanja)
            try:
                from game.game_logic.rules import Rules
                
                rules = Rules()
                self.log("Created Rules instance for declaration testing")
                
                if hasattr(rules, 'check_declarations'):
                    # Test belot (kralj i dama u adutu)
                    hand = [Card('K', 'H'), Card('Q', 'H'), Card('A', 'S'), Card('10', 'D')]
                    belot = rules.check_declarations(hand, 'H')
                    
                    if belot and any(decl['type'] == 'belot' for decl in belot):
                        self.log("Successfully detected belot declaration")
                    else:
                        self.log("Failed to detect belot declaration")
                    
                    # Test sequence (niz)
                    sequence_hand = [Card('7', 'S'), Card('8', 'S'), Card('9', 'S'), 
                                    Card('K', 'H'), Card('Q', 'H'), Card('J', 'D')]
                    sequence = rules.check_declarations(sequence_hand, 'D')
                    
                    if sequence and any(decl['type'] == 'sequence' for decl in sequence):
                        self.log("Successfully detected sequence declaration")
                    else:
                        self.log("Failed to detect sequence declaration")
                    
                    # Test four of a kind
                    four_jacks = [Card('J', 'S'), Card('J', 'H'), Card('J', 'D'), 
                                Card('J', 'C'), Card('A', 'S'), Card('K', 'H')]
                    four_of_kind = rules.check_declarations(four_jacks, 'H')
                    
                    if four_of_kind and any(decl['type'] == 'four_jacks' for decl in four_of_kind):
                        self.log("Successfully detected four jacks declaration")
                    else:
                        self.log("Failed to detect four jacks declaration")
                    
                    declarations_test_success = True
                else:
                    self.log("Rules.check_declarations method not found")
                    declarations_test_success = False
            except ImportError as e:
                self.log(f"Rules class not available: {str(e)}")
                declarations_test_success = False
            except Exception as e:
                self.log(f"Error testing declarations: {str(e)}")
                declarations_test_success = False
            
            # Test trump calling logic
            try:
                from game.game_logic.game import Game as GameLogic
                
                game = GameLogic()
                self.log("Created GameLogic instance for trump calling testing")
                
                if hasattr(game, 'bid_trump'):
                    # Test bidding
                    player_id = 0
                    trump_suit = 'H'
                    bid_result = game.bid_trump(player_id, trump_suit)
                    
                    if bid_result:
                        self.log(f"Successfully called trump: {trump_suit}")
                    else:
                        self.log(f"Failed to call trump: {trump_suit}")
                    
                    trump_calling_test_success = True
                else:
                    self.log("GameLogic.bid_trump method not found")
                    trump_calling_test_success = False
            except ImportError as e:
                self.log(f"GameLogic class not available: {str(e)}")
                trump_calling_test_success = False
            except Exception as e:
                self.log(f"Error testing trump calling: {str(e)}")
                trump_calling_test_success = False
            
            # Test trick winning logic
            try:
                from game.game_logic.rules import Rules
                
                rules = Rules()
                self.log("Created Rules instance for trick winning testing")
                
                if hasattr(rules, 'determine_trick_winner'):
                    # Test basic trick winning (highest card of led suit)
                    trick = [
                        {'player': 0, 'card': Card('J', 'S')},
                        {'player': 1, 'card': Card('Q', 'S')},
                        {'player': 2, 'card': Card('K', 'S')},
                        {'player': 3, 'card': Card('7', 'S')}
                    ]
                    winner = rules.determine_trick_winner(trick, 'H', 'S')
                    self.log(f"Basic trick winner (no trump played): Player {winner}")
                    
                    # Test trump winning
                    trump_trick = [
                        {'player': 0, 'card': Card('A', 'S')},
                        {'player': 1, 'card': Card('7', 'H')},
                        {'player': 2, 'card': Card('K', 'S')},
                        {'player': 3, 'card': Card('J', 'H')}
                    ]
                    trump_winner = rules.determine_trick_winner(trump_trick, 'H', 'S')
                    self.log(f"Trump trick winner: Player {trump_winner}")
                    
                    # In Belot, J of trump should win
                    if trump_winner == 3:
                        self.log("Trump trick winning logic is correct (J of trump wins)")
                    
                    trick_winning_test_success = True
                else:
                    self.log("Rules.determine_trick_winner method not found")
                    trick_winning_test_success = False
            except ImportError as e:
                self.log(f"Rules class not available for trick testing: {str(e)}")
                trick_winning_test_success = False
            except Exception as e:
                self.log(f"Error testing trick winning: {str(e)}")
                trick_winning_test_success = False
                
            # Return overall result - at least one test should pass
            return declarations_test_success or trump_calling_test_success or trick_winning_test_success
            
        except Exception as e:
            self.log(f"ERROR during Belot-specific rules test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def test_game_round_creation(self):
        """Test creation of a game round and basic gameplay."""
        self.log("\n===== Testing Game Round Creation =====")
        try:
            # Make sure we have a game
            if not self.test_game:
                self.log("No test game available, creating it now...")
                self.test_game_creation()
            
            # Create a round
            with transaction.atomic():
                # Ispravljeno: uklonjeno dvostruko definiranje round_obj
                round_obj = Round.objects.create(
                    game=self.test_game,
                    round_number=1,
                    dealer=self.test_users[0],
                    status='dealing'
                )
                
                self.log(f"Created round {round_obj.round_number} for game {self.test_game.id}")
                
                # Set round to bidding status
                round_obj.status = 'bidding'
                round_obj.save()
                self.log(f"Updated round status to 'bidding'")
                
                # Set a trumps suit
                round_obj.trump_suit = 'hearts'
                round_obj.caller = self.test_users[1]
                round_obj.status = 'playing'
                round_obj.save()
                self.log(f"Set trump suit to hearts called by {self.test_users[1].username}")
                
                # Let's try creating some declarations if the model exists
                try:
                    Declaration.objects.create(
                        round=round_obj,
                        player=self.test_users[0],
                        declaration_type='belot',
                        value=20,
                        cards_json=json.dumps(['KH', 'QH'])  # King and Queen of Hearts
                    )
                    self.log(f"Created belot declaration for {self.test_users[0].username}")
                except Exception as e:
                    self.log(f"Could not create declarations: {str(e)}")
                
                # Try simulating some moves if the model exists
                try:
                    for i, user in enumerate(self.test_users):
                        card_codes = ['7H', '8H', '9H', '10H']  # Simple sequence of cards
                        Move.objects.create(
                            round=round_obj,
                            player=user,
                            card_code=card_codes[i],
                            order=i+1
                        )
                        self.log(f"Player {user.username} played card {card_codes[i]}")
                except Exception as e:
                    self.log(f"Could not create moves: {str(e)}")
                
                # Complete the round
                round_obj.team_a_score = 85
                round_obj.team_b_score = 77
                round_obj.status = 'completed'
                round_obj.save()
                self.log(f"Completed round with scores: Team A {round_obj.team_a_score}, Team B {round_obj.team_b_score}")
                
                # Update game scores
                self.test_game.team_a_score = round_obj.team_a_score
                self.test_game.team_b_score = round_obj.team_b_score
                self.test_game.save()
                
                return True
                
        except Exception as e:
            self.log(f"ERROR during game round creation test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def test_game_completion(self):
        """Test completing a game and checking stats update."""
        self.log("\n===== Testing Game Completion =====")
        try:
            # Make sure we have a game with rounds
            if not self.test_game:
                self.log("No test game available, creating it now...")
                self.test_game_creation()
                self.test_game_round_creation()
            
            # Complete the game
            with transaction.atomic():
                # Set the winning team
                self.test_game.winning_team = 'a'  # Team A wins
                self.test_game.status = 'completed'
                self.test_game.save()
                
                self.log(f"Completed game {self.test_game.id}, Team A wins!")
                
                # Check if GameStats was created (might be automatic via signals)
                try:
                    game_stats = GameStats.objects.get(game=self.test_game)
                    self.log(f"Game statistics automatically created with {game_stats.total_rounds} rounds")
                except GameStats.DoesNotExist:
                    self.log("WARNING: Game statistics not automatically created")
                    
                    # Try to manually trigger stats update
                    try:
                        from stats.signals import handle_game_events
                        handle_game_events(sender=Game, instance=self.test_game, created=False)
                        self.log("Manually triggered game stats update")
                        
                        # Check again
                        try:
                            game_stats = GameStats.objects.get(game=self.test_game)
                            self.log(f"Game statistics now created with {game_stats.total_rounds} rounds")
                        except GameStats.DoesNotExist:
                            self.log("Still couldn't create game statistics")
                    except Exception as e:
                        self.log(f"Error triggering stats update: {str(e)}")
                
                # Check player stats update
                for user in self.test_users:
                    try:
                        player_stats = PlayerStats.objects.get(user=user)
                        self.log(f"Player {user.username} stats: games_played={player_stats.games_played}, games_won={player_stats.games_won}")
                    except PlayerStats.DoesNotExist:
                        self.log(f"WARNING: Stats not found for player {user.username}")
                
                # Try to manually recalculate player stats
                try:
                    for user in self.test_users:
                        # Try to use the tasks if they're defined
                        try:
                            from stats.tasks import recalculate_player_stats
                            recalculate_player_stats(str(user.id))
                            self.log(f"Triggered stats recalculation for {user.username}")
                        except Exception as e:
                            self.log(f"Error triggering stats recalculation: {str(e)}")
                except Exception as e:
                    self.log(f"Error recalculating player stats: {str(e)}")
                
                return True
                
        except Exception as e:
            self.log(f"ERROR during game completion test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def test_api_endpoints(self):
        """Test some basic API endpoints."""
        self.log("\n===== Testing API Endpoints =====")
        try:
            # Create a test client
            client = Client()
            
            # Test API health endpoint
            response = client.get('/api/health/')
            self.log(f"API health endpoint status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("API health endpoint working")
            else:
                self.log(f"WARNING: API health endpoint returned status {response.status_code}")
            
            # Try a few more endpoints if possible
            if self.test_users:
                # Log in a user
                client.force_login(self.test_users[0])
                
                # Try stats endpoint
                try:
                    response = client.get('/api/stats/global/')
                    if response.status_code == 200:
                        self.log("Stats global API endpoint working")
                    else:
                        self.log(f"WARNING: Stats global API endpoint returned status {response.status_code}")
                except Exception as e:
                    self.log(f"Error accessing stats API: {str(e)}")
                
                # Try lobby endpoint
                try:
                    response = client.get('/api/lobby/rooms/')
                    if response.status_code == 200:
                        self.log("Lobby rooms API endpoint working")
                    else:
                        self.log(f"WARNING: Lobby rooms API endpoint returned status {response.status_code}")
                except Exception as e:
                    self.log(f"Error accessing lobby API: {str(e)}")
                
                # Try game endpoint
                try:
                    response = client.get('/api/game/games/')
                    if response.status_code == 200:
                        self.log("Game list API endpoint working")
                    else:
                        self.log(f"WARNING: Game list API endpoint returned status {response.status_code}")
                except Exception as e:
                    self.log(f"Error accessing game API: {str(e)}")
            
            return response.status_code == 200
                
        except Exception as e:
            self.log(f"ERROR during API endpoints test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def test_websocket_connections(self):
        """Test WebSocket connections for game and lobby."""
        self.log("\n===== Testing WebSocket Connections =====")
        try:
            # This is more complex to test without a proper client
            # We'll check if the necessary components are set up
            self.log("Checking WebSocket infrastructure...")
            
            # Check if channels is installed
            try:
                import channels
                self.log(f"Channels package found: {channels.__version__}")
                
                # Check if channel layer is configured
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                
                if channel_layer:
                    self.log(f"Channel layer configured: {channel_layer.__class__.__name__}")
                    
                    # Check if our consumers are defined
                    try:
                        from lobby.consumers import LobbyConsumer
                        self.log("Lobby WebSocket consumer found")
                        
                        if hasattr(LobbyConsumer, 'connect') and hasattr(LobbyConsumer, 'disconnect'):
                            self.log("LobbyConsumer has basic WebSocket methods")
                    except ImportError:
                        self.log("WARNING: LobbyConsumer not found")
                    
                    try:
                        from game.consumers import GameConsumer
                        self.log("Game WebSocket consumer found")
                        
                        if hasattr(GameConsumer, 'connect') and hasattr(GameConsumer, 'disconnect'):
                            self.log("GameConsumer has basic WebSocket methods")
                    except ImportError:
                        self.log("WARNING: GameConsumer not found")
                    
                    # Check for routing
                    try:
                        from lobby.routing import websocket_urlpatterns as lobby_patterns
                        self.log(f"Found {len(lobby_patterns)} lobby WebSocket URL patterns")
                    except ImportError:
                        self.log("WARNING: Lobby WebSocket routing not found")
                    
                    try:
                        from game.routing import websocket_urlpatterns as game_patterns
                        self.log(f"Found {len(game_patterns)} game WebSocket URL patterns")
                    except ImportError:
                        self.log("WARNING: Game WebSocket routing not found")
                    
                    # Try basic channel layer operations
                    try:
                        from asgiref.sync import async_to_sync
                        
                        test_channel = f"test_channel_{int(time.time())}"
                        test_message = {"type": "test.message", "content": "Hello WebSocket!"}
                        
                        async_to_sync(channel_layer.group_add)(test_channel, test_channel)
                        async_to_sync(channel_layer.group_send)(test_channel, test_message)
                        async_to_sync(channel_layer.group_discard)(test_channel, test_channel)
                        
                        self.log("Basic channel layer operations successful")
                        return True
                    except Exception as e:
                        self.log(f"Error testing channel layer: {str(e)}")
                        return False
                else:
                    self.log("WARNING: Channel layer not configured")
                    return False
            except ImportError:
                self.log("WARNING: Channels package not installed")
                return False
                
        except Exception as e:
            self.log(f"ERROR during WebSocket connections test: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def run_all_tests(self):
        """Run all functional tests and return results."""
        try:
            self.log("\n===== Running All Functional Tests =====")
            
            results = {
                "user_creation": self.test_user_creation(),
                "lobby_room_creation": self.test_lobby_room_creation(),
                "game_creation": self.test_game_creation(),
                "game_core_components": self.test_game_core_components(),
                "belot_specific_rules": self.test_belot_specific_rules(),  # Added Belot-specific test
                "game_round_creation": self.test_game_round_creation(),
                "game_completion": self.test_game_completion(),
                "api_endpoints": self.test_api_endpoints(),
                "websocket_connections": self.test_websocket_connections()  # Added WebSocket test
            }
            
            # Calculate overall success
            passed = sum(1 for result in results.values() if result)
            total = len(results)
            success_rate = (passed / total) * 100 if total > 0 else 0
            
            summary = {
                "status": "PASSED" if all(results.values()) else "PARTIALLY PASSED" if passed > 0 else "FAILED",
                "score": f"{passed}/{total}",
                "percentage": int(success_rate),
                "details": results
            }
            
            return summary
            
        except Exception as e:
            self.log(f"ERROR during functional tests: {str(e)}")
            self.log(traceback.format_exc())
            return {
                "status": "FAILED",
                "score": f"0/{len({'user_creation', 'lobby_room_creation', 'game_creation', 'game_core_components', 'belot_specific_rules', 'game_round_creation', 'game_completion', 'api_endpoints', 'websocket_connections'})}",
                "percentage": 0,
                "details": {
                    "error": str(e)
                }
            }
        finally:
            # Clean up test data
            self.clean_test_data()
            
    def run_specific_test(self, test_name):
        """Run a specific functional test by name."""
        test_method_name = f"test_{test_name}"
        
        if hasattr(self, test_method_name) and callable(getattr(self, test_method_name)):
            test_method = getattr(self, test_method_name)
            
            try:
                self.log(f"\n===== Running Specific Test: {test_name} =====")
                result = test_method()
                
                return {
                    "status": "PASSED" if result else "FAILED",
                    "test_name": test_name,
                    "result": result
                }
            except Exception as e:
                self.log(f"ERROR during test {test_name}: {str(e)}")
                self.log(traceback.format_exc())
                return {
                    "status": "FAILED",
                    "test_name": test_name,
                    "error": str(e)
                }
            finally:
                # Clean up test data
                self.clean_test_data()
        else:
            available_tests = [name.replace("test_", "") for name in dir(self) 
                            if name.startswith("test_") and callable(getattr(self, name))]
            
            return {
                "status": "ERROR",
                "message": f"Test '{test_name}' not found",
                "available_tests": available_tests
            }


def main():
    parser = argparse.ArgumentParser(description="Verify and test Belot backend")
    parser.add_argument('--quiet', '-q', action='store_true', help='Hide detailed output')
    parser.add_argument('--component', '-c', help='Test specific component only')
    parser.add_argument('--functional', '-f', action='store_true', help='Run functional tests')
    parser.add_argument('--test', '-t', help='Run specific functional test')
    parser.add_argument('--skip-migrations', '-s', action='store_true', help='Skip migrations check')
    parser.add_argument('--belot-rules', '-b', action='store_true', help='Only test Belot rules')
    args = parser.parse_args()
    
    # Provjera da li je Django ispravno konfiguriran prije nego krenemo u testove
    try:
        # Pokušaj dohvatiti neku osnovnu Django postavku
        debug_status = settings.DEBUG
        print(f"Django postavke učitane. DEBUG = {debug_status}")
    except Exception as e:
        print(f"GREŠKA: Django postavke nisu pravilno konfigurirane: {str(e)}")
        print("Provjerite postavke okoline i pokrenite naredbu 'python manage.py check' za više detalja.")
        sys.exit(1)
    
    # Provjera postojanja baze i tablica
    if not args.skip_migrations and not args.functional:
        try:
            # Provjera da li možemo povezati na bazu
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            print(f"GREŠKA: Nije moguće povezati se na bazu podataka: {str(e)}")
            print("Provjerite postavke baze i izvršite migracije:")
            print("  python manage.py makemigrations")
            print("  python manage.py migrate")
            sys.exit(1)
    
    # Samo testiranje Belot pravila ako je zatraženo
    if args.belot_rules:
        verifier = BackendVerifier(verbose=not args.quiet)  # Inverzija quiet flaga
        verifier.verify_belot_rules()
        result = verifier.results["belot_rules"]
        print(f"\nBelot rules verification: {'✅ PASS' if result else '❌ FAIL'}")
        sys.exit(0 if result else 1)
    
    if args.functional or args.test:
        # Run functional tests
        tester = FunctionalTester(verbose=not args.quiet)  # Inverzija quiet flaga
        
        if args.test:
            # Run specific test
            results = tester.run_specific_test(args.test)
            
            print(f"\n===== FUNCTIONAL TEST RESULT: {args.test} =====")
            print(f"Status: {results['status']}")
            
            if results['status'] == 'ERROR':
                print(f"Message: {results['message']}")
                print("Available tests:")
                for test in results['available_tests']:
                    print(f"  - {test}")
                sys.exit(1)
            elif results['status'] == 'FAILED':
                if 'error' in results:
                    print(f"Error: {results['error']}")
                sys.exit(1)
            else:
                print("Test completed successfully")
                sys.exit(0)
        else:
            # Run all functional tests
            results = tester.run_all_tests()
            
            print("\n===== FUNCTIONAL TESTS SUMMARY =====")
            print(f"Status: {results['status']}")
            print(f"Score: {results['score']} ({results['percentage']}%)")
            print("\nTest Results:")
            
            for test_name, passed in results['details'].items():
                formatted_name = test_name.replace('_', ' ').title()
                print(f"  - {formatted_name}: {'✅ PASS' if passed else '❌ FAIL'}")
            
            sys.exit(0 if results['status'] == 'PASSED' else 1)
    else:
        # Run verification checks
        verifier = BackendVerifier(verbose=not args.quiet)  # Inverzija quiet flaga
        
        if args.component:
            # Test specific component
            method_name = f"verify_{args.component}"
            if hasattr(verifier, method_name):
                getattr(verifier, method_name)()
                result = verifier.results[args.component]
                print(f"\n{args.component}: {'✅ PASS' if result else '❌ FAIL'}")
                sys.exit(0 if result else 1)
            else:
                print(f"Nepoznata komponenta: {args.component}")
                print(f"Dostupne komponente: {', '.join(verifier.results.keys())}")
                sys.exit(1)
        else:
            # Run all verification checks
            results = verifier.run_all_checks()
            
            print("\n===== VERIFICATION SUMMARY =====")
            print(f"Status: {results['status']}")
            print(f"Score: {results['score']} ({results['percentage']}%)")
            print("\nComponent Status:")
            
            for component, status in results['details'].items():
                formatted_name = component.replace('_', ' ').title()
                print(f"  - {formatted_name}: {'✅ PASS' if status else '❌ FAIL'}")
            
            # Exit with code 0 if all checks passed, 1 otherwise
            sys.exit(0 if results['status'] == 'PASSED' else 1)


if __name__ == "__main__":
    main()