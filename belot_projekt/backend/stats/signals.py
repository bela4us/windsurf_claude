"""
Signali za Django aplikaciju "stats".

Ovaj modul definira signale koji se koriste za ažuriranje
statistike pri određenim događajima, poput završetka igre,
promjene statusa igre, završetka runde, itd.
"""

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from game.models import Game, Round, Declaration, Move
from .models import (
    PlayerStats, TeamStats, GameStats, GlobalStats,
    DailyStats, Leaderboard
)

User = get_user_model()
logger = logging.getLogger('stats.signals')


@receiver(post_save, sender=User)
def create_user_stats(sender, instance, created, **kwargs):
    """
    Signal koji stvara statistiku za novog korisnika.
    
    Args:
        sender: Model koji je poslao signal
        instance: Instanca modela koja se sprema
        created: Je li instanca upravo stvorena
        **kwargs: Dodatni argumenti
    """
    if created:
        # Stvori statistiku za novog korisnika
        PlayerStats.objects.create(user=instance)
        
        # Ažuriraj globalnu statistiku
        try:
            with transaction.atomic():
                global_stats = GlobalStats.get_instance()
                global_stats.total_players += 1
                global_stats.save()
        except Exception as e:
            logger.error(f"Greška pri ažuriranju globalne statistike za novog korisnika: {e}")
        
        # Ažuriraj dnevnu statistiku
        try:
            with transaction.atomic():
                daily_stats = DailyStats.get_or_create_for_today()
                daily_stats.new_users += 1
                daily_stats.save()
        except Exception as e:
            logger.error(f"Greška pri ažuriranju dnevne statistike za novog korisnika: {e}")


