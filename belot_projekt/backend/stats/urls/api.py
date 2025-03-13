"""
API pogledi za Django aplikaciju "stats".

Ovaj modul definira REST API endpointe za pristup i manipulaciju
statističkim podacima Belot igre, omogućujući frontend aplikacijama
da prikazuju različite statistike, ljestvice i analitičke podatke.
"""

import logging
from datetime import datetime, timedelta
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from ..models import (
    PlayerStats, TeamStats, GameStats, GlobalStats,
    DailyStats, StatisticsSnapshot, Leaderboard
)
from ..serializers import (
    PlayerStatsSerializer, PlayerStatsMinimalSerializer,
    TeamStatsSerializer, GameStatsSerializer,
    GlobalStatsSerializer, DailyStatsSerializer,
    StatisticsSnapshotSerializer, LeaderboardSerializer,
    LeaderboardMinimalSerializer, GameHistoryStatsSerializer,
    PlayerComparisonSerializer, TopPlayersByStatSerializer
)
from utils.decorators import track_execution_time
from utils.exceptions import ResourceNotFoundError

User = get_user_model()
logger = logging.getLogger('stats.api')


class PlayerStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za statistiku igrača.
    
    Pružaju pristup statistikama pojedinačnih igrača,
    uključujući filtere, sortiranje i posebne akcije.
    """
    queryset = PlayerStats.objects.all().select_related('user')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering_fields = [
        'games_played', 'games_won', 'win_percentage', 
        'total_score', 'avg_points_per_game', 'longest_winning_streak',
        'last_game_date'
    ]
    ordering = ['-games_played']
    
    def get_serializer_class(self):
        """Odabire odgovarajući serializator ovisno o akciji."""
        if self.action == 'list':
            return PlayerStatsMinimalSerializer
        return PlayerStatsSerializer
    
    @track_execution_time
    def retrieve(self, request, *args, **kwargs):
        """Dohvaća detalje statistike određenog igrača."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju statistike igrača: {str(e)}")
            return Response(
                {"error": "Statistika igrača nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Dohvaća statistiku trenutno prijavljenog korisnika."""
        try:
            stats = PlayerStats.objects.get(user=request.user)
            serializer = self.get_serializer(stats)
            return Response(serializer.data)
        except PlayerStats.DoesNotExist:
            return Response(
                {"error": "Statistika nije pronađena za ovog korisnika"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Dohvaća povijest igara za određenog igrača."""
        try:
            player_stats = self.get_object()
            
            # Dohvati period za grupiranje
            period = request.query_params.get('period', 'daily')
            limit = int(request.query_params.get('limit', 30))
            
            # Izračunaj grupiranu povijest igara
            history_data = self._calculate_player_history(player_stats.user, period, limit)
            
            # Serializiraj podatke
            serializer = GameHistoryStatsSerializer(history_data, many=True)
            return Response(serializer.data)
            
        except PlayerStats.DoesNotExist:
            return Response(
                {"error": "Statistika igrača nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju povijesti igrača: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju povijesti igrača"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def teams(self, request, pk=None):
        """Dohvaća timske statistike za određenog igrača."""
        try:
            player_stats = self.get_object()
            user = player_stats.user
            
            # Dohvati timske statistike za korisnika
            teams = TeamStats.objects.filter(
                Q(player1=user) | Q(player2=user)
            ).order_by('-games_played')
            
            # Filtriraj po broju igara ako je navedeno
            min_games = request.query_params.get('min_games')
            if min_games:
                teams = teams.filter(games_played__gte=int(min_games))
            
            # Serializiraj podatke
            serializer = TeamStatsSerializer(teams, many=True)
            return Response(serializer.data)
            
        except PlayerStats.DoesNotExist:
            return Response(
                {"error": "Statistika igrača nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju timskih statistika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju timskih statistika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def top(self, request):
        """Dohvaća najbolje igrače po određenoj statistici."""
        try:
            # Dohvati parametar po kojem se sortira
            stat = request.query_params.get('stat', 'win_percentage')
            limit = int(request.query_params.get('limit', 10))
            
            # Validiraj parametar
            valid_stats = [
                'games_played', 'games_won', 'win_percentage', 
                'total_score', 'avg_points_per_game', 'longest_winning_streak'
            ]
            
            if stat not in valid_stats:
                return Response(
                    {"error": f"Nevažeći statistički parametar. Dozvoljeni parametri: {', '.join(valid_stats)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati igrače sortirane po zadanom parametru
            if stat == 'win_percentage':
                # Za postotak pobjeda, filtriraj samo igrače s dovoljno igara
                players = PlayerStats.objects.filter(
                    games_played__gte=10  # Minimalni broj igara za kvalifikaciju
                ).order_by(f'-{stat}', '-games_played')[:limit]
            else:
                players = PlayerStats.objects.order_by(f'-{stat}')[:limit]
            
            # Pripremi podatke za odgovor
            result = []
            for i, player in enumerate(players):
                result.append({
                    'user_id': player.user.id,
                    'username': player.user.username,
                    'value': getattr(player, stat),
                    'rank': i + 1
                })
            
            # Serializiraj podatke
            serializer = TopPlayersByStatSerializer(result, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju najboljih igrača: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju najboljih igrača"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def compare(self, request):
        """Uspoređuje statistiku dva igrača."""
        try:
            # Dohvati ID-ove igrača za usporedbu
            player1_id = request.query_params.get('player1')
            player2_id = request.query_params.get('player2')
            
            if not player1_id or not player2_id:
                return Response(
                    {"error": "Potrebno je navesti ID-ove oba igrača (player1 i player2)"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati statistiku oba igrača
            player1_stats = get_object_or_404(PlayerStats, user__id=player1_id)
            player2_stats = get_object_or_404(PlayerStats, user__id=player2_id)
            
            # Izračunaj razlike
            comparison_data = self._compare_players(player1_stats, player2_stats)
            
            # Serializiraj podatke
            serializer = PlayerComparisonSerializer(comparison_data)
            return Response(serializer.data)
            
        except PlayerStats.DoesNotExist:
            return Response(
                {"error": "Statistika jednog ili oba igrača nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Greška pri usporedbi igrača: {str(e)}")
            return Response(
                {"error": "Greška pri usporedbi igrača"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_player_history(self, user, period='daily', limit=30):
        """
        Izračunava povijest igara za igrača.
        
        Args:
            user: Korisnik za kojeg se izračunava povijest
            period: Period grupiranja ('daily', 'weekly', 'monthly')
            limit: Maksimalni broj rezultata
            
        Returns:
            list: Lista s podacima povijesti igara
        """
        from django.db import connection
        
        # Odredi SQL dio za grupiranje ovisno o periodu
        if period == 'weekly':
            date_trunc = "week"
            date_format = "YYYY-WW"
        elif period == 'monthly':
            date_trunc = "month"
            date_format = "YYYY-MM"
        else:  # daily
            date_trunc = "day"
            date_format = "YYYY-MM-DD"
        
        # Izvrši složeni upit za dobivanje povijesti igara
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    WITH game_data AS (
                        SELECT 
                            DATE_TRUNC(%s, gs.end_time) AS period,
                            g.id AS game_id,
                            CASE 
                                WHEN (g.team_a_players @> ARRAY[%s::uuid] AND g.winning_team = 'a') OR
                                    (g.team_b_players @> ARRAY[%s::uuid] AND g.winning_team = 'b')
                                THEN 1
                                ELSE 0
                            END AS won,
                            CASE
                                WHEN g.team_a_players @> ARRAY[%s::uuid] THEN g.team_a_score
                                ELSE g.team_b_score
                            END AS score
                        FROM 
                            game_game g
                            JOIN game_gamestats gs ON g.id = gs.game_id
                        WHERE 
                            g.status = 'completed' AND
                            g.players @> ARRAY[%s::uuid] AND
                            gs.end_time IS NOT NULL
                    )
                    SELECT
                        period,
                        COUNT(*) AS games_played,
                        SUM(won) AS games_won,
                        CASE 
                            WHEN COUNT(*) > 0 THEN ROUND((SUM(won)::float / COUNT(*)) * 100, 2)
                            ELSE 0
                        END AS win_rate,
                        SUM(score) AS total_score,
                        CASE 
                            WHEN COUNT(*) > 0 THEN ROUND((SUM(score)::float / COUNT(*)), 2)
                            ELSE 0
                        END AS avg_score
                    FROM
                        game_data
                    GROUP BY
                        period
                    ORDER BY
                        period DESC
                    LIMIT %s;
                """, [
                    date_trunc, str(user.id), str(user.id), 
                    str(user.id), str(user.id), limit
                ])
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'date': row[0],
                        'games_played': row[1],
                        'games_won': row[2],
                        'win_rate': row[3],
                        'total_score': row[4],
                        'avg_score': row[5]
                    })
                
                return results
        
        except Exception as e:
            logger.error(f"Greška pri izračunu povijesti igrača: {str(e)}")
            return []
    
    def _compare_players(self, player1_stats, player2_stats):
        """
        Uspoređuje statistiku dva igrača.
        
        Args:
            player1_stats: Statistika prvog igrača
            player2_stats: Statistika drugog igrača
            
        Returns:
            dict: Rječnik s podacima za usporedbu
        """
        # Izračunaj razlike
        games_played_diff = player1_stats.games_played - player2_stats.games_played
        win_percentage_diff = player1_stats.win_percentage - player2_stats.win_percentage
        avg_points_diff = player1_stats.avg_points_per_game - player2_stats.avg_points_per_game
        
        # Dohvati zajedničke igre (igre gdje su oba igrača sudjelovala)
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM game_game g
                WHERE 
                    g.status = 'completed' AND
                    g.players @> ARRAY[%s::uuid, %s::uuid]
            """, [str(player1_stats.user.id), str(player2_stats.user.id)])
            
            common_games = cursor.fetchone()[0]
        
        # Dohvati pobjednike među zajedničkim igrama
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM game_game g
                WHERE 
                    g.status = 'completed' AND
                    g.players @> ARRAY[%s::uuid, %s::uuid] AND
                    ((g.team_a_players @> ARRAY[%s::uuid] AND g.winning_team = 'a') OR
                     (g.team_b_players @> ARRAY[%s::uuid] AND g.winning_team = 'b'))
            """, [
                str(player1_stats.user.id), str(player2_stats.user.id), 
                str(player1_stats.user.id), str(player1_stats.user.id)
            ])
            
            player1_wins = cursor.fetchone()[0]
        
        player2_wins = common_games - player1_wins
        
        # Vrati podatke za usporedbu
        return {
            'player1': player1_stats,
            'player2': player2_stats,
            'games_played_diff': games_played_diff,
            'win_percentage_diff': win_percentage_diff,
            'avg_points_diff': avg_points_diff,
            'common_games': common_games,
            'player1_wins_against_player2': player1_wins,
            'player2_wins_against_player1': player2_wins
        }


class TeamStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za statistiku timova.
    
    Pružaju pristup statistikama timova,
    uključujući filtere, sortiranje i posebne akcije.
    """
    queryset = TeamStats.objects.all().select_related('player1', 'player2')
    serializer_class = TeamStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        'games_played', 'games_won', 'win_percentage', 
        'total_score', 'avg_points_per_game', 'longest_winning_streak',
        'last_game_date'
    ]
    ordering = ['-games_played']
    
    @track_execution_time
    def retrieve(self, request, *args, **kwargs):
        """Dohvaća detalje statistike određenog tima."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju statistike tima: {str(e)}")
            return Response(
                {"error": "Statistika tima nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def user(self, request):
        """Dohvaća timske statistike za trenutno prijavljenog korisnika."""
        try:
            user = request.user
            
            # Dohvati timske statistike za korisnika
            teams = TeamStats.objects.filter(
                Q(player1=user) | Q(player2=user)
            ).order_by('-games_played')
            
            # Filtriraj po broju igara ako je navedeno
            min_games = request.query_params.get('min_games')
            if min_games:
                teams = teams.filter(games_played__gte=int(min_games))
            
            # Ograniči broj rezultata ako je navedeno
            limit = request.query_params.get('limit')
            if limit:
                teams = teams[:int(limit)]
            
            # Serializiraj podatke
            serializer = self.get_serializer(teams, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju timskih statistika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju timskih statistika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def player(self, request):
        """Dohvaća timske statistike za određenog igrača."""
        try:
            # Dohvati ID igrača
            player_id = request.query_params.get('id')
            if not player_id:
                return Response(
                    {"error": "Potrebno je navesti ID igrača"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati korisnika
            user = get_object_or_404(User, id=player_id)
            
            # Dohvati timske statistike za korisnika
            teams = TeamStats.objects.filter(
                Q(player1=user) | Q(player2=user)
            ).order_by('-games_played')
            
            # Filtriraj po broju igara ako je navedeno
            min_games = request.query_params.get('min_games')
            if min_games:
                teams = teams.filter(games_played__gte=int(min_games))
            
            # Ograniči broj rezultata ako je navedeno
            limit = request.query_params.get('limit')
            if limit:
                teams = teams[:int(limit)]
            
            # Serializiraj podatke
            serializer = self.get_serializer(teams, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju timskih statistika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju timskih statistika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def top(self, request):
        """Dohvaća najbolje timove po određenoj statistici."""
        try:
            # Dohvati parametar po kojem se sortira
            stat = request.query_params.get('stat', 'win_percentage')
            limit = int(request.query_params.get('limit', 10))
            
            # Validiraj parametar
            valid_stats = [
                'games_played', 'games_won', 'win_percentage', 
                'total_score', 'avg_points_per_game', 'longest_winning_streak'
            ]
            
            if stat not in valid_stats:
                return Response(
                    {"error": f"Nevažeći statistički parametar. Dozvoljeni parametri: {', '.join(valid_stats)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati timove sortirane po zadanom parametru
            if stat == 'win_percentage':
                # Za postotak pobjeda, filtriraj samo timove s dovoljno igara
                teams = TeamStats.objects.filter(
                    games_played__gte=5  # Minimalni broj igara za kvalifikaciju
                ).order_by(f'-{stat}', '-games_played')[:limit]
            else:
                teams = TeamStats.objects.order_by(f'-{stat}')[:limit]
            
            # Serializiraj podatke
            serializer = self.get_serializer(teams, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju najboljih timova: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju najboljih timova"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GameStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za statistiku igara.
    
    Pružaju pristup statistikama pojedinačnih igara,
    uključujući filtere, sortiranje i posebne akcije.
    """
    queryset = GameStats.objects.all().select_related('game')
    serializer_class = GameStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        'start_time', 'end_time', 'duration', 'total_rounds',
        'team_a_score', 'team_b_score'
    ]
    ordering = ['-end_time']
    
    @track_execution_time
    def retrieve(self, request, *args, **kwargs):
        """Dohvaća detalje statistike određene igre."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju statistike igre: {str(e)}")
            return Response(
                {"error": "Statistika igre nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Dohvaća nedavno završene igre."""
        try:
            # Dohvati broj igara koje treba vratiti
            limit = int(request.query_params.get('limit', 10))
            
            # Dohvati zadnje završene igre
            recent_games = GameStats.objects.filter(
                game__status='completed'
            ).order_by('-end_time')[:limit]
            
            # Serializiraj podatke
            serializer = self.get_serializer(recent_games, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju nedavnih igara: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju nedavnih igara"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def user(self, request):
        """Dohvaća igre za određenog korisnika."""
        try:
            # Dohvati ID korisnika
            user_id = request.query_params.get('id')
            
            # Ako nije naveden ID, koristi trenutnog korisnika
            if not user_id:
                user = request.user
            else:
                user = get_object_or_404(User, id=user_id)
            
            # Dohvati igre korisnika
            user_games = GameStats.objects.filter(
                game__players=user,
                game__status='completed'
            ).order_by('-end_time')
            
            # Ograniči broj rezultata ako je navedeno
            limit = request.query_params.get('limit')
            if limit:
                user_games = user_games[:int(limit)]
            
            # Serializiraj podatke
            serializer = self.get_serializer(user_games, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju igara korisnika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju igara korisnika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GlobalStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za globalne statistike.
    
    Pruža pristup agregiranim statistikama cijele platforme.
    """
    serializer_class = GlobalStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Dohvaća globalne statistike."""
        return GlobalStats.objects.all()
    
    def list(self, request):
        """Dohvaća globalne statistike."""
        try:
            # Dohvati jedinstvenu instancu globalnih statistika
            global_stats = GlobalStats.get_instance()
            
            # Serializiraj podatke
            serializer = self.get_serializer(global_stats)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju globalnih statistika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju globalnih statistika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Dohvaća trendove iz globalnih statistika."""
        try:
            # Dohvati dnevne statistike za zadnjih 30 dana
            daily_stats = DailyStats.objects.order_by('-date')[:30]
            
            # Serializiraj podatke
            serializer = DailyStatsSerializer(daily_stats, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju trendova: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju trendova"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za ljestvice.
    
    Pružaju pristup ljestvicama najboljih igrača
    po različitim kategorijama i vremenskim periodima.
    """
    queryset = Leaderboard.objects.all().order_by('-updated_at')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['updated_at']
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        """Odabire odgovarajući serializator ovisno o akciji."""
        if self.action == 'list':
            return LeaderboardMinimalSerializer
        return LeaderboardSerializer
    
    @track_execution_time
    def retrieve(self, request, *args, **kwargs):
        """Dohvaća detalje određene ljestvice."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju ljestvice: {str(e)}")
            return Response(
                {"error": "Ljestvica nije pronađena"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Dohvaća ljestvice po kategoriji."""
        try:
            # Dohvati kategoriju
            category = request.query_params.get('category')
            if not category:
                return Response(
                    {"error": "Potrebno je navesti kategoriju"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validiraj kategoriju
            valid_categories = ['wins', 'win_percentage', 'points', 'games_played', 'belot_declarations', 'four_of_a_kind']
            if category not in valid_categories:
                return Response(
                    {"error": f"Nevažeća kategorija. Dozvoljene kategorije: {', '.join(valid_categories)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati ljestvice za kategoriju
            leaderboards = Leaderboard.objects.filter(
                category=category
            ).order_by('period')
            
            # Serializiraj podatke
            serializer = self.get_serializer(leaderboards, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju ljestvica po kategoriji: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju ljestvica po kategoriji"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_period(self, request):
        """Dohvaća ljestvice po vremenskom periodu."""
        try:
            # Dohvati period
            period = request.query_params.get('period')
            if not period:
                return Response(
                    {"error": "Potrebno je navesti period"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validiraj period
            valid_periods = ['daily', 'weekly', 'monthly', 'all_time']
            if period not in valid_periods:
                return Response(
                    {"error": f"Nevažeći period. Dozvoljeni periodi: {', '.join(valid_periods)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Dohvati ljestvice za period
            leaderboards = Leaderboard.objects.filter(
                period=period
            ).order_by('category')
            
            # Serializiraj podatke
            serializer = self.get_serializer(leaderboards, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju ljestvica po periodu: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju ljestvica po periodu"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def user_positions(self, request):
        """Dohvaća pozicije korisnika na ljestvicama."""
        try:
            # Dohvati ID korisnika
            user_id = request.query_params.get('id')
            
            # Ako nije naveden ID, koristi trenutnog korisnika
            if not user_id:
                user_id = str(request.user.id)
            
            # Dohvati sve ljestvice
            leaderboards = Leaderboard.objects.filter(
                updated_at__gte=timezone.now() - timedelta(days=7)
            )
            
            # Za svaku ljestvicu, pronađi poziciju korisnika
            user_positions = {}
            for leaderboard in leaderboards:
                key = f"{leaderboard.period}_{leaderboard.category}"
                user_positions[key] = {
                    'leaderboard_id': str(leaderboard.id),
                    'period': leaderboard.period,
                    'period_display': leaderboard.get_period_display(),
                    'category': leaderboard.category,
                    'category_display': leaderboard.get_category_display(),
                    'position': None,
                    'value': None
                }
                
                # Provjeri je li korisnik na ljestvici
                for player in leaderboard.players:
                    if str(player.get('id')) == user_id:
                        user_positions[key]['position'] = player.get('rank')
                        user_positions[key]['value'] = player.get('value')
                        break
            
            return Response(user_positions)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju pozicija korisnika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju pozicija korisnika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DailyStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpointi za dnevne statistike.
    
    Pružaju pristup dnevnim agregiranim statistikama.
    """
    queryset = DailyStats.objects.all().order_by('-date')
    serializer_class = DailyStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'total_games', 'active_players', 'new_users']
    ordering = ['-date']
    
    @action(detail=False, methods=['get'])
    def range(self, request):
        """Dohvaća dnevne statistike za određeni vremenski raspon."""
        try:
            # Dohvati početni i završni datum
            start_date = request.query_params.get('start')
            end_date = request.query_params.get('end')
            
            if not start_date:
                # Ako nije naveden početni datum, koristi zadnjih 30 dana
                start_date = (timezone.now() - timedelta(days=30)).date()
            else:
                # Pretvori string u datum
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if not end_date:
                # Ako nije naveden završni datum, koristi današnji datum
                end_date = timezone.now().date()
            else:
                # Pretvori string u datum
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Dohvati statistike za raspon datuma
            stats = DailyStats.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            # Serializiraj podatke
            serializer = self.get_serializer(stats, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju dnevnih statistika: {str(e)}")
            return Response(
                {"error": "Greška pri dohvaćanju dnevnih statistika"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )