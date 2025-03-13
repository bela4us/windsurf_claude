"""
Pomoćne funkcije za Django aplikaciju "stats".

Ovaj modul sadrži pomoćne funkcije za izračunavanje i manipulaciju
statističkim podacima u Belot aplikaciji, uključujući izračunavanje
složenih statistika, formatiranje podataka i generiranje vizualnih
prikaza statistike.
"""

import logging
import calendar
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional, Union
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.db import connection

User = get_user_model()
logger = logging.getLogger('stats.utils')


def get_date_range_bounds(period: str) -> Tuple[datetime, datetime]:
    """
    Dohvaća početni i završni datum za određeni vremenski period.
    
    Args:
        period: Vremenski period ('daily', 'weekly', 'monthly', 'all_time')
        
    Returns:
        Tuple[datetime, datetime]: Početni i završni datum
    """
    now = timezone.now()
    
    if period == 'daily':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == 'weekly':
        # Početak tjedna (ponedjeljak)
        start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == 'monthly':
        # Početak mjeseca
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    else:  # all_time
        # Početak vremena za aplikaciju (ili neki vrlo stari datum)
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_date = now
    
    return start_date, end_date


def format_duration(seconds: Union[int, float]) -> str:
    """
    Formatira trajanje u sekundama u čitljivi oblik.
    
    Args:
        seconds: Trajanje u sekundama
        
    Returns:
        str: Formatirano trajanje (npr. "2h 15min 30s")
    """
    if seconds is None:
        return "0s"
    
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


def format_timedelta(delta: timedelta) -> str:
    """
    Formatira timedelta objekt u čitljivi oblik.
    
    Args:
        delta: Timedelta objekt
        
    Returns:
        str: Formatirano trajanje
    """
    if delta is None:
        return "0s"
    
    return format_duration(delta.total_seconds())


def format_percentage(value: Union[int, float], decimals: int = 2) -> str:
    """
    Formatira vrijednost kao postotak.
    
    Args:
        value: Vrijednost za formatiranje
        decimals: Broj decimalnih mjesta
        
    Returns:
        str: Formatirani postotak (npr. "42.50%")
    """
    if value is None:
        return "0.00%"
    
    return f"{round(float(value), decimals):.{decimals}f}%"


def format_suit(suit: str) -> str:
    """
    Formatira boju aduta za prikaz.
    
    Args:
        suit: Boja aduta ('hearts', 'diamonds', 'clubs', 'spades')
        
    Returns:
        str: Formatirana boja aduta s Unicode simbolom
    """
    suit_map = {
        'hearts': '♥ Herc',
        'diamonds': '♦ Karo',
        'clubs': '♣ Tref',
        'spades': '♠ Pik'
    }
    
    return suit_map.get(suit, suit)


def calculate_win_percentage(wins: int, total: int) -> float:
    """
    Izračunava postotak pobjeda.
    
    Args:
        wins: Broj pobjeda
        total: Ukupan broj igara
        
    Returns:
        float: Postotak pobjeda
    """
    if total == 0:
        return 0.0
    
    return round((wins / total) * 100, 2)


def calculate_relative_performance(player_value: float, avg_value: float) -> Dict[str, Any]:
    """
    Izračunava relativnu performansu igrača u odnosu na prosjek.
    
    Args:
        player_value: Vrijednost statistike igrača
        avg_value: Prosječna vrijednost statistike
        
    Returns:
        Dict[str, Any]: Rječnik s rezultatima usporedbe
    """
    if avg_value == 0:
        percentage_diff = 0
    else:
        percentage_diff = round(((player_value - avg_value) / avg_value) * 100, 2)
    
    return {
        'value': player_value,
        'avg_value': avg_value,
        'difference': player_value - avg_value,
        'percentage_diff': percentage_diff,
        'is_above_average': player_value > avg_value
    }


def create_time_series_data(stats_queryset, date_field: str, value_field: str,
                          period: str = 'daily', limit: int = 30) -> List[Dict[str, Any]]:
    """
    Stvara podatke vremenske serije iz queryseta.
    
    Args:
        stats_queryset: QuerySet statističkih podataka
        date_field: Naziv polja s datumom
        value_field: Naziv polja s vrijednošću
        period: Period grupiranja ('daily', 'weekly', 'monthly')
        limit: Maksimalni broj točaka podataka
        
    Returns:
        List[Dict[str, Any]]: Lista točaka podataka za vremensku seriju
    """
    # Odaberi odgovarajuću funkciju za grupiranje po datumu
    if period == 'weekly':
        from django.db.models.functions import TruncWeek
        trunc_function = TruncWeek(date_field)
    elif period == 'monthly':
        from django.db.models.functions import TruncMonth
        trunc_function = TruncMonth(date_field)
    else:  # daily
        from django.db.models.functions import TruncDate
        trunc_function = TruncDate(date_field)
    
    # Grupiraj podatke po datumu
    data = stats_queryset.annotate(
        period=trunc_function
    ).values(
        'period'
    ).annotate(
        value=Sum(value_field)
    ).order_by('period')
    
    # Ograniči broj točaka podataka
    data = data.order_by('-period')[:limit]
    
    # Formatiraj rezultate
    results = []
    for point in data:
        results.append({
            'date': point['period'],
            'value': point['value']
        })
    
    return sorted(results, key=lambda x: x['date'])


def calculate_player_game_history(user_id, period: str = 'daily', limit: int = 30) -> List[Dict[str, Any]]:
    """
    Izračunava povijest igara za igrača grupirano po vremenskom periodu.
    
    Args:
        user_id: ID korisnika
        period: Period grupiranja ('daily', 'weekly', 'monthly')
        limit: Maksimalni broj rezultata
        
    Returns:
        List[Dict[str, Any]]: Lista s podacima povijesti igara
    """
    # Odredi SQL dio za grupiranje ovisno o periodu
    if period == 'weekly':
        date_trunc = "week"
    elif period == 'monthly':
        date_trunc = "month"
    else:  # daily
        date_trunc = "day"
    
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
                date_trunc, str(user_id), str(user_id), 
                str(user_id), str(user_id), limit
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


def calculate_common_opponents(user_id, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Izračunava najčešće protivnike za igrača.
    
    Args:
        user_id: ID korisnika
        limit: Maksimalni broj rezultata
        
    Returns:
        List[Dict[str, Any]]: Lista najčešćih protivnika
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH game_opponents AS (
                    SELECT
                        g.id AS game_id,
                        u.id AS opponent_id,
                        u.username AS opponent_username,
                        CASE 
                            WHEN (g.team_a_players @> ARRAY[%s::uuid] AND g.winning_team = 'a') OR
                                (g.team_b_players @> ARRAY[%s::uuid] AND g.winning_team = 'b')
                            THEN 1
                            ELSE 0
                        END AS player_won
                    FROM 
                        game_game g
                        JOIN game_game_players gp ON g.id = gp.game_id
                        JOIN auth_user u ON gp.user_id = u.id
                    WHERE 
                        g.status = 'completed' AND
                        g.players @> ARRAY[%s::uuid] AND
                        u.id != %s AND
                        (
                            (g.team_a_players @> ARRAY[%s::uuid] AND g.team_b_players @> ARRAY[u.id::uuid]) OR
                            (g.team_b_players @> ARRAY[%s::uuid] AND g.team_a_players @> ARRAY[u.id::uuid])
                        )
                )
                SELECT
                    opponent_id,
                    opponent_username,
                    COUNT(*) AS games_played,
                    SUM(player_won) AS player_wins,
                    COUNT(*) - SUM(player_won) AS opponent_wins,
                    CASE 
                        WHEN COUNT(*) > 0 THEN ROUND((SUM(player_won)::float / COUNT(*)) * 100, 2)
                        ELSE 0
                    END AS win_rate
                FROM
                    game_opponents
                GROUP BY
                    opponent_id, opponent_username
                ORDER BY
                    games_played DESC, opponent_username
                LIMIT %s;
            """, [
                str(user_id), str(user_id), str(user_id), 
                str(user_id), str(user_id), str(user_id), limit
            ])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'opponent_id': row[0],
                    'opponent_username': row[1],
                    'games_played': row[2],
                    'player_wins': row[3],
                    'opponent_wins': row[4],
                    'win_rate': row[5]
                })
            
            return results
    
    except Exception as e:
        logger.error(f"Greška pri izračunu najčešćih protivnika: {str(e)}")
        return []


def calculate_best_teammates(user_id, min_games: int = 5, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Izračunava najbolje suigrače za igrača.
    
    Args:
        user_id: ID korisnika
        min_games: Minimalni broj zajedničkih igara
        limit: Maksimalni broj rezultata
        
    Returns:
        List[Dict[str, Any]]: Lista najboljih suigrača
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH game_teammates AS (
                    SELECT
                        g.id AS game_id,
                        u.id AS teammate_id,
                        u.username AS teammate_username,
                        CASE 
                            WHEN g.winning_team IS NOT NULL THEN 1
                            ELSE 0
                        END AS has_winner,
                        CASE 
                            WHEN ((g.team_a_players @> ARRAY[%s::uuid, u.id::uuid]) AND g.winning_team = 'a') OR
                                ((g.team_b_players @> ARRAY[%s::uuid, u.id::uuid]) AND g.winning_team = 'b')
                            THEN 1
                            ELSE 0
                        END AS team_won
                    FROM 
                        game_game g
                        JOIN game_game_players gp ON g.id = gp.game_id
                        JOIN auth_user u ON gp.user_id = u.id
                    WHERE 
                        g.status = 'completed' AND
                        g.players @> ARRAY[%s::uuid] AND
                        u.id != %s AND
                        (
                            (g.team_a_players @> ARRAY[%s::uuid] AND g.team_a_players @> ARRAY[u.id::uuid]) OR
                            (g.team_b_players @> ARRAY[%s::uuid] AND g.team_b_players @> ARRAY[u.id::uuid])
                        )
                )
                SELECT
                    teammate_id,
                    teammate_username,
                    COUNT(*) AS games_played,
                    SUM(team_won) AS games_won,
                    SUM(has_winner) - SUM(team_won) AS games_lost,
                    CASE 
                        WHEN SUM(has_winner) > 0 THEN ROUND((SUM(team_won)::float / SUM(has_winner)) * 100, 2)
                        ELSE 0
                    END AS win_rate
                FROM
                    game_teammates
                GROUP BY
                    teammate_id, teammate_username
                HAVING
                    COUNT(*) >= %s
                ORDER BY
                    win_rate DESC, games_played DESC
                LIMIT %s;
            """, [
                str(user_id), str(user_id), str(user_id), 
                str(user_id), str(user_id), str(user_id),
                min_games, limit
            ])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'teammate_id': row[0],
                    'teammate_username': row[1],
                    'games_played': row[2],
                    'games_won': row[3],
                    'games_lost': row[4],
                    'win_rate': row[5]
                })
            
            return results
    
    except Exception as e:
        logger.error(f"Greška pri izračunu najboljih suigrača: {str(e)}")
        return []


def calculate_most_called_suits(user_id) -> Dict[str, int]:
    """
    Izračunava najčešće zvane adute za igrača.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        Dict[str, int]: Rječnik s brojem zvanja za svaki adut
    """
    from game.models import Round
    
    try:
        # Dohvati runde gdje je korisnik zvao adut
        suits_count = Round.objects.filter(
            caller_id=user_id,
            status='completed'
        ).values('trump_suit').annotate(
            count=Count('trump_suit')
        ).order_by('-count')
        
        # Formatiraj rezultate
        results = {
            'hearts': 0,
            'diamonds': 0,
            'clubs': 0,
            'spades': 0
        }
        
        for item in suits_count:
            suit = item['trump_suit']
            count = item['count']
            
            if suit in results:
                results[suit] = count
        
        return results
    
    except Exception as e:
        logger.error(f"Greška pri izračunu najčešćih aduta: {str(e)}")
        return {
            'hearts': 0,
            'diamonds': 0,
            'clubs': 0,
            'spades': 0
        }


def calculate_declaration_stats(user_id) -> Dict[str, int]:
    """
    Izračunava statistiku zvanja za igrača.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        Dict[str, int]: Rječnik s brojem zvanja po tipu
    """
    from game.models import Declaration
    
    try:
        # Dohvati zvanja korisnika
        declarations = Declaration.objects.filter(
            player_id=user_id
        ).values('declaration_type').annotate(
            count=Count('declaration_type')
        ).order_by('-count')
        
        # Grupiraj rezultate
        results = {
            'belot': 0,
            'four_of_a_kind': 0,
            'straight': 0
        }
        
        four_of_a_kind_types = ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']
        straight_types = ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']
        
        for item in declarations:
            decl_type = item['declaration_type']
            count = item['count']
            
            if decl_type == 'belot':
                results['belot'] += count
            elif decl_type in four_of_a_kind_types:
                results['four_of_a_kind'] += count
            elif decl_type in straight_types:
                results['straight'] += count
        
        return results
    
    except Exception as e:
        logger.error(f"Greška pri izračunu statistike zvanja: {str(e)}")
        return {
            'belot': 0,
            'four_of_a_kind': 0,
            'straight': 0
        }


def get_monthly_activity_heatmap(user_id, year: Optional[int] = None) -> Dict[str, Dict[str, int]]:
    """
    Generira podatke za toplinski prikaz aktivnosti po mjesecima.
    
    Args:
        user_id: ID korisnika
        year: Godina za prikaz (ako nije navedena, koristi se trenutna godina)
        
    Returns:
        Dict[str, Dict[str, int]]: Rječnik s podacima za toplinski prikaz
    """
    if year is None:
        year = timezone.now().year
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    EXTRACT(MONTH FROM gs.end_time) AS month,
                    EXTRACT(DAY FROM gs.end_time) AS day,
                    COUNT(*) AS game_count
                FROM
                    game_game g
                    JOIN game_gamestats gs ON g.id = gs.game_id
                WHERE
                    g.status = 'completed' AND
                    g.players @> ARRAY[%s::uuid] AND
                    EXTRACT(YEAR FROM gs.end_time) = %s
                GROUP BY
                    month, day
                ORDER BY
                    month, day;
            """, [str(user_id), year])
            
            # Inicijaliziraj rezultate s nulama za sve dane
            results = {}
            for month in range(1, 13):
                month_data = {}
                month_name = calendar.month_name[month]
                
                # Broj dana u mjesecu (prilagođeno za prijestupne godine)
                days_in_month = calendar.monthrange(year, month)[1]
                
                for day in range(1, days_in_month + 1):
                    month_data[str(day)] = 0
                
                results[month_name] = month_data
            
            # Popuni podatke iz upita
            for row in cursor.fetchall():
                month = int(row[0])
                day = int(row[1])
                game_count = row[2]
                
                month_name = calendar.month_name[month]
                results[month_name][str(day)] = game_count
            
            return results
    
    except Exception as e:
        logger.error(f"Greška pri generiranju toplinskog prikaza aktivnosti: {str(e)}")
        return {}


def calculate_win_streak_distribution(user_id) -> Dict[int, int]:
    """
    Izračunava distribuciju duljina nizova pobjeda za igrača.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        Dict[int, int]: Rječnik s brojem nizova za svaku duljinu
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH game_results AS (
                    SELECT
                        g.id,
                        g.created_at,
                        CASE 
                            WHEN (g.team_a_players @> ARRAY[%s::uuid] AND g.winning_team = 'a') OR
                                (g.team_b_players @> ARRAY[%s::uuid] AND g.winning_team = 'b')
                            THEN 1
                            ELSE 0
                        END AS won
                    FROM 
                        game_game g
                    WHERE 
                        g.status = 'completed' AND
                        g.players @> ARRAY[%s::uuid]
                    ORDER BY
                        g.created_at
                ),
                streaks AS (
                    SELECT
                        SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) AS streak_length,
                        COUNT(*) AS games_in_group
                    FROM (
                        SELECT
                            won,
                            SUM(CASE WHEN won != LAG(won, 1, -1) OVER (ORDER BY created_at) THEN 1 ELSE 0 END) 
                                OVER (ORDER BY created_at) AS group_id
                        FROM
                            game_results
                    ) AS grouped
                    WHERE won = 1
                    GROUP BY group_id
                )
                SELECT
                    streak_length,
                    COUNT(*) AS streak_count
                FROM
                    streaks
                GROUP BY
                    streak_length
                ORDER BY
                    streak_length;
            """, [str(user_id), str(user_id), str(user_id)])
            
            results = {}
            for row in cursor.fetchall():
                streak_length = int(row[0])
                streak_count = int(row[1])
                results[streak_length] = streak_count
            
            return results
    
    except Exception as e:
        logger.error(f"Greška pri izračunu distribucije nizova pobjeda: {str(e)}")
        return {}


def get_player_rank_data(user_id) -> Dict[str, Dict[str, Any]]:
    """
    Dohvaća podatke o pozicijama igrača na ljestvicama.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        Dict[str, Dict[str, Any]]: Rječnik s podacima o pozicijama na ljestvicama
    """
    from .models import Leaderboard
    
    try:
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
                'value': None,
                'total_players': len(leaderboard.players)
            }
            
            # Provjeri je li korisnik na ljestvici
            for player in leaderboard.players:
                if str(player.get('id')) == str(user_id):
                    user_positions[key]['position'] = player.get('rank')
                    user_positions[key]['value'] = player.get('value')
                    break
        
        return user_positions
    
    except Exception as e:
        logger.error(f"Greška pri dohvaćanju podataka o pozicijama na ljestvicama: {str(e)}")
        return {}