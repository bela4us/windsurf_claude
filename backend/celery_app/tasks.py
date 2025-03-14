<<<<<<< HEAD
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta
from ..game.models import Game, Player
from ..stats.models import GameStats
from ..utils.db_optimizations import db_optimizer
from ..cache.redis_cache import cache_manager
from celery.schedules import crontab
import json
import psutil
import os

logger = logging.getLogger(__name__)

@shared_task(
    name='send_game_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def send_game_notification(self, game_id: int, notification_type: str):
    """Asinkrono slanje obavijesti o igri"""
    try:
        game = Game.objects.get(id=game_id)
        players = game.players.all()
        
        # Pripremi email poruke
        subject = f"Belot - {notification_type}"
        message = f"Obavijest o igri {game.name}: {notification_type}"
        
        # Asinkrono pošalji email svim igračima
        for player in players:
            if player.email:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[player.email],
                    fail_silently=True
                )
        
        return True
    except Exception as e:
        logger.error(f"Greška pri slanju obavijesti: {e}")
        self.retry(exc=e)

@shared_task(
    name='update_game_stats',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def update_game_stats(self, game_id: int):
    """Asinkrono ažuriranje statistike igre"""
    try:
        game = Game.objects.get(id=game_id)
        
        # Pripremi statistiku
        stats = {
            'total_players': game.players.count(),
            'total_moves': game.moves.count(),
            'average_score': game.calculate_average_score(),
            'last_updated': datetime.now().isoformat()
        }
        
        # Spremi statistiku
        GameStats.objects.update_or_create(
            game=game,
            defaults=stats
        )
        
        # Invalidate cache
        cache_manager.invalidate_pattern(f"game_stats:{game_id}")
        
        return stats
    except Exception as e:
        logger.error(f"Greška pri ažuriranju statistike: {e}")
        self.retry(exc=e)

@shared_task(
    name='cleanup_old_games',
    bind=True,
    max_retries=3,
    default_retry_delay=3600
)
def cleanup_old_games(self, days: int = 30):
    """Asinkrono čišćenje starih igara"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        old_games = Game.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        )
        
        # Bulk delete starih igara
        count = db_optimizer.bulk_delete(old_games)
        
        # Invalidate cache
        cache_manager.invalidate_pattern("game:*")
        
        return f"Obrisano {count} starih igara"
    except Exception as e:
        logger.error(f"Greška pri čišćenju starih igara: {e}")
        self.retry(exc=e)

@shared_task(
    name='process_game_batch',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def process_game_batch(self, game_ids: List[int]):
    """Asinkrono procesiranje batch-a igara"""
    try:
        games = Game.objects.filter(id__in=game_ids)
        results = []
        
        for game in games:
            # Procesiraj svaku igru
            stats = update_game_stats.delay(game.id)
            results.append({
                'game_id': game.id,
                'status': 'processed',
                'stats': stats
            })
        
        return results
    except Exception as e:
        logger.error(f"Greška pri procesiranju batch-a: {e}")
        self.retry(exc=e)

@shared_task(
    name='generate_player_report',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def generate_player_report(self, player_id: int):
    """Asinkrono generiranje izvještaja za igrača"""
    try:
        player = Player.objects.get(id=player_id)
        
        # Pripremi podatke za izvještaj
        report = {
            'player_name': player.name,
            'total_games': player.games.count(),
            'win_rate': player.calculate_win_rate(),
            'average_score': player.calculate_average_score(),
            'generated_at': datetime.now().isoformat()
        }
        
        # Spremi izvještaj
        cache_manager.set(
            f"player_report:{player_id}",
            report,
            timeout=3600  # 1 sat
        )
        
        return report
    except Exception as e:
        logger.error(f"Greška pri generiranju izvještaja: {e}")
        self.retry(exc=e)

@shared_task
def send_email_notification(subject: str, message: str, recipient_list: list):
    """Asinkrono slanje email obavijesti"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email uspješno poslan: {subject}")
    except Exception as e:
        logger.error(f"Greška pri slanju emaila: {e}")
        raise

@shared_task
def cleanup_cache():
    """Čišćenje keša"""
    try:
        # Očisti stari keš
        cache.delete_pattern("old_cache:*")
        logger.info("Keš uspješno očišćen")
    except Exception as e:
        logger.error(f"Greška pri čišćenju keša: {e}")
        raise

@shared_task
def backup_database():
    """Backup baze podataka"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.sql"
        
        # Izvrši backup
        os.system(f"pg_dump -U {settings.DB_USER} {settings.DB_NAME} > {backup_file}")
        
        # Kompresiraj backup
        os.system(f"gzip {backup_file}")
        
        logger.info(f"Backup uspješno kreiran: {backup_file}.gz")
    except Exception as e:
        logger.error(f"Greška pri backupu baze: {e}")
        raise

@shared_task
def analyze_game_statistics():
    """Analiza statistike igre"""
    try:
        from game.models import Game
        from stats.models import GameStatistics
        
        # Prikupi statistiku
        games = Game.objects.filter(
            created_at__gte=datetime.now() - timedelta(days=7)
        )
        
        stats = {
            'total_games': games.count(),
            'avg_duration': games.aggregate(Avg('duration'))['duration__avg'],
            'total_players': games.values('players').distinct().count(),
        }
        
        # Spremi statistiku
        GameStatistics.objects.create(
            data=json.dumps(stats),
            period='weekly'
        )
        
        logger.info("Statistika igre uspješno analizirana")
    except Exception as e:
        logger.error(f"Greška pri analizi statistike: {e}")
        raise

@shared_task
def monitor_system_resources():
    """Praćenje sistemskih resursa"""
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'timestamp': datetime.now().isoformat()
        }
        
        # Spremi metrike
        cache.set('system_metrics', metrics, 3600)
        
        # Provjeri kritične vrijednosti
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            logger.warning(f"Kritične sistemske metrike: {metrics}")
            
        logger.info("Sistemske metrike uspješno ažurirane")
    except Exception as e:
        logger.error(f"Greška pri praćenju resursa: {e}")
        raise

@shared_task
def cleanup_old_data():
    """Čišćenje starih podataka"""
    try:
        from game.models import Game
        from lobby.models import Lobby
        
        # Obriši stare igre
        old_games = Game.objects.filter(
            created_at__lt=datetime.now() - timedelta(days=30)
        )
        old_games.delete()
        
        # Obriši stare lobbije
        old_lobbies = Lobby.objects.filter(
            created_at__lt=datetime.now() - timedelta(days=7)
        )
        old_lobbies.delete()
        
        logger.info("Stari podaci uspješno očišćeni")
    except Exception as e:
        logger.error(f"Greška pri čišćenju starih podataka: {e}")
        raise

@shared_task
def warm_cache():
    """Cache warming za često korištene podatke"""
    try:
        from game.models import Game
        from users.models import User
        
        # Keširaj aktivne igre
        active_games = Game.objects.filter(status='active')
        for game in active_games:
            cache.set(f"game:{game.id}", game, 300)
        
        # Keširaj aktivne korisnike
        active_users = User.objects.filter(is_active=True)
        for user in active_users:
            cache.set(f"user:{user.id}", user, 300)
        
        logger.info("Cache uspješno zagrijan")
    except Exception as e:
        logger.error(f"Greška pri cache warmingu: {e}")
        raise

# Konfiguracija Celery-a
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-games': {
        'task': 'cleanup_old_games',
        'schedule': crontab(hour=0, minute=0)  # Svaki dan u ponoć
    },
    'update-all-game-stats': {
        'task': 'update_game_stats',
        'schedule': crontab(minute='*/15')  # Svakih 15 minuta
    }
=======
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta
from ..game.models import Game, Player
from ..stats.models import GameStats
from ..utils.db_optimizations import db_optimizer
from ..cache.redis_cache import cache_manager
from celery.schedules import crontab
import json
import psutil
import os

logger = logging.getLogger(__name__)

@shared_task(
    name='send_game_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def send_game_notification(self, game_id: int, notification_type: str):
    """Asinkrono slanje obavijesti o igri"""
    try:
        game = Game.objects.get(id=game_id)
        players = game.players.all()
        
        # Pripremi email poruke
        subject = f"Belot - {notification_type}"
        message = f"Obavijest o igri {game.name}: {notification_type}"
        
        # Asinkrono pošalji email svim igračima
        for player in players:
            if player.email:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[player.email],
                    fail_silently=True
                )
        
        return True
    except Exception as e:
        logger.error(f"Greška pri slanju obavijesti: {e}")
        self.retry(exc=e)

@shared_task(
    name='update_game_stats',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def update_game_stats(self, game_id: int):
    """Asinkrono ažuriranje statistike igre"""
    try:
        game = Game.objects.get(id=game_id)
        
        # Pripremi statistiku
        stats = {
            'total_players': game.players.count(),
            'total_moves': game.moves.count(),
            'average_score': game.calculate_average_score(),
            'last_updated': datetime.now().isoformat()
        }
        
        # Spremi statistiku
        GameStats.objects.update_or_create(
            game=game,
            defaults=stats
        )
        
        # Invalidate cache
        cache_manager.invalidate_pattern(f"game_stats:{game_id}")
        
        return stats
    except Exception as e:
        logger.error(f"Greška pri ažuriranju statistike: {e}")
        self.retry(exc=e)

@shared_task(
    name='cleanup_old_games',
    bind=True,
    max_retries=3,
    default_retry_delay=3600
)
def cleanup_old_games(self, days: int = 30):
    """Asinkrono čišćenje starih igara"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        old_games = Game.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        )
        
        # Bulk delete starih igara
        count = db_optimizer.bulk_delete(old_games)
        
        # Invalidate cache
        cache_manager.invalidate_pattern("game:*")
        
        return f"Obrisano {count} starih igara"
    except Exception as e:
        logger.error(f"Greška pri čišćenju starih igara: {e}")
        self.retry(exc=e)