@receiver(post_save, sender=Game)
def handle_game_events(sender, instance, created, **kwargs):
    """
    Signal koji prati promjene statusa igre i ažurira statistiku.
    
    Args:
        sender: Model koji je poslao signal
        instance: Instanca modela koja se sprema
        created: Je li instanca upravo stvorena
        **kwargs: Dodatni argumenti
    """
    # Ako je igra nova, stvori GameStats
    if created:
        try:
            with transaction.atomic():
                game_stats = GameStats.objects.create(
                    game=instance,
                    start_time=instance.created_at
                )
                
                # Ažuriraj globalnu statistiku
                global_stats = GlobalStats.get_instance()
                global_stats.total_games += 1
                global_stats.games_in_progress += 1
                global_stats.save()
                
                # Ažuriraj dnevnu statistiku
                daily_stats = DailyStats.get_or_create_for_today()
                daily_stats.total_games += 1
                daily_stats.save()
        except Exception as e:
            logger.error(f"Greška pri stvaranju statistike za novu igru: {e}")
    
    # Ako je igra završena, ažuriraj statistiku
    elif instance.status == 'completed' and instance.tracker.has_changed('status'):
        try:
            # Ažuriraj GameStats
            with transaction.atomic():
                game_stats, created = GameStats.objects.get_or_create(game=instance)
                game_stats.end_time = timezone.now()
                
                if game_stats.start_time:
                    game_stats.duration = game_stats.end_time - game_stats.start_time
                
                game_stats.team_a_score = instance.team_a_score
                game_stats.team_b_score = instance.team_b_score
                
                # Dohvati podatke iz rundi
                rounds = Round.objects.filter(game=instance)
                game_stats.total_rounds = rounds.count()
                
                # Analiziraj adute i zvanja
                hearts_called = 0
                diamonds_called = 0
                clubs_called = 0
                spades_called = 0
                belot_declarations = 0
                four_of_a_kind_declarations = 0
                straight_declarations = 0
                
                for round_obj in rounds:
                    # Aduti
                    if round_obj.trump_suit == 'hearts':
                        hearts_called += 1
                    elif round_obj.trump_suit == 'diamonds':
                        diamonds_called += 1
                    elif round_obj.trump_suit == 'clubs':
                        clubs_called += 1
                    elif round_obj.trump_suit == 'spades':
                        spades_called += 1
                    
                    # Zvanja
                    declarations = Declaration.objects.filter(round=round_obj)
                    for declaration in declarations:
                        if declaration.declaration_type == 'belot':
                            belot_declarations += 1
                        elif declaration.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                            four_of_a_kind_declarations += 1
                        elif declaration.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                            straight_declarations += 1
                
                game_stats.hearts_called = hearts_called
                game_stats.diamonds_called = diamonds_called
                game_stats.clubs_called = clubs_called
                game_stats.spades_called = spades_called
                game_stats.belot_declarations = belot_declarations
                game_stats.four_of_a_kind_declarations = four_of_a_kind_declarations
                game_stats.straight_declarations = straight_declarations
                
                # Pronađi rundu s najviše bodova
                highest_score = 0
                highest_round = None
                
                for round_obj in rounds:
                    score = round_obj.team_a_score + round_obj.team_b_score
                    if score > highest_score:
                        highest_score = score
                        highest_round = round_obj
                
                if highest_round:
                    game_stats.highest_scoring_round = highest_round.round_number
                    game_stats.highest_round_score = highest_score
                
                game_stats.save()
                
                # Ažuriraj globalnu statistiku
                global_stats = GlobalStats.get_instance()
                global_stats.games_in_progress -= 1
                global_stats.total_rounds += game_stats.total_rounds
                global_stats.hearts_called += game_stats.hearts_called
                global_stats.diamonds_called += game_stats.diamonds_called
                global_stats.clubs_called += game_stats.clubs_called
                global_stats.spades_called += game_stats.spades_called
                global_stats.belot_declarations += game_stats.belot_declarations
                global_stats.four_of_a_kind_declarations += game_stats.four_of_a_kind_declarations
                global_stats.straight_declarations += game_stats.straight_declarations
                
                # Ažuriraj prosječno trajanje igre
                if game_stats.duration:
                    if global_stats.total_games > 1:
                        # Težinski prosjek s novom igrom
                        avg_duration_seconds = global_stats.avg_game_duration.total_seconds()
                        new_duration_seconds = game_stats.duration.total_seconds()
                        
                        avg_duration_seconds = (
                            (avg_duration_seconds * (global_stats.total_games - 1)) + new_duration_seconds
                        ) / global_stats.total_games
                        
                        global_stats.avg_game_duration = timezone.timedelta(seconds=avg_duration_seconds)
                    else:
                        # Prva igra, postavi prosjek na trajanje igre
                        global_stats.avg_game_duration = game_stats.duration
                    
                    # Ažuriraj ukupno vrijeme igranja
                    global_stats.total_play_time += game_stats.duration
                
                global_stats.save()
                
                # Ažuriraj dnevnu statistiku
                daily_stats = DailyStats.get_or_create_for_today()
                daily_stats.total_rounds += game_stats.total_rounds
                daily_stats.hearts_called += game_stats.hearts_called
                daily_stats.diamonds_called += game_stats.diamonds_called
                daily_stats.clubs_called += game_stats.clubs_called
                daily_stats.spades_called += game_stats.spades_called
                daily_stats.belot_declarations += game_stats.belot_declarations
                daily_stats.four_of_a_kind_declarations += game_stats.four_of_a_kind_declarations
                daily_stats.straight_declarations += game_stats.straight_declarations
                
                # Ažuriraj prosječno trajanje igre za taj dan
                if game_stats.duration:
                    if daily_stats.total_games > 1:
                        # Težinski prosjek s novom igrom
                        avg_duration_seconds = daily_stats.avg_game_duration.total_seconds()
                        new_duration_seconds = game_stats.duration.total_seconds()
                        
                        avg_duration_seconds = (
                            (avg_duration_seconds * (daily_stats.total_games - 1)) + new_duration_seconds
                        ) / daily_stats.total_games
                        
                        daily_stats.avg_game_duration = timezone.timedelta(seconds=avg_duration_seconds)
                    else:
                        # Prva igra u danu, postavi prosjek na trajanje igre
                        daily_stats.avg_game_duration = game_stats.duration
                    
                    # Ažuriraj ukupno vrijeme igranja za taj dan
                    daily_stats.total_play_time += game_stats.duration
                
                daily_stats.save()
                
                # Ažuriraj statistiku igrača i timova
                update_player_and_team_stats(instance)
        
        except Exception as e:
            logger.error(f"Greška pri ažuriranju statistike za završenu igru: {e}")
    
    # Ako je status igre promijenjen u 'in_progress', ažuriraj globalnu statistiku
    elif instance.status == 'in_progress' and instance.tracker.has_changed('status'):
        try:
            with transaction.atomic():
                global_stats = GlobalStats.get_instance()
                global_stats.games_in_progress += 1
                global_stats.save()
        except Exception as e:
            logger.error(f"Greška pri ažuriranju globalne statistike za igru u tijeku: {e}")
    
    # Ako je status igre promijenjen u 'aborted', ažuriraj globalnu statistiku
    elif instance.status == 'aborted' and instance.tracker.has_changed('status'):
        try:
            with transaction.atomic():
                global_stats = GlobalStats.get_instance()
                global_stats.games_in_progress -= 1
                global_stats.save()
        except Exception as e:
            logger.error(f"Greška pri ažuriranju globalne statistike za prekinutu igru: {e}")


