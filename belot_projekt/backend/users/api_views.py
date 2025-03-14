"""
API pogledi za Django aplikaciju "users".

Ovaj modul definira klase pogleda i viewsetove za REST API
korisničkih podataka u Belot igri.
"""

from rest_framework import viewsets, generics, permissions, status, mixins, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

from .serializers import (
    UserSerializer, UserDetailSerializer, UserCreateSerializer, 
    UserUpdateSerializer, UserProfileSerializer, UserStatsSerializer,
    UserPreferencesSerializer, RegisterSerializer, LoginSerializer, 
    PasswordResetSerializer, PasswordResetConfirmSerializer,
    PasswordChangeSerializer, TokenRefreshSerializer, 
    EmailVerificationSerializer, UserDeviceSerializer
)

User = get_user_model()


class StandardResultsPagination(PageNumberPagination):
    """Standardna paginacija za API."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AuthRateThrottle(AnonRateThrottle):
    """Ograničavanje broja pokušaja autentikacije za anonimne korisnike."""
    rate = '5/min'  # 5 zahtjeva po minuti


class UserRateThrottle(UserRateThrottle):
    """Ograničavanje broja zahtjeva za prijavljene korisnike."""
    rate = '10/min'  # 10 zahtjeva po minuti


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet za pregledavanje i uređivanje korisničkih podataka.
    
    Omogućuje CRUD operacije nad korisničkim podacima, s različitim
    razinama pristupa ovisno o autentikaciji i autorizaciji.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering_fields = ['username', 'date_joined', 'elo_rating']
    ordering = ['-elo_rating']  # Zadani poredak
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        """Filtrira korisnike prema zahtjevu."""
        queryset = User.objects.all()
        
        # Filtriranje po polju "active" ako je specificirano
        is_active = self.request.query_params.get('active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        # Filtriranje po elo ratingu
        min_elo = self.request.query_params.get('min_elo')
        if min_elo and min_elo.isdigit():
            queryset = queryset.filter(elo_rating__gte=int(min_elo))
        
        max_elo = self.request.query_params.get('max_elo')
        if max_elo and max_elo.isdigit():
            queryset = queryset.filter(elo_rating__lte=int(max_elo))
        
        # Filtriranje po broju odigranih igara
        min_games = self.request.query_params.get('min_games')
        if min_games and min_games.isdigit():
            queryset = queryset.filter(total_games__gte=int(min_games))
        
        return queryset
    
    def get_serializer_class(self):
        """Odabir odgovarajućeg serializera ovisno o akciji."""
        if self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return UserUpdateSerializer
        elif self.action == 'profile':
            return UserProfileSerializer
        elif self.action == 'stats':
            return UserStatsSerializer
        elif self.action == 'preferences':
            return UserPreferencesSerializer
        return UserSerializer
    
    def get_permissions(self):
        """Postavlja dozvole ovisno o akciji."""
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Samo vlasnik računa ili admin može mijenjati/brisati račun
            # Ovo bi trebalo biti implementirano kroz custom permission klasu
            return [permissions.IsAdminUser()]  # Privremeno samo admin
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Ažurira korisnika prilikom stvaranja."""
        user = serializer.save()
        # Ovdje možete obaviti dodatne radnje nakon stvaranja korisnika
        # Npr. slanje pozdravnog emaila
    
    def perform_update(self, serializer):
        """Ažurira korisnika."""
        user = serializer.save()
        # Ovdje možete obaviti dodatne radnje nakon ažuriranja korisnika
        # Npr. zabilježiti povijest izmjena
    
    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """Dohvaća profil korisnika."""
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Dohvaća statistike korisnika."""
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Dohvaća podatke trenutno prijavljenog korisnika."""
        # Ažuriranje zadnje aktivnosti korisnika
        request.user.last_active = timezone.now()
        request.user.save(update_fields=['last_active'])
        
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'put', 'patch'])
    def preferences(self, request, pk=None):
        """Dohvaća ili ažurira korisničke postavke."""
        user = self.get_object()
        
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def top_players(self, request):
        """Dohvaća najbolje igrače po elo ratingu."""
        limit = int(request.query_params.get('limit', 10))
        top_users = User.objects.filter(is_active=True, total_games__gt=0).order_by('-elo_rating')[:limit]
        serializer = UserSerializer(top_users, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Napredna pretraga korisnika."""
        query = request.query_params.get('q', '')
        if not query:
            return Response([], status=status.HTTP_200_OK)
        
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query)
        )
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = UserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class RegisterView(generics.CreateAPIView):
    """
    Pogled za registraciju novih korisnika.
    
    Omogućuje korisnicima da se registriraju s korisničkim imenom,
    e-mail adresom i lozinkom.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Registrira novog korisnika i vraća token za autentikaciju."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Stvaranje tokena za autentikaciju
        token, created = Token.objects.get_or_create(user=user)
        
        # Slanje potvrdnog e-maila
        # Ovdje treba implementirati slanje e-maila
        
        # Zabilježi IP adresu i datum registracije
        user.registration_ip = self.get_client_ip(request)
        user.save(update_fields=['registration_ip'])
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        """Dohvaća IP adresu klijenta."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LoginView(APIView):
    """
    Pogled za prijavu korisnika.
    
    Omogućuje korisnicima da se prijave s korisničkim imenom/e-mailom i lozinkom.
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Prijavljuje korisnika i vraća token za autentikaciju."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        remember_me = serializer.validated_data.get('remember_me', False)
        
        # Prijava korisnika u sesiju
        login(request, user)
        
        # Ako remember_me nije aktivan, postavi kraći rok trajanja sesije
        if not remember_me:
            request.session.set_expiry(0)  # Istječe kad se zatvori preglednik
        
        # Stvaranje ili dohvaćanje tokena
        token, created = Token.objects.get_or_create(user=user)
        
        # Ažuriranje zadnje prijave
        user.last_login = timezone.now()
        user.last_login_ip = self.get_client_ip(request)
        user.save(update_fields=['last_login', 'last_login_ip'])
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        })
    
    def get_client_ip(self, request):
        """Dohvaća IP adresu klijenta."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LogoutView(APIView):
    """
    Pogled za odjavu korisnika.
    
    Omogućuje korisnicima da se odjave i ponište svoj token.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Odjavljuje korisnika i poništava token."""
        # Poništavanje tokena
        try:
            request.user.auth_token.delete()
        except (AttributeError, Token.DoesNotExist):
            pass
        
        # Odjava iz sesije
        logout(request)
        
        # Ažuriranje zadnje odjave
        user = request.user
        if user.is_authenticated:
            user.last_logout = timezone.now()
            user.save(update_fields=['last_logout'])
        
        return Response({"detail": "Uspješno ste odjavljeni."}, status=status.HTTP_200_OK)


class PasswordResetView(APIView):
    """
    Pogled za resetiranje lozinke.
    
    Omogućuje korisnicima da zatraže resetiranje lozinke putem e-maila.
    """
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Šalje e-mail za resetiranje lozinke."""
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email__iexact=email)
            
            # Implementacija slanja e-maila za resetiranje lozinke
            # Ovdje treba implementirati generiranje tokena i slanje e-maila
            
            # Zabilježi zahtjev za reset lozinke
            user.password_reset_requested = timezone.now()
            user.save(update_fields=['password_reset_requested'])
            
        except User.DoesNotExist:
            # Ne otkrivamo da korisnik ne postoji zbog sigurnosti
            pass
        
        # Uvijek vraćamo uspjeh, čak i ako korisnik ne postoji
        return Response({"detail": "E-mail za resetiranje lozinke je poslan ako korisnik postoji."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Pogled za potvrdu resetiranja lozinke.
    
    Omogućuje korisnicima da postave novu lozinku nakon klika na link u e-mailu.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Postavlja novu lozinku."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Implementacija provjere tokena i postavljanja nove lozinke
        # Ovdje treba implementirati provjeru tokena i uid-a te postavljanje nove lozinke
        
        return Response({"detail": "Lozinka je uspješno promijenjena."}, status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    """
    Pogled za promjenu lozinke.
    
    Omogućuje korisnicima da promijene svoju lozinku.
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Mijenja lozinku korisnika."""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Promjena lozinke
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        
        # Zabilježi promjenu lozinke
        user.password_last_changed = timezone.now()
        user.save(update_fields=['password', 'password_last_changed'])
        
        # Poništavanje svih tokena korisnika za dodatnu sigurnost
        Token.objects.filter(user=user).delete()
        
        # Stvaranje novog tokena
        token, created = Token.objects.get_or_create(user=user)
        
        # Odjava iz svih ostalih sesija
        if hasattr(request, 'session'):
            request.session.flush()
        
        # Ponovno prijavi korisnika u trenutnu sesiju
        login(request, user)
        
        return Response({
            "detail": "Lozinka je uspješno promijenjena.",
            "token": token.key
        }, status=status.HTTP_200_OK)


class EmailVerificationView(APIView):
    """
    Pogled za verifikaciju e-mail adrese.
    
    Koristi se za verifikaciju e-mail adrese korisnika.
    """
    serializer_class = EmailVerificationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request, *args, **kwargs):
        """Verificira e-mail adresu korisnika."""
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Implementacija verifikacije e-mail adrese
        # Ovdje treba implementirati provjeru tokena i označavanje e-maila kao verificiranog
        
        return Response({"detail": "E-mail adresa je uspješno verificirana."}, status=status.HTTP_200_OK)


class UserDeviceViewSet(mixins.CreateModelMixin, 
                         mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin,
                         viewsets.GenericViewSet):
    """
    ViewSet za upravljanje korisničkim uređajima za notifikacije.
    
    Omogućuje registraciju, ažuriranje i brisanje uređaja korisnika
    za slanje push notifikacija.
    """
    serializer_class = UserDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Stvara novi uređaj povezan s korisnikom."""
        # Implementacija registracije uređaja
        pass
    
    def perform_update(self, serializer):
        """Ažurira postojeći uređaj korisnika."""
        # Implementacija ažuriranja uređaja
        pass
    
    def perform_destroy(self, instance):
        """Briše uređaj korisnika."""
        # Implementacija brisanja uređaja
        pass


# Definiramo javni API ovog modula
__all__ = [
    'UserViewSet',
    'RegisterView',
    'LoginView',
    'LogoutView',
    'PasswordResetView',
    'PasswordResetConfirmView',
    'PasswordChangeView',
    'EmailVerificationView',
    'UserDeviceViewSet',
] 