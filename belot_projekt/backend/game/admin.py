"""
Konfiguracija Django admin sučelja za Belot igru.

Ovaj modul definira kako će modeli iz aplikacije game biti prikazani
u Django admin sučelju, omogućujući administratorima jednostavno
upravljanje igrama, rundama, potezima i ostalim entitetima.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, F, Q

from game.models.game import Game
from game.models.round import Round
from game.models.move import Move
from game.models.declaration import Declaration


class MoveInline(admin.TabularInline):
    """Inline prikaz poteza unutar runde."""
    model = Move
    extra = 0
    readonly_fields = ['order', 'player', 'card', 'is_winning']
    can_delete = False
    max_num = 0
    fields = ['order', 'player', 'card', 'is_winning']


class DeclarationInline(admin.TabularInline):
    """Inline prikaz zvanja unutar runde."""
    model = Declaration
    extra = 0
    readonly_fields = ['player', 'type', 'suit', 'cards', 'value']
    can_delete = False
    max_num = 0
    fields = ['player', 'type', 'suit', 'value', 'cards']


class RoundInline(admin.TabularInline):
    """Inline prikaz rundi unutar igre."""
    model = Round
    extra = 0
    readonly_fields = ['number', 'dealer', 'trump_suit', 'calling_team', 'winner_team', 
                      'team_a_score', 'team_b_score', 'is_completed', 'started_at', 'finished_at']
    can_delete = False
    max_num = 0
    fields = ['number', 'dealer', 'trump_suit', 'calling_team', 'winner_team', 
             'team_a_score', 'team_b_score', 'is_completed', 'started_at', 'finished_at']


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model Game."""
    list_display = ['id', 'room_code', 'creator_display', 'status', 'team_a_score', 
                   'team_b_score', 'winner_team', 'created_at', 'player_count', 'view_game_link']
    list_filter = ['status', 'created_at', 'is_private']
    search_fields = ['room_code', 'creator__username', 'players__username']
    readonly_fields = ['id', 'room_code', 'created_at', 'started_at', 'finished_at']
    fieldsets = [
        ('Osnovni podaci', {
            'fields': ['id', 'room_code', 'creator', 'status', 'points_to_win', 'is_private']
        }),
        ('Timovi', {
            'fields': ['team_a_players', 'team_b_players', 'team_a_score', 'team_b_score', 'winner_team']
        }),
        ('Igrači', {
            'fields': ['players', 'active_players']
        }),
        ('Vremenski podaci', {
            'fields': ['created_at', 'started_at', 'finished_at']
        })
    ]
    inlines = [RoundInline]
    filter_horizontal = ['players', 'active_players', 'team_a_players', 'team_b_players']
    
    def creator_display(self, obj):
        """Prikazuje kreatora igre s linkom na njegov profil."""
        if obj.creator:
            return format_html('<a href="{}">{}</a>',
                reverse('admin:users_user_change', args=(obj.creator.id,)),
                obj.creator.username)
        return '-'
    creator_display.short_description = 'Kreator'
    
    def player_count(self, obj):
        """Prikazuje broj igrača u igri."""
        return obj.players.count()
    player_count.short_description = 'Broj igrača'
    
    def view_game_link(self, obj):
        """Prikazuje link za pregled igre na frontendu."""
        return format_html('<a href="{}" target="_blank">Pregledaj igru</a>',
            reverse('game:detail', args=(obj.id,)))
    view_game_link.short_description = 'Akcije'
    
    def get_queryset(self, request):
        """Optimizira dohvat podataka iz baze s predučitavanjem povezanih modela."""
        return super().get_queryset(request).select_related('creator').prefetch_related(
            'players', 'active_players', 'team_a_players', 'team_b_players', 'rounds')


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model Round."""
    list_display = ['id', 'game_link', 'number', 'dealer_display', 'trump_suit_display', 
                   'calling_team', 'team_a_score', 'team_b_score', 'winner_team', 'is_completed']
    list_filter = ['is_completed', 'trump_suit', 'game__status']
    search_fields = ['game__room_code', 'dealer__username']
    readonly_fields = ['id', 'game', 'started_at', 'finished_at']
    fieldsets = [
        ('Osnovni podaci', {
            'fields': ['id', 'game', 'number', 'dealer', 'trump_suit', 'calling_team']
        }),
        ('Rezultati', {
            'fields': ['team_a_score', 'team_b_score', 'winner_team', 'is_completed']
        }),
        ('Vremenski podaci', {
            'fields': ['started_at', 'finished_at']
        })
    ]
    inlines = [DeclarationInline, MoveInline]
    
    def game_link(self, obj):
        """Prikazuje igru s linkom na detalje igre."""
        if obj.game:
            return format_html('<a href="{}">{}</a>',
                reverse('admin:game_game_change', args=(obj.game.id,)),
                obj.game.room_code)
        return '-'
    game_link.short_description = 'Igra'
    
    def dealer_display(self, obj):
        """Prikazuje djelitelja s linkom na njegov profil."""
        if obj.dealer:
            return format_html('<a href="{}">{}</a>',
                reverse('admin:users_user_change', args=(obj.dealer.id,)),
                obj.dealer.username)
        return '-'
    dealer_display.short_description = 'Djelitelj'
    
    def trump_suit_display(self, obj):
        """Prikazuje adutsku boju s ikonom."""
        suit_icons = {
            'spades': '♠️',
            'hearts': '♥️',
            'diamonds': '♦️',
            'clubs': '♣️',
            'no_trump': '✗',
            'all_trump': '★'
        }
        icon = suit_icons.get(obj.trump_suit, '')
        return format_html('{} {}', icon, obj.get_trump_suit_display())
    trump_suit_display.short_description = 'Adut'
    
    def get_queryset(self, request):
        """Optimizira dohvat podataka iz baze s predučitavanjem povezanih modela."""
        return super().get_queryset(request).select_related('game', 'dealer')


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model Move."""
    list_display = ['id', 'round_link', 'player_display', 'card', 'order', 
                   'is_winning', 'trick_number']
    list_filter = ['is_winning', 'is_valid', 'round__game__status']
    search_fields = ['round__game__room_code', 'player__username', 'card']
    readonly_fields = ['id', 'round']
    fieldsets = [
        ('Osnovni podaci', {
            'fields': ['id', 'round', 'player', 'card', 'order']
        }),
        ('Status', {
            'fields': ['is_winning', 'is_valid']
        })
    ]
    
    def round_link(self, obj):
        """Prikazuje rundu s linkom na detalje runde."""
        if obj.round:
            return format_html('<a href="{}">{} (Runda {})</a>',
                reverse('admin:game_round_change', args=(obj.round.id,)),
                obj.round.game.room_code, obj.round.number)
        return '-'
    round_link.short_description = 'Runda'
    
    def player_display(self, obj):
        """Prikazuje igrača s linkom na njegov profil."""
        if obj.player:
            return format_html('<a href="{}">{}</a>',
                reverse('admin:users_user_change', args=(obj.player.id,)),
                obj.player.username)
        return '-'
    player_display.short_description = 'Igrač'
    
    def trick_number(self, obj):
        """Prikazuje broj štiha kojemu pripada ovaj potez."""
        if obj.order is not None:
            return obj.order // 4 + 1
        return '-'
    trick_number.short_description = 'Štih #'
    
    def get_queryset(self, request):
        """Optimizira dohvat podataka iz baze s predučitavanjem povezanih modela."""
        return super().get_queryset(request).select_related('round', 'round__game', 'player')


