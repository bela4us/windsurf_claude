"""
Admin konfiguracija za Django aplikaciju "users".

Ovaj modul definira kako će se modeli users aplikacije
prikazivati u Django admin sučelju. Omogućuje administratorima
lako upravljanje korisnicima, profilima, prijateljstvima i
drugim korisničkim podacima.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import User, Profile, Friendship, Achievement, UserAchievement, Notification


class ProfileInline(admin.StackedInline):
    """
    Inline prikaz korisničkog profila.
    
    Prikazuje se unutar admin prikaza User modela.
    """
    model = Profile
    can_delete = False
    verbose_name_plural = 'profil'
    fk_name = 'user'


class UserAchievementInline(admin.TabularInline):
    """
    Inline prikaz korisničkih postignuća.
    
    Prikazuje se unutar admin prikaza Profile modela.
    """
    model = UserAchievement
    extra = 0
    verbose_name = _('Postignuće')
    verbose_name_plural = _('Postignuća')
    readonly_fields = ['unlocked_at']
    autocomplete_fields = ['achievement']


class CustomUserAdmin(UserAdmin):
    """
    Admin konfiguracija za model User.
    
    Proširuje standardni Django UserAdmin s poljima
    specifičnim za Belot aplikaciju.
    """
    list_display = (
        'username', 'email', 'nickname', 'is_email_verified',
        'is_online', 'rating', 'games_played', 'get_win_rate',
        'date_joined', 'is_staff', 'is_active'
    )
    list_filter = (
        'is_email_verified', 'is_online', 'is_active',
        'is_staff', 'date_joined'
    )
    search_fields = (
        'username', 'email', 'nickname', 'first_name', 'last_name'
    )
    ordering = ('-date_joined',)
    
    inlines = [ProfileInline]
    
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        (_('Osobni podaci'), {'fields': ('first_name', 'last_name', 'nickname', 'bio', 'date_of_birth', 'avatar')}),
        (_('Verifikacija'), {'fields': ('is_email_verified', 'verification_token')}),
        (_('Privatnost'), {'fields': ('is_profile_public', 'show_online_status')}),
        (_('Status'), {'fields': ('is_online', 'last_activity')}),
        (_('Statistika'), {'fields': ('rating', 'games_played', 'games_won', 'games_lost')}),
        (_('Obavijesti'), {'fields': ('receive_email_notifications', 'receive_game_invites', 'receive_friend_requests')}),
        (_('Dozvole'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Važni datumi'), {'fields': ('last_login', 'date_joined')}),
    )
    
    def get_win_rate(self, obj):
        """Prikazuje postotak pobjeda."""
        return f"{obj.get_win_rate()}%"
    get_win_rate.short_description = _('Postotak pobjeda')
    get_win_rate.admin_order_field = 'games_won'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model Profile.
    """
    list_display = [
        'user', 'preferred_game_type', 'preferred_card_deck',
        'sound_enabled', 'music_enabled', 'language', 'created_at'
    ]
    list_filter = [
        'preferred_game_type', 'preferred_card_deck', 'sound_enabled',
        'music_enabled', 'animation_speed', 'language', 'auto_ready'
    ]
    search_fields = ['user__username', 'user__email', 'user__nickname']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [UserAchievementInline]
    
    def get_queryset(self, request):
        """Optimizira upite prefetchanjem veza."""
        return super().get_queryset(request).select_related('user')


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model Friendship.
    """
    list_display = [
        'id', 'sender', 'receiver', 'status', 'created_at', 'updated_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'sender__username', 'sender__email',
        'receiver__username', 'receiver__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['sender', 'receiver']
    actions = ['mark_as_accepted', 'mark_as_declined', 'mark_as_blocked']
    
    def mark_as_accepted(self, request, queryset):
        """Označava odabrana prijateljstva kao prihvaćena."""
        queryset.update(status='accepted')
        self.message_user(request, _(f"{queryset.count()} prijateljstava je označeno kao prihvaćeno."))
    mark_as_accepted.short_description = _('Označi kao prihvaćeno')
    
    def mark_as_declined(self, request, queryset):
        """Označava odabrana prijateljstva kao odbijena."""
        queryset.update(status='declined')
        self.message_user(request, _(f"{queryset.count()} prijateljstava je označeno kao odbijeno."))
    mark_as_declined.short_description = _('Označi kao odbijeno')
    
    def mark_as_blocked(self, request, queryset):
        """Označava odabrana prijateljstva kao blokirana."""
        queryset.update(status='blocked')
        self.message_user(request, _(f"{queryset.count()} prijateljstava je označeno kao blokirano."))
    mark_as_blocked.short_description = _('Označi kao blokirano')


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model Achievement.
    """
    list_display = [
        'name', 'achievement_type', 'threshold', 'points',
        'created_at', 'user_count'
    ]
    list_filter = ['achievement_type', 'points', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    
    def user_count(self, obj):
        """Prikazuje broj korisnika koji su otključali postignuće."""
        return obj.users.count()
    user_count.short_description = _('Broj korisnika')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin konfiguracija za model Notification.
    """
    list_display = [
        'id', 'user', 'notification_type', 'title', 'is_read',
        'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
    autocomplete_fields = ['user']
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        """Označava odabrane obavijesti kao pročitane."""
        queryset.update(is_read=True)
        self.message_user(request, _(f"{queryset.count()} obavijesti je označeno kao pročitano."))
    mark_as_read.short_description = _('Označi kao pročitano')
    
    def mark_as_unread(self, request, queryset):
        """Označava odabrane obavijesti kao nepročitane."""
        queryset.update(is_read=False)
        self.message_user(request, _(f"{queryset.count()} obavijesti je označeno kao nepročitano."))
    mark_as_unread.short_description = _('Označi kao nepročitano')


# Registracija modela u admin sučelju
admin.site.register(User, CustomUserAdmin)