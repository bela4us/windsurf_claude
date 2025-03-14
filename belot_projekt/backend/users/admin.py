"""
Admin konfiguracija za Django aplikaciju "users".

Ovaj modul definira kako će se modeli users aplikacije
prikazivati u Django admin sučelju. Omogućuje administratorima
lako upravljanje korisnicima i njihovim profilima.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

User = get_user_model()

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin konfiguracija za model User.
    """
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Osobni podaci'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Dozvole'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Važni datumi'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    ordering = ['username']
    filter_horizontal = ['groups', 'user_permissions'] 