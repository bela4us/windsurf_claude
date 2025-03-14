"""
Model podataka za Belot igru.

Ovaj modul definira Game model koji predstavlja jednu partiju Belot kartaške igre.
Model prati sve ključne informacije o igri, uključujući igrače, timove, rezultate,
status igre i vremenske oznake.
"""

import uuid
import random
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class Game(models.Model):
    """
    Model koji predstavlja jednu igru Belot kartaške igre.
    
    Svaka igra ima jedinstven ID, igrače podijeljene u dva tima,
    rezultate i trenutno stanje igre. Prati se i vrijeme početka,
    završetka i eventualni pobjednik.
    """
    
    # Mogući statusi igre
    STATUS_CHOICES = (
        ('waiting', 'Čekanje igrača'),
        ('ready', 'Spremno za početak'),
        ('in_progress', 'U tijeku'),
        ('paused', 'Pauzirano'),
        ('finished', 'Završeno'),
        ('abandoned', 'Napušteno'),
    )
    
    # Osnovni podaci o igri
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                         help_text="Jedinstveni identifikator igre")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting',
                             help_text="Trenutni status igre")
    room_code = models.CharField(max_length=8, unique=True, blank=True, null=True, 
                                help_text="Kod sobe za pridruživanje igri")
    
    # Vremenske oznake
    created_at = models.DateTimeField(auto_now_add=True, 
                                     help_text="Vrijeme stvaranja igre")
    started_at = models.DateTimeField(null=True, blank=True, 
                                    help_text="Vrijeme početka igre")
    finished_at = models.DateTimeField(null=True, blank=True, 
                                      help_text="Vrijeme završetka igre")
    updated_at = models.DateTimeField(auto_now=True, 
                                     help_text="Vrijeme posljednjeg ažuriranja")
    
    # Veze s igračima
    players = models.ManyToManyField(User, related_name='games',
                                    help_text="Igrači koji sudjeluju u igri")
    active_players = models.ManyToManyField(User, related_name='active_games',
                                          help_text="Trenutno aktivni igrači u igri")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Podaci o timovima
    team_a_players = models.ManyToManyField(User, related_name='team_a_games', blank=True,
                                         help_text="Igrači u timu A")
    team_b_players = models.ManyToManyField(User, related_name='team_b_games', blank=True,
                                         help_text="Igrači u timu B")
    
    # Rezultati igre
    team_a_score = models.IntegerField(default=0, help_text="Trenutni rezultat tima A")
    team_b_score = models.IntegerField(default=0, help_text="Trenutni rezultat tima B")
    winner_team = models.CharField(max_length=1, null=True, blank=True, 
                                 help_text="Pobjednički tim ('a' ili 'b')")
    
    # Postavke igre
    points_to_win = models.IntegerField(default=1001, 
                                      help_text="Broj bodova potreban za pobjedu")
    is_private = models.BooleanField(default=False, 
                                   help_text="Je li igra privatna (samo s pozivnicom)")
    
    # Meta podaci
    game_data = models.JSONField(default=dict, blank=True, 
                               help_text="Dodatni podaci o igri u JSON formatu")
    
    class Meta:
        verbose_name = "Igra"
        verbose_name_plural = "Igre"
        ordering = ['-created_at']
        db_table = 'belot_game'
    
    def __str__(self):
        """Tekstualni prikaz igre."""
        return f"Igra {self.id} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """
        Nadglašena metoda za spremanje, osigurava da svaka igra ima
        jedinstven kod sobe ako je isti prazan.
        """
        if not self.room_code:
            self.room_code = self._generate_room_code()
        super().save(*args, **kwargs)
    
    def _generate_room_code(self):
        """Generira nasumičan kod sobe duljine 6 znakova."""
        # Znakovi koji se mogu pojaviti u kodu sobe (bez zbunjujućih znakova)
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        while True:
            # Generiraj kod od 6 znakova
            code = ''.join(random.choice(chars) for _ in range(6))
            
            # Provjeri je li kod već u upotrebi
            if not Game.objects.filter(room_code=code).exists():
                return code
    
    def start_game(self):
        """Započinje igru, postavlja status i bilježi vrijeme početka."""
        if self.status not in ['waiting', 'ready']:
            raise ValueError("Nije moguće započeti igru koja nije u statusu čekanja ili spremna")
        
        # Provjera ima li igra dovoljno igrača
        if self.players.count() != 4:
            raise ValueError("Za početak igre potrebna su točno 4 igrača")
        
        # Postavljanje statusa i vremena početka
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
        
        # Vraća True ako je igra uspješno započeta
        return True
    
    def finish_game(self, winner_team=None):
        """Završava igru, postavlja pobjednika i bilježi vrijeme završetka."""
        if self.status != 'in_progress':
            raise ValueError("Nije moguće završiti igru koja nije u tijeku")
        
        # Postavljanje pobjednika i završnog vremena
        if winner_team in ['a', 'b']:
            self.winner_team = winner_team
        
        self.status = 'finished'
        self.finished_at = timezone.now()
        self.save()
        
        # Vraća True ako je igra uspješno završena
        return True
    
    def abandon_game(self):
        """Označava igru kao napuštenu."""
        if self.status not in ['waiting', 'ready', 'in_progress', 'paused']:
            raise ValueError("Nije moguće napustiti igru koja je već završena")
        
        self.status = 'abandoned'
        self.finished_at = timezone.now()
        self.save()
        
        return True
    
    def add_player(self, user):
        """Dodaje igrača u igru ako ima slobodnog mjesta."""
        # Provjera je li igra u statusu čekanja
        if self.status != 'waiting':
            raise ValueError("Nije moguće dodati igrača u igru koja je već počela")
        
        # Provjera ima li mjesta za novog igrača
        if self.players.count() >= 4:
            raise ValueError("Igra već ima maksimalan broj igrača (4)")
        
        # Provjera je li korisnik već u igri
        if self.players.filter(id=user.id).exists():
            raise ValueError("Korisnik je već dodan u ovu igru")
        
        # Dodavanje igrača
        self.players.add(user)
        self.active_players.add(user)
        
        # Ako su svi igrači pristigli, promijeni status u ready
        if self.players.count() == 4:
            self.status = 'ready'
            self.save()
        
        return True
    
    def remove_player(self, user):
        """Uklanja igrača iz igre."""
        # Provjera je li korisnik u igri
        if not self.players.filter(id=user.id).exists():
            raise ValueError("Korisnik nije član ove igre")
        
        # Uklanjanje igrača iz igre
        self.players.remove(user)
        self.active_players.remove(user)
        
        # Uklanjanje iz timova ako je dio nekog tima
        if user in self.team_a_players.all():
            self.team_a_players.remove(user)
        elif user in self.team_b_players.all():
            self.team_b_players.remove(user)
        
        # Ako je igra u tijeku, označi je kao napuštenu
        if self.status == 'in_progress':
            self.abandon_game()
        # Ako igra čeka i nema igrača, obriši je
        elif self.status == 'waiting' and self.players.count() == 0:
            self.delete()
            return False
        
        return True
    
    def assign_teams(self):
        """
        Raspoređuje igrače u timove nasumično.
        Ova metoda se poziva prije početka igre.
        """
        if self.status != 'ready':
            raise ValueError("Nije moguće formirati timove za igru koja nije spremna")
        
        # Provjera ima li igra točno 4 igrača
        if self.players.count() != 4:
            raise ValueError("Za formiranje timova potrebna su točno 4 igrača")
        
        # Očisti postojeće timove
        self.team_a_players.clear()
        self.team_b_players.clear()
        
        # Dohvati sve igrače i izmiješaj ih
        all_players = list(self.players.all())
        random.shuffle(all_players)
        
        # Dodijeli prva dva igrača timu A, a druga dva timu B
        self.team_a_players.add(all_players[0], all_players[1])
        self.team_b_players.add(all_players[2], all_players[3])
        
        self.save()
        return True
    
    def get_team_a_players(self):
        """Vraća queryset igrača iz tima A."""
        return self.team_a_players.all()
    
    def get_team_b_players(self):
        """Vraća queryset igrača iz tima B."""
        return self.team_b_players.all()
    
    def get_team_for_player(self, user):
        """
        Vraća oznaku tima ('a' ili 'b') kojem pripada igrač,
        ili None ako igrač nije član nijednog tima.
        """
        if self.team_a_players.filter(id=user.id).exists():
            return 'a'
        elif self.team_b_players.filter(id=user.id).exists():
            return 'b'
        return None
    
    def is_player_active(self, user):
        """Provjerava je li igrač trenutno aktivan u igri."""
        return self.active_players.filter(id=user.id).exists()
    
    def update_scores(self, team_a_points=0, team_b_points=0):
        """
        Ažurira rezultate timova dodavanjem novih bodova.
        Također provjerava je li neki tim dostigao broj bodova za pobjedu.
        """
        # Dodavanje bodova
        self.team_a_score += team_a_points
        self.team_b_score += team_b_points
        
        # Provjera uvjeta za pobjedu
        winner = None
        if self.team_a_score >= self.points_to_win:
            winner = 'a'
        elif self.team_b_score >= self.points_to_win:
            winner = 'b'
        
        # Spremi rezultat
        self.save()
        
        # Ako imamo pobjednika, završi igru
        if winner:
            self.finish_game(winner_team=winner)
            return winner
        
        return None
    
    def get_current_round(self):
        """Vraća trenutnu (posljednju) rundu igre."""
        return self.rounds.order_by('-number').first()
    
    def get_dealer_for_next_round(self):
        """
        Određuje tko je djelitelj za sljedeću rundu.
        U prvoj rundi djelitelj se određuje nasumično.
        U sljedećim rundama djelitelj je osoba lijevo od prethodnog djelitelja.
        """
        current_round = self.get_current_round()
        
        # Ako nema prethodnih rundi, odaberi nasumičnog igrača
        if not current_round:
            all_players = list(self.players.all())
            return random.choice(all_players)
        
        # Dohvati prethodnog djelitelja
        previous_dealer = current_round.dealer
        
        # Poredak igrača u igri (u smjeru suprotnom od kazaljke na satu)
        # Ovo pretpostavlja da su igrači poredani u smjeru igre
        all_players = list(self.players.all())
        try:
            current_index = all_players.index(previous_dealer)
            next_index = (current_index + 1) % 4  # Sljedeći u nizu
            return all_players[next_index]
        except (ValueError, IndexError):
            # Ako iz nekog razloga ne možemo odrediti sljedećeg djelitelja,
            # odaberi nasumičnog igrača
            return random.choice(all_players)
    
    def can_player_start_game(self, user):
        """
        Provjerava može li korisnik pokrenuti igru.
        Igru može pokrenuti bilo koji igrač kada su svi igrači prisutni.
        """
        # Provjera je li korisnik u igri
        if not self.players.filter(id=user.id).exists():
            return False
        
        # Provjera statusa igre
        if self.status != 'ready':
            return False
        
        # Provjera jesu li svi igrači aktivni
        return self.active_players.count() == 4
    
    def get_partner(self, user):
        """Vraća suigrača (partnera) za danog igrača."""
        team = self.get_team_for_player(user)
        if not team:
            return None
        
        team_players = self.team_a_players if team == 'a' else self.team_b_players
        partners = team_players.exclude(id=user.id)
        return partners.first() if partners.exists() else None
    
    def are_opponents(self, user1, user2):
        """Provjerava jesu li dva igrača protivnici."""
        team1 = self.get_team_for_player(user1)
        team2 = self.get_team_for_player(user2)
        
        # Ako neki od igrača nema tim, nisu protivnici
        if not team1 or not team2:
            return False
        
        # Igrači su protivnici ako su u različitim timovima
        return team1 != team2

class GameHistory(models.Model):
    """
    Model za praćenje povijesti odigranih igara.
    
    Sadrži arhivirane podatke o završenim igrama, uključujući
    konačne rezultate, vrijeme trajanja i statistiku.
    """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='history')
    completed_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(default=0)
    total_rounds = models.IntegerField(default=0)
    team_a_score = models.IntegerField(default=0)
    team_b_score = models.IntegerField(default=0)
    winner_team = models.CharField(max_length=1, choices=[('a', 'Tim A'), ('b', 'Tim B')], null=True)
    player_a1 = models.ForeignKey('users.User', on_delete=models.SET_NULL, related_name='history_team_a1', null=True)
    player_a2 = models.ForeignKey('users.User', on_delete=models.SET_NULL, related_name='history_team_a2', null=True)
    player_b1 = models.ForeignKey('users.User', on_delete=models.SET_NULL, related_name='history_team_b1', null=True)
    player_b2 = models.ForeignKey('users.User', on_delete=models.SET_NULL, related_name='history_team_b2', null=True)
    data = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = "Povijest igre"
        verbose_name_plural = "Povijest igara"
        ordering = ['-completed_at']
        indexes = [
            models.Index(fields=['completed_at']),
            models.Index(fields=['winner_team']),
        ]
    
    def __str__(self):
        return f"Povijest igre {self.game.id} - {self.completed_at}"
    
    @classmethod
    def create_from_game(cls, game):
        """
        Stvara zapis povijesti iz završene igre.
        
        Args:
            game: Instanca igre koja je završena
            
        Returns:
            GameHistory: Stvoreni zapis povijesti
        """
        history = cls(
            game=game,
            total_rounds=game.rounds.count(),
            team_a_score=game.team_a_score,
            team_b_score=game.team_b_score,
            winner_team=game.winner_team,
            player_a1=game.player_a1,
            player_a2=game.player_a2,
            player_b1=game.player_b1,
            player_b2=game.player_b2,
            data={
                'rounds': [round.get_data() for round in game.rounds.all()],
                'declarations': [decl.get_data() for decl in game.declarations.all()],
                'moves': [move.get_data() for move in game.moves.all()],
            }
        )
        
        # Izračunaj trajanje u sekundama
        if game.completed_at and game.created_at:
            delta = game.completed_at - game.created_at
            history.duration_seconds = int(delta.total_seconds())
            
        history.save()
        return history