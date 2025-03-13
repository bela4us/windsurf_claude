"""
Pogledi (views) za Django aplikaciju "users".

Ovaj modul implementira poglede za rad s korisnicima Belot igre,
uključujući registraciju, prijavu, profil, statistiku, prijatelje i
druge korisničke funkcionalnosti.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, DetailView, ListView, View
from django.views.generic.edit import FormView
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _

# Dodani REST Framework importi
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .forms.web_forms import (
    CustomUserCreationForm, CustomAuthenticationForm, CustomPasswordChangeForm,
    CustomPasswordResetForm, UserProfileForm, ProfileSettingsForm, 
    PrivacySettingsForm, FriendRequestForm, SearchUsersForm
)
from .models import Profile, Friendship, Achievement, Notification

User = get_user_model()
logger = logging.getLogger('users.views')

# Dodani UserSerializer
class UserSerializer(serializers.ModelSerializer):
    """
    Serializator za korisnički model.
    
    Omogućuje transformaciju korisničkog modela u JSON reprezentaciju
    i obrnuto, za korištenje u API-ju.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True}
        }

class RegisterView(CreateView):
    """
    Pogled za registraciju novih korisnika.
    """
    template_name = 'users/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        """
        Sprema korisnika, generira verifikacijski token i šalje
        email za verifikaciju.
        """
        # Spremi korisnika
        user = form.save(commit=False)
        
        # Generiraj verifikacijski token
        import uuid
        import hashlib
        token = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
        user.verification_token = token
        
        # Spremi korisnika u bazu
        user.save()
        
        # Pošalji email za verifikaciju (u stvarnoj aplikaciji)
        # send_verification_email(user.email, token)
        
        # Prikaži poruku o uspjehu
        messages.success(
            self.request,
            _('Registracija uspješna! Provjerite email za verifikaciju računa.')
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        context['title'] = _('Registracija')
        return context


class LoginView(FormView):
    """
    Pogled za prijavu korisnika.
    """
    template_name = 'users/login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('lobby:home')
    
    def form_valid(self, form):
        """Prijavljuje korisnika i ažurira status aktivnosti."""
        # Dohvati podatke iz forme
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me', False)
        
        # Pokušaj autentikaciju s korisničkim imenom
        user = authenticate(username=username, password=password)
        
        # Ako nije uspjelo, pokušaj s emailom
        if not user and '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        
        if user:
            # Prijavi korisnika
            login(self.request, user)
            
            # Postavi duljinu sessije ako je "zapamti me"
            if not remember_me:
                self.request.session.set_expiry(0)  # Istječe pri zatvaranju preglednika
            
            # Ažuriraj online status
            user.update_online_status(True)
            
            # Preusmjeri na traženu stranicu ako postoji
            next_url = self.request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            messages.success(self.request, _('Uspješna prijava!'))
            return super().form_valid(form)
        else:
            messages.error(self.request, _('Nevažeće korisničko ime ili lozinka.'))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        context['title'] = _('Prijava')
        return context


@login_required
def logout_view(request):
    """
    Pogled za odjavu korisnika.
    """
    # Ažuriraj online status
    request.user.update_online_status(False)
    
    # Odjavi korisnika
    logout(request)
    
    messages.success(request, _('Uspješno ste se odjavili.'))
    return redirect('users:login')


class VerifyEmailView(View):
    """
    Pogled za verifikaciju email adrese.
    """
    def get(self, request, token):
        """Verificira email adresu putem tokena."""
        # Pronađi korisnika s tim tokenom
        try:
            user = User.objects.get(verification_token=token)
            
            # Verificiraj korisnika
            user.is_email_verified = True
            user.verification_token = ''
            user.save()
            
            messages.success(request, _('Email adresa je uspješno verificirana! Sada se možete prijaviti.'))
            return redirect('users:login')
            
        except User.DoesNotExist:
            messages.error(request, _('Nevažeći token za verifikaciju.'))
            return redirect('users:login')


class UserProfileView(DetailView):
    """
    Pogled za prikaz korisničkog profila.
    """
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'
    
    def get_object(self):
        """Dohvaća korisnika prema username parametru."""
        username = self.kwargs.get('username')
        return get_object_or_404(User, username=username)
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()
        
        # Ako profil nije javan i trenutni korisnik nije vlasnik,
        # prikaži ograničene informacije
        is_owner = self.request.user == profile_user
        is_public = profile_user.is_profile_public
        
        if not is_owner and not is_public and not self.request.user.is_staff:
            context['limited_view'] = True
        else:
            context['limited_view'] = False
            
            # Dohvati prijateljstvo između korisnika
            if self.request.user.is_authenticated and not is_owner:
                friendship = Friendship.objects.filter(
                    (Q(sender=self.request.user, receiver=profile_user) | 
                    Q(sender=profile_user, receiver=self.request.user))
                ).first()
                context['friendship'] = friendship
                
                if not friendship:
                    context['can_send_request'] = True
        
        # Dohvati nedavne igre korisnika
        from game.models import Game, Round, Move
        recent_games = Game.objects.filter(
            players=profile_user
        ).order_by('-created_at')[:10]
        context['recent_games'] = recent_games
        
        # Dohvati statistiku
        context['win_rate'] = profile_user.get_win_rate()
        
        # Dohvati postignuća
        achievements = profile_user.profile.achievements.all()
        context['achievements'] = achievements
        
        return context


@method_decorator(login_required, name='dispatch')
class EditProfileView(UpdateView):
    """
    Pogled za uređivanje korisničkog profila.
    """
    model = User
    form_class = UserProfileForm
    template_name = 'users/edit_profile.html'
    
    def get_object(self):
        """Dohvaća trenutnog korisnika."""
        return self.request.user
    
    def get_success_url(self):
        """Vraća URL za preusmjeravanje nakon uspješnog ažuriranja."""
        messages.success(self.request, _('Profil je uspješno ažuriran!'))
        return reverse('users:profile', kwargs={'username': self.request.user.username})


@method_decorator(login_required, name='dispatch')
class EditProfileSettingsView(UpdateView):
    """
    Pogled za uređivanje postavki profila.
    """
    model = Profile
    form_class = ProfileSettingsForm
    template_name = 'users/edit_settings.html'
    
    def get_object(self):
        """Dohvaća profil trenutnog korisnika."""
        return self.request.user.profile
    
    def get_success_url(self):
        """Vraća URL za preusmjeravanje nakon uspješnog ažuriranja."""
        messages.success(self.request, _('Postavke su uspješno ažurirane!'))
        return reverse('users:profile', kwargs={'username': self.request.user.username})


@method_decorator(login_required, name='dispatch')
class EditPrivacySettingsView(UpdateView):
    """
    Pogled za uređivanje postavki privatnosti.
    """
    model = User
    form_class = PrivacySettingsForm
    template_name = 'users/edit_privacy.html'
    
    def get_object(self):
        """Dohvaća trenutnog korisnika."""
        return self.request.user
    
    def get_success_url(self):
        """Vraća URL za preusmjeravanje nakon uspješnog ažuriranja."""
        messages.success(self.request, _('Postavke privatnosti su uspješno ažurirane!'))
        return reverse('users:profile', kwargs={'username': self.request.user.username})


@method_decorator(login_required, name='dispatch')
class ChangePasswordView(FormView):
    """
    Pogled za promjenu lozinke.
    """
    form_class = CustomPasswordChangeForm
    template_name = 'users/change_password.html'
    success_url = reverse_lazy('users:profile')
    
    def get_form_kwargs(self):
        """Dodaje korisnika u kwargs za formular."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Sprema novu lozinku i ažurira sessiju."""
        form.save()
        messages.success(self.request, _('Lozinka je uspješno promijenjena!'))
        
        # Ažuriraj sessionu da korisnik ostane prijavljen
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(self.request, form.user)
        
        return super().form_valid(form)
    
    def get_success_url(self):
        """Vraća URL za preusmjeravanje nakon uspješne promjene lozinke."""
        return reverse('users:profile', kwargs={'username': self.request.user.username})


