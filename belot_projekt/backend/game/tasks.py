"""
Bridge modul za Celery zadatke vezane uz igru.

Ovaj modul ukazuje na postojeće implementacije Celery zadataka
iz celery_app i dodaje specifične zadatke vezane uz igru.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

# Uvoz općih zadataka iz celery_app
from celery_app.tasks import cleanup_expired_items

logger = logging.getLogger('game.tasks')

@shared_task
def cleanup_abandoned_games():
    """
    Čisti igre koje su napuštene i nisu aktivne dulje od 24 sata.
    """
    try:
        from game.models.game import Game
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        abandoned_games = Game.objects.filter(
            status__in=['waiting', 'paused'],
            last_activity__lt=cutoff_time
        )
        
        count = abandoned_games.count()
        if count > 0:
            abandoned_games.update(status='abandoned')
            
        return count
    except Exception as e:
        logger.error(f"Error cleaning up abandoned games: {str(e)}")
        return 0

@shared_task
def update_game_statistics(game_id):
    """
    Ažurira statistiku igre nakon završetka.
    """
    try:
        from game.models.game import Game
        from stats.models import PlayerStats, TeamStats
        
        game = Game.objects.get(id=game_id)
        
        # Samo ažuriramo statistiku za završene igre
        if game.status != 'completed':
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error updating game statistics: {str(e)}")
        return False