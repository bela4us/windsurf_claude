"""
Model podataka za rundu (dijeljenje) u Belot igri.

Ovaj modul definira Round model koji predstavlja jednu rundu (dijeljenje) 
u Belot kartaškoj igri. Svaka runda započinje dijeljenjem karata, 
nastavlja se određivanjem aduta, odigravanjem štihova i završava bodovanjem.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Round(models.Model):
    """
    Model koji predstavlja jednu rundu (dijeljenje) u Belot igri.
    
    Svaka runda ima svoj redni broj unutar igre, djelitelja, adutsku boju,
    i prati bodove koje su timovi ostvarili. Runda također sadrži informacije
    o timu koji je zvao aduta, što je važno za bodovanje.
    """
    
    # Mogući izbori za adutsku boju
    SUIT_CHOICES = (
        ('spades', 'Pik ♠'),
        ('hearts', 'Herc ♥'),
        ('diamonds', 'Karo ♦'),
        ('clubs', 'Tref ♣'),
        ('no_trump', 'Bez aduta'),
        ('all_trump', 'Sve boje adut'),
    )
    
    # Veza s igrom kojoj runda pripada
    game = models.ForeignKey('game.Game', on_delete=models.CASCADE, related_name='rounds',
                           help_text="Igra kojoj runda pripada")
    
    # Osnovni podaci o rundi
    number = models.PositiveIntegerField(validators=[MinValueValidator(1)],
                                       help_text="Redni broj runde unutar igre")
    dealer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dealt_rounds',
                             help_text="Igrač koji je dijelio karte u ovoj rundi")
    
    # Podaci o adutu
    trump_suit = models.CharField(max_length=10, choices=SUIT_CHOICES, null=True, blank=True,
                                help_text="Adutska boja za ovu rundu")
    calling_team = models.CharField(max_length=1, null=True, blank=True,
                                 help_text="Tim koji je zvao aduta ('a' ili 'b')")
    trump_caller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='called_trumps',
                                   help_text="Igrač koji je zvao aduta")
    
    # Rezultati runde
    team_a_score = models.IntegerField(default=0,
                                    help_text="Bodovi koje je osvojio tim A u ovoj rundi")
    team_b_score = models.IntegerField(default=0,
                                    help_text="Bodovi koje je osvojio tim B u ovoj rundi")
    winner_team = models.CharField(max_length=1, null=True, blank=True,
                               help_text="Tim koji je pobijedio u rundi ('a' ili 'b')")
    
    # Vremenske oznake
    started_at = models.DateTimeField(auto_now_add=True,
                                    help_text="Vrijeme početka runde")
    finished_at = models.DateTimeField(null=True, blank=True,
                                     help_text="Vrijeme završetka runde")
    
    # Status runde
    is_completed = models.BooleanField(default=False,
                                     help_text="Označava je li runda završena")
    
    # Dodatni podaci
    round_data = models.JSONField(default=dict, blank=True,
                                help_text="Dodatni podaci o rundi u JSON formatu")
    
    class Meta:
        verbose_name = "Runda"
        verbose_name_plural = "Runde"
        ordering = ['game', 'number']
        unique_together = [['game', 'number']]
        db_table = 'belot_round'
    
    def __str__(self):
        """Tekstualni prikaz runde."""
        trump_text = self.get_trump_suit_display() if self.trump_suit else 'Još nije određen'
        return f"Runda {self.number} (Igra {self.game.id}) - Adut: {trump_text}"
    
    def set_trump(self, suit, user):
        """
        Postavlja adutsku boju za rundu i pamti koji je igrač/tim zvao aduta.
        Ova informacija je važna za bodovanje na kraju runde.
        """
        if self.trump_suit:
            raise ValueError("Adut je već određen za ovu rundu")
        
        # Provjera valjanosti adutske boje
        if suit not in dict(self.SUIT_CHOICES).keys():
            raise ValueError(f"Nevažeća adutska boja: {suit}")
        
        # Provjera je li korisnik igrač u ovoj igri
        if not self.game.players.filter(id=user.id).exists():
            raise ValueError("Korisnik nije igrač u ovoj igri")
        
        # Postavljanje aduta
        self.trump_suit = suit
        self.trump_caller = user
        
        # Određivanje tima koji je zvao aduta
        team = self.game.get_team_for_player(user)
        if team not in ('a', 'b'):
            raise ValueError("Korisnik nije član nijednog tima")
        
        self.calling_team = team
        self.save()
        
        return True
    
    def complete_round(self, team_a_score, team_b_score):
        """
        Završava rundu s konačnim rezultatima i određuje pobjednika.
        """
        if self.is_completed:
            raise ValueError("Runda je već završena")
        
        # Postavljanje rezultata
        self.team_a_score = team_a_score
        self.team_b_score = team_b_score
        
        # Određivanje pobjednika
        # Tim koji je zvao aduta mora imati više bodova da bi "prošao"
        # Ako ima jednako ili manje bodova, pao je i suprotni tim dobiva sve bodove
        if self.calling_team == 'a':
            if team_a_score > team_b_score:
                self.winner_team = 'a'
            else:
                self.winner_team = 'b'
                # Tim A je "pao", tim B dobiva sve bodove
                self.team_b_score = team_a_score + team_b_score
                self.team_a_score = 0
        else:  # calling_team == 'b'
            if team_b_score > team_a_score:
                self.winner_team = 'b'
            else:
                self.winner_team = 'a'
                # Tim B je "pao", tim A dobiva sve bodove
                self.team_a_score = team_a_score + team_b_score
                self.team_b_score = 0
        
        # Označavanje runde kao završene
        self.is_completed = True
        self.finished_at = timezone.now()
        self.save()
        
        # Ažuriranje rezultata igre
        self.game.update_scores(self.team_a_score, self.team_b_score)
        
        return self.winner_team
    
    def get_tricks(self):
        """
        Vraća sve štihove u ovoj rundi, poredane po rednom broju.
        """
        # Grupiranje poteza po štihovima (4 poteza čine jedan štih)
        from django.db.models import Count
        tricks = []
        
        # Svaki štih ima 4 poteza (po jedan od svakog igrača)
        all_moves = self.moves.all().order_by('order')
        
        # Grupiranje poteza u štihove (po 4)
        trick_number = 0
        current_trick = []
        
        for move in all_moves:
            current_trick.append(move)
            if len(current_trick) == 4:
                tricks.append(current_trick)
                current_trick = []
                trick_number += 1
        
        # Dodaj posljednji nedovršeni štih ako postoji
        if current_trick:
            tricks.append(current_trick)
        
        return tricks
    
    def get_last_trick_winner(self):
        """
        Vraća igrača koji je osvojio posljednji odigrani štih.
        """
        tricks = self.get_tricks()
        if not tricks:
            return None
        
        # Analiza posljednjeg dovršenog štiha (4 poteza)
        last_completed_trick = next((t for t in tricks if len(t) == 4), None)
        if not last_completed_trick:
            return None
        
        # Pronalaženje pobjedničkog poteza
        winning_move = None
        for move in last_completed_trick:
            if move.is_winning:
                winning_move = move
                break
        
        return winning_move.player if winning_move else None
    
    def get_declarations(self):
        """
        Vraća sva zvanja u ovoj rundi.
        """
        return self.declarations.all().order_by('-value')
    
    def get_points_for_declarations(self, team):
        """
        Izračunava ukupne bodove za zvanja za određeni tim.
        """
        if team not in ('a', 'b'):
            raise ValueError("Nevažeći tim (mora biti 'a' ili 'b')")
        
        # Dohvaćanje svih igrača u timu
        team_players = self.game.team_a_players.all() if team == 'a' else self.game.team_b_players.all()
        team_player_ids = [player.id for player in team_players]
        
        # Zbrajanje bodova za zvanja
        total_points = 0
        declarations = self.declarations.filter(player_id__in=team_player_ids)
        for decl in declarations:
            total_points += decl.value
        
        return total_points
    
    def calculate_scores(self):
        """
        Izračunava konačne rezultate runde, uključujući bodove za štihove i zvanja.
        """
        # U stvarnoj implementaciji, ova metoda bi analizirala sve poteze
        # i izračunala bodove prema pravilima Belota. Ovo je pojednostavljeni primjer.
        
        team_a_trick_points = 0
        team_b_trick_points = 0
        
        # Bodovi za zvanja
        team_a_declaration_points = self.get_points_for_declarations('a')
        team_b_declaration_points = self.get_points_for_declarations('b')
        
        # Bodovi za štihove iz poteza
        for trick in self.get_tricks():
            if len(trick) == 4:  # Samo dovršeni štihovi
                winning_move = next((m for m in trick if m.is_winning), None)
                if winning_move:
                    winner_team = self.game.get_team_for_player(winning_move.player)
                    trick_points = sum(m.get_card_points(self.trump_suit) for m in trick)
                    
                    # Dodatnih 10 bodova za posljednji štih
                    if trick == self.get_tricks()[-1]:
                        trick_points += 10
                    
                    if winner_team == 'a':
                        team_a_trick_points += trick_points
                    elif winner_team == 'b':
                        team_b_trick_points += trick_points
        
        # Provjera štih-mača (štiglje) - 90 dodatnih bodova
        if team_a_trick_points == 0:
            team_b_trick_points += 90
        elif team_b_trick_points == 0:
            team_a_trick_points += 90
        
        # Ukupni rezultati
        team_a_total = team_a_trick_points + team_a_declaration_points
        team_b_total = team_b_trick_points + team_b_declaration_points
        
        return team_a_total, team_b_total
    
    def get_current_player(self):
        """
        Vraća igrača koji je na potezu.
        """
        # Ako runda još nije započela, vraća igrača nakon djelitelja
        if not self.moves.exists():
            # U Belotu, prvi potez ima igrač lijevo od djelitelja
            all_players = list(self.game.players.all())
            dealer_index = all_players.index(self.dealer)
            # Prvi potez ima igrač nakon djelitelja (u smjeru suprotnom od kazaljke na satu)
            first_player_index = (dealer_index + 1) % 4
            return all_players[first_player_index]
        
        # Ako je runda u tijeku, sljedeći na potezu je igrač nakon
        # onog koji je osvojio posljednji štih
        last_trick_winner = self.get_last_trick_winner()
        if last_trick_winner:
            return last_trick_winner
        
        # Ako još nema završenih štihova, vraća igrača koji je na redu
        # prema redoslijedu poteza
        all_moves = self.moves.all().order_by('order')
        if all_moves.exists():
            # Provjera je li posljednji štih dovršen
            moves_count = all_moves.count()
            if moves_count % 4 == 0:
                # Novi štih - započinje ga pobjednik prethodnog štiha
                winning_move = all_moves.filter(is_winning=True).order_by('-order').first()
                if winning_move:
                    return winning_move.player
            else:
                # Štih u tijeku - sljedeći igrač po redu
                last_player = all_moves.last().player
                all_players = list(self.game.players.all())
                last_player_index = all_players.index(last_player)
                next_player_index = (last_player_index + 1) % 4
                return all_players[next_player_index]
        
        # Ako iz nekog razloga ne možemo odrediti sljedećeg igrača,
        # vraćamo None
        return None
    
    def get_next_calling_player(self):
        """
        Određuje koji je igrač sljedeći na redu za zvanje aduta.
        Ovo se koristi tijekom faze određivanja aduta.
        """
        # U Belotu, prvi priliku za zvati aduta ima igrač lijevo od djelitelja
        all_players = list(self.game.players.all())
        dealer_index = all_players.index(self.dealer)
        
        # Prva prilika za zvanje aduta - igrač nakon djelitelja
        if not hasattr(self, 'trump_calling_order'):
            self.trump_calling_order = []
        
        if not self.trump_calling_order:
            first_caller_index = (dealer_index + 1) % 4
            return all_players[first_caller_index]
        
        # Ako su svi već imali priliku, posljednji igrač (djelitelj) mora zvati aduta
        if len(self.trump_calling_order) == 3:
            return self.dealer
        
        # Inače, sljedeći igrač nakon posljednjeg koji je rekao "dalje"
        last_caller = self.trump_calling_order[-1]
        last_caller_index = all_players.index(last_caller)
        next_caller_index = (last_caller_index + 1) % 4
        return all_players[next_caller_index]
    
    def add_to_calling_order(self, user):
        """
        Dodaje igrača u listu onih koji su rekli "dalje" prilikom zvanja aduta.
        """
        if not hasattr(self, 'trump_calling_order'):
            self.trump_calling_order = []
        
        if user not in self.trump_calling_order:
            self.trump_calling_order.append(user)
        
        # Ažuriranje podataka o rundi
        if self.round_data is None:
            self.round_data = {}
        
        self.round_data['trump_calling_order'] = [player.id for player in self.trump_calling_order]
        self.save()