"""
API URL konfiguracija za Django aplikaciju "users".

Ovaj modul definira URL uzorke za REST API endpointe vezane uz
korisnike, autentikaciju i profile.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..api_views import (
    UserViewSet, RegisterView, LoginView, LogoutView,
    PasswordResetView, PasswordResetConfirmView, PasswordChangeView, 
    EmailVerificationView, UserDeviceViewSet
)

# Definiranje verzije API-ja
API_VERSION = 'v1'

# Inicijaliziraj router za viewsetove
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'devices', UserDeviceViewSet, basename='user-device')

# URL uzorci za API - verzija 1
# Svi URL-ovi će imati prefiks /api/v1/
urlpatterns = [
    # Autentikacijski endpointi
    path(f'{API_VERSION}/auth/register/', RegisterView.as_view(), name='register'),
    path(f'{API_VERSION}/auth/login/', LoginView.as_view(), name='login'),
    path(f'{API_VERSION}/auth/logout/', LogoutView.as_view(), name='logout'),
    path(f'{API_VERSION}/auth/password/reset/', PasswordResetView.as_view(), name='password-reset'),
    path(f'{API_VERSION}/auth/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path(f'{API_VERSION}/auth/password/change/', PasswordChangeView.as_view(), name='password-change'),
    path(f'{API_VERSION}/auth/email/verify/', EmailVerificationView.as_view(), name='email-verify'),
    
    # Dodatni posebni endpointi
    path(f'{API_VERSION}/users/me/', UserViewSet.as_view({'get': 'me'}), name='current-user'),
    path(f'{API_VERSION}/users/top/', UserViewSet.as_view({'get': 'top_players'}), name='top-players'),
    path(f'{API_VERSION}/users/search/', UserViewSet.as_view({'get': 'search'}), name='user-search'),

    # REST API endpointi - uključuju sve rute definirane u routeru
    path(f'{API_VERSION}/', include(router.urls)),
]

# Alias za trenutnu verziju API-ja
# Ovo omogućuje pristup bez eksplicitnog navođenja verzije
urlpatterns += [
    # Autentikacijski endpointi bez verzije
    path('auth/register/', RegisterView.as_view(), name='register-current'),
    path('auth/login/', LoginView.as_view(), name='login-current'),
    path('auth/logout/', LogoutView.as_view(), name='logout-current'),
    path('auth/password/reset/', PasswordResetView.as_view(), name='password-reset-current'),
    path('auth/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm-current'),
    path('auth/password/change/', PasswordChangeView.as_view(), name='password-change-current'),
    path('auth/email/verify/', EmailVerificationView.as_view(), name='email-verify-current'),
    
    # Dodatni posebni endpointi bez verzije
    path('users/me/', UserViewSet.as_view({'get': 'me'}), name='current-user-current'),
    path('users/top/', UserViewSet.as_view({'get': 'top_players'}), name='top-players-current'),
    path('users/search/', UserViewSet.as_view({'get': 'search'}), name='user-search-current'),

    # REST API endpointi bez verzije - uključuju sve rute definirane u routeru
    path('', include(router.urls)),
] 