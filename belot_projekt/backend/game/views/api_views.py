"""
API pogledi za Belot igru.

Ovaj modul implementira REST API poglede koji omogućuju pristup funkcionalnostima
Belot igre kroz standardiziran JSON API. Ovi pogledi koriste Django REST Framework
i pružaju endpointe za frontend aplikaciju, mobilne klijente i druge servise.

API pogledi koriste servisni sloj za poslovnu logiku i serializatore za
transformaciju između JSON reprezentacije i Python objekata.
"""

import logging
from django.db.models import Count, F, Q, Sum, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import Http404

from rest_framework import viewsets, status, mixins, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from game.models import Game, Round, Move, Declaration
from game.serializers.game_serializers import (
    GameSerializer, GameCreateSerializer, GameDetailSerializer,
    GameListSerializer, GameStateSerializer, GameActionSerializer,
    GameJoinSerializer, GameStatisticsSerializer
)
from game.serializers.move_serializers import (
    MoveSerializer, MoveCreateSerializer, MoveListSerializer,
    RoundSerializer, RoundDetailSerializer,
    DeclarationSerializer, DeclarationCreateSerializer
)
from game.services.game_service import GameService
from game.services.scoring_service import ScoringService
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger('game.api_views')


class GameViewSet(viewsets.ModelViewSet):
    """
    ViewSet za igre Belota.
    
    Omogućuje CRUD operacije nad igrama i dodatne akcije
    poput pridruživanja igri, napuštanja igre i pokretanja igre.
    """
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Odabire odgovarajući serializator ovisno o akciji."""
        if self.action == 'create':
            return GameCreateSerializer
        elif self.action == 'list':
            return GameListSerializer
        elif self.action == 'retrieve':
            return GameDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filtrira queryset ovisno o parametrima upita."""
        queryset = self._apply_base_filters(Game.objects.all())
        return queryset.order_by('-created_at')
    
    def _apply_base_filters(self, queryset):
        """Primjenjuje osnovne filtere na queryset prema query parametrima."""
        # Filtriraj po statusu
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filtriraj igre gdje je korisnik član
        my_games = self.request.query_params.get('my_games')
        if my_games and my_games.lower() == 'true':
            queryset = queryset.filter(players=self.request.user)
        
        # Filtriraj po privatnosti
        is_private = self.request.query_params.get('is_private')
        if is_private is not None:
            queryset = queryset.filter(is_private=(is_private.lower() == 'true'))
        
        # Filtriraj po broju igrača
        queryset = queryset.annotate(player_count=Count('players'))
        player_count = self.request.query_params.get('player_count')
        if player_count:
            queryset = queryset.filter(player_count=int(player_count))
        
        # Filtriraj samo igre koje čekaju igrače
        waiting = self.request.query_params.get('waiting')
        if waiting and waiting.lower() == 'true':
            queryset = queryset.filter(
                status__in=['waiting', 'ready'],
                player_count__lt=4
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Stvara novu igru i koristi GameService za postavljanje."""
        game = serializer.save()
        # Dodatno postavljanje se obavlja u serializer.create metodi
        logger.info(f"Korisnik {self.request.user.username} stvorio igru {game.id}")
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """API akcija za pridruživanje igri."""
        service = GameService(game_id=pk)
        result = service.join_game(user_id=request.user.id)
        
        if result.get('valid', False):
            return Response({
                'status': 'success',
                'message': 'Uspješno ste se pridružili igri',
                'game_id': result['game_id']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('message', 'Nije moguće pridružiti se igri')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """API akcija za napuštanje igre."""
        service = GameService(game_id=pk)
        result = service.leave_game(user_id=request.user.id)
        
        if result.get('valid', False):
            return Response({
                'status': 'success',
                'message': 'Uspješno ste napustili igru',
                'game_status': result.get('game_status')
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('message', 'Nije moguće napustiti igru')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """API akcija za pokretanje igre."""
        service = GameService(game_id=pk)
        result = service.start_game(user_id=request.user.id)
        
        if result.get('valid', False):
            return Response({
                'status': 'success',
                'message': 'Igra je uspješno pokrenuta',
                'dealer': result.get('dealer'),
                'next_player': result.get('next_player')
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('message', 'Nije moguće pokrenuti igru')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def state(self, request, pk=None):
        """API akcija za dohvaćanje trenutnog stanja igre prilagođenog za igrača."""
        service = GameService(game_id=pk)
        game_state = service.get_game_state(user_id=request.user.id)
        
        if 'error' in game_state:
            return Response({
                'status': 'error',
                'message': game_state['error']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = GameStateSerializer(game_state)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def join_by_code(self, request):
        """API akcija za pridruživanje igri putem koda sobe."""
        room_code = request.data.get('room_code')
        if not room_code:
            return Response({
                'status': 'error',
                'message': 'Kod sobe je obavezan'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        service = GameService()
        result = service.join_game(user_id=request.user.id, room_code=room_code)
        
        if result.get('valid', False):
            return Response({
                'status': 'success',
                'message': 'Uspješno ste se pridružili igri',
                'game_id': result['game_id']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('message', 'Nije moguće pridružiti se igri')
            }, status=status.HTTP_400_BAD_REQUEST)


class RoundViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet za runde igre.
    
    Omogućuje dohvaćanje informacija o rundama, uključujući
    poteze, zvanja i rezultate.
    """
    queryset = Round.objects.all()
    serializer_class = RoundSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Odabire serializator ovisno o akciji."""
        if self.action == 'retrieve':
            return RoundDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filtrira runde ovisno o parametrima upita."""
        queryset = Round.objects.all()
        
        # Filtriraj po igri
        game_id = self.request.query_params.get('game')
        if game_id:
            queryset = queryset.filter(game_id=game_id)
        
        # Primijeni dodatne filtere
        queryset = self._apply_additional_filters(queryset)
        
        return queryset.order_by('game', 'round_number')
    
    def _apply_additional_filters(self, queryset):
        """Primijeni dodatne filtere na queryset rundi."""
        # Filtriraj po broju runde
        number = self.request.query_params.get('number')
        if number:
            queryset = queryset.filter(round_number=int(number))
        
        # Filtriraj po statusu završenosti
        is_completed = self.request.query_params.get('is_completed')
        if is_completed is not None:
            queryset = queryset.filter(is_completed=(is_completed.lower() == 'true'))
        
        # Filtriraj po adutskoj boji
        trump_suit = self.request.query_params.get('trump_suit')
        if trump_suit:
            queryset = queryset.filter(trump_suit=trump_suit)
            
        return queryset


class MoveViewSet(viewsets.ModelViewSet):
    """
    ViewSet za poteze u igri.
    
    Omogućuje igranje poteza i pregled povijesti poteza.
    """
    queryset = Move.objects.all()
    serializer_class = MoveSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Odabire serializator ovisno o akciji."""
        if self.action == 'create':
            return MoveCreateSerializer
        elif self.action == 'list':
            return MoveListSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filtrira poteze ovisno o parametrima upita."""
        queryset = Move.objects.all()
        
        # Primijeni filtere
        queryset = self._apply_move_filters(queryset)
        
        return queryset.order_by('round', 'order')
    
    def _apply_move_filters(self, queryset):
        """Primijeni filtere na queryset poteza."""
        # Filtriraj po rundi
        round_id = self.request.query_params.get('round')
        if round_id:
            queryset = queryset.filter(round_id=round_id)
        
        # Filtriraj po igraču
        player_id = self.request.query_params.get('player')
        if player_id:
            queryset = queryset.filter(player_id=player_id)
        
        # Filtriraj po pobjedničkom statusu
        is_winning = self.request.query_params.get('is_winning')
        if is_winning is not None:
            queryset = queryset.filter(is_winning_card=(is_winning.lower() == 'true'))
        
        # Filtriraj po broju štiha
        trick_number = self.request.query_params.get('trick')
        if trick_number:
            trick_num = int(trick_number)
            queryset = queryset.filter(
                order__gte=trick_num * 4,
                order__lt=(trick_num + 1) * 4
            )
            
        return queryset
    
    def perform_create(self, serializer):
        """Stvara novi potez i koristi GameService za validaciju i obradu."""
        # Dohvati rundu i igru
        round_obj = serializer.validated_data['round']
        game = round_obj.game
        
        # Koristi servis za validaciju i obradu poteza
        service = GameService(game_id=str(game.id))
        result = service.process_move(
            user_id=self.request.user.id,
            card=serializer.validated_data['card_code']
        )
        
        if not result.get('valid', False):
            raise serializers.ValidationError(result.get('message', 'Nevažeći potez'))
        
        # Potez je već stvoren u service.process_move, 
        # pa ne pozivamo standardni serializer.save()
        logger.info(f"Korisnik {self.request.user.username} odigrao kartu {serializer.validated_data['card_code']}")


class DeclarationViewSet(viewsets.ModelViewSet):
    """
    ViewSet za zvanja u igri.
    
    Omogućuje prijavu zvanja i pregled postojećih zvanja.
    """
    queryset = Declaration.objects.all()
    serializer_class = DeclarationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Odabire serializator ovisno o akciji."""
        if self.action == 'create':
            return DeclarationCreateSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filtrira zvanja ovisno o parametrima upita."""
        queryset = Declaration.objects.all()
        
        # Primijeni filtere na zvanja
        queryset = self._apply_declaration_filters(queryset)
        
        return queryset.order_by('-value', 'round', 'created_at')
    
    def _apply_declaration_filters(self, queryset):
        """Primijeni filtere na queryset zvanja."""
        # Filtriraj po rundi
        round_id = self.request.query_params.get('round')
        if round_id:
            queryset = queryset.filter(round_id=round_id)
        
        # Filtriraj po igraču
        player_id = self.request.query_params.get('player')
        if player_id:
            queryset = queryset.filter(player_id=player_id)
        
        # Filtriraj po tipu zvanja
        declaration_type = self.request.query_params.get('type')
        if declaration_type:
            queryset = queryset.filter(declaration_type=declaration_type)
        
        # Filtriraj po boji
        suit = self.request.query_params.get('suit')
        if suit:
            queryset = queryset.filter(suit=suit)
            
        return queryset
    
    def perform_create(self, serializer):
        """Stvara novo zvanje i koristi GameService za validaciju i obradu."""
        # Dohvati rundu i igru
        round_obj = serializer.validated_data['round']
        game = round_obj.game
        
        # Koristi servis za validaciju i obradu zvanja
        service = GameService(game_id=str(game.id))
        
        # Obradi različite tipove zvanja
        if serializer.validated_data['declaration_type'] == 'bela':
            result = service.process_bela(user_id=self.request.user.id)
        else:
            result = service.process_declaration(
                user_id=self.request.user.id,
                declaration_type=serializer.validated_data['declaration_type'],
                cards=serializer.validated_data.get('cards_json', [])
            )
        
        if not result.get('valid', False):
            raise serializers.ValidationError(result.get('message', 'Nevažeće zvanje'))
        
        # Zvanje je već stvoreno u service metodi, 
        # pa ne pozivamo standardni serializer.save()
        logger.info(f"Korisnik {self.request.user.username} prijavio zvanje {serializer.validated_data['declaration_type']}")


class GameActionView(APIView):
    """
    API pogled za izvršavanje različitih akcija na igri.
    
    Prihvaća različite akcije poput igranja poteza, zvanja aduta,
    prijave zvanja, itd. kroz jedinstveni endpoint.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, game_id, format=None):
        """Obrađuje POST zahtjev s akcijom."""
        # Validacija zahtjeva
        serializer = GameActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Dohvati akciju i podatke
        action = serializer.validated_data['action']
        
        # Inicijaliziraj servis
        service = GameService(game_id=game_id)
        
        # Izvrši odgovarajuću akciju
        result = self._execute_game_action(service, action, request.user.id, serializer.validated_data)
        
        # Vrati rezultat
        if result and result.get('valid', False):
            return Response({
                'status': 'success',
                'action': action,
                **{k: v for k, v in result.items() if k != 'valid'}
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('message', 'Greška prilikom izvršavanja akcije')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _execute_game_action(self, service, action, user_id, data):
        """Izvršava odgovarajuću akciju na igri."""
        if action == 'make_move':
            return service.process_move(user_id=user_id, card=data.get('card'))
        
        elif action == 'call_trump':
            return service.process_trump_call(user_id=user_id, suit=data.get('trump_suit'))
        
        elif action == 'pass_trump':
            return service.process_trump_pass(user_id=user_id)
        
        elif action == 'declare':
            return service.process_declaration(
                user_id=user_id,
                declaration_type=data.get('declaration_type'),
                cards=data.get('cards', [])
            )
        
        elif action == 'bela':
            return service.process_bela(user_id=user_id)
        
        elif action == 'join_game':
            return service.join_game(user_id=user_id)
        
        elif action == 'leave_game':
            return service.leave_game(user_id=user_id)
        
        elif action == 'start_game':
            return service.start_game(user_id=user_id)
        
        elif action == 'ready':
            return service.mark_player_ready(user_id=user_id)
        
        return {'valid': False, 'message': f'Nepodržana akcija: {action}'}


class GameStatisticsView(APIView):
    """
    API pogled za statistiku igre.
    
    Pruža statistiku o igrama, poput broja odigranih igara,
    prosječnog trajanja, najboljih igrača, itd.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, game_id=None, format=None):
        """Dohvaća statistiku za sve igre ili specifičnu igru."""
        if game_id:
            return self._get_single_game_statistics(game_id)
        else:
            return self._get_global_statistics(request)
    
    def _get_single_game_statistics(self, game_id):
        """Dohvaća statistiku za specifičnu igru."""
        try:
            game = Game.objects.get(id=game_id)
            
            # Osnovna statistika igre
            stats = self._get_basic_game_stats(game)
            
            # Statistika rundi
            stats['rounds'] = self._get_rounds_stats(game)
            
            # Statistika igrača
            stats['players'] = self._get_players_stats(game)
            
            return Response(stats)
            
        except Game.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Igra nije pronađena'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def _get_basic_game_stats(self, game):
        """Dohvaća osnovne statistike igre."""
        return {
            'game_id': str(game.id),
            'room_code': game.room_code,
            'status': game.status,
            'created_at': game.created_at,
            'started_at': game.started_at,
            'finished_at': game.finished_at,
            'duration': (game.finished_at - game.started_at).total_seconds() if game.finished_at and game.started_at else None,
            'team_a_score': game.team_a_score,
            'team_b_score': game.team_b_score,
            'winner_team': game.winner_team,
            'points_to_win': game.points_to_win,
            'rounds_count': game.rounds.count(),
        }
    
    def _get_rounds_stats(self, game):
        """Dohvaća statistiku rundi za specifičnu igru."""
        rounds_stats = []
        for round_obj in game.rounds.all().order_by('round_number'):
            moves_count = round_obj.moves.count()
            declarations_count = round_obj.declarations.count()
            bela_count = round_obj.declarations.filter(declaration_type='belot').count()
            
            rounds_stats.append({
                'number': round_obj.round_number,
                'trump_suit': round_obj.trump_suit,
                'calling_team': round_obj.calling_team,
                'team_a_score': round_obj.team_a_score,
                'team_b_score': round_obj.team_b_score,
                'winner_team': round_obj.winner_team,
                'moves_count': moves_count,
                'declarations_count': declarations_count,
                'bela_count': bela_count,
            })
        
        return rounds_stats
    
    def _get_players_stats(self, game):
        """Dohvaća statistiku igrača za specifičnu igru."""
        player_stats = []
        for player in game.players.all():
            team = 'a' if player in game.team_a_players.all() else 'b' if player in game.team_b_players.all() else None
            moves = Move.objects.filter(round__game=game, player=player)
            declarations = Declaration.objects.filter(round__game=game, player=player)
            
            player_stats.append({
                'id': player.id,
                'username': player.username,
                'team': team,
                'moves_count': moves.count(),
                'winning_moves': moves.filter(is_winning_card=True).count(),
                'declarations_count': declarations.count(),
                'declaration_points': declarations.aggregate(total=Sum('value'))['total'] or 0,
                'winner': (team == game.winner_team) if game.winner_team else None
            })
        
        return player_stats
    
    def _get_global_statistics(self, request):
        """Dohvaća globalnu statistiku za sve igre."""
        # Broj igara po statusu
        games_count = Game.objects.count()
        games_in_progress = Game.objects.filter(status='in_progress').count()
        games_waiting = Game.objects.filter(status__in=['waiting', 'ready']).count()
        completed_games = Game.objects.filter(status='finished').count()
        
        # Prosječno trajanje završenih igara
        average_duration = self._calculate_average_duration()
        
        # Prosječni broj bodova
        average_points = Game.objects.filter(
            status='finished'
        ).aggregate(
            avg_team_a=Avg('team_a_score'),
            avg_team_b=Avg('team_b_score')
        )
        
        # Najaktivniji igrači
        most_active_players = self._get_most_active_players()
        
        # Statistika korisnika koji šalje zahtjev
        user_stats = self._get_user_statistics(request.user)
        
        stats = {
            'total_games': games_count,
            'games_in_progress': games_in_progress,
            'games_waiting': games_waiting,
            'completed_games': completed_games,
            'average_duration': average_duration,
            'average_points': {
                'team_a': average_points['avg_team_a'],
                'team_b': average_points['avg_team_b']
            },
            'most_active_players': most_active_players,
            'user_stats': user_stats
        }
        
        return Response(stats)
    
    def _calculate_average_duration(self):
        """Izračunava prosječno trajanje završenih igara."""
        average_duration = None
        avg_duration_query = Game.objects.filter(
            status='finished',
            started_at__isnull=False,
            finished_at__isnull=False
        ).annotate(
            duration=F('finished_at') - F('started_at')
        ).aggregate(avg=Avg('duration'))
        
        if avg_duration_query['avg']:
            average_duration = avg_duration_query['avg'].total_seconds()
            
        return average_duration
    
    def _get_most_active_players(self):
        """Dohvaća najaktivnije igrače."""
        most_active_players = User.objects.annotate(
            games_count=Count('games')
        ).order_by('-games_count')[:10]
        
        return [
            {
                'id': player.id,
                'username': player.username,
                'games_count': player.games_count
            }
            for player in most_active_players
        ]
    
    def _get_user_statistics(self, user):
        """Dohvaća statistiku za specifičnog korisnika."""
        if not user.is_authenticated:
            return None
            
        user_games = Game.objects.filter(players=user)
        user_wins = Game.objects.filter(
            Q(team_a_players=user, winner_team='a') | 
            Q(team_b_players=user, winner_team='b'),
            status='completed'
        ).count()
        
        return {
            'games_played': user_games.count(),
            'games_won': user_wins,
            'win_rate': (user_wins / user_games.count()) * 100 if user_games.count() > 0 else 0,
            'active_games': user_games.filter(status='in_progress').count()
        }


