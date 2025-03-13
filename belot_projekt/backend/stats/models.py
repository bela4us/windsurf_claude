"""
Modeli podataka za Django aplikaciju "stats".

Ovaj modul definira modele podataka za praćenje i analizu
statistike Belot igre, uključujući statistiku igrača,
timova, igara i partija.
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator

from game.models import Game, Round

User = get_user_model()


class PlayerStats(models.Model):
    """
    Model za praćenje statistike pojedinog igrača.
    
    Prati različite statistike vezane uz igrača kroz sve odigrane
    partije, uključujući broj pobjeda, poraza, prosječni rezultat,
    najčešće zvani adut i slično.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='stats',
        verbose_name=_('Korisnik')
    )
    
    # Osnovne statistike
    games_played = models.PositiveIntegerField(_('Odigrane igre'), default=0)
    games_won = models.PositiveIntegerField(_('Pobjede'), default=0)
    games_lost = models.PositiveIntegerField(_('Porazi'), default=0)
    total_score = models.PositiveIntegerField(_('Ukupni bodovi'), default=0)
    rounds_played = models.PositiveIntegerField(_('Odigrane runde'), default=0)
    
    # Statistike za adute
    hearts_called = models.PositiveIntegerField(_('Zvani adut herc'), default=0)
    diamonds_called = models.PositiveIntegerField(_('Zvani adut karo'), default=0)
    clubs_called = models.PositiveIntegerField(_('Zvani adut tref'), default=0)
    spades_called = models.PositiveIntegerField(_('Zvani adut pik'), default=0)
    
    # Statistike za zvanja
    belot_declarations = models.PositiveIntegerField(_('Belot zvanja'), default=0)
    four_of_a_kind_declarations = models.PositiveIntegerField(_('Četiri iste'), default=0)
    straight_declarations = models.PositiveIntegerField(_('Terci i više'), default=0)
    
    # Statistike za način igre
    rounds_as_caller = models.PositiveIntegerField(_('Runde kao zvač'), default=0)
    rounds_won_as_caller = models.PositiveIntegerField(_('Pobjede kao zvač'), default=0)
    rounds_lost_as_caller = models.PositiveIntegerField(_('Porazi kao zvač'), default=0)
    
    # Napredne statistike
    avg_points_per_game = models.FloatField(_('Prosječni bodovi po igri'), default=0.0)
    avg_points_per_round = models.FloatField(_('Prosječni bodovi po rundi'), default=0.0)
    highest_game_score = models.PositiveIntegerField(_('Najviši rezultat igre'), default=0)
    longest_winning_streak = models.PositiveIntegerField(_('Najduži niz pobjeda'), default=0)
    current_winning_streak = models.PositiveIntegerField(_('Trenutni niz pobjeda'), default=0)
    
    # Vremenski podaci
    first_game_date = models.DateTimeField(_('Datum prve igre'), null=True, blank=True)
    last_game_date = models.DateTimeField(_('Datum zadnje igre'), null=True, blank=True)
    total_play_time = models.DurationField(_('Ukupno vrijeme igranja'), default=timezone.timedelta(0))
    
    # Meta podaci
    last_updated = models.DateTimeField(_('Zadnje ažuriranje'), auto_now=True)
    
    class Meta:
        verbose_name = _('Statistika igrača')
        verbose_name_plural = _('Statistike igrača')
        ordering = ['-games_played', '-games_won']
    
    def __str__(self):
        return f"Statistika za {self.user.username}"
    
    @property
    def win_percentage(self):
        """Izračunava postotak pobjeda."""
        if self.games_played == 0:
            return 0
        return round((self.games_won / self.games_played) * 100, 2)
    
    @property
    def most_called_suit(self):
        """Vraća najčešće zvani adut."""
        suits = {
            'hearts': self.hearts_called,
            'diamonds': self.diamonds_called,
            'clubs': self.clubs_called,
            'spades': self.spades_called
        }
        return max(suits, key=suits.get)
    
    @property
    def caller_success_rate(self):
        """Izračunava postotak uspješnosti kao zvač."""
        if self.rounds_as_caller == 0:
            return 0
        return round((self.rounds_won_as_caller / self.rounds_as_caller) * 100, 2)
    
    def update_streaks(self, won: bool):
        """
        Ažurira nizove pobjeda.
        
        Args:
            won: Je li igrač pobijedio u zadnjoj igri
        """
        if won:
            self.current_winning_streak += 1
            self.longest_winning_streak = max(self.longest_winning_streak, self.current_winning_streak)
        else:
            self.current_winning_streak = 0
    
    def update_avg_points(self):
        """Ažurira prosječne bodove po igri i rundi."""
        if self.games_played > 0:
            self.avg_points_per_game = round(self.total_score / self.games_played, 2)
        
        if self.rounds_played > 0:
            self.avg_points_per_round = round(self.total_score / self.rounds_played, 2)


class TeamStats(models.Model):
    """
    Model za praćenje statistike timova.
    
    Prati statistike za specifične kombinacije igrača koji
    su igrali zajedno kao tim, uključujući broj pobjeda,
    poraza, ukupne bodove i slično.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_stats_as_player1',
        verbose_name=_('Igrač 1')
    )
    player2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_stats_as_player2',
        verbose_name=_('Igrač 2')
    )
    
    # Osnovne statistike
    games_played = models.PositiveIntegerField(_('Odigrane igre'), default=0)
    games_won = models.PositiveIntegerField(_('Pobjede'), default=0)
    games_lost = models.PositiveIntegerField(_('Porazi'), default=0)
    total_score = models.PositiveIntegerField(_('Ukupni bodovi'), default=0)
    
    # Statistike za adute
    hearts_called = models.PositiveIntegerField(_('Zvani adut herc'), default=0)
    diamonds_called = models.PositiveIntegerField(_('Zvani adut karo'), default=0)
    clubs_called = models.PositiveIntegerField(_('Zvani adut tref'), default=0)
    spades_called = models.PositiveIntegerField(_('Zvani adut pik'), default=0)
    
    # Napredne statistike
    avg_points_per_game = models.FloatField(_('Prosječni bodovi po igri'), default=0.0)
    highest_game_score = models.PositiveIntegerField(_('Najviši rezultat igre'), default=0)
    longest_winning_streak = models.PositiveIntegerField(_('Najduži niz pobjeda'), default=0)
    current_winning_streak = models.PositiveIntegerField(_('Trenutni niz pobjeda'), default=0)
    
    # Vremenski podaci
    first_game_date = models.DateTimeField(_('Datum prve igre'), null=True, blank=True)
    last_game_date = models.DateTimeField(_('Datum zadnje igre'), null=True, blank=True)
    
    # Meta podaci
    last_updated = models.DateTimeField(_('Zadnje ažuriranje'), auto_now=True)
    
    class Meta:
        verbose_name = _('Statistika tima')
        verbose_name_plural = _('Statistike timova')
        ordering = ['-games_played', '-games_won']
        unique_together = [['player1', 'player2']]
    
    def __str__(self):
        return f"Tim: {self.player1.username} i {self.player2.username}"
    
    @property
    def win_percentage(self):
        """Izračunava postotak pobjeda."""
        if self.games_played == 0:
            return 0
        return round((self.games_won / self.games_played) * 100, 2)
    
    @property
    def most_called_suit(self):
        """Vraća najčešće zvani adut."""
        suits = {
            'hearts': self.hearts_called,
            'diamonds': self.diamonds_called,
            'clubs': self.clubs_called,
            'spades': self.spades_called
        }
        return max(suits, key=suits.get)
    
    def update_streaks(self, won: bool):
        """
        Ažurira nizove pobjeda.
        
        Args:
            won: Je li tim pobijedio u zadnjoj igri
        """
        if won:
            self.current_winning_streak += 1
            self.longest_winning_streak = max(self.longest_winning_streak, self.current_winning_streak)
        else:
            self.current_winning_streak = 0
    
    def update_avg_points(self):
        """Ažurira prosječne bodove po igri."""
        if self.games_played > 0:
            self.avg_points_per_game = round(self.total_score / self.games_played, 2)
    
    @classmethod
    def get_or_create_for_players(cls, player1, player2):
        """
        Dohvaća ili stvara statistiku tima za dva igrača.
        
        Metoda osigurava da se statistika tima vodi konzistentno,
        bez obzira na redoslijed igrača.
        
        Args:
            player1: Prvi igrač
            player2: Drugi igrač
            
        Returns:
            TeamStats: Statistika tima
        """
        # Osiguraj da su igrači sortirani po ID-u za konzistentnost
        if player1.id > player2.id:
            player1, player2 = player2, player1
        
        # Dohvati ili stvori statistiku tima
        stats, created = cls.objects.get_or_create(
            player1=player1,
            player2=player2
        )
        
        return stats


class GameStats(models.Model):
    """
    Model za detaljnu statistiku pojedine igre.
    
    Prati različite statistike i metrike za pojedinu igru,
    uključujući trajanje, broj rundi, najčešće zvane adute,
    zvanja i slično.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.OneToOneField(
        Game,
        on_delete=models.CASCADE,
        related_name='stats',
        verbose_name=_('Igra')
    )
    
    # Vremenski podaci
    duration = models.DurationField(_('Trajanje'), default=timezone.timedelta(0))
    start_time = models.DateTimeField(_('Vrijeme početka'), null=True, blank=True)
    end_time = models.DateTimeField(_('Vrijeme završetka'), null=True, blank=True)
    
    # Statistike za runde
    total_rounds = models.PositiveIntegerField(_('Ukupno rundi'), default=0)
    
    # Statistike za adute
    hearts_called = models.PositiveIntegerField(_('Zvani adut herc'), default=0)
    diamonds_called = models.PositiveIntegerField(_('Zvani adut karo'), default=0)
    clubs_called = models.PositiveIntegerField(_('Zvani adut tref'), default=0)
    spades_called = models.PositiveIntegerField(_('Zvani adut pik'), default=0)
    
    # Statistike za zvanja
    belot_declarations = models.PositiveIntegerField(_('Belot zvanja'), default=0)
    four_of_a_kind_declarations = models.PositiveIntegerField(_('Četiri iste'), default=0)
    straight_declarations = models.PositiveIntegerField(_('Terci i više'), default=0)
    
    # Rezultati timova
    team_a_score = models.PositiveIntegerField(_('Bodovi tima A'), default=0)
    team_b_score = models.PositiveIntegerField(_('Bodovi tima B'), default=0)
    
    # Najznačajniji događaji
    highest_scoring_round = models.PositiveIntegerField(_('Runda s najviše bodova'), default=0)
    highest_round_score = models.PositiveIntegerField(_('Najviši rezultat u rundi'), default=0)
    
    # Meta podaci
    created_at = models.DateTimeField(_('Vrijeme stvaranja'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Vrijeme ažuriranja'), auto_now=True)
    
    class Meta:
        verbose_name = _('Statistika igre')
        verbose_name_plural = _('Statistike igara')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Statistika za igru {self.game.id}"
    
    @property
    def most_called_suit(self):
        """Vraća najčešće zvani adut."""
        suits = {
            'hearts': self.hearts_called,
            'diamonds': self.diamonds_called,
            'clubs': self.clubs_called,
            'spades': self.spades_called
        }
        return max(suits, key=suits.get)
    
    @property
    def winning_team(self):
        """Vraća pobjednički tim."""
        if self.team_a_score > self.team_b_score:
            return 'A'
        elif self.team_b_score > self.team_a_score:
            return 'B'
        return None
    
    @property
    def score_difference(self):
        """Vraća razliku u bodovima između timova."""
        return abs(self.team_a_score - self.team_b_score)
    
    @property
    def average_round_score(self):
        """Vraća prosječni broj bodova po rundi."""
        if self.total_rounds == 0:
            return 0
        total_score = self.team_a_score + self.team_b_score
        return round(total_score / self.total_rounds, 2)


class GlobalStats(models.Model):
    """
    Model za globalne statistike igre.
    
    Prati agregiranu statistiku za cijelu platformu,
    uključujući ukupan broj igara, igrača, prosječno
    trajanje igre i slično.
    """
    
    # Jedinstveni ključ - uvijek imamo samo jedan zapis
    id = models.PositiveIntegerField(primary_key=True, default=1)
    
    # Osnovne statistike
    total_games = models.PositiveIntegerField(_('Ukupno igara'), default=0)
    total_players = models.PositiveIntegerField(_('Ukupno igrača'), default=0)
    total_rounds = models.PositiveIntegerField(_('Ukupno rundi'), default=0)
    games_in_progress = models.PositiveIntegerField(_('Igre u tijeku'), default=0)
    
    # Vremenski podaci
    avg_game_duration = models.DurationField(
        _('Prosječno trajanje igre'),
        default=timezone.timedelta(0)
    )
    total_play_time = models.DurationField(
        _('Ukupno vrijeme igranja'),
        default=timezone.timedelta(0)
    )
    
    # Statistike za adute
    hearts_called = models.PositiveIntegerField(_('Zvani adut herc'), default=0)
    diamonds_called = models.PositiveIntegerField(_('Zvani adut karo'), default=0)
    clubs_called = models.PositiveIntegerField(_('Zvani adut tref'), default=0)
    spades_called = models.PositiveIntegerField(_('Zvani adut pik'), default=0)
    
    # Statistike za zvanja
    belot_declarations = models.PositiveIntegerField(_('Belot zvanja'), default=0)
    four_of_a_kind_declarations = models.PositiveIntegerField(_('Četiri iste'), default=0)
    straight_declarations = models.PositiveIntegerField(_('Terci i više'), default=0)
    
    # Meta podaci
    last_updated = models.DateTimeField(_('Zadnje ažuriranje'), auto_now=True)
    
    class Meta:
        verbose_name = _('Globalna statistika')
        verbose_name_plural = _('Globalne statistike')
    
    def __str__(self):
        return f"Globalna statistika (ažurirano: {self.last_updated})"
    
    @property
    def most_called_suit(self):
        """Vraća najčešće zvani adut."""
        suits = {
            'hearts': self.hearts_called,
            'diamonds': self.diamonds_called,
            'clubs': self.clubs_called,
            'spades': self.spades_called
        }
        return max(suits, key=suits.get)
    
    @property
    def avg_rounds_per_game(self):
        """Vraća prosječni broj rundi po igri."""
        if self.total_games == 0:
            return 0
        return round(self.total_rounds / self.total_games, 2)
    
    @classmethod
    def get_instance(cls):
        """
        Dohvaća jedinstvenu instancu globalne statistike.
        
        Returns:
            GlobalStats: Jedinstvena instanca globalne statistike
        """
        instance, created = cls.objects.get_or_create(id=1)
        return instance


class DailyStats(models.Model):
    """
    Model za dnevne statistike igre.
    
    Prati agregiranu statistiku za svaki pojedini dan,
    uključujući broj igara, igrača, prosječno trajanje
    igre i slično.
    """
    
    # Jedinstveni ključ - datum
    date = models.DateField(_('Datum'), primary_key=True)
    
    # Osnovne statistike
    total_games = models.PositiveIntegerField(_('Ukupno igara'), default=0)
    active_players = models.PositiveIntegerField(_('Aktivni igrači'), default=0)
    total_rounds = models.PositiveIntegerField(_('Ukupno rundi'), default=0)
    
    # Vremenski podaci
    avg_game_duration = models.DurationField(
        _('Prosječno trajanje igre'),
        default=timezone.timedelta(0)
    )
    total_play_time = models.DurationField(
        _('Ukupno vrijeme igranja'),
        default=timezone.timedelta(0)
    )
    
    # Statistike za adute
    hearts_called = models.PositiveIntegerField(_('Zvani adut herc'), default=0)
    diamonds_called = models.PositiveIntegerField(_('Zvani adut karo'), default=0)
    clubs_called = models.PositiveIntegerField(_('Zvani adut tref'), default=0)
    spades_called = models.PositiveIntegerField(_('Zvani adut pik'), default=0)
    
    # Statistike za zvanja
    belot_declarations = models.PositiveIntegerField(_('Belot zvanja'), default=0)
    four_of_a_kind_declarations = models.PositiveIntegerField(_('Četiri iste'), default=0)
    straight_declarations = models.PositiveIntegerField(_('Terci i više'), default=0)
    
    # Novi korisnici
    new_users = models.PositiveIntegerField(_('Novi korisnici'), default=0)
    
    # Meta podaci
    created_at = models.DateTimeField(_('Vrijeme stvaranja'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Vrijeme ažuriranja'), auto_now=True)
    
    class Meta:
        verbose_name = _('Dnevna statistika')
        verbose_name_plural = _('Dnevne statistike')
        ordering = ['-date']
    
    def __str__(self):
        return f"Statistika za {self.date}"
    
    @property
    def most_called_suit(self):
        """Vraća najčešće zvani adut."""
        suits = {
            'hearts': self.hearts_called,
            'diamonds': self.diamonds_called,
            'clubs': self.clubs_called,
            'spades': self.spades_called
        }
        return max(suits, key=suits.get)
    
    @property
    def avg_rounds_per_game(self):
        """Vraća prosječni broj rundi po igri."""
        if self.total_games == 0:
            return 0
        return round(self.total_rounds / self.total_games, 2)
    
    @classmethod
    def get_or_create_for_today(cls):
        """
        Dohvaća ili stvara statistiku za današnji dan.
        
        Returns:
            DailyStats: Statistika za današnji dan
        """
        today = timezone.now().date()
        stats, created = cls.objects.get_or_create(date=today)
        return stats
    
    @classmethod
    def get_for_date_range(cls, start_date, end_date):
        """
        Dohvaća statistiku za raspon datuma.
        
        Args:
            start_date: Početni datum
            end_date: Završni datum
            
        Returns:
            QuerySet: Statistika za raspon datuma
        """
        return cls.objects.filter(date__range=[start_date, end_date])


class StatisticsSnapshot(models.Model):
    """
    Model za snimke stanja statistike.
    
    Periodički sprema stanje različitih statistika
    kako bi se omogućilo praćenje trendova kroz vrijeme.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(_('Vrijeme snimke'), auto_now_add=True)
    
    # Osnovne statistike
    total_games = models.PositiveIntegerField(_('Ukupno igara'), default=0)
    total_players = models.PositiveIntegerField(_('Ukupno igrača'), default=0)
    active_players = models.PositiveIntegerField(_('Aktivni igrači'), default=0)
    games_in_progress = models.PositiveIntegerField(_('Igre u tijeku'), default=0)
    
    # Dodatne statistike
    top_suit = models.CharField(_('Najčešći adut'), max_length=20, blank=True)
    avg_game_duration = models.DurationField(
        _('Prosječno trajanje igre'),
        default=timezone.timedelta(0)
    )
    
    # Dodatni podaci
    new_users_last_day = models.PositiveIntegerField(_('Novi korisnici (24h)'), default=0)
    new_games_last_day = models.PositiveIntegerField(_('Nove igre (24h)'), default=0)
    
    # Serializirani dodatni podaci
    extra_data = models.JSONField(_('Dodatni podaci'), default=dict, blank=True)
    
    class Meta:
        verbose_name = _('Snimka statistike')
        verbose_name_plural = _('Snimke statistike')
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Snimka statistike ({self.timestamp})"
    
    @classmethod
    def create_snapshot(cls):
        """
        Stvara novu snimku trenutnog stanja statistike.
        
        Returns:
            StatisticsSnapshot: Stvorena snimka
        """
        from django.contrib.auth import get_user_model
        from game.models import Game
        
        User = get_user_model()
        
        # Dohvati globalne statistike
        global_stats = GlobalStats.get_instance()
        
        # Izračunaj aktivne igrače (logirali se u zadnjih 24h)
        yesterday = timezone.now() - timezone.timedelta(days=1)
        active_players = User.objects.filter(last_login__gte=yesterday).count()
        
        # Novi korisnici u zadnjih 24h
        new_users = User.objects.filter(date_joined__gte=yesterday).count()
        
        # Nove igre u zadnjih 24h
        new_games = Game.objects.filter(created_at__gte=yesterday).count()
        
        # Igre u tijeku
        games_in_progress = Game.objects.filter(status='in_progress').count()
        
        # Stvori snimku
        snapshot = cls.objects.create(
            total_games=global_stats.total_games,
            total_players=global_stats.total_players,
            active_players=active_players,
            games_in_progress=games_in_progress,
            top_suit=global_stats.most_called_suit,
            avg_game_duration=global_stats.avg_game_duration,
            new_users_last_day=new_users,
            new_games_last_day=new_games,
            extra_data={
                'hearts_called': global_stats.hearts_called,
                'diamonds_called': global_stats.diamonds_called,
                'clubs_called': global_stats.clubs_called,
                'spades_called': global_stats.spades_called,
                'belot_declarations': global_stats.belot_declarations,
                'four_of_a_kind_declarations': global_stats.four_of_a_kind_declarations,
                'straight_declarations': global_stats.straight_declarations,
            }
        )
        
        return snapshot


class Leaderboard(models.Model):
    """
    Model za ljestvice najboljih igrača.
    
    Prati najbolje igrače prema različitim kategorijama
    i za različite vremenske periode.
    """
    
    PERIOD_CHOICES = [
        ('daily', _('Dnevno')),
        ('weekly', _('Tjedno')),
        ('monthly', _('Mjesečno')),
        ('all_time', _('Svi vremena')),
    ]
    
    CATEGORY_CHOICES = [
        ('wins', _('Pobjede')),
        ('win_percentage', _('Postotak pobjeda')),
        ('points', _('Bodovi')),
        ('belot_declarations', _('Belot zvanja')),
        ('four_of_a_kind', _('Četiri iste')),
        ('games_played', _('Odigrane igre')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(_('Period'), max_length=20, choices=PERIOD_CHOICES)
    category = models.CharField(_('Kategorija'), max_length=20, choices=CATEGORY_CHOICES)
    start_date = models.DateField(_('Početni datum'), null=True, blank=True)
    end_date = models.DateField(_('Završni datum'), null=True, blank=True)
    
    # Lista korisnika i njihovih rezultata
    players = models.JSONField(_('Igrači i rezultati'), default=list)
    
    # Meta podaci
    created_at = models.DateTimeField(_('Vrijeme stvaranja'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Vrijeme ažuriranja'), auto_now=True)
    
    class Meta:
        verbose_name = _('Ljestvica')
        verbose_name_plural = _('Ljestvice')
        ordering = ['-updated_at']
        unique_together = [['period', 'category']]
    
    def __str__(self):
        return f"Ljestvica - {self.get_category_display()} ({self.get_period_display()})"
    
    @property
    def top_player(self):
        """Vraća najboljeg igrača s ljestvice."""
        if not self.players:
            return None
        
        return self.players[0]
    
    @property
    def player_count(self):
        """Vraća broj igrača na ljestvici."""
        return len(self.players)
    
    @classmethod
    def update_leaderboard(cls, period, category):
        """
        Ažurira ljestvicu za određeni period i kategoriju.
        
        Args:
            period: Period ljestvice (daily, weekly, monthly, all_time)
            category: Kategorija ljestvice (wins, points, itd.)
            
        Returns:
            Leaderboard: Ažurirana ljestvica
        """
        # Izračunaj period
        today = timezone.now().date()
        start_date = None
        
        if period == 'daily':
            start_date = today
        elif period == 'weekly':
            start_date = today - timezone.timedelta(days=today.weekday())
        elif period == 'monthly':
            start_date = today.replace(day=1)
        
        # Dohvati ili stvori ljestvicu
        leaderboard, created = cls.objects.get_or_create(
            period=period,
            category=category,
            defaults={
                'start_date': start_date,
                'end_date': today,
            }
        )
        
        if not created:
            leaderboard.start_date = start_date
            leaderboard.end_date = today
        
        # Izračunaj i ažuriraj ljestvicu
        if category == 'wins':
            players = PlayerStats.objects.filter(
                games_played__gt=0
            ).order_by('-games_won')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.games_won,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        elif category == 'win_percentage':
            players = PlayerStats.objects.filter(
                games_played__gte=10  # Minimalni broj igara za kvalifikaciju
            ).order_by('-games_won', '-games_played')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.win_percentage,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        elif category == 'points':
            players = PlayerStats.objects.filter(
                games_played__gt=0
            ).order_by('-total_score')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.total_score,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        elif category == 'belot_declarations':
            players = PlayerStats.objects.filter(
                games_played__gt=0
            ).order_by('-belot_declarations')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.belot_declarations,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        elif category == 'four_of_a_kind':
            players = PlayerStats.objects.filter(
                games_played__gt=0
            ).order_by('-four_of_a_kind_declarations')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.four_of_a_kind_declarations,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        elif category == 'games_played':
            players = PlayerStats.objects.filter(
                games_played__gt=0
            ).order_by('-games_played')[:100]
            
            leaderboard.players = [
                {
                    'id': str(player.user.id),
                    'username': player.user.username,
                    'value': player.games_played,
                    'rank': i + 1
                }
                for i, player in enumerate(players)
            ]
        
        leaderboard.save()
        return leaderboard