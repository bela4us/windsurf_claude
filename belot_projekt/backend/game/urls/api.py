"""
Konfiguracija URL-ova za API igre Belot.

Ovaj modul definira URL obrasce za REST API endpointe
koji omogućuju pristup resursima igre putem HTTP metoda.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Promijenjeno importiranje - koristi direktni import iz api_views 
# umjesto iz game.views.api_views
try:
    # Probaj prvo ovaj import
    from game.views.api_views import (
        GameViewSet, RoundViewSet, MoveViewSet, DeclarationViewSet,
        GameActionView, GameStatisticsView, CurrentGamesView
    )
except ImportError:
    # Ako ne uspije, koristi originalni import
    from game.views.api_views import (
        GameViewSet, RoundViewSet, MoveViewSet, DeclarationViewSet,
        GameActionView, GameStatisticsView, CurrentGamesView
    )

# Stvaramo router za ViewSet klase
router = DefaultRouter()
router.register(r'games', GameViewSet)
router.register(r'rounds', RoundViewSet)
router.register(r'moves', MoveViewSet)
router.register(r'declarations', DeclarationViewSet)

# URL obrasci za API
urlpatterns = [
    # ViewSet rute
    path('', include(router.urls)),
    
    # Dodatne API rute
    path('games/<uuid:game_id>/action/', GameActionView.as_view(), name='game-action'),
    path('games/<uuid:game_id>/statistics/', GameStatisticsView.as_view(), name='game-statistics'),
    path('statistics/', GameStatisticsView.as_view(), name='global-statistics'),
    path('current-games/', CurrentGamesView.as_view(), name='current-games'),
]