@method_decorator(login_required, name='dispatch')
class FriendsListView(ListView):
    """
    Pogled za prikaz liste prijatelja.
    """
    template_name = 'users/friends.html'
    context_object_name = 'friendships'
    paginate_by = 20
    
    def get_queryset(self):
        """Dohvaća listu prijatelja za trenutnog korisnika."""
        user = self.request.user
        
        # Dohvati prihvaćena prijateljstva
        friendships = Friendship.objects.filter(
            (Q(sender=user) | Q(receiver=user)),
            status='accepted'
        ).select_related('sender', 'receiver')
        
        return friendships
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Dohvati primljene zahtjeve za prijateljstvo
        friend_requests = Friendship.objects.filter(
            receiver=user,
            status='pending'
        ).select_related('sender')
        context['friend_requests'] = friend_requests
        
        # Dohvati poslane zahtjeve za prijateljstvo
        sent_requests = Friendship.objects.filter(
            sender=user,
            status='pending'
        ).select_related('receiver')
        context['sent_requests'] = sent_requests
        
        # Dohvati blokirane korisnike
        blocked_users = Friendship.objects.filter(
            sender=user,
            status='blocked'
        ).select_related('receiver')
        context['blocked_users'] = blocked_users
        
        return context


@login_required
def send_friend_request(request, username):
    """
    Pogled za slanje zahtjeva za prijateljstvo.
    """
    # Dohvati ciljnog korisnika
    recipient = get_object_or_404(User, username=username)
    
    # Provjeri da korisnik ne šalje zahtjev samom sebi
    if request.user == recipient:
        messages.error(request, _('Ne možete poslati zahtjev za prijateljstvo sami sebi.'))
        return redirect('users:profile', username=username)
    
    # Provjeri postojeće prijateljstvo ili zahtjev
    existing = Friendship.objects.filter(
        (Q(sender=request.user, receiver=recipient) | 
         Q(sender=recipient, receiver=request.user))
    ).first()
    
    if existing:
        if existing.status == 'accepted':
            messages.info(request, _('Već ste prijatelji s ovim korisnikom.'))
        elif existing.status == 'pending':
            messages.info(request, _('Zahtjev za prijateljstvo je već poslan.'))
        elif existing.status == 'blocked':
            messages.error(request, _('Ne možete poslati zahtjev ovom korisniku.'))
        return redirect('users:profile', username=username)
    
    # Stvori novo prijateljstvo
    friendship = Friendship.objects.create(
        sender=request.user,
        receiver=recipient,
        status='pending'
    )
    
    # Stvori obavijest za primatelja
    Notification.objects.create(
        user=recipient,
        notification_type='friend_request',
        title=_('Novi zahtjev za prijateljstvo'),
        message=f"{request.user.username} vam je poslao/la zahtjev za prijateljstvo.",
        related_object_id=str(friendship.id)
    )
    
    messages.success(request, _('Zahtjev za prijateljstvo je uspješno poslan.'))
    return redirect('users:profile', username=username)


