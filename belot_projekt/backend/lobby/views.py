"""
Pogledi (views) za Django aplikaciju "lobby".

Ovaj modul implementira različite poglede za rad s predvorjem Belot igre,
uključujući prikaz dostupnih soba, stvaranje novih soba, pridruživanje
sobama, upravljanje pozivnicama i chat funkcionalnost.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.views import View
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, Http404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, F, Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from utils.decorators import login_required_ajax, admin_required, throttle_request
from django.core.paginator import Paginator

from .models import LobbyRoom, LobbyMembership, LobbyInvitation, LobbyMessage, LobbyEvent
from .forms import LobbyRoomForm, LobbyInvitationForm, LobbyMessageForm
from game.models import Game

logger = logging.getLogger('lobby.views')


class LobbyHomeView(LoginRequiredMixin, ListView):
    """
    Početna stranica predvorja s prikazom dostupnih soba.
    
    Prikazuje popis javnih soba koje čekaju igrače, kao i
    sobe koje je stvorio prijavljeni korisnik ili kojima se pridružio.
    """
    model = LobbyRoom
    template_name = 'lobby/home.html'
    context_object_name = 'rooms'
    paginate_by = 10
    
    def get_queryset(self):
        """Dohvaća sobe za prikaz u predvorju."""
        # Dohvati javne sobe koje nisu pune
        public_rooms = LobbyRoom.objects.filter(
            is_private=False,
            status='open'
        ).annotate(
            player_count=Count('players')
        ).order_by('-created_at')
        
        # Uključi privatne sobe kojima je korisnik vlasnik ili član
        user_rooms = LobbyRoom.objects.filter(
            Q(creator=self.request.user) | Q(players=self.request.user)
        ).exclude(
            status='closed'
        ).annotate(
            player_count=Count('players')
        ).order_by('-created_at')
        
        # Kombiniraj upite i ukloni duplikate
        combined = public_rooms | user_rooms
        return combined.distinct()
    
    def get_context_data(self, **kwargs):
        """Dodaje dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        
        # Dodaj formular za stvaranje nove sobe
        context['room_form'] = LobbyRoomForm()
        
        # Pozivnice za korisnika
        context['invitations'] = LobbyInvitation.objects.filter(
            recipient=self.request.user,
            status='pending'
        ).select_related('room', 'sender').order_by('-created_at')
        
        # Aktivne igre korisnika
        context['active_games'] = Game.objects.filter(
            players=self.request.user,
            status__in=['waiting', 'in_progress', 'ready']
        ).order_by('-created_at')
        
        return context


class LobbyRoomCreateView(LoginRequiredMixin, CreateView):
    """
    Pogled za stvaranje nove sobe u predvorju.
    """
    model = LobbyRoom
    form_class = LobbyRoomForm
    template_name = 'lobby/room_create.html'
    
    def form_valid(self, form):
        """Dodaje trenutnog korisnika kao kreatora sobe."""
        form.instance.creator = self.request.user
        
        # Postavi bodove za pobjedu na temelju brzog formata
        if form.cleaned_data.get('use_quick_format'):
            form.instance.points_to_win = 701
        else:
            form.instance.points_to_win = 1001
        
        room = form.save()
        
        # Dodaj kreatora kao prvog igrača
        room.add_player(self.request.user)
        
        # Dodaj sistemsku poruku o stvaranju sobe
        LobbyMessage.add_system_message(
            room=room,
            content=f"Soba '{room.name}' je stvorena. Čekam igrače za početak igre..."
        )
        
        messages.success(self.request, f"Soba '{room.name}' je uspješno stvorena!")
        return HttpResponseRedirect(reverse('lobby:room_detail', kwargs={'pk': room.pk}))
    
    def form_invalid(self, form):
        """Prikazuje poruku o greškama u formularu."""
        messages.error(self.request, "Molimo ispravite greške u formularu.")
        return super().form_invalid(form)


