"""
URL konfiguracija za web sučelje Belot igre.
"""
from django.urls import path
from game.views.game_views import (
    LobbyView, GameCreateView, GameJoinView, 
    GameDetailView, GamePlayView, GameListView
)

# Web URL putanje za game aplikaciju
urlpatterns = [
    # Prikaz igre
    path('', LobbyView.as_view(), name='game_lobby'),
    path('<int:pk>/', GameDetailView.as_view(), name='game_detail'),
    path('create/', GameCreateView.as_view(), name='create_game'),
    path('join/', GameJoinView.as_view(), name='join_game'),
    path('join/<str:room_code>/', GameJoinView.as_view(), name='join_game_by_code'),
    path('play/<int:pk>/', GamePlayView.as_view(), name='play'),
    path('list/', GameListView.as_view(), name='game_list'),
]