@login_required
def respond_to_friend_request(request, friendship_id, action):
    """
    Pogled za odgovaranje na zahtjev za prijateljstvo.
    """
    # Dohvati prijateljstvo
    friendship = get_object_or_404(
        Friendship,
        id=friendship_id,
        receiver=request.user,
        status='pending'
    )
    
    # Obradi akciju
    if action == 'accept':
        # Prihvati zahtjev
        friendship.status = 'accepted'
        friendship.save()
        
        # Stvori obavijest za pošiljatelja
        Notification.objects.create(
            user=friendship.sender,
            notification_type='friend_accept',
            title=_('Zahtjev za prijateljstvo prihvaćen'),
            message=f"{request.user.username} je prihvatio/la vaš zahtjev za prijateljstvo.",
            related_object_id=str(friendship.id)
        )
        
        messages.success(request, _('Zahtjev za prijateljstvo je prihvaćen.'))
    elif action == 'decline':
        # Odbij zahtjev
        friendship.status = 'declined'
        friendship.save()
        
        messages.info(request, _('Zahtjev za prijateljstvo je odbijen.'))
    else:
        messages.error(request, _('Nevažeća akcija.'))
    
    # Preusmjeri na listu prijatelja
    return redirect('users:friends')


@login_required
def remove_friend(request, friendship_id):
    """
    Pogled za uklanjanje prijatelja.
    """
    # Dohvati prijateljstvo
    friendship = get_object_or_404(
        Friendship,
        id=friendship_id,
        status='accepted'
    )
    
    # Provjeri je li korisnik dio prijateljstva
    if request.user != friendship.sender and request.user != friendship.receiver:
        messages.error(request, _('Nemate ovlasti za ovu akciju.'))
        return redirect('users:friends')
    
    # Odredi drugog korisnika u prijateljstvu
    other_user = friendship.receiver if friendship.sender == request.user else friendship.sender
    
    # Obriši prijateljstvo
    friendship.delete()
    
    # Ispravljeno - korektan način za f-string s _() funkcijom za prijevod
    messages.success(request, f"{_('Uklonili ste')} {other_user.username} {_('iz prijatelja')}")
    return redirect('users:friends')