class LobbyRoomDetailView(LoginRequiredMixin, DetailView):
    """
    Pogled za prikaz detalja sobe i interakciju s njom.
    """
    model = LobbyRoom
    template_name = 'lobby/room_detail.html'
    context_object_name = 'room'
    
    def get_object(self, queryset=None):
        """Dohvaća sobu s predučitanim vezama za bolju performansu."""
        if queryset is None:
            queryset = self.get_queryset()
        
        pk = self.kwargs.get('pk')
        room_code = self.kwargs.get('room_code')
        
        if pk:
            room = get_object_or_404(
                queryset.prefetch_related(
                    'players', 
                    Prefetch('lobbymembership_set', queryset=LobbyMembership.objects.select_related('user')),
                    Prefetch('messages', queryset=LobbyMessage.objects.select_related('sender').order_by('created_at')[:50])
                ),
                pk=pk
            )
        elif room_code:
            room = get_object_or_404(
                queryset.prefetch_related(
                    'players', 
                    Prefetch('lobbymembership_set', queryset=LobbyMembership.objects.select_related('user')),
                    Prefetch('messages', queryset=LobbyMessage.objects.select_related('sender').order_by('created_at')[:50])
                ),
                room_code=room_code
            )
        else:
            raise Http404("Nedostaje identifikator sobe.")
        
        return room
    
    def get_context_data(self, **kwargs):
        """Dodaje dodatne podatke u kontekst."""
        context = super().get_context_data(**kwargs)
        room = self.object
        
        # Dohvati članstvo korisnika u sobi
        user_membership = LobbyMembership.objects.filter(
            room=room,
            user=self.request.user
        ).first()
        
        context['is_member'] = user_membership is not None
        context['is_ready'] = user_membership.is_ready if user_membership else False
        context['is_creator'] = (room.creator == self.request.user)
        context['can_join'] = (not context['is_member'] and room.status == 'open')
        context['can_start'] = (context['is_creator'] and 
                               room.lobbymembership_set.count() >= 4 and 
                               room.are_all_players_ready())
        
        # Formular za slanje poruka
        context['message_form'] = LobbyMessageForm()
        
        # Formular za slanje pozivnica
        context['invitation_form'] = LobbyInvitationForm()
        
        # Chat poruke
        context['messages'] = room.messages.select_related('sender').order_by('created_at')
        
        # Članstva
        context['memberships'] = room.lobbymembership_set.select_related('user').order_by('joined_at')
        
        # Povezana igra ako postoji
        if room.game:
            context['game'] = room.game
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Obrađuje POST zahtjeve za sobu (chat poruke)."""
        self.object = self.get_object()
        room = self.object
        
        # Provjeri je li korisnik član sobe
        if not room.lobbymembership_set.filter(user=request.user).exists():
            messages.error(request, "Morate biti član sobe za slanje poruka.")
            return self.get(request, *args, **kwargs)
        
        # Obradi formular za poruke
        message_form = LobbyMessageForm(request.POST)
        if message_form.is_valid():
            message = message_form.save(commit=False)
            message.room = room
            message.sender = request.user
            message.save()
            
            # Preusmjeri natrag na detalje sobe
            return HttpResponseRedirect(request.path)
        
        # Ako formular nije valjan, vrati se na stranicu s greškama
        context = self.get_context_data()
        context['message_form'] = message_form
        return self.render_to_response(context)


@method_decorator(login_required, name='dispatch')
class JoinLobbyRoomView(View):
    """
    Pogled za pridruživanje sobi u predvorju.
    """
    def post(self, request, pk=None, room_code=None):
        """Obrađuje zahtjev za pridruživanje sobi."""
        # Dohvati sobu prema ID-u ili kodu
        if pk:
            room = get_object_or_404(LobbyRoom, pk=pk)
        elif room_code:
            room = get_object_or_404(LobbyRoom, room_code=room_code)
        else:
            messages.error(request, "Nedostaje identifikator sobe.")
            return redirect('lobby:home')
        
        # Pokušaj pridruživanje
        try:
            success = room.add_player(request.user)
            if success:
                messages.success(request, f"Uspješno ste se pridružili sobi '{room.name}'.")
                
                # Dodaj sistemsku poruku u chat
                LobbyMessage.add_system_message(
                    room=room,
                    content=f"{request.user.username} se pridružio/la sobi."
                )
            else:
                messages.info(request, "Već ste član ove sobe.")
        except ValueError as e:
            messages.error(request, str(e))
        
        # Preusmjeri na detalje sobe
        return redirect('lobby:room_detail', pk=room.pk)


@method_decorator(login_required, name='dispatch')
class LeaveLobbyRoomView(View):
    """
    Pogled za napuštanje sobe u predvorju.
    """
    def post(self, request, pk):
        """Obrađuje zahtjev za napuštanje sobe."""
        room = get_object_or_404(LobbyRoom, pk=pk)
        
        # Pokušaj napuštanje
        try:
            success = room.remove_player(request.user)
            if success:
                messages.success(request, f"Uspješno ste napustili sobu '{room.name}'.")
                
                # Ako je soba zatvorena nakon napuštanja, preusmjeri na početnu
                if room.status == 'closed':
                    return redirect('lobby:home')
                
                # Dodaj sistemsku poruku u chat
                LobbyMessage.add_system_message(
                    room=room,
                    content=f"{request.user.username} je napustio/la sobu."
                )
            else:
                messages.info(request, "Niste član ove sobe.")
        except ValueError as e:
            messages.error(request, str(e))
        
        # Preusmjeri na detalje sobe ili početnu stranicu
        if room.status != 'closed':
            return redirect('lobby:room_detail', pk=room.pk)
        else:
            return redirect('lobby:home')


@method_decorator(login_required, name='dispatch')
class ToggleReadyStatusView(View):
    """
    Pogled za promjenu statusa spremnosti igrača.
    """
    def post(self, request, pk):
        """Obrađuje zahtjev za promjenu statusa spremnosti."""
        room = get_object_or_404(LobbyRoom, pk=pk)
        
        # Dohvati trenutni status spremnosti
        membership = get_object_or_404(LobbyMembership, room=room, user=request.user)
        is_ready = not membership.is_ready  # Prebaci status
        
        # Ažuriraj status
        success = room.mark_player_ready(request.user, is_ready)
        if success:
            if is_ready:
                messages.success(request, "Označeni ste kao spremni za igru.")
            else:
                messages.info(request, "Više niste označeni kao spremni za igru.")
        
        # Preusmjeri natrag na detalje sobe
        return redirect('lobby:room_detail', pk=room.pk)


@method_decorator(login_required, name='dispatch')
class StartGameFromLobbyView(View):
    """
    Pogled za pokretanje igre iz sobe u predvorju.
    """
    def post(self, request, pk):
        """Obrađuje zahtjev za pokretanje igre."""
        room = get_object_or_404(LobbyRoom, pk=pk)
        
        # Provjeri je li korisnik kreator sobe
        if room.creator != request.user:
            messages.error(request, "Samo kreator sobe može pokrenuti igru.")
            return redirect('lobby:room_detail', pk=room.pk)
        
        # Pokušaj pokrenuti igru
        try:
            game = room.start_game()
            messages.success(request, "Igra je uspješno pokrenuta!")
            
            # Preusmjeri na igru
            return redirect('game:detail', pk=game.id)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('lobby:room_detail', pk=room.pk)


@method_decorator(login_required, name='dispatch')
class SendInvitationView(View):
    """
    Pogled za slanje pozivnica u sobu.
    """
    def post(self, request, pk):
        """Obrađuje zahtjev za slanje pozivnice."""
        room = get_object_or_404(LobbyRoom, pk=pk)
        
        # Provjeri je li korisnik član sobe
        if not room.lobbymembership_set.filter(user=request.user).exists():
            messages.error(request, "Morate biti član sobe da biste mogli poslati pozivnicu.")
            return redirect('lobby:room_detail', pk=room.pk)
        
        # Obradi formular
        form = LobbyInvitationForm(request.POST)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.room = room
            invitation.sender = request.user
            
            # Provjeri je li primatelj već član sobe
            if room.lobbymembership_set.filter(user=invitation.recipient).exists():
                messages.error(request, f"{invitation.recipient.username} je već član ove sobe.")
                return redirect('lobby:room_detail', pk=room.pk)
            
            # Provjeri postoji li već pozivnica za tog korisnika
            if LobbyInvitation.objects.filter(
                room=room,
                recipient=invitation.recipient,
                status='pending'
            ).exists():
                messages.info(request, f"Pozivnica za {invitation.recipient.username} je već poslana i čeka odgovor.")
                return redirect('lobby:room_detail', pk=room.pk)
            
            # Spremi pozivnicu
            invitation.save()
            
            # Stvori događaj
            LobbyEvent.objects.create(
                room=room,
                user=request.user,
                event_type='invitation_sent',
                message=f"{request.user.username} je poslao/la pozivnicu za {invitation.recipient.username}."
            )
            
            messages.success(request, f"Pozivnica za {invitation.recipient.username} je uspješno poslana.")
        else:
            messages.error(request, "Molimo ispravite greške u formularu za pozivnicu.")
        
        return redirect('lobby:room_detail', pk=room.pk)


@method_decorator(login_required, name='dispatch')
class RespondToInvitationView(View):
    """
    Pogled za odgovaranje na pozivnice (prihvaćanje/odbijanje).
    """
    def post(self, request, pk, action):
        """Obrađuje odgovor na pozivnicu."""
        invitation = get_object_or_404(
            LobbyInvitation, 
            pk=pk, 
            recipient=request.user,
            status='pending'
        )
        
        # Obradi akciju
        if action == 'accept':
            success = invitation.accept()
            if success:
                messages.success(request, f"Pridružili ste se sobi '{invitation.room.name}'.")
                return redirect('lobby:room_detail', pk=invitation.room.pk)
            else:
                messages.error(request, "Nije moguće prihvatiti pozivnicu. Možda je soba puna ili zatvorena.")
        elif action == 'decline':
            invitation.decline()
            messages.info(request, "Pozivnica je odbijena.")
        else:
            messages.error(request, "Nevažeća akcija.")
        
        return redirect('lobby:home')


class LobbyRoomListView(LoginRequiredMixin, ListView):
    """
    Pogled za prikaz popisa svih dostupnih soba.
    """
    model = LobbyRoom
    template_name = 'lobby/room_list.html'
    context_object_name = 'rooms'
    paginate_by = 20
    
    def get_queryset(self):
        """Dohvaća filtrirani popis soba."""
        queryset = LobbyRoom.objects.exclude(status='closed')
        
        # Filtriranje po statusu
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtriranje po privatnosti
        privacy = self.request.GET.get('privacy')
        if privacy == 'public':
            queryset = queryset.filter(is_private=False)
        elif privacy == 'private':
            queryset = queryset.filter(is_private=True)
        
        # Filtriranje po članstvu
        membership = self.request.GET.get('membership')
        if membership == 'my':
            queryset = queryset.filter(
                Q(creator=self.request.user) | Q(players=self.request.user)
            )
        
        # Filtriranje po dostupnosti
        availability = self.request.GET.get('availability')
        if availability == 'joinable':
            queryset = queryset.filter(status='open')
        
        # Sortiranje
        sort = self.request.GET.get('sort', '-created_at')
        if sort in ['name', '-name', 'created_at', '-created_at']:
            queryset = queryset.order_by(sort)
        else:
            queryset = queryset.order_by('-created_at')
        
        # Dodaj broj igrača kao anotaciju
        return queryset.annotate(player_count=Count('players')).distinct()
    
    def get_context_data(self, **kwargs):
        """Dodaje filtere u kontekst."""
        context = super().get_context_data(**kwargs)
        
        # Dodaj aktivne filtere
        context['filters'] = {
            'status': self.request.GET.get('status', ''),
            'privacy': self.request.GET.get('privacy', ''),
            'membership': self.request.GET.get('membership', ''),
            'availability': self.request.GET.get('availability', ''),
            'sort': self.request.GET.get('sort', '-created_at')
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class LobbyRoomByCodeView(View):
    """
    Pogled za pridruživanje sobi putem koda.
    """
    def get(self, request):
        """Prikazuje formular za unos koda sobe."""
        return render(request, 'lobby/join_by_code.html')
    
    def post(self, request):
        """Obrađuje zahtjev za pridruživanje sobi putem koda."""
        room_code = request.POST.get('room_code', '').strip().upper()
        
        if not room_code:
            messages.error(request, "Molimo unesite kod sobe.")
            return render(request, 'lobby/join_by_code.html')
        
        # Pokušaj pronaći sobu s tim kodom
        try:
            room = LobbyRoom.objects.get(room_code=room_code)
            
            # Ako je soba zatvorena, prikaži poruku
            if room.status == 'closed':
                messages.error(request, "Ova soba je zatvorena i ne prima nove igrače.")
                return render(request, 'lobby/join_by_code.html')
            
            # Ako je soba puna, prikaži poruku
            if room.status == 'full':
                messages.error(request, "Ova soba je puna i ne prima nove igrače.")
                return render(request, 'lobby/join_by_code.html')
            
            # Preusmjeri na detalje sobe
            return redirect('lobby:room_detail', pk=room.pk)
            
        except LobbyRoom.DoesNotExist:
            messages.error(request, f"Soba s kodom '{room_code}' nije pronađena.")
            return render(request, 'lobby/join_by_code.html')


@method_decorator(login_required, name='dispatch')
class LobbyMessageListView(ListView):
    """
    Pogled za prikaz chat poruka u sobi.
    
    Koristi se za AJAX dohvat novih poruka bez osvježavanja cijele stranice.
    """
    model = LobbyMessage
    template_name = 'lobby/partials/messages.html'
    context_object_name = 'messages'
    
    def get_queryset(self):
        """Dohvaća poruke za određenu sobu."""
        room_id = self.kwargs.get('pk')
        room = get_object_or_404(LobbyRoom, pk=room_id)
        
        # Provjeri je li korisnik član sobe
        if not room.lobbymembership_set.filter(user=self.request.user).exists():
            return LobbyMessage.objects.none()
        
        # Dohvati poruke nakon određenog vremena ako je navedeno
        since = self.request.GET.get('since')
        if since:
            try:
                since_time = timezone.datetime.fromtimestamp(float(since), tz=timezone.utc)
                return room.messages.filter(created_at__gt=since_time).order_by('created_at')
            except (ValueError, TypeError):
                pass
        
        # Inače vrati zadnjih 50 poruka
        return room.messages.order_by('-created_at')[:50].order_by('created_at')
    
    def render_to_response(self, context, **response_kwargs):
        """Vraća samo HTML za poruke ako je zahtjev AJAX."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render(self.request, self.template_name, context).content.decode('utf-8')
            
            # Zadnja poruka za polling
            last_message = context['messages'].last()
            last_timestamp = last_message.created_at.timestamp() if last_message else None
            
            return JsonResponse({
                'html': html,
                'last_timestamp': last_timestamp
            })
        
        # Inače, vrati normalan odgovor
        return super().render_to_response(context, **response_kwargs)


@method_decorator(login_required, name='dispatch')
@method_decorator(require_POST, name='dispatch')
class SendMessageView(View):
    """
    Pogled za slanje chat poruka u sobi (AJAX).
    """
    def post(self, request, pk):
        """Obrađuje zahtjev za slanje poruke."""
        room = get_object_or_404(LobbyRoom, pk=pk)
        
        # Provjeri je li korisnik član sobe
        if not room.lobbymembership_set.filter(user=request.user).exists():
            return JsonResponse({'status': 'error', 'message': 'Niste član ove sobe.'}, status=403)
        
        # Obradi formular
        form = LobbyMessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.room = room
            message.sender = request.user
            message.save()
            
            # Ako je AJAX zahtjev, vrati JSON odgovor
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'sender': message.sender.username,
                        'created_at': message.created_at.isoformat(),
                        'is_system_message': message.is_system_message
                    }
                })
            
            # Inače, preusmjeri natrag na sobu
            return redirect('lobby:room_detail', pk=room.pk)
        
        # Ako formular nije valjan, vrati grešku
        errors = form.errors.as_json()
        return JsonResponse({'status': 'error', 'errors': errors}, status=400)


@login_required
def update_lobby_status(request, pk):
    """
    View za ažuriranje statusa sobe putem AJAX zahtjeva.
    
    Ovo omogućuje realtime ažuriranje stanja sobe bez osvježavanja stranice.
    """
    room = get_object_or_404(LobbyRoom, pk=pk)
    
    # Provjeri je li korisnik član sobe
    if not room.lobbymembership_set.filter(user=request.user).exists():
        return JsonResponse({'status': 'error', 'message': 'Niste član ove sobe.'}, status=403)
    
    # Dohvati članstva s korisnicima
    memberships = list(room.lobbymembership_set.select_related('user'))
    
    # Provjeri je li igra započeta
    if room.game:
        return JsonResponse({
            'status': 'game_started',
            'game_id': str(room.game.id)
        })
    
    # Pripremi podatke o članovima
    members = []
    for m in memberships:
        members.append({
            'id': m.user.id,
            'username': m.user.username,
            'is_ready': m.is_ready,
            'is_creator': (m.user == room.creator)
        })
    
    # Podaci o sobi
    data = {
        'status': 'success',
        'room': {
            'id': str(room.id),
            'name': room.name,
            'status': room.status,
            'creator': room.creator.username,
            'all_ready': room.are_all_players_ready(),
            'can_start': (room.are_all_players_ready() and len(memberships) >= 4),
            'is_creator': (request.user == room.creator),
            'members': members,
            'member_count': len(members)
        }
    }
    
    return JsonResponse(data)