"""
Admin konfiguracija za Django aplikaciju "lobby".

Ovaj modul definira kako će se modeli lobby aplikacije
prikazivati u Django admin sučelju. Omogućuje administratorima
lako upravljanje sobama, porukama, pozivnicama i drugim
elementima predvorja Belot igre.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import (
    LobbyRoom, 
    LobbyMembership, 
    LobbyInvitation, 
    LobbyMessage, 
    LobbyEvent
)


class LobbyMembershipInline(admin.TabularInline):
    """
    Inline prikaz članstava sobe u predvorju.
    
    Prikazuje se unutar admin prikaza LobbyRoom modela.
    """
    model = LobbyMembership
    extra = 0
    readonly_fields = ['joined_at']
    autocomplete_fields = ['user']
    

class LobbyMessageInline(admin.TabularInline):
    """
    Inline prikaz poruka u sobi.
    
    Prikazuje se unutar admin prikaza LobbyRoom modela.
    """
    model = LobbyMessage
    extra = 0
    readonly_fields = ['sender', 'created_at', 'is_system_message']
    fields = ['sender', 'content', 'created_at', 'is_system_message']
    ordering = ['-created_at']
    max_num = 20
    

class LobbyInvitationInline(admin.TabularInline):
    """
    Inline prikaz pozivnica u sobu.
    
    Prikazuje se unutar admin prikaza LobbyRoom modela.
    """
    model = LobbyInvitation
    extra = 0
    readonly_fields = ['sender', 'created_at', 'status']
    fields = ['sender', 'recipient', 'status', 'created_at', 'expires_at']
    autocomplete_fields = ['recipient']
    

class LobbyEventInline(admin.TabularInline):
    """
    Inline prikaz događaja u sobi.
    
    Prikazuje se unutar admin prikaza LobbyRoom modela.
    """
    model = LobbyEvent
    extra = 0
    readonly_fields = ['user', 'event_type', 'created_at']
    fields = ['user', 'event_type', 'message', 'created_at', 'is_private']
    ordering = ['-created_at']
    max_num = 20


@admin.register(LobbyRoom)
class LobbyRoomAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model LobbyRoom.
    """
    list_display = [
        'name', 
        'room_code', 
        'creator', 
        'status', 
        'is_private', 
        'player_count',
        'created_at',
        'view_game_link'
    ]
    list_filter = ['status', 'is_private', 'created_at', 'use_quick_format']
    search_fields = ['name', 'room_code', 'creator__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['creator', 'game']
    inlines = [
        LobbyMembershipInline,
        LobbyInvitationInline,
        LobbyMessageInline,
        LobbyEventInline
    ]
    fieldsets = [
        (_('Osnovne informacije'), {
            'fields': ['id', 'name', 'room_code', 'creator', 'status']
        }),
        (_('Postavke'), {
            'fields': ['is_private', 'max_players', 'points_to_win', 'use_quick_format']
        }),
        (_('Vremenske oznake'), {
            'fields': ['created_at', 'updated_at', 'active_until']
        }),
        (_('Povezana igra'), {
            'fields': ['game']
        })
    ]
    
    def player_count(self, obj):
        """Prikazuje broj igrača u sobi."""
        count = obj.lobbymembership_set.count()
        return f"{count}/{obj.max_players}"
    player_count.short_description = _('Broj igrača')
    
    def view_game_link(self, obj):
        """Prikazuje poveznicu na igru ako postoji."""
        if obj.game:
            url = reverse('admin:game_game_change', args=[obj.game.id])
            return format_html('<a href="{}">Vidi igru</a>', url)
        return '-'
    view_game_link.short_description = _('Igra')


@admin.register(LobbyMembership)
class LobbyMembershipAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model LobbyMembership.
    """
    list_display = ['user', 'room_name', 'joined_at', 'is_ready']
    list_filter = ['is_ready', 'joined_at']
    search_fields = ['user__username', 'room__name', 'room__room_code']
    readonly_fields = ['joined_at']
    autocomplete_fields = ['user', 'room']
    
    def room_name(self, obj):
        """Prikazuje ime sobe."""
        return obj.room.name
    room_name.short_description = _('Soba')
    room_name.admin_order_field = 'room__name'


@admin.register(LobbyInvitation)
class LobbyInvitationAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model LobbyInvitation.
    """
    list_display = [
        'id', 
        'sender', 
        'recipient', 
        'room_name', 
        'status', 
        'created_at', 
        'expires_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'sender__username', 
        'recipient__username', 
        'room__name', 
        'message'
    ]
    readonly_fields = ['id', 'created_at']
    autocomplete_fields = ['sender', 'recipient', 'room']
    actions = ['expire_invitations']
    
    def room_name(self, obj):
        """Prikazuje ime sobe."""
        return obj.room.name
    room_name.short_description = _('Soba')
    room_name.admin_order_field = 'room__name'
    
    def expire_invitations(self, request, queryset):
        """Akcija za označavanje odabranih pozivnica kao isteklih."""
        count = queryset.filter(status='pending').update(status='expired')
        self.message_user(
            request, 
            _(f"{count} pozivnica je označeno kao isteklo.")
        )
    expire_invitations.short_description = _('Označi odabrane pozivnice kao istekle')


@admin.register(LobbyMessage)
class LobbyMessageAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model LobbyMessage.
    """
    list_display = [
        'id', 
        'sender', 
        'room_name', 
        'short_content', 
        'created_at',
        'is_system_message'
    ]
    list_filter = ['is_system_message', 'created_at']
    search_fields = ['sender__username', 'room__name', 'content']
    readonly_fields = ['id', 'created_at']
    autocomplete_fields = ['sender', 'room']
    
    def room_name(self, obj):
        """Prikazuje ime sobe."""
        return obj.room.name
    room_name.short_description = _('Soba')
    room_name.admin_order_field = 'room__name'
    
    def short_content(self, obj):
        """Prikazuje skraćeni sadržaj poruke."""
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    short_content.short_description = _('Sadržaj')


@admin.register(LobbyEvent)
class LobbyEventAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model LobbyEvent.
    """
    list_display = [
        'id', 
        'room_name', 
        'user', 
        'event_type', 
        'short_message', 
        'created_at',
        'is_private'
    ]
    list_filter = ['event_type', 'is_private', 'created_at']
    search_fields = ['user__username', 'room__name', 'message']
    readonly_fields = ['id', 'created_at']
    autocomplete_fields = ['user', 'room', 'private_recipient']
    
    def room_name(self, obj):
        """Prikazuje ime sobe."""
        return obj.room.name
    room_name.short_description = _('Soba')
    room_name.admin_order_field = 'room__name'
    
    def short_message(self, obj):
        """Prikazuje skraćenu poruku događaja."""
        if len(obj.message) > 50:
            return f"{obj.message[:50]}..."
        return obj.message
    short_message.short_description = _('Poruka')