@login_required
def block_user(request, username):
    """
    Pogled za blokiranje korisnika.
    """
    # Dohvati ciljnog korisnika
    target_user = get_object_or_404(User, username=username)
    
    # Provjeri da korisnik ne blokira samog sebe
    if request.user == target_user:
        messages.error(request, _('Ne možete blokirati sami sebe.'))
        return redirect('users:profile', username=username)
    
    # Provjeri postojeće prijateljstvo
    existing = Friendship.objects.filter(
        (Q(sender=request.user, receiver=target_user) | 
         Q(sender=target_user, receiver=request.user))
    ).first()
    
    if existing:
        if existing.status == 'blocked' and existing.sender == request.user:
            messages.info(request, _('Već ste blokirali ovog korisnika.'))
            return redirect('users:friends')
        
        # Obriši postojeće prijateljstvo
        existing.delete()
    
    # Stvori novi blokirani odnos
    Friendship.objects.create(
        sender=request.user,
        receiver=target_user,
        status='blocked'
    )
    
    # Ispravljeno - korektan način za f-string s _() funkcijom za prijevod
    messages.success(request, f"{_('Uspješno ste blokirali korisnika')} {target_user.username}")
    return redirect('users:friends')


@login_required
def unblock_user(request, friendship_id):
    """
    Pogled za deblokiranje korisnika.
    """
    # Dohvati prijateljstvo
    friendship = get_object_or_404(
        Friendship,
        id=friendship_id,
        sender=request.user,
        status='blocked'
    )
    
    # Obriši blokirani odnos
    friendship.delete()
    
    # Ispravljeno - korektan način za f-string s _() funkcijom za prijevod
    messages.success(request, f"{_('Uspješno ste deblokirali korisnika')} {friendship.receiver.username}")
    return redirect('users:friends')


@method_decorator(login_required, name='dispatch')
class UserSearchView(ListView):
    """
    Pogled za pretraživanje korisnika.
    """
    template_name = 'users/search.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        """Dohvaća korisnike prema kriterijima pretrage."""
        form = SearchUsersForm(self.request.GET)
        
        # Inicijalni queryset - isključi trenutnog korisnika
        queryset = User.objects.exclude(id=self.request.user.id)
        
        if form.is_valid():
            query = form.cleaned_data.get('query')
            show_only_online = form.cleaned_data.get('show_only_online')
            sort_by = form.cleaned_data.get('sort_by')
            
            # Filtriraj po upitu pretrage
            if query:
                queryset = queryset.filter(
                    Q(username__icontains=query) |
                    Q(nickname__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query)
                )
            
            # Filtriraj po online statusu
            if show_only_online:
                queryset = queryset.filter(is_online=True)
            
            # Sortiraj rezultate
            if sort_by:
                if sort_by == 'username':
                    queryset = queryset.order_by('username')
                elif sort_by == 'rating':
                    queryset = queryset.order_by('-rating')
                elif sort_by == 'games_played':
                    queryset = queryset.order_by('-games_played')
                elif sort_by == 'date_joined':
                    queryset = queryset.order_by('-date_joined')
            else:
                # Zadano sortiranje
                queryset = queryset.order_by('username')
        
        # Označi odnos prijateljstva za svakog korisnika
        for user in queryset:
            friendship = Friendship.objects.filter(
                (Q(sender=self.request.user, receiver=user) | 
                 Q(sender=user, receiver=self.request.user))
            ).first()
            
            if friendship:
                user.friendship_status = friendship.status
                user.friendship_id = friendship.id
            else:
                user.friendship_status = None
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        context['form'] = SearchUsersForm(self.request.GET)
        return context