@admin.register(Declaration)
class DeclarationAdmin(admin.ModelAdmin):
    """Admin konfiguracija za model Declaration."""
    list_display = ['id', 'round_link', 'player_display', 'type_display', 
                   'value', 'suit_display']
    list_filter = ['type', 'round__game__status']
    search_fields = ['round__game__room_code', 'player__username', 'type']
    readonly_fields = ['id', 'round', 'value']
    fieldsets = [
        ('Osnovni podaci', {
            'fields': ['id', 'round', 'player', 'type', 'suit']
        }),
        ('Detalji', {
            'fields': ['cards', 'value']
        })
    ]
    
    def round_link(self, obj):
        """Prikazuje rundu s linkom na detalje runde."""
        if obj.round:
            return format_html('<a href="{}">{} (Runda {})</a>',
                reverse('admin:game_round_change', args=(obj.round.id,)),
                obj.round.game.room_code, obj.round.number)
        return '-'
    round_link.short_description = 'Runda'
    
    def player_display(self, obj):
        """Prikazuje igrača s linkom na njegov profil."""
        if obj.player:
            return format_html('<a href="{}">{}</a>',
                reverse('admin:users_user_change', args=(obj.player.id,)),
                obj.player.username)
        return '-'
    player_display.short_description = 'Igrač'
    
    def type_display(self, obj):
        """Prikazuje tip zvanja s ikonom."""
        type_icons = {
            'bela': '👑',
            'four_of_a_kind': '4️⃣',
            'sequence_3': '3️⃣',
            'sequence_4': '4️⃣',
            'sequence_5': '5️⃣',
            'sequence_6': '6️⃣',
            'sequence_7': '7️⃣',
            'sequence_8': '8️⃣',
        }
        icon = type_icons.get(obj.type, '')
        return format_html('{} {}', icon, obj.get_type_display())
    type_display.short_description = 'Tip zvanja'
    
    def suit_display(self, obj):
        """Prikazuje boju zvanja s ikonom."""
        if not obj.suit:
            return '-'
            
        suit_icons = {
            'S': '♠️',
            'H': '♥️',
            'D': '♦️',
            'C': '♣️',
        }
        icon = suit_icons.get(obj.suit, '')
        return format_html('{} {}', icon, obj.get_suit_display())
    suit_display.short_description = 'Boja'
    
    def get_queryset(self, request):
        """Optimizira dohvat podataka iz baze s predučitavanjem povezanih modela."""
        return super().get_queryset(request).select_related('round', 'round__game', 'player')