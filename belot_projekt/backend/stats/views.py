"""
Pogledi (views) za Django aplikaciju "stats".

Ovaj modul implementira poglede za prikaz statistika igre Belot,
uključujući osobne statistike, statistike timova, ljestvice i drugo.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.views.generic import TemplateView, ListView, DetailView, View
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta

from .models import (
    PlayerStats, TeamStats, GameStats, GlobalStats,
    DailyStats, StatisticsSnapshot, Leaderboard
)

User = get_user_model()
logger = logging.getLogger('stats.views')


class StatisticsHomeView(LoginRequiredMixin, TemplateView):
    """Početna stranica statistike."""
    template_name = 'stats/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['player_stats'] = PlayerStats.objects.get(user=self.request.user)
        context['global_stats'] = GlobalStats.get_instance()
        context['recent_games'] = GameStats.objects.filter(
            game__players=self.request.user
        ).order_by('-end_time')[:5]
        return context


class PlayerStatsDetailView(LoginRequiredMixin, DetailView):
    """Prikaz osobnih statistika igrača."""
    model = PlayerStats
    template_name = 'stats/player_stats_detail.html'
    context_object_name = 'player_stats'
    
    def get_object(self):
        if 'pk' in self.kwargs:
            return get_object_or_404(PlayerStats, user__id=self.kwargs['pk'])
        return get_object_or_404(PlayerStats, user=self.request.user)


class TeamStatsListView(LoginRequiredMixin, ListView):
    """Prikaz liste timskih statistika."""
    model = TeamStats
    template_name = 'stats/team_stats_list.html'
    context_object_name = 'team_stats'
    
    def get_queryset(self):
        return TeamStats.objects.filter(
            Q(player1=self.request.user) | Q(player2=self.request.user)
        ).order_by('-games_played')


class TeamStatsDetailView(LoginRequiredMixin, DetailView):
    """Prikaz detalja timske statistike."""
    model = TeamStats
    template_name = 'stats/team_stats_detail.html'
    context_object_name = 'team_stats'


class GameStatsListView(LoginRequiredMixin, ListView):
    """Prikaz liste statistika igara."""
    model = GameStats
    template_name = 'stats/game_stats_list.html'
    context_object_name = 'game_stats'
    
    def get_queryset(self):
        return GameStats.objects.filter(
            game__players=self.request.user
        ).order_by('-end_time')


class GameStatsDetailView(LoginRequiredMixin, DetailView):
    """Prikaz detalja statistike igre."""
    model = GameStats
    template_name = 'stats/game_stats_detail.html'
    context_object_name = 'game_stats'


class LeaderboardView(LoginRequiredMixin, TemplateView):
    """Prikaz ljestvica."""
    template_name = 'stats/leaderboards.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['leaderboards'] = Leaderboard.objects.all().order_by('category', 'period')
        return context


class LeaderboardCategoryView(LoginRequiredMixin, TemplateView):
    """Prikaz ljestvice po kategoriji."""
    template_name = 'stats/leaderboard_category.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.kwargs.get('category')
        context['leaderboards'] = Leaderboard.objects.filter(
            category=category
        ).order_by('period')
        context['category'] = category
        return context


class GlobalStatsView(LoginRequiredMixin, TemplateView):
    """Prikaz globalnih statistika."""
    template_name = 'stats/global_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['global_stats'] = GlobalStats.get_instance()
        context['daily_stats'] = DailyStats.objects.order_by('-date')[:30]
        return context


class PlayerCompareView(LoginRequiredMixin, TemplateView):
    """Prikaz usporedbe igrača."""
    template_name = 'stats/player_compare.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.exclude(id=self.request.user.id)
        return context


class PlayerCompareDetailView(LoginRequiredMixin, TemplateView):
    """Prikaz detalja usporedbe igrača."""
    template_name = 'stats/player_compare_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        player1 = get_object_or_404(User, id=self.kwargs.get('pk1'))
        player2 = get_object_or_404(User, id=self.kwargs.get('pk2'))
        
        context['player1_stats'] = get_object_or_404(PlayerStats, user=player1)
        context['player2_stats'] = get_object_or_404(PlayerStats, user=player2)
        
        return context


class StatsTrendsView(LoginRequiredMixin, TemplateView):
    """Prikaz trendova statistike."""
    template_name = 'stats/trends.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['daily_stats'] = DailyStats.objects.order_by('-date')[:30]
        return context


class StatsAnalyticsView(LoginRequiredMixin, TemplateView):
    """Prikaz analitike statistike."""
    template_name = 'stats/analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['global_stats'] = GlobalStats.get_instance()
        return context 