@method_decorator(login_required, name='dispatch')
class NotificationsView(ListView):
    """
    Pogled za prikaz korisničkih obavijesti.
    """
    template_name = 'users/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
    def get_queryset(self):
        """Dohvaća obavijesti za trenutnog korisnika."""
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get(self, request, *args, **kwargs):
        """Označava sve obavijesti kao pročitane."""
        # Dohvati nepročitane obavijesti
        unread = Notification.objects.filter(
            user=request.user,
            is_read=False
        )
        
        # Označi sve kao pročitane
        unread.update(is_read=True)
        
        return super().get(request, *args, **kwargs)


@login_required
def mark_notification_read(request, notification_id):
    """
    Pogled za označavanje obavijesti kao pročitane.
    """
    # Dohvati obavijest
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    
    # Označi kao pročitanu
    notification.is_read = True
    notification.save()
    
    # Ako je AJAX zahtjev, vrati JSON odgovor
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    # Inače, preusmjeri natrag na obavijesti
    return redirect('users:notifications')


@login_required
def clear_all_notifications(request):
    """
    Pogled za brisanje svih obavijesti.
    """
    # Obriši sve obavijesti korisnika
    Notification.objects.filter(user=request.user).delete()
    
    messages.success(request, _('Sve obavijesti su uspješno obrisane.'))
    return redirect('users:notifications')


@method_decorator(login_required, name='dispatch')
class AchievementsView(ListView):
    """
    Pogled za prikaz korisničkih postignuća.
    """
    template_name = 'users/achievements.html'
    context_object_name = 'achievements'
    
    def get_queryset(self):
        """Dohvaća postignuća za trenutnog korisnika."""
        # Dohvati sva postignuća
        all_achievements = Achievement.objects.all()
        
        # Dohvati otključana postignuća korisnika
        unlocked_ids = self.request.user.profile.achievements.values_list('id', flat=True)
        
        # Označi koja postignuća su otključana
        for achievement in all_achievements:
            achievement.is_unlocked = achievement.id in unlocked_ids
        
        return all_achievements
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        
        # Dohvati broj otključanih postignuća
        unlocked_count = self.request.user.profile.achievements.count()
        total_count = Achievement.objects.count()
        
        context['unlocked_count'] = unlocked_count
        context['total_count'] = total_count
        context['completion_percentage'] = (unlocked_count / total_count * 100) if total_count > 0 else 0
        
        return context