def update_player_and_team_stats(game):
    """
    Ažurira statistiku igrača i timova nakon završetka igre.
    
    Args:
        game: Završena igra
    """
    try:
        # Dohvati tim koji je pobijedio
        winning_team = 'a' if game.team_a_score > game.team_b_score else 'b'
        
        # Dohvati igrače iz igre
        players = list(game.players.all())
        if len(players) != 4:
            logger.error(f"Igra {game.id} nema točno 4 igrača.")
            return
        
        # Odredi timove
        # Tim A: [0, 2], Tim B: [1, 3]
        team_a = [players[0], players[2]]
        team_b = [players[1], players[3]]
        
        # Ažuriraj statistiku igrača
        for player in players:
            with transaction.atomic():
                player_stats, created = PlayerStats.objects.get_or_create(user=player)
                
                # Osnovne statistike
                player_stats.games_played += 1
                player_stats.total_score += (
                    game.team_a_score if player in team_a else game.team_b_score
                )
                
                # Pobjede i porazi
                is_winner = (
                    (player in team_a and winning_team == 'a') or
                    (player in team_b and winning_team == 'b')
                )
                
                if is_winner:
                    player_stats.games_won += 1
                    player_stats.update_streaks(won=True)
                else:
                    player_stats.games_lost += 1
                    player_stats.update_streaks(won=False)
                
                # Runde
                rounds = Round.objects.filter(game=game)
                player_stats.rounds_played += rounds.count()
                
                # Aduti i zvanja
                for round_obj in rounds:
                    if round_obj.caller == player:
                        player_stats.rounds_as_caller += 1
                        
                        # Pobjeda ili poraz kao zvač
                        round_winner = 'a' if round_obj.team_a_score > round_obj.team_b_score else 'b'
                        player_in_team_a = player in team_a
                        
                        if (round_winner == 'a' and player_in_team_a) or (round_winner == 'b' and not player_in_team_a):
                            player_stats.rounds_won_as_caller += 1
                        else:
                            player_stats.rounds_lost_as_caller += 1
                        
                        # Aduti
                        if round_obj.trump_suit == 'hearts':
                            player_stats.hearts_called += 1
                        elif round_obj.trump_suit == 'diamonds':
                            player_stats.diamonds_called += 1
                        elif round_obj.trump_suit == 'clubs':
                            player_stats.clubs_called += 1
                        elif round_obj.trump_suit == 'spades':
                            player_stats.spades_called += 1
                    
                    # Zvanja
                    declarations = Declaration.objects.filter(round=round_obj, player=player)
                    for declaration in declarations:
                        if declaration.declaration_type == 'belot':
                            player_stats.belot_declarations += 1
                        elif declaration.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                            player_stats.four_of_a_kind_declarations += 1
                        elif declaration.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                            player_stats.straight_declarations += 1
                
                # Najviši rezultat igre
                player_score = game.team_a_score if player in team_a else game.team_b_score
                if player_score > player_stats.highest_game_score:
                    player_stats.highest_game_score = player_score
                
                # Vremenski podaci
                now = timezone.now()
                if player_stats.first_game_date is None:
                    player_stats.first_game_date = now
                player_stats.last_game_date = now
                
                game_stats = GameStats.objects.get(game=game)
                if game_stats.duration:
                    player_stats.total_play_time += game_stats.duration
                
                # Ažuriraj prosjeke
                player_stats.update_avg_points()
                
                player_stats.save()
        
        # Ažuriraj statistiku timova
        # Tim A
        with transaction.atomic():
            team_a_stats = TeamStats.get_or_create_for_players(team_a[0], team_a[1])
            
            # Osnovne statistike
            team_a_stats.games_played += 1
            team_a_stats.total_score += game.team_a_score
            
            # Pobjede i porazi
            if winning_team == 'a':
                team_a_stats.games_won += 1
                team_a_stats.update_streaks(won=True)
            else:
                team_a_stats.games_lost += 1
                team_a_stats.update_streaks(won=False)
            
            # Aduti
            for round_obj in rounds:
                if round_obj.caller in team_a:
                    if round_obj.trump_suit == 'hearts':
                        team_a_stats.hearts_called += 1
                    elif round_obj.trump_suit == 'diamonds':
                        team_a_stats.diamonds_called += 1
                    elif round_obj.trump_suit == 'clubs':
                        team_a_stats.clubs_called += 1
                    elif round_obj.trump_suit == 'spades':
                        team_a_stats.spades_called += 1
            
            # Najviši rezultat igre
            if game.team_a_score > team_a_stats.highest_game_score:
                team_a_stats.highest_game_score = game.team_a_score
            
            # Vremenski podaci
            now = timezone.now()
            if team_a_stats.first_game_date is None:
                team_a_stats.first_game_date = now
            team_a_stats.last_game_date = now
            
            # Ažuriraj prosjeke
            team_a_stats.update_avg_points()
            
            team_a_stats.save()
        
        # Tim B
        with transaction.atomic():
            team_b_stats = TeamStats.get_or_create_for_players(team_b[0], team_b[1])
            
            # Osnovne statistike
            team_b_stats.games_played += 1
            team_b_stats.total_score += game.team_b_score
            
            # Pobjede i porazi
            if winning_team == 'b':
                team_b_stats.games_won += 1
                team_b_stats.update_streaks(won=True)
            else:
                team_b_stats.games_lost += 1
                team_b_stats.update_streaks(won=False)
            
            # Aduti
            for round_obj in rounds:
                if round_obj.caller in team_b:
                    if round_obj.trump_suit == 'hearts':
                        team_b_stats.hearts_called += 1
                    elif round_obj.trump_suit == 'diamonds':
                        team_b_stats.diamonds_called += 1
                    elif round_obj.trump_suit == 'clubs':
                        team_b_stats.clubs_called += 1
                    elif round_obj.trump_suit == 'spades':
                        team_b_stats.spades_called += 1
            
            # Najviši rezultat igre
            if game.team_b_score > team_b_stats.highest_game_score:
                team_b_stats.highest_game_score = game.team_b_score
            
            # Vremenski podaci
            if team_b_stats.first_game_date is None:
                team_b_stats.first_game_date = now
            team_b_stats.last_game_date = now
            
            # Ažuriraj prosjeke
            team_b_stats.update_avg_points()
            
            team_b_stats.save()
        
        # Ažuriraj ljestvice
        try:
            # Ljestvice za sve vrijeme
            Leaderboard.update_leaderboard('all_time', 'wins')
            Leaderboard.update_leaderboard('all_time', 'win_percentage')
            Leaderboard.update_leaderboard('all_time', 'points')
            
            # Ljestvice za mjesec
            Leaderboard.update_leaderboard('monthly', 'wins')
            Leaderboard.update_leaderboard('monthly', 'win_percentage')
            
            # Ljestvice za tjedan
            Leaderboard.update_leaderboard('weekly', 'wins')
        except Exception as e:
            logger.error(f"Greška pri ažuriranju ljestvica: {e}")
    
    except Exception as e:
        logger.error(f"Greška pri ažuriranju statistike igrača i timova: {e}")


@receiver(post_save, sender=Round)
def handle_round_events(sender, instance, created, **kwargs):
    """
    Signal koji prati promjene statusa runde i ažurira statistiku.
    
    Args:
        sender: Model koji je poslao signal
        instance: Instanca modela koja se sprema
        created: Je li instanca upravo stvorena
        **kwargs: Dodatni argumenti
    """
    # Ako je runda nova, nema potrebe za ažuriranjem statistike
    if created:
        return
    
    # Ako je runda završena, ažuriraj statistiku
    if instance.status == 'completed' and instance.tracker.has_changed('status'):
        try:
            # Ažuriraj GameStats
            with transaction.atomic():
                game_stats, created = GameStats.objects.get_or_create(game=instance.game)
                game_stats.total_rounds += 1
                
                # Aduti
                if instance.trump_suit == 'hearts':
                    game_stats.hearts_called += 1
                elif instance.trump_suit == 'diamonds':
                    game_stats.diamonds_called += 1
                elif instance.trump_suit == 'clubs':
                    game_stats.clubs_called += 1
                elif instance.trump_suit == 'spades':
                    game_stats.spades_called += 1
                
                # Zvanja
                declarations = Declaration.objects.filter(round=instance)
                for declaration in declarations:
                    if declaration.declaration_type == 'belot':
                        game_stats.belot_declarations += 1
                    elif declaration.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                        game_stats.four_of_a_kind_declarations += 1
                    elif declaration.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                        game_stats.straight_declarations += 1
                
                # Provjeri je li ovo runda s najviše bodova
                round_score = instance.team_a_score + instance.team_b_score
                if round_score > game_stats.highest_round_score:
                    game_stats.highest_round_score = round_score
                    game_stats.highest_scoring_round = instance.round_number
                
                game_stats.save()
                
                # Ažuriraj GlobalStats
                global_stats = GlobalStats.get_instance()
                global_stats.total_rounds += 1
                
                # Aduti
                if instance.trump_suit == 'hearts':
                    global_stats.hearts_called += 1
                elif instance.trump_suit == 'diamonds':
                    global_stats.diamonds_called += 1
                elif instance.trump_suit == 'clubs':
                    global_stats.clubs_called += 1
                elif instance.trump_suit == 'spades':
                    global_stats.spades_called += 1
                
                # Zvanja iz ove runde
                for declaration in declarations:
                    if declaration.declaration_type == 'belot':
                        global_stats.belot_declarations += 1
                    elif declaration.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                        global_stats.four_of_a_kind_declarations += 1
                    elif declaration.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                        global_stats.straight_declarations += 1
                
                global_stats.save()
                
                # Ažuriraj DailyStats
                daily_stats = DailyStats.get_or_create_for_today()
                daily_stats.total_rounds += 1
                
                # Aduti
                if instance.trump_suit == 'hearts':
                    daily_stats.hearts_called += 1
                elif instance.trump_suit == 'diamonds':
                    daily_stats.diamonds_called += 1
                elif instance.trump_suit == 'clubs':
                    daily_stats.clubs_called += 1
                elif instance.trump_suit == 'spades':
                    daily_stats.spades_called += 1
                
                # Zvanja iz ove runde
                for declaration in declarations:
                    if declaration.declaration_type == 'belot':
                        daily_stats.belot_declarations += 1
                    elif declaration.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                        daily_stats.four_of_a_kind_declarations += 1
                    elif declaration.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                        daily_stats.straight_declarations += 1
                
                daily_stats.save()
        
        except Exception as e:
            logger.error(f"Greška pri ažuriranju statistike za završenu rundu: {e}")