@shared_task(
    name='process_game_batch',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def process_game_batch(self, game_ids: List[int]):
    """Asinkrono procesiranje batch-a igara"""
    try:
        games = Game.objects.filter(id__in=game_ids)
        results = []
        
        for game in games:
            # Procesiraj svaku igru
            stats = update_game_stats.delay(game.id)
            results.append({
                'game_id': game.id,
                'status': 'processed',
                'stats': stats
            })
        
        return results
    except Exception as e:
        logger.error(f"Greška pri procesiranju batch-a: {e}")
        self.retry(exc=e)

@shared_task(
    name='generate_player_report',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def generate_player_report(self, player_id: int):
    """Asinkrono generiranje izvještaja za igrača"""
    try:
        player = Player.objects.get(id=player_id)
        
        # Pripremi podatke za izvještaj
        report = {
            'player_name': player.name,
            'total_games': player.games.count(),
            'win_rate': player.calculate_win_rate(),
            'average_score': player.calculate_average_score(),
            'generated_at': datetime.now().isoformat()
        }
        
        # Spremi izvještaj
        cache_manager.set(
            f"player_report:{player_id}",
            report,
            timeout=3600  # 1 sat
        )
        
        return report
    except Exception as e:
        logger.error(f"Greška pri generiranju izvještaja: {e}")
        self.retry(exc=e)

@shared_task
def send_email_notification(subject: str, message: str, recipient_list: list):
    """Asinkrono slanje email obavijesti"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email uspješno poslan: {subject}")
    except Exception as e:
        logger.error(f"Greška pri slanju emaila: {e}")
        raise

@shared_task
def cleanup_cache():
    """Čišćenje keša"""
    try:
        # Očisti stari keš
        cache.delete_pattern("old_cache:*")
        logger.info("Keš uspješno očišćen")
    except Exception as e:
        logger.error(f"Greška pri čišćenju keša: {e}")
        raise

@shared_task
def backup_database():
    """Backup baze podataka"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.sql"
        
        # Izvrši backup
        os.system(f"pg_dump -U {settings.DB_USER} {settings.DB_NAME} > {backup_file}")
        
        # Kompresiraj backup
        os.system(f"gzip {backup_file}")
        
        logger.info(f"Backup uspješno kreiran: {backup_file}.gz")
    except Exception as e:
        logger.error(f"Greška pri backupu baze: {e}")
        raise

@shared_task
def analyze_game_statistics():
    """Analiza statistike igre"""
    try:
        from game.models import Game
        from stats.models import GameStatistics
        
        # Prikupi statistiku
        games = Game.objects.filter(
            created_at__gte=datetime.now() - timedelta(days=7)
        )
        
        stats = {
            'total_games': games.count(),
            'avg_duration': games.aggregate(Avg('duration'))['duration__avg'],
            'total_players': games.values('players').distinct().count(),
        }
        
        # Spremi statistiku
        GameStatistics.objects.create(
            data=json.dumps(stats),
            period='weekly'
        )
        
        logger.info("Statistika igre uspješno analizirana")
    except Exception as e:
        logger.error(f"Greška pri analizi statistike: {e}")
        raise

@shared_task
def monitor_system_resources():
    """Praćenje sistemskih resursa"""
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'timestamp': datetime.now().isoformat()
        }
        
        # Spremi metrike
        cache.set('system_metrics', metrics, 3600)
        
        # Provjeri kritične vrijednosti
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            logger.warning(f"Kritične sistemske metrike: {metrics}")
            
        logger.info("Sistemske metrike uspješno ažurirane")
    except Exception as e:
        logger.error(f"Greška pri praćenju resursa: {e}")
        raise

@shared_task
def cleanup_old_data():
    """Čišćenje starih podataka"""
    try:
        from game.models import Game
        from lobby.models import Lobby
        
        # Obriši stare igre
        old_games = Game.objects.filter(
            created_at__lt=datetime.now() - timedelta(days=30)
        )
        old_games.delete()
        
        # Obriši stare lobbije
        old_lobbies = Lobby.objects.filter(
            created_at__lt=datetime.now() - timedelta(days=7)
        )
        old_lobbies.delete()
        
        logger.info("Stari podaci uspješno očišćeni")
    except Exception as e:
        logger.error(f"Greška pri čišćenju starih podataka: {e}")
        raise

@shared_task
def warm_cache():
    """Cache warming za često korištene podatke"""
    try:
        from game.models import Game
        from users.models import User
        
        # Keširaj aktivne igre
        active_games = Game.objects.filter(status='active')
        for game in active_games:
            cache.set(f"game:{game.id}", game, 300)
        
        # Keširaj aktivne korisnike
        active_users = User.objects.filter(is_active=True)
        for user in active_users:
            cache.set(f"user:{user.id}", user, 300)
        
        logger.info("Cache uspješno zagrijan")
    except Exception as e:
        logger.error(f"Greška pri cache warmingu: {e}")
        raise

# Konfiguracija Celery-a
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-games': {
        'task': 'cleanup_old_games',
        'schedule': crontab(hour=0, minute=0)  # Svaki dan u ponoć
    },
    'update-all-game-stats': {
        'task': 'update_game_stats',
        'schedule': crontab(minute='*/15')  # Svakih 15 minuta
    }
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
} 