@method_decorator(login_required, name='dispatch')
class StatsView(DetailView):
    """
    Pogled za prikaz detaljne statistike korisnika.
    """
    model = User
    template_name = 'users/stats.html'
    context_object_name = 'profile_user'
    
    def get_object(self):
        """Dohvaća korisnika prema username parametru ili trenutnog korisnika."""
        username = self.kwargs.get('username')
        if username:
            return get_object_or_404(User, username=username)
        return self.request.user
    
    def get_context_data(self, **kwargs):
        """Dodaj dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        # Dohvati statistiku igara iz game aplikacije
        from game.models import Game, Round, Move
        
        # Ukupna statistika
        context['total_games'] = user.games_played
        context['wins'] = user.games_won
        context['losses'] = user.games_lost
        context['win_rate'] = user.get_win_rate()
        
        # Detaljnija statistika iz Game modela
        games = Game.objects.filter(players=user)
        
        # Prosječni bodovi po igri
        game_stats = []
        for game in games:
            # Ovdje bi trebalo dohvatiti detaljnu statistiku za svaku igru
            # Ovo će ovisiti o implementaciji Game modela
            pass
        
        # Druge statistike koje bi mogle biti korisne
        # - Distribucija pobjeda po igračkom partneru
        # - Distribucija pobjeda po adutima
        # - Statistika zvanja
        # - Prosječan broj poena po igri
        # - Najbolje igre
        
        return context

# UserViewSet - dodajte na kraj datoteke
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet za korisnike.
    
    Omogućuje pregled i upravljanje korisničkim računima
    kroz standardno REST API sučelje.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrira queryset ovisno o parametrima upita."""
        queryset = User.objects.all()
        
        # Ako nije admin, vidi samo svoj profil
        if not self.request.user.is_staff:
            return queryset.filter(id=self.request.user.id)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Dohvaća profil trenutno ulogiranog korisnika."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class ProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet za korisničke profile.
    
    Omogućuje pregled i upravljanje korisničkim profilima
    kroz standardno REST API sučelje.
    """
    queryset = Profile.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Vraća odgovarajući serializer za profil."""
        # Ovdje bismo trebali definirati serializer, ali kako ga nema,
        # koristimo UserSerializer privremeno
        return UserSerializer
    
    def get_queryset(self):
        """Filtrira queryset ovisno o parametrima upita."""
        queryset = Profile.objects.select_related('user').all()
        
        # Ako nije admin, vidi samo svoj profil
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Dohvaća profil trenutno ulogiranog korisnika."""
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
class FriendshipViewSet(viewsets.ModelViewSet):
    """
    ViewSet za prijateljstva između korisnika.
    
    Omogućuje upravljanje prijateljstvima, uključujući slanje,
    prihvaćanje i odbijanje zahtjeva za prijateljstvo.
    """
    queryset = Friendship.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrira queryset prema ulogiranom korisniku."""
        user = self.request.user
        return Friendship.objects.filter(
            Q(sender=user) | Q(receiver=user)
        )
    
    @action(detail=False, methods=['get'])
    def requests(self, request):
        """Dohvaća zahtjeve za prijateljstvo koje je korisnik primio."""
        friendship_requests = Friendship.objects.filter(
            receiver=request.user,
            status='pending'
        )
        serializer = self.get_serializer(friendship_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def friends(self, request):
        """Dohvaća prijatelje korisnika."""
        friendships = Friendship.objects.filter(
            (Q(sender=request.user) | Q(receiver=request.user)),
            status='accepted'
        )
        serializer = self.get_serializer(friendships, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Prihvaća zahtjev za prijateljstvo."""
        friendship = self.get_object()
        if friendship.receiver != request.user or friendship.status != 'pending':
            return Response(
                {"error": "Nemate ovlasti za ovu akciju ili zahtjev nije u ispravnom statusu."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        friendship.status = 'accepted'
        friendship.save()
        return Response({"message": "Zahtjev za prijateljstvo prihvaćen."})
    
    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Odbija zahtjev za prijateljstvo."""
        friendship = self.get_object()
        if friendship.receiver != request.user or friendship.status != 'pending':
            return Response(
                {"error": "Nemate ovlasti za ovu akciju ili zahtjev nije u ispravnom statusu."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        friendship.status = 'declined'
        friendship.save()
        return Response({"message": "Zahtjev za prijateljstvo odbijen."})

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet za obavijesti korisnika.
    
    Omogućuje pregled i upravljanje obavijestima koje korisnik prima.
    """
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrira queryset prema ulogiranom korisniku."""
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Označava obavijest kao pročitanu."""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"message": "Obavijest označena kao pročitana."})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Označava sve obavijesti kao pročitane."""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"message": "Sve obavijesti označene kao pročitane."})

class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet za postignuća korisnika.
    
    Omogućuje pregled postignuća koja je korisnik ostvario.
    """
    queryset = Achievement.objects.all()
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def user(self, request):
        """Dohvaća postignuća koja je korisnik ostvario."""
        user_achievements = request.user.profile.achievements.all()
        serializer = self.get_serializer(user_achievements, many=True)
        return Response(serializer.data)

class AuthAPIView(APIView):
    """
    API pogled za autentikaciju korisnika.
    
    Omogućuje prijavu korisnika i dohvaćanje token-a za autentikaciju.
    """
    permission_classes = []
    
    def post(self, request):
        """Autentificira korisnika i vraća token."""
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {"error": "Potrebno je navesti korisničko ime i lozinku."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Pokušaj autentikaciju s korisničkim imenom
        user = authenticate(username=username, password=password)
        
        # Ako nije uspjelo, pokušaj s emailom
        if not user and '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        
        if user:
            # Dohvati ili stvori token
            from rest_framework.authtoken.models import Token
            token, _ = Token.objects.get_or_create(user=user)
            
            # Ažuriraj online status
            user.update_online_status(True)
            
            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username
            })
        else:
            return Response(
                {"error": "Nevažeće korisničko ime ili lozinka."},
                status=status.HTTP_401_UNAUTHORIZED
            )

class RegistrationAPIView(APIView):
    """
    API pogled za registraciju korisnika.
    
    Omogućuje registraciju novih korisnika.
    """
    permission_classes = []
    
    def post(self, request):
        """Registrira novog korisnika."""
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not all([username, email, password]):
            return Response(
                {"error": "Potrebno je navesti korisničko ime, email i lozinku."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Provjera postojećeg korisnika
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Korisničko ime već postoji."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "Email adresa već postoji."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Stvori korisnika
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Generiraj token za verifikaciju
            import uuid
            import hashlib
            token = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
            user.verification_token = token
            user.save()
            
            # Vrati podatke o korisniku
            return Response({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'message': 'Registracija uspješna! Provjerite email za verifikaciju računa.'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"error": f"Greška prilikom registracije: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailVerificationAPIView(APIView):
    """
    API pogled za verifikaciju email adrese.
    
    Omogućuje verifikaciju email adrese putem tokena.
    """
    permission_classes = []
    
    def post(self, request):
        """Verificira email adresu putem tokena."""
        token = request.data.get('token')
        
        if not token:
            return Response(
                {"error": "Token je obavezan."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(verification_token=token)
            user.is_email_verified = True
            user.verification_token = ''
            user.save()
            
            return Response({
                'message': 'Email adresa je uspješno verificirana!'
            })
        except User.DoesNotExist:
            return Response(
                {"error": "Nevažeći token za verifikaciju."},
                status=status.HTTP_400_BAD_REQUEST
            )

class PasswordResetRequestAPIView(APIView):
    """
    API pogled za zahtjev za resetiranje lozinke.
    
    Omogućuje slanje zahtjeva za resetiranje lozinke na email adresu.
    """
    permission_classes = []
    
    def post(self, request):
        """Šalje zahtjev za resetiranje lozinke."""
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error": "Email adresa je obavezna."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            # Generiraj token
            import uuid
            reset_token = str(uuid.uuid4())
            user.reset_password_token = reset_token
            user.save()
            
            # Ovdje bi se u stvarnoj implementaciji poslao email
            
            return Response({
                'message': 'Zahtjev za resetiranje lozinke je poslan na vašu email adresu.'
            })
        except User.DoesNotExist:
            # Iz sigurnosnih razloga, ne otkrivamo da korisnik ne postoji
            return Response({
                'message': 'Zahtjev za resetiranje lozinke je poslan na vašu email adresu (ako postoji).'
            })

class PasswordResetConfirmAPIView(APIView):
    """
    API pogled za potvrdu resetiranja lozinke.
    
    Omogućuje resetiranje lozinke putem tokena.
    """
    permission_classes = []
    
    def post(self, request):
        """Resetira lozinku putem tokena."""
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not token or not new_password:
            return Response(
                {"error": "Token i nova lozinka su obavezni."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(reset_password_token=token)
            user.set_password(new_password)
            user.reset_password_token = ''
            user.save()
            
            return Response({
                'message': 'Lozinka je uspješno promijenjena. Možete se prijaviti s novom lozinkom.'
            })
        except User.DoesNotExist:
            return Response(
                {"error": "Nevažeći token za resetiranje lozinke."},
                status=status.HTTP_400_BAD_REQUEST
            )

@login_required
def update_last_activity(request):
    """
    Pogled za ažuriranje zadnje aktivnosti korisnika.
    
    Koristi se za AJAX zahtjeve za praćenje online statusa.
    """
    # Ažuriraj zadnju aktivnost
    request.user.last_activity = timezone.now()
    request.user.is_online = True
    request.user.save(update_fields=['last_activity', 'is_online'])
    
    return JsonResponse({'status': 'success'})