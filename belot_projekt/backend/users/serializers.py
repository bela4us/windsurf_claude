"""
Modul za jednostavan uvoz serializera iz users aplikacije.

Ovaj modul omogućuje jednostavan uvoz serializera iz users aplikacije
bez potrebe za direktnim uvozom iz poddirektorija.

Korištenje:
    from users.serializers import UserSerializer, RegisterSerializer
    
    serializer = UserSerializer(data=request.data)
    ...
"""

from .serializers.user_serializers import (
    UserSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserProfileSerializer,
    UserStatsSerializer,
    UserPreferencesSerializer,
)

from .serializers.auth_serializers import (
    RegisterSerializer,
    LoginSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
    PasswordChangeSerializer,
    TokenRefreshSerializer,
    EmailVerificationSerializer,
    UserDeviceSerializer,
)

# Definiramo javni API ovog modula
__all__ = [
    # User serializeri
    'UserSerializer',           # Osnovni serializer za prikaz korisnika
    'UserDetailSerializer',     # Detaljni prikaz korisnika
    'UserCreateSerializer',     # Stvaranje korisnika
    'UserUpdateSerializer',     # Ažuriranje korisnika
    'UserProfileSerializer',    # Profil korisnika
    'UserStatsSerializer',      # Statistike korisnika
    'UserPreferencesSerializer',# Postavke korisnika
    
    # Auth serializeri
    'RegisterSerializer',       # Registracija novog korisnika
    'LoginSerializer',          # Prijava korisnika
    'PasswordResetSerializer',  # Zahtjev za resetiranje lozinke
    'PasswordResetConfirmSerializer',  # Potvrda resetiranja lozinke
    'PasswordChangeSerializer', # Promjena lozinke
    'TokenRefreshSerializer',   # Obnavljanje tokena
    'EmailVerificationSerializer',  # Verifikacija e-maila
    'UserDeviceSerializer',     # Upravljanje korisničkim uređajima
] 