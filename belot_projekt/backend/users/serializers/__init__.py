"""
Inicijalizacijski modul za paket serializera u Django aplikaciji "users".

Ovaj modul definira serializere koji se koriste za pretvaranje složenih tipova podataka
(poput Django querysetova i instanci modela) u nativne Python tipove koji se mogu lako
pretvoriti u JSON ili druge formate, i obrnuto.

Serializeri u ovom paketu se koriste za:
1. Izlaganje korisničkih podataka kroz REST API
2. Slanje korisničkih podataka putem WebSocket kanala
3. Validaciju ulaznih podataka od klijenata
4. Pretvaranje tipova podataka između različitih dijelova aplikacije

Ovaj paket sadrži serializere za:
- Korisnike (User model): osnovni prikaz, detalji, profil, statistike
- Korisničke profile i postavke: preferencije, teme, obavijesti
- Autentikaciju: registracija, prijava, obnavljanje tokena, resetiranje lozinke
- Upravljanje uređajima: registracija uređaja za push notifikacije
"""

from .user_serializers import (
    UserSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserProfileSerializer,
    UserStatsSerializer,
    UserPreferencesSerializer,
)

from .auth_serializers import (
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