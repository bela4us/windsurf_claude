"""
Celery zadaci za Django aplikaciju "stats".

Ovaj modul definira asinkrone zadatke za ažuriranje i održavanje
statističkih podataka Belot igre. Ovi zadaci se izvršavaju 
periodički ili na zahtjev za osiguravanje točnosti podataka.
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models import Q
from .models import (
    PlayerStats, TeamStats, GameStats, GlobalStats,
    DailyStats, StatisticsSnapshot, Leaderboard
)
from game.models import Game, Round, Declaration, Move

User = get_user_model()
logger = logging.getLogger('stats.tasks')


@shared_task(name='stats.tasks.update_global_statistics')
def update_global_statistics():
    """
    Zadatak za ažuriranje globalnih statistika.
    
    Osvježava agregirane podatke o igrama, igračima i
    drugim metrikama za cijelu platformu.
    """
    logger.info("Pokretanje zadatka za ažuriranje globalnih statistika")
    
    try:
        # Svi SQL upiti i ažuriranja se izvršavaju u jednoj transakciji
        with transaction.atomic():
            # Dohvati ili stvori globalnu statistiku
            global_stats = GlobalStats.get_instance()
            
            # Dohvati osnovne metrike iz baze
            total_games = Game.objects.count()
            total_players = User.objects.count()
            games_in_progress = Game.objects.filter(status='in_progress').count()
            total_rounds = Round.objects.count()
            
            # Ažuriraj osnovne brojeve
            global_stats.total_games = total_games
            global_stats.total_players = total_players
            global_stats.games_in_progress = games_in_progress
            global_stats.total_rounds = total_rounds
            
            # Dohvati statistiku aduta jednim upitom
            suit_counts = Round.objects.values('trump_suit').annotate(count=Count('id'))
            
            # Resetiraj brojače aduta
            global_stats.hearts_called = 0
            global_stats.diamonds_called = 0
            global_stats.clubs_called = 0
            global_stats.spades_called = 0
            
            # Ažuriraj brojače aduta
            for item in suit_counts:
                if item['trump_suit'] == 'hearts':
                    global_stats.hearts_called = item['count']
                elif item['trump_suit'] == 'diamonds':
                    global_stats.diamonds_called = item['count']
                elif item['trump_suit'] == 'clubs':
                    global_stats.clubs_called = item['count']
                elif item['trump_suit'] == 'spades':
                    global_stats.spades_called = item['count']
            
            # Ažuriraj statistiku zvanja jednim upitom
            declaration_counts = Declaration.objects.values('declaration_type').annotate(count=Count('id'))
            
            # Resetiraj brojače zvanja
            global_stats.belot_declarations = 0
            global_stats.four_of_a_kind_declarations = 0
            global_stats.straight_declarations = 0
            
            # Ažuriraj brojače zvanja
            for item in declaration_counts:
                decl_type = item['declaration_type']
                count = item['count']
                
                if decl_type == 'belot':
                    global_stats.belot_declarations = count
                elif decl_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                    global_stats.four_of_a_kind_declarations += count
                elif decl_type in ['straight_three', 'straight_four', 'straight_five', 
                                  'straight_six', 'straight_seven', 'straight_eight']:
                    global_stats.straight_declarations += count
            
            # Dohvati prosječno trajanje igre
            avg_duration = GameStats.objects.filter(
                game__status='completed'
            ).aggregate(avg_duration=Avg('duration'))['avg_duration']
            
            if avg_duration:
                global_stats.avg_game_duration = avg_duration
            
            # Dohvati ukupno vrijeme igranja
            total_play_time = GameStats.objects.filter(
                game__status='completed'
            ).aggregate(total=Sum('duration'))['total']
            
            if total_play_time:
                global_stats.total_play_time = total_play_time
            
            # Spremi ažuriranu globalnu statistiku
            global_stats.save()
            
            logger.info(f"Globalne statistike su uspješno ažurirane. Ukupno igara: {global_stats.total_games}")
            
            # Stvori novu snimku stanja
            snapshot = StatisticsSnapshot.create_snapshot()
            logger.info(f"Stvorena nova snimka statistike (ID: {snapshot.id})")
            
            return {
                'status': 'success',
                'updated_at': timezone.now().isoformat(),
                'total_games': global_stats.total_games,
                'total_players': global_stats.total_players,
                'games_in_progress': global_stats.games_in_progress
            }
            
    except Exception as e:
        logger.error(f"Greška pri ažuriranju globalnih statistika: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='stats.tasks.update_daily_statistics')
def update_daily_statistics():
    """
    Zadatak za ažuriranje dnevnih statistika.
    
    Stvara ili ažurira statistiku za današnji dan
    s agregiranim podacima o aktivnosti.
    """
    logger.info("Pokretanje zadatka za ažuriranje dnevnih statistika")
    
    try:
        # Jedna transakcija za sve operacije
        with transaction.atomic():
            # Dohvati ili stvori dnevnu statistiku za danas
            today_stats = DailyStats.get_or_create_for_today()
            today = timezone.now().date()
            
            # Dohvati sve potrebne podatke u što manje upita
            # Igre stvorene danas
            games_today_count = Game.objects.filter(
                created_at__date=today
            ).count()
            
            # Aktivni igrači danas
            active_players_count = User.objects.filter(
                last_login__date=today
            ).count()
            
            # Novi korisnici danas
            new_users_count = User.objects.filter(
                date_joined__date=today
            ).count()
            
            # Runde stvorene danas
            rounds_today = Round.objects.filter(
                created_at__date=today
            )
            rounds_count = rounds_today.count()
            
            # Aduti u rundama danas - jednim upitom
            suit_counts = rounds_today.values('trump_suit').annotate(count=Count('trump_suit'))
            hearts_count = 0
            diamonds_count = 0
            clubs_count = 0
            spades_count = 0
            
            for item in suit_counts:
                if item['trump_suit'] == 'hearts':
                    hearts_count = item['count']
                elif item['trump_suit'] == 'diamonds':
                    diamonds_count = item['count']
                elif item['trump_suit'] == 'clubs':
                    clubs_count = item['count']
                elif item['trump_suit'] == 'spades':
                    spades_count = item['count']
            
            # Zvanja stvorena danas - jednim upitom
            declarations_today = Declaration.objects.filter(
                created_at__date=today
            )
            
            decl_counts = declarations_today.values('declaration_type').annotate(count=Count('declaration_type'))
            belot_count = 0
            four_count = 0
            straight_count = 0
            
            for item in decl_counts:
                decl_type = item['declaration_type']
                count = item['count']
                
                if decl_type == 'belot':
                    belot_count = count
                elif decl_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                    four_count += count
                elif decl_type in ['straight_three', 'straight_four', 'straight_five', 
                                  'straight_six', 'straight_seven', 'straight_eight']:
                    straight_count += count
            
            # Prosječno trajanje igre za danas
            completed_games_today = GameStats.objects.filter(
                game__status='completed',
                end_time__date=today
            )
            
            avg_duration = None
            total_play_time = None
            
            if completed_games_today.exists():
                agg_result = completed_games_today.aggregate(
                    avg_duration=Avg('duration'),
                    total=Sum('duration')
                )
                avg_duration = agg_result['avg_duration']
                total_play_time = agg_result['total']
            
            # Ažuriraj statistiku s jednim spremanjem
            today_stats.total_games = games_today_count
            today_stats.active_players = active_players_count
            today_stats.new_users = new_users_count
            today_stats.total_rounds = rounds_count
            
            today_stats.hearts_called = hearts_count
            today_stats.diamonds_called = diamonds_count
            today_stats.clubs_called = clubs_count
            today_stats.spades_called = spades_count
            
            today_stats.belot_declarations = belot_count
            today_stats.four_of_a_kind_declarations = four_count
            today_stats.straight_declarations = straight_count
            
            if avg_duration:
                today_stats.avg_game_duration = avg_duration
            
            if total_play_time:
                today_stats.total_play_time = total_play_time
            
            today_stats.save()
            
            logger.info(f"Dnevne statistike su uspješno ažurirane za {today}. Ukupno igara: {today_stats.total_games}")
            
            return {
                'status': 'success',
                'date': today.isoformat(),
                'updated_at': timezone.now().isoformat(),
                'total_games': today_stats.total_games,
                'active_players': today_stats.active_players,
                'new_users': today_stats.new_users
            }
            
    except Exception as e:
        logger.error(f"Greška pri ažuriranju dnevnih statistika: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='stats.tasks.update_leaderboards')
def update_leaderboards():
    """
    Zadatak za ažuriranje ljestvica najboljih igrača.
    
    Stvara ili ažurira ljestvice za različite kategorije
    i vremenske periode.
    """
    logger.info("Pokretanje zadatka za ažuriranje ljestvica")
    
    try:
        # Lista kategorija i perioda za ažuriranje
        categories = ['wins', 'win_percentage', 'points', 'games_played', 'belot_declarations', 'four_of_a_kind']
        periods = ['daily', 'weekly', 'monthly', 'all_time']
        
        updated_leaderboards = []
        
        # Ažuriraj sve kombinacije kategorija i perioda
        for category in categories:
            for period in periods:
                try:
                    # Svaka ljestvica se ažurira u svojoj transakciji
                    # kako bi greška u jednoj ne bi utjecala na ostale
                    with transaction.atomic():
                        leaderboard = Leaderboard.update_leaderboard(period, category)
                        updated_leaderboards.append({
                            'id': str(leaderboard.id),
                            'period': period,
                            'category': category,
                            'player_count': leaderboard.player_count
                        })
                        
                        logger.info(f"Ažurirana ljestvica: {period} - {category}")
                
                except Exception as e:
                    logger.error(f"Greška pri ažuriranju ljestvice {period} - {category}: {str(e)}")
        
        logger.info(f"Ažuriranje ljestvica je završeno. Ažurirano: {len(updated_leaderboards)} ljestvica")
        
        return {
            'status': 'success',
            'updated_at': timezone.now().isoformat(),
            'updated_leaderboards': updated_leaderboards
        }
            
    except Exception as e:
        logger.error(f"Greška pri ažuriranju ljestvica: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='stats.tasks.recalculate_player_stats')
def recalculate_player_stats(user_id):
    """
    Zadatak za ponovno izračunavanje statistike igrača.
    
    Ažurira sve statistike za određenog igrača na temelju
    podataka iz igara u kojima je sudjelovao.
    
    Args:
        user_id: ID korisnika čija se statistika ažurira
    """
    logger.info(f"Pokretanje zadatka za ponovno izračunavanje statistike igrača (ID: {user_id})")
    
    try:
        with transaction.atomic():
            # Dohvati korisnika
            user = User.objects.get(id=user_id)
            
            # Dohvati ili stvori statistiku igrača
            player_stats, created = PlayerStats.objects.get_or_create(user=user)
            
            # Resetiraj brojače
            player_stats.games_played = 0
            player_stats.games_won = 0
            player_stats.games_lost = 0
            player_stats.total_score = 0
            player_stats.rounds_played = 0
            player_stats.hearts_called = 0
            player_stats.diamonds_called = 0
            player_stats.clubs_called = 0
            player_stats.spades_called = 0
            player_stats.belot_declarations = 0
            player_stats.four_of_a_kind_declarations = 0
            player_stats.straight_declarations = 0
            player_stats.rounds_as_caller = 0
            player_stats.rounds_won_as_caller = 0
            player_stats.rounds_lost_as_caller = 0
            player_stats.highest_game_score = 0
            player_stats.longest_winning_streak = 0
            player_stats.current_winning_streak = 0
            
            # Dohvati završene igre korisnika
            games = Game.objects.filter(
                players=user,
                status='completed'
            ).order_by('created_at')
            
            if not games.exists():
                logger.info(f"Korisnik {user.username} nema završenih igara")
                player_stats.save()
                return {
                    'status': 'success',
                    'message': 'Korisnik nema završenih igara',
                    'user_id': user_id
                }
            
            # Broj igara, datumi prve i zadnje igre
            player_stats.games_played = games.count()
            player_stats.first_game_date = games.first().created_at
            player_stats.last_game_date = games.last().updated_at
            
            # Optimizirajmo upite prema baznim konceptima u igri Belot:
            
            # 1. Računanje pobjeda i poraza zajedno s nizovima
            won_games = []
            current_streak = 0
            max_streak = 0
            
            # Dohvati sve igre s timovima i pobjednikom u jednom upitu
            game_data = games.values(
                'id', 'winning_team', 'team_a_players', 'team_b_players', 
                'team_a_score', 'team_b_score'
            )
            
            for game in game_data:
                # Izračunaj je li korisnik član tima A
                in_team_a = user.id in game['team_a_players']
                
                # Izračunaj je li korisnik pobijedio
                user_won = (in_team_a and game['winning_team'] == 'a') or (not in_team_a and game['winning_team'] == 'b')
                
                # Ažuriraj ukupne bodove
                score = game['team_a_score'] if in_team_a else game['team_b_score']
                player_stats.total_score += score
                
                # Ažuriraj najviši rezultat igre
                if score > player_stats.highest_game_score:
                    player_stats.highest_game_score = score
                
                # Ažuriraj pobjede, poraze i nizove
                if user_won:
                    player_stats.games_won += 1
                    won_games.append(game['id'])
                    current_streak += 1
                    if current_streak > max_streak:
                        max_streak = current_streak
                else:
                    player_stats.games_lost += 1
                    current_streak = 0
            
            player_stats.longest_winning_streak = max_streak
            player_stats.current_winning_streak = current_streak
            
            # 2. Statistika rundi - dohvati sve runde za igre korisnika
            rounds = Round.objects.filter(
                game__in=games,
                status='completed'
            )
            
            player_stats.rounds_played = rounds.count()
            
            # 3. Statistika aduta i zvača - dohvati samo runde gdje je korisnik zvač
            caller_rounds = rounds.filter(caller=user)
            player_stats.rounds_as_caller = caller_rounds.count()
            
            # Agregiraj statistiku aduta jednim upitom
            suit_counts = caller_rounds.values('trump_suit').annotate(count=Count('trump_suit'))
            
            for item in suit_counts:
                if item['trump_suit'] == 'hearts':
                    player_stats.hearts_called = item['count']
                elif item['trump_suit'] == 'diamonds':
                    player_stats.diamonds_called = item['count']
                elif item['trump_suit'] == 'clubs':
                    player_stats.clubs_called = item['count']
                elif item['trump_suit'] == 'spades':
                    player_stats.spades_called = item['count']
            
            # 4. Statistika zvanja - dohvati sva zvanja korisnika
            declarations = Declaration.objects.filter(
                player=user,
                round__game__status='completed',
                round__status='completed'
            ).values('declaration_type').annotate(count=Count('declaration_type'))
            
            for decl in declarations:
                decl_type = decl['declaration_type']
                count = decl['count']
                
                if decl_type == 'belot':
                    player_stats.belot_declarations = count
                elif decl_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                    player_stats.four_of_a_kind_declarations += count
                elif decl_type in ['straight_three', 'straight_four', 'straight_five', 
                                  'straight_six', 'straight_seven', 'straight_eight']:
                    player_stats.straight_declarations += count
            
            # 5. Pobjede i porazi kao zvač
            # Ovo zahtijeva malo složeniji upit jer moramo provjeriti tim korisnika
            for round_obj in caller_rounds:
                game = round_obj.game
                
                # Odredi tim korisnika
                in_team_a = user.id in game.team_a_players
                
                # Odredi pobjednika runde
                round_winner = 'a' if round_obj.team_a_score > round_obj.team_b_score else 'b'
                
                if (round_winner == 'a' and in_team_a) or (round_winner == 'b' and not in_team_a):
                    player_stats.rounds_won_as_caller += 1
                else:
                    player_stats.rounds_lost_as_caller += 1
            
            # 6. Ukupno vrijeme igranja
            game_stats = GameStats.objects.filter(
                game__in=games
            ).aggregate(total_time=Sum('duration'))
            
            if game_stats['total_time']:
                player_stats.total_play_time = game_stats['total_time']
            
            # Ažuriraj prosječne bodove
            player_stats.update_avg_points()
            
            # Spremi ažuriranu statistiku
            player_stats.save()
            
            logger.info(f"Statistika je uspješno ažurirana za korisnika {user.username}")
            
            return {
                'status': 'success',
                'user_id': user_id,
                'games_played': player_stats.games_played,
                'games_won': player_stats.games_won,
                'win_percentage': player_stats.win_percentage
            }
            
    except User.DoesNotExist:
        logger.error(f"Korisnik s ID-om {user_id} nije pronađen")
        return {
            'status': 'error',
            'error': f"Korisnik s ID-om {user_id} nije pronađen",
            'user_id': user_id
        }
    
    except Exception as e:
        logger.error(f"Greška pri ponovnom izračunavanju statistike igrača: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'user_id': user_id
        }


@shared_task(name='stats.tasks.recalculate_team_stats')
def recalculate_team_stats(team_id=None):
    """
    Zadatak za ponovno izračunavanje statistike timova.
    
    Ažurira statistike za određeni tim ili sve timove
    na temelju podataka iz igara.
    
    Args:
        team_id: ID tima čija se statistika ažurira (ako je None, ažuriraju se svi timovi)
    """
    logger.info(f"Pokretanje zadatka za ponovno izračunavanje statistike timova (ID: {team_id or 'svi'})")
    
    try:
        # Dohvati tim ili sve timove
        if team_id:
            teams = [TeamStats.objects.get(id=team_id)]
        else:
            teams = TeamStats.objects.all()
        
        updated_teams = []
        
        for team in teams:
            try:
                with transaction.atomic():
                    # Resetiraj brojače
                    team.games_played = 0
                    team.games_won = 0
                    team.games_lost = 0
                    team.total_score = 0
                    team.hearts_called = 0
                    team.diamonds_called = 0
                    team.clubs_called = 0
                    team.spades_called = 0
                    team.highest_game_score = 0
                    team.longest_winning_streak = 0
                    team.current_winning_streak = 0
                    
                    # Dohvati završene igre tima (oba igrača moraju biti u njima)
                    games = Game.objects.filter(
                        Q(players=team.player1) & Q(players=team.player2),
                        status='completed'
                    ).order_by('created_at')
                    
                    if not games.exists():
                        logger.info(f"Tim {team.id} nema završenih igara")
                        team.save()
                        continue
                    
                    # Izračunaj statistiku na temelju igara - slično kao kod igrača, ali moramo provjeriti da su oba igrača u istom timu
                    player1_id = team.player1.id
                    player2_id = team.player2.id
                    
                    # Broj igara, datumi prve i zadnje igre
                    team.games_played = games.count()
                    team.first_game_date = games.first().created_at
                    team.last_game_date = games.last().updated_at
                    
                    # Pobjede, porazi i nizovi
                    current_streak = 0
                    max_streak = 0
                    
                    # Dohvati sve igre s timovima i pobjednikom u jednom upitu
                    game_data = games.values(
                        'id', 'winning_team', 'team_a_players', 'team_b_players', 
                        'team_a_score', 'team_b_score'
                    )
                    
                    for game in game_data:
                        # Provjeri jesu li oba igrača u istom timu
                        both_in_team_a = player1_id in game['team_a_players'] and player2_id in game['team_a_players']
                        both_in_team_b = player1_id in game['team_b_players'] and player2_id in game['team_b_players']
                        
                        # Ako nisu u istom timu, preskoči ovu igru
                        if not (both_in_team_a or both_in_team_b):
                            continue
                        
                        # Izračunaj je li tim pobijedio
                        team_won = (both_in_team_a and game['winning_team'] == 'a') or (both_in_team_b and game['winning_team'] == 'b')
                        
                        # Ažuriraj ukupne bodove
                        score = game['team_a_score'] if both_in_team_a else game['team_b_score']
                        team.total_score += score
                        
                        # Ažuriraj najviši rezultat igre
                        if score > team.highest_game_score:
                            team.highest_game_score = score
                        
                        # Ažuriraj pobjede, poraze i nizove
                        if team_won:
                            team.games_won += 1
                            current_streak += 1
                            if current_streak > max_streak:
                                max_streak = current_streak
                        else:
                            team.games_lost += 1
                            current_streak = 0
                    
                    team.longest_winning_streak = max_streak
                    team.current_winning_streak = current_streak
                    
                    # Aduti - runde gdje je netko iz tima zvao adut
                    rounds = Round.objects.filter(
                        game__in=games,
                        status='completed',
                        caller__in=[team.player1, team.player2]
                    )
                    
                    # Agregiraj statistiku aduta jednim upitom
                    suit_counts = rounds.values('trump_suit').annotate(count=Count('trump_suit'))
                    
                    for item in suit_counts:
                        if item['trump_suit'] == 'hearts':
                            team.hearts_called = item['count']
                        elif item['trump_suit'] == 'diamonds':
                            team.diamonds_called = item['count']
                        elif item['trump_suit'] == 'clubs':
                            team.clubs_called = item['count']
                        elif item['trump_suit'] == 'spades':
                            team.spades_called = item['count']
                    
                    # Ažuriraj prosječne bodove
                    if team.games_played > 0:
                        team.avg_points_per_game = round(team.total_score / team.games_played, 2)
                    
                    # Spremi ažuriranu statistiku
                    team.save()
                    
                    updated_teams.append(str(team.id))
                    logger.info(f"Statistika je uspješno ažurirana za tim {team.id}")
                    
            except Exception as e:
                logger.error(f"Greška pri ažuriranju statistike tima {team.id}: {str(e)}")
        
        logger.info(f"Ažuriranje statistike timova je završeno. Ažurirano: {len(updated_teams)} timova")
        
        return {
            'status': 'success',
            'updated_teams': updated_teams,
            'count': len(updated_teams)
        }
            
    except TeamStats.DoesNotExist:
        logger.error(f"Tim s ID-om {team_id} nije pronađen")
        return {
            'status': 'error',
            'error': f"Tim s ID-om {team_id} nije pronađen",
            'team_id': team_id
        }
    
    except Exception as e:
        logger.error(f"Greška pri ponovnom izračunavanju statistike timova: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'team_id': team_id
        }


@shared_task(name='stats.tasks.cleanup_old_statistics')
def cleanup_old_statistics(days=30):
    """
    Zadatak za čišćenje starih statističkih podataka.
    
    Briše stare snimke statistike i druge privremene podatke
    kako bi se održavala optimalna performansa baze.
    
    Args:
        days: Broj dana nakon kojih se podaci smatraju starima
    """
    logger.info(f"Pokretanje zadatka za čišćenje starih statističkih podataka (stariji od {days} dana)")
    
    try:
        with transaction.atomic():
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Obriši stare snimke statistike
            old_snapshots = StatisticsSnapshot.objects.filter(
                timestamp__lt=cutoff_date
            )
            
            snapshot_count = old_snapshots.count()
            old_snapshots.delete()
            
            logger.info(f"Obrisano {snapshot_count} starih snimki statistike")
            
            return {
                'status': 'success',
                'deleted_snapshots': snapshot_count,
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Greška pri čišćenju starih statističkih podataka: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'days': days
        }