class CurrentGamesView(APIView):
    """
    API pogled za prikaz trenutno aktivnih igara.
    
    Vraća listu igara koje su trenutno u tijeku ili čekaju igrače,
    s mogućnošću filtriranja po različitim kriterijima.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, format=None):
        """Dohvaća trenutno aktivne igre."""
        queryset = self._get_filtered_games(request)
        
        # Ograniči broj rezultata
        limit = self._get_limit_param(request)
        queryset = queryset[:limit]
        
        # Serializiraj rezultate
        serializer = GameListSerializer(
            queryset.order_by('-created_at'),
            many=True,
            context={'request': request}
        )
        
        return Response(serializer.data)
    
    def _get_filtered_games(self, request):
        """Dohvaća i filtrira igre prema query parametrima."""
        queryset = Game.objects.all()
        
        # Filtriraj po statusu
        status = request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Zadano prikaži samo igre u tijeku i one koje čekaju
            queryset = queryset.filter(status__in=['in_progress', 'waiting', 'ready'])
        
        # Filtriraj po privatnosti
        is_private = request.query_params.get('is_private')
        if is_private is not None:
            queryset = queryset.filter(is_private=(is_private.lower() == 'true'))
        
        # Filtriraj igre koje korisnik trenutno igra
        my_games = request.query_params.get('my_games')
        if my_games and my_games.lower() == 'true':
            queryset = queryset.filter(players=request.user)
        
        # Filtriraj igre koje čekaju više igrača
        waiting_for_players = request.query_params.get('waiting_for_players')
        if waiting_for_players and waiting_for_players.lower() == 'true':
            queryset = queryset.annotate(player_count=Count('players')).filter(
                status__in=['waiting', 'ready'],
                player_count__lt=4
            )
            
        return queryset
    
    def _get_limit_param(self, request):
        """Dohvaća limit parametar iz query stringa ili vraća zadani limit."""
        limit = request.query_params.get('limit')
        if limit:
            try:
                return int(limit)
            except ValueError:
                pass
        return 20  # Zadani limit