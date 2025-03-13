"""
URL konfiguracija za API endpointe Django aplikacije "users".

Ovaj modul definira URL rute za REST API funkcionalnosti korisničkih računa,
uključujući registraciju, prijavu, upravljanje profilom, prijateljstva i drugo.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..api_views import (
    UserViewSet, ProfileViewSet, FriendshipViewSet, NotificationViewSet,
    AchievementViewSet, AuthAPIView, RegistrationAPIView,
    EmailVerificationAPIView, PasswordResetRequestAPIView, PasswordResetConfirmAPIView
)

# Stvaramo router za ViewSet klase
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'profiles', ProfileViewSet)
router.register(r'friendships', FriendshipViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'achievements', AchievementViewSet)

app_name = 'users_api'

urlpatterns = [
    # ViewSet rute
    path('', include(router.urls)),
    
    # Autentikacija
    path('auth/', AuthAPIView.as_view(), name='auth'),
    path('register/', RegistrationAPIView.as_view(), name='register'),
    path('verify-email/', EmailVerificationAPIView.as_view(), name='verify_email'),
    path('reset-password/', PasswordResetRequestAPIView.as_view(), name='reset_password'),
    path('reset-password/confirm/', PasswordResetConfirmAPIView.as_view(), name='reset_password_confirm'),
]