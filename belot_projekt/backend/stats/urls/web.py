"""
URL konfiguracija za web sučelje Django aplikacije "stats".

Ovaj modul definira URL rute za prikaz statistika igre Belot,
uključujući osobne statistike, statistike timova, ljestvice i drugo.
"""

from django.urls import path

from .. import views

app_name = 'stats'

urlpatterns = [
    # Početna stranica statistike
    path('', views.StatisticsHomeView.as_view(), name='home'),
    
    # Osobne statistike
    path('player/', views.PlayerStatsDetailView.as_view(), name='player_stats'),
    path('player/<uuid:pk>/', views.PlayerStatsDetailView.as_view(), name='player_stats_detail'),
    
    # Statistike timova
    path('teams/', views.TeamStatsListView.as_view(), name='team_stats'),
    path('teams/<uuid:pk>/', views.TeamStatsDetailView.as_view(), name='team_stats_detail'),
    
    # Povijest igara
    path('games/', views.GameStatsListView.as_view(), name='game_stats'),
    path('games/<uuid:pk>/', views.GameStatsDetailView.as_view(), name='game_stats_detail'),
    
    # Ljestvice
    path('leaderboards/', views.LeaderboardView.as_view(), name='leaderboards'),
    path('leaderboards/<str:category>/', views.LeaderboardCategoryView.as_view(), name='leaderboard_category'),
    
    # Globalne statistike
    path('global/', views.GlobalStatsView.as_view(), name='global_stats'),
    
    # Usporedba igrača
    path('compare/', views.PlayerCompareView.as_view(), name='player_compare'),
    path('compare/<uuid:pk1>/<uuid:pk2>/', views.PlayerCompareDetailView.as_view(), name='player_compare_detail'),
    
    # Trendovi
    path('trends/', views.StatsTrendsView.as_view(), name='trends'),
    
    # Analitika
    path('analytics/', views.StatsAnalyticsView.as_view(), name='analytics'),
]