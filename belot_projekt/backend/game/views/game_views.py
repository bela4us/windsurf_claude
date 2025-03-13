"""
Web pogledi za Belot igru.

Ovaj modul implementira klasične Django poglede koji vraćaju HTML stranice
za web sučelje Belot aplikacije. Ovi pogledi omogućuju korisnicima pregled
dostupnih igara, stvaranje novih igara, pridruživanje igrama i samo igranje.

Pogledi koriste Django predloške za generiranje HTML-a i oslanjaju se na
servisni sloj za implementaciju poslovne logike.
"""

import logging
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.contrib import messages
from django.db.models import Count, Q, F, Max

from game.models import Game, Round, Move, Declaration
from game.services.game_service import GameService
from game.forms.web_forms import GameCreateForm, GameJoinForm

logger = logging.getLogger('game.views')


class LobbyView(LoginRequiredMixin, TemplateView):
    """
    Pogled za predvorje (lobby) igre.
    
    Prikazuje listu dostupnih igara i omogućuje stvaranje nove igre
    ili pridruživanje postojećoj.
    """
    template_name = 'game/lobby.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Dohvat javnih igara koje čekaju igrače
        public_games = Game.objects.filter(
            status__in=['waiting', 'ready'],
            is_private=False
        ).annotate(
            player_count=Count('players')
        ).filter(
            player_count__lt=4
        ).order_by('-created_at')[:10]
        
        # Dohvat igara u kojima korisnik već sudjeluje
        my_games = Game.objects.filter(
            players=self.request.user
        ).exclude(
            status__in=['finished', 'abandoned']
        ).order_by('-created_at')
        
        # Statistika
        games_played = Game.objects.filter(
            players=self.request.user,
            status='finished'
        ).count()
        
        wins = Game.objects.filter(
            Q(team1_players=self.request.user, winner_team=1) | 
            Q(team2_players=self.request.user, winner_team=2),
            status='finished'
        ).count()
        
        context.update({
            'public_games': public_games,
            'my_games': my_games,
            'create_form': GameCreateForm(),
            'join_form': GameJoinForm(),
            'games_played': games_played,
            'wins': wins,
            'win_rate': round(wins / games_played * 100 if games_played > 0 else 0, 1)
        })
        
        return context


class GameCreateView(LoginRequiredMixin, FormView):
    """
    Pogled za stvaranje nove igre.
    
    Obrađuje formu za stvaranje nove igre i preusmjerava korisnika
    na stranicu igre nakon uspješnog stvaranja.
    """
    form_class = GameCreateForm
    template_name = 'game/create_game.html'
    success_url = reverse_lazy('game:game_lobby')
    
    def form_valid(self, form):
        # Koristi GameService za stvaranje igre
        service = GameService()
        result = service.create_game(
            creator_id=self.request.user.id,
            private=form.cleaned_data.get('is_private', False),
            points_to_win=form.cleaned_data.get('points_to_win', 1001)
        )
        
        if result.get('valid', False):
            messages.success(self.request, 'Igra je uspješno stvorena!')
            return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': result['game_id']}))
        else:
            messages.error(self.request, f"Greška pri stvaranju igre: {result.get('message', 'Nepoznata greška')}")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Greška u podacima forme. Molimo provjerite unos.')
        return HttpResponseRedirect(reverse('game:game_lobby'))


