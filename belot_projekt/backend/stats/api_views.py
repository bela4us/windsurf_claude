"""
API pogledi za Django aplikaciju "stats".

Ovaj modul definira klase pogleda i viewsetove za REST API
statističkih podataka Belot igre.
"""

# Uvoz iz urls.api modula radi kompatibilnosti
from .urls.api import (
    PlayerStatsViewSet, TeamStatsViewSet, 
    GameStatsViewSet, GlobalStatsViewSet, 
    LeaderboardViewSet, DailyStatsViewSet
)

__all__ = [
    'PlayerStatsViewSet',
    'TeamStatsViewSet',
    'GameStatsViewSet',
    'GlobalStatsViewSet',
    'LeaderboardViewSet',
    'DailyStatsViewSet',
] 