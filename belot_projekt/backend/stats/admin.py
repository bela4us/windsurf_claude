"""
Admin sučelje za Django aplikaciju "stats".

Ovaj modul definira konfiguraciju admin sučelja
za modele iz aplikacije za statistiku Belot igre.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    PlayerStats, TeamStats, GameStats, GlobalStats,
    DailyStats, StatisticsSnapshot, Leaderboard
)


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model PlayerStats."""
    
    list_display = [
        'user', 'games_played', 'games_won', 'win_percentage_display',
        'total_score', 'avg_points_per_game', 'last_updated'
    ]
    list_filter = ['first_game_date', 'last_game_date']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'id', 'user', 'games_played', 'games_won', 'games_lost',
        'total_score', 'rounds_played', 'hearts_called', 'diamonds_called',
        'clubs_called', 'spades_called', 'belot_declarations',
        'four_of_a_kind_declarations', 'straight_declarations',
        'rounds_as_caller', 'rounds_won_as_caller', 'rounds_lost_as_caller',
        'avg_points_per_game', 'avg_points_per_round', 'highest_game_score',
        'longest_winning_streak', 'current_winning_streak', 'first_game_date',
        'last_game_date', 'total_play_time', 'last_updated',
        'win_percentage', 'most_called_suit', 'caller_success_rate'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'user', 'last_updated']
        }),
        (_('Statistika igara'), {
            'fields': [
                'games_played', 'games_won', 'games_lost',
                'win_percentage', 'total_score'
            ]
        }),
        (_('Statistika rundi'), {
            'fields': [
                'rounds_played', 'rounds_as_caller',
                'rounds_won_as_caller', 'rounds_lost_as_caller',
                'caller_success_rate'
            ]
        }),
        (_('Statistika aduta'), {
            'fields': [
                'hearts_called', 'diamonds_called',
                'clubs_called', 'spades_called',
                'most_called_suit'
            ]
        }),
        (_('Statistika zvanja'), {
            'fields': [
                'belot_declarations', 'four_of_a_kind_declarations',
                'straight_declarations'
            ]
        }),
        (_('Napredne statistike'), {
            'fields': [
                'avg_points_per_game', 'avg_points_per_round',
                'highest_game_score', 'longest_winning_streak',
                'current_winning_streak'
            ],
            'classes': ['collapse']
        }),
        (_('Vremenski podaci'), {
            'fields': [
                'first_game_date', 'last_game_date',
                'total_play_time'
            ],
            'classes': ['collapse']
        })
    ]
    
    def win_percentage_display(self, obj):
        """Formatirani prikaz postotka pobjeda."""
        return f"{obj.win_percentage}%"
    win_percentage_display.short_description = _('Postotak pobjeda')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje statistike igrača."""
        return False


@admin.register(TeamStats)
class TeamStatsAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model TeamStats."""
    
    list_display = [
        'team_display', 'games_played', 'games_won', 'win_percentage_display',
        'total_score', 'avg_points_per_game', 'last_updated'
    ]
    list_filter = ['first_game_date', 'last_game_date']
    search_fields = [
        'player1__username', 'player2__username',
        'player1__email', 'player2__email'
    ]
    readonly_fields = [
        'id', 'player1', 'player2', 'games_played', 'games_won', 'games_lost',
        'total_score', 'hearts_called', 'diamonds_called', 'clubs_called',
        'spades_called', 'avg_points_per_game', 'highest_game_score',
        'longest_winning_streak', 'current_winning_streak',
        'first_game_date', 'last_game_date', 'last_updated',
        'win_percentage', 'most_called_suit'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'player1', 'player2', 'last_updated']
        }),
        (_('Statistika igara'), {
            'fields': [
                'games_played', 'games_won', 'games_lost',
                'win_percentage', 'total_score'
            ]
        }),
        (_('Statistika aduta'), {
            'fields': [
                'hearts_called', 'diamonds_called',
                'clubs_called', 'spades_called',
                'most_called_suit'
            ]
        }),
        (_('Napredne statistike'), {
            'fields': [
                'avg_points_per_game', 'highest_game_score',
                'longest_winning_streak', 'current_winning_streak'
            ],
            'classes': ['collapse']
        }),
        (_('Vremenski podaci'), {
            'fields': [
                'first_game_date', 'last_game_date'
            ],
            'classes': ['collapse']
        })
    ]
    
    def team_display(self, obj):
        """Formatirani prikaz tima."""
        return f"{obj.player1.username} i {obj.player2.username}"
    team_display.short_description = _('Tim')
    
    def win_percentage_display(self, obj):
        """Formatirani prikaz postotka pobjeda."""
        return f"{obj.win_percentage}%"
    win_percentage_display.short_description = _('Postotak pobjeda')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje statistike timova."""
        return False


@admin.register(GameStats)
class GameStatsAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model GameStats."""
    
    list_display = [
        'game_link', 'total_rounds', 'duration_display',
        'team_a_score', 'team_b_score', 'winning_team_display',
        'start_time'
    ]
    list_filter = ['start_time', 'end_time']
    search_fields = ['game__id']
    readonly_fields = [
        'id', 'game', 'duration', 'start_time', 'end_time',
        'total_rounds', 'hearts_called', 'diamonds_called',
        'clubs_called', 'spades_called', 'belot_declarations',
        'four_of_a_kind_declarations', 'straight_declarations',
        'team_a_score', 'team_b_score', 'highest_scoring_round',
        'highest_round_score', 'created_at', 'updated_at',
        'most_called_suit', 'winning_team', 'score_difference',
        'average_round_score'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'game', 'created_at', 'updated_at']
        }),
        (_('Vremenski podaci'), {
            'fields': [
                'start_time', 'end_time', 'duration'
            ]
        }),
        (_('Statistika rundi'), {
            'fields': [
                'total_rounds', 'highest_scoring_round',
                'highest_round_score', 'average_round_score'
            ]
        }),
        (_('Statistika aduta'), {
            'fields': [
                'hearts_called', 'diamonds_called',
                'clubs_called', 'spades_called',
                'most_called_suit'
            ]
        }),
        (_('Statistika zvanja'), {
            'fields': [
                'belot_declarations', 'four_of_a_kind_declarations',
                'straight_declarations'
            ]
        }),
        (_('Rezultati'), {
            'fields': [
                'team_a_score', 'team_b_score',
                'winning_team', 'score_difference'
            ]
        })
    ]
    
    def duration_display(self, obj):
        """Formatirani prikaz trajanja."""
        total_seconds = obj.duration.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}min"
        else:
            return f"{minutes}min"
    duration_display.short_description = _('Trajanje')
    
    def winning_team_display(self, obj):
        """Formatirani prikaz pobjedničkog tima."""
        if obj.winning_team == 'A':
            return format_html('<span style="color: green;">Tim A</span>')
        elif obj.winning_team == 'B':
            return format_html('<span style="color: blue;">Tim B</span>')
        return '-'
    winning_team_display.short_description = _('Pobjednik')
    
    def game_link(self, obj):
        """Link na igru."""
        url = reverse('admin:game_game_change', args=[obj.game.id])
        return format_html('<a href="{}">{}</a>', url, obj.game.id)
    game_link.short_description = _('Igra')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje statistike igara."""
        return False


@admin.register(GlobalStats)
class GlobalStatsAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model GlobalStats."""
    
    list_display = [
        'id', 'total_games', 'total_players', 'games_in_progress',
        'avg_game_duration_display', 'last_updated'
    ]
    readonly_fields = [
        'id', 'total_games', 'total_players', 'total_rounds',
        'games_in_progress', 'avg_game_duration', 'total_play_time',
        'hearts_called', 'diamonds_called', 'clubs_called', 'spades_called',
        'belot_declarations', 'four_of_a_kind_declarations',
        'straight_declarations', 'last_updated', 'most_called_suit',
        'avg_rounds_per_game'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'last_updated']
        }),
        (_('Statistika igara'), {
            'fields': [
                'total_games', 'total_players', 'total_rounds',
                'games_in_progress', 'avg_rounds_per_game'
            ]
        }),
        (_('Vremenski podaci'), {
            'fields': [
                'avg_game_duration', 'total_play_time'
            ]
        }),
        (_('Statistika aduta'), {
            'fields': [
                'hearts_called', 'diamonds_called',
                'clubs_called', 'spades_called',
                'most_called_suit'
            ]
        }),
        (_('Statistika zvanja'), {
            'fields': [
                'belot_declarations', 'four_of_a_kind_declarations',
                'straight_declarations'
            ]
        })
    ]
    
    def avg_game_duration_display(self, obj):
        """Formatirani prikaz prosječnog trajanja igre."""
        total_seconds = obj.avg_game_duration.total_seconds()
        minutes = int(total_seconds // 60)
        return f"{minutes}min"
    avg_game_duration_display.short_description = _('Prosječno trajanje')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje globalne statistike."""
        return False


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model DailyStats."""
    
    list_display = [
        'date', 'total_games', 'active_players', 'new_users',
        'avg_game_duration_display', 'last_suit_display'
    ]
    list_filter = ['date']
    readonly_fields = [
        'date', 'total_games', 'active_players', 'total_rounds',
        'avg_game_duration', 'total_play_time', 'hearts_called',
        'diamonds_called', 'clubs_called', 'spades_called',
        'belot_declarations', 'four_of_a_kind_declarations',
        'straight_declarations', 'new_users', 'created_at',
        'updated_at', 'most_called_suit', 'avg_rounds_per_game'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['date', 'created_at', 'updated_at']
        }),
        (_('Statistika igara'), {
            'fields': [
                'total_games', 'active_players', 'total_rounds',
                'avg_rounds_per_game'
            ]
        }),
        (_('Vremenski podaci'), {
            'fields': [
                'avg_game_duration', 'total_play_time'
            ]
        }),
        (_('Statistika aduta'), {
            'fields': [
                'hearts_called', 'diamonds_called',
                'clubs_called', 'spades_called',
                'most_called_suit'
            ]
        }),
        (_('Statistika zvanja'), {
            'fields': [
                'belot_declarations', 'four_of_a_kind_declarations',
                'straight_declarations'
            ]
        }),
        (_('Korisnici'), {
            'fields': [
                'new_users'
            ]
        })
    ]
    
    def avg_game_duration_display(self, obj):
        """Formatirani prikaz prosječnog trajanja igre."""
        total_seconds = obj.avg_game_duration.total_seconds()
        minutes = int(total_seconds // 60)
        return f"{minutes}min"
    avg_game_duration_display.short_description = _('Prosječno trajanje')
    
    def last_suit_display(self, obj):
        """Formatirani prikaz najčešćeg aduta."""
        suit_map = {
            'hearts': '♥',
            'diamonds': '♦',
            'clubs': '♣',
            'spades': '♠'
        }
        return suit_map.get(obj.most_called_suit, obj.most_called_suit)
    last_suit_display.short_description = _('Najčešći adut')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje dnevne statistike."""
        return False


@admin.register(StatisticsSnapshot)
class StatisticsSnapshotAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model StatisticsSnapshot."""
    
    list_display = [
        'timestamp', 'total_games', 'total_players', 'active_players',
        'games_in_progress', 'new_users_last_day'
    ]
    list_filter = ['timestamp']
    readonly_fields = [
        'id', 'timestamp', 'total_games', 'total_players',
        'active_players', 'games_in_progress', 'top_suit',
        'avg_game_duration', 'new_users_last_day', 'new_games_last_day',
        'extra_data'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'timestamp']
        }),
        (_('Statistika'), {
            'fields': [
                'total_games', 'total_players', 'active_players',
                'games_in_progress', 'top_suit', 'avg_game_duration'
            ]
        }),
        (_('Dnevne aktivnosti'), {
            'fields': [
                'new_users_last_day', 'new_games_last_day'
            ]
        }),
        (_('Dodatni podaci'), {
            'fields': [
                'extra_data'
            ],
            'classes': ['collapse']
        })
    ]
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje snimki statistike."""
        return False


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model Leaderboard."""
    
    list_display = [
        'category_display', 'period_display', 'start_date', 'end_date',
        'player_count', 'top_player_display', 'updated_at'
    ]
    list_filter = ['period', 'category', 'updated_at']
    readonly_fields = [
        'id', 'period', 'category', 'start_date', 'end_date',
        'players', 'created_at', 'updated_at', 'player_count',
        'top_player'
    ]
    
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'period', 'category', 'created_at', 'updated_at']
        }),
        (_('Vremenski period'), {
            'fields': [
                'start_date', 'end_date'
            ]
        }),
        (_('Statistika'), {
            'fields': [
                'player_count', 'top_player'
            ]
        }),
        (_('Igrači na ljestvici'), {
            'fields': [
                'players'
            ],
            'classes': ['collapse']
        })
    ]
    
    def category_display(self, obj):
        """Formatirani prikaz kategorije."""
        return obj.get_category_display()
    category_display.short_description = _('Kategorija')
    category_display.admin_order_field = 'category'
    
    def period_display(self, obj):
        """Formatirani prikaz perioda."""
        return obj.get_period_display()
    period_display.short_description = _('Period')
    period_display.admin_order_field = 'period'
    
    def top_player_display(self, obj):
        """Formatirani prikaz najboljeg igrača."""
        top = obj.top_player
        if not top:
            return '-'
        
        return f"{top.get('username')} ({top.get('value')})"
    top_player_display.short_description = _('Najbolji igrač')
    
    def has_add_permission(self, request):
        """Onemogući ručno dodavanje ljestvica."""
        return False
    
    actions = ['update_leaderboard']
    
    def update_leaderboard(self, request, queryset):
        """Akcija za ažuriranje odabranih ljestvica."""
        for leaderboard in queryset:
            Leaderboard.update_leaderboard(leaderboard.period, leaderboard.category)
        
        self.message_user(request, _('Odabrane ljestvice su ažurirane.'))
    update_leaderboard.short_description = _('Ažuriraj odabrane ljestvice')