class GameJoinView(LoginRequiredMixin, FormView):
    """
    Pogled za pridruživanje postojećoj igri.
    
    Omogućuje pridruživanje putem ID-a igre ili koda sobe.
    """
    form_class = GameJoinForm
    template_name = 'game/join_game.html'
    success_url = reverse_lazy('game:game_lobby')
    
    def get(self, request, *args, **kwargs):
        # Ako je room_code proslijeđen u URL-u, automatski popuni formu
        room_code = kwargs.get('room_code')
        if room_code:
            form = self.form_class(initial={'room_code': room_code})
            return render(request, self.template_name, {'form': form})
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        service = GameService()
        
        # Pridruživanje putem room_code ili game_id
        room_code = form.cleaned_data.get('room_code') or self.kwargs.get('room_code')
        game_id = form.cleaned_data.get('game_id')
        
        result = service.join_game(
            user_id=self.request.user.id, 
            room_code=room_code,
            game_id=game_id
        )
        
        if result.get('valid', False):
            messages.success(self.request, 'Uspješno ste se pridružili igri!')
            return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': result['game_id']}))
        else:
            messages.error(self.request, f"Greška pri pridruživanju igri: {result.get('message', 'Nepoznata greška')}")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Greška u podacima forme. Molimo provjerite unos.')
        return HttpResponseRedirect(reverse('game:game_lobby'))


class GameListView(LoginRequiredMixin, ListView):
    """
    Pogled za prikaz liste igara.
    
    Omogućuje pregled i filtriranje dostupnih igara.
    """
    model = Game
    template_name = 'game/game_list.html'
    context_object_name = 'games'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Game.objects.all()
        
        # Filtriranje po statusu
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtriranje po privatnosti
        is_private = self.request.GET.get('is_private')
        if is_private is not None:
            queryset = queryset.filter(is_private=(is_private.lower() == 'true'))
        
        # Filtriranje igara gdje korisnik sudjeluje
        my_games = self.request.GET.get('my_games')
        if my_games:
            queryset = queryset.filter(players=self.request.user)
        
        # Filtriranje po broju igrača
        queryset = queryset.annotate(player_count=Count('players'))
        player_count = self.request.GET.get('player_count')
        if player_count:
            queryset = queryset.filter(player_count=int(player_count))
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Dodavanje formulara za brzo stvaranje/pridruživanje
        context['create_form'] = GameCreateForm()
        context['join_form'] = GameJoinForm()
        
        # Dodavanje parametara filtriranja za održavanje stanja filtera
        context['filters'] = {
            'status': self.request.GET.get('status', ''),
            'is_private': self.request.GET.get('is_private', ''),
            'my_games': self.request.GET.get('my_games', ''),
            'player_count': self.request.GET.get('player_count', '')
        }
        
        return context


class GameDetailView(LoginRequiredMixin, DetailView):
    """
    Pogled za detalje igre.
    
    Prikazuje informacije o specifičnoj igri, uključujući status, igrače i rezultate.
    Ako je igra u statusu čekanja, prikazuje sučelje za čekanje.
    Ako je igra u tijeku, preusmjerava na sučelje za igranje.
    """
    model = Game
    template_name = 'game/game_detail.html'
    context_object_name = 'game'
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Ako korisnik nije član igre, provjeri može li se pridružiti
        if not self.object.players.filter(id=request.user.id).exists():
            if self.object.can_join(request.user):
                context = self.get_context_data(object=self.object)
                context['can_join'] = True
                return self.render_to_response(context)
            else:
                messages.error(request, 'Ne možete pristupiti ovoj igri.')
                return HttpResponseRedirect(reverse('game:game_lobby'))
        
        # Ako je igra u tijeku, preusmjeri na sučelje za igranje
        if self.object.status == 'in_progress':
            return HttpResponseRedirect(reverse('game:play', kwargs={'pk': self.object.id}))
        
        context = self.get_context_data(object=self.object)
        
        # Provjeri je li korisnik kreator igre (posebne mogućnosti)
        context['is_creator'] = (request.user == self.object.creator)
        
        # Dodaj dodatne informacije za čekaonicu
        if self.object.status in ['waiting', 'ready']:
            context['waiting_for_players'] = self.object.players.count() < 4
            context['room_code_for_sharing'] = self.object.room_code
            context['can_start'] = (self.object.players.count() == 4 and 
                                    request.user == self.object.creator)
        
        return self.render_to_response(context)
    
    def post(self, request, *args, **kwargs):
        """Obrada POST zahtjeva za akcije na igri (start, leave)."""
        self.object = self.get_object()
        action = request.POST.get('action')
        
        service = GameService(game_id=str(self.object.id))
        
        if action == 'start_game':
            # Pokretanje igre
            return self._handle_start_game(request, service)
        elif action == 'join_game':
            # Pridruživanje igri
            return self._handle_join_game(request, service)
        elif action == 'leave_game':
            # Napuštanje igre
            return self._handle_leave_game(request, service)
        
        return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
    
    def _handle_start_game(self, request, service):
        """Obrada akcije pokretanja igre."""
        if not self.object.can_player_start_game(request.user):
            messages.error(request, 'Nemate prava za pokretanje ove igre.')
            return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
        
        result = service.start_game(user_id=request.user.id)
        
        if result.get('valid', False):
            messages.success(request, 'Igra je započeta!')
            return HttpResponseRedirect(reverse('game:play', kwargs={'pk': self.object.id}))
        else:
            messages.error(request, f"Greška pri pokretanju igre: {result.get('message', 'Nepoznata greška')}")
            return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
    
    def _handle_join_game(self, request, service):
        """Obrada akcije pridruživanja igri."""
        result = service.join_game(user_id=request.user.id)
        
        if result.get('valid', False):
            messages.success(request, 'Uspješno ste se pridružili igri!')
        else:
            messages.error(request, f"Greška pri pridruživanju igri: {result.get('message', 'Nepoznata greška')}")
        
        return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
    
    def _handle_leave_game(self, request, service):
        """Obrada akcije napuštanja igre."""
        result = service.leave_game(user_id=request.user.id)
        
        if result.get('valid', False):
            messages.success(request, 'Uspješno ste napustili igru.')
            return HttpResponseRedirect(reverse('game:game_lobby'))
        else:
            messages.error(request, f"Greška pri napuštanju igre: {result.get('message', 'Nepoznata greška')}")
            return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))


class GamePlayView(LoginRequiredMixin, DetailView):
    """
    Pogled za igranje Belot igre.
    
    Ovo je glavni pogled za korisničko sučelje igre koji prikazuje
    karte, štihove, zvanja i omogućuje interakciju s igrom.
    """
    model = Game
    template_name = 'game/game_play.html'
    context_object_name = 'game'
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Provjera je li korisnik član igre
        if not self.object.players.filter(id=request.user.id).exists():
            messages.error(request, 'Niste član ove igre.')
            return HttpResponseRedirect(reverse('game:game_lobby'))
        
        # Provjera je li igra u tijeku
        if self.object.status != 'in_progress':
            if self.object.status in ['waiting', 'ready']:
                return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
            elif self.object.status in ['finished', 'abandoned']:
                # Ako je igra završena, prikaži rezultate
                return HttpResponseRedirect(reverse('game:game_detail', kwargs={'pk': self.object.id}))
        
        # Dohvati trenutno stanje igre za igrača
        service = GameService(game_id=str(self.object.id))
        game_state = service.get_game_state(user_id=request.user.id)
        
        if 'error' in game_state:
            messages.error(request, f"Greška pri dohvaćanju stanja igre: {game_state['error']}")
            return HttpResponseRedirect(reverse('game:game_lobby'))
        
        context = self.get_context_data(object=self.object)
        context['game_state'] = game_state
        
        # Informacije o igraču
        context['player_id'] = request.user.id
        context['is_your_turn'] = game_state.get('is_your_turn', False)
        
        # Informacije potrebne za frontend - koristimo wss:// za sigurnu komunikaciju
        protocol = 'wss' if self.request.is_secure() else 'ws'
        context['websocket_url'] = f"{protocol}://{request.get_host()}/ws/game/{self.object.room_code}/"
        
        return self.render_to_response(context)