@receiver(post_save, sender=Declaration)
def handle_declaration_events(sender, instance, created, **kwargs):
    """
    Signal koji prati zvanja i ažurira statistiku.
    
    Args:
        sender: Model koji je poslao signal
        instance: Instanca modela koja se sprema
        created: Je li instanca upravo stvorena
        **kwargs: Dodatni argumenti
    """
    # Ako zvanje nije novo, izađi
    if not created:
        return
    
    try:
        # Ažuriraj statistiku igrača
        with transaction.atomic():
            player_stats, _ = PlayerStats.objects.get_or_create(user=instance.player)
            
            if instance.declaration_type == 'belot':
                player_stats.belot_declarations += 1
            elif instance.declaration_type in ['four_jacks', 'four_nines', 'four_aces', 'four_kings', 'four_queens']:
                player_stats.four_of_a_kind_declarations += 1
            elif instance.declaration_type in ['straight_three', 'straight_four', 'straight_five', 'straight_six', 'straight_seven', 'straight_eight']:
                player_stats.straight_declarations += 1
            
            player_stats.save()
    
    except Exception as e:
        logger.error(f"Greška pri ažuriranju statistike igrača za zvanje: {e}")
    
    # Ako je runda završena, GameStats će biti ažuriran kroz signal za rundu
    # tako da ne trebamo ovdje ažurirati GameStats


@receiver(post_save, sender=GlobalStats)
def trigger_snapshot_creation(sender, instance, **kwargs):
    """
    Signal koji stvara snimku statistike nakon ažuriranja globalne statistike.
    
    Stvara snimku periodički (ne za svako ažuriranje).
    
    Args:
        sender: Model koji je poslao signal
        instance: Instanca modela koja se sprema
        **kwargs: Dodatni argumenti
    """
    # Stvaraj snimku svakih 6 sati
    try:
        # Provjeri kada je zadnja snimka stvorena
        last_snapshot = StatisticsSnapshot.objects.order_by('-timestamp').first()
        
        if last_snapshot is None or (timezone.now() - last_snapshot.timestamp).total_seconds() >= 21600:  # 6 sati = 21600 sekundi
            StatisticsSnapshot.create_snapshot()
    except Exception as e:
        logger.error(f"Greška pri stvaranju snimke statistike: {e}")