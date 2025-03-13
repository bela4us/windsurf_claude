"""
Model podataka za potez (igranje karte) u Belot igri.

Ovaj modul definira Move model koji predstavlja pojedinačni potez igrača,
odnosno igranje jedne karte tijekom runde. Model prati koja je karta odigrana,
koji igrač ju je odigrao, i dodatne informacije poput redoslijeda poteza
unutar runde i je li potez bio pobjednički u svom štihu.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()

class Move(models.Model):
    """
    Model koji predstavlja jedan potez (igranje karte) u Belot igri.
    
    Svaki potez je vezan uz određenu rundu i igrača, sadrži informaciju
    o odigranoj karti i njenom redoslijedu unutar runde. Također prati
    je li potez bio pobjednički (odnio štih) i vrijeme odigravanja.
    """
    
    # Veza s rundom kojoj potez pripada
    round = models.ForeignKey('game.Round', on_delete=models.CASCADE, related_name='moves',
                            help_text="Runda u kojoj je potez odigran")
    
    # Igrač koji je odigrao potez
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='moves',
                             help_text="Igrač koji je odigrao potez")
    
    # Karta koja je odigrana
    # Format: dvoznakovni string gdje prvi znak označava vrijednost karte (7-A),
    # a drugi znak boju (S-pik, H-herc, D-karo, C-tref)
    # Primjeri: "7S" (sedmica pik), "AH" (as herc), "JC" (dečko tref)
    card = models.CharField(max_length=3, help_text="Kod odigrane karte (npr. '7S', 'AH', 'JC')")
    
    # Redoslijed poteza unutar runde
    order = models.PositiveIntegerField(validators=[MinValueValidator(0)],
                                      help_text="Redni broj poteza unutar runde")
    
    # Oznaka pobjedničkog poteza (koji je odnio štih)
    is_winning = models.BooleanField(default=False,
                                   help_text="Označava je li potez pobjednički (odnio štih)")
    
    # Validacija poteza prema pravilima
    is_valid = models.BooleanField(default=True,
                                 help_text="Označava je li potez validan prema pravilima")
    
    # Vrijeme odigravanja poteza
    timestamp = models.DateTimeField(auto_now_add=True,
                                   help_text="Vrijeme kada je potez odigran")
    
    # Dodatni podaci o potezu
    move_data = models.JSONField(default=dict, blank=True,
                               help_text="Dodatni podaci o potezu u JSON formatu")
    
    class Meta:
        verbose_name = "Potez"
        verbose_name_plural = "Potezi"
        ordering = ['round', 'order']
        db_table = 'belot_move'
    
    def __str__(self):
        """Tekstualni prikaz poteza."""
        return f"Potez {self.order} (Runda {self.round.number}): {self.player.username} igra {self.card}"
    
    def get_card_value(self):
        """Vraća vrijednost karte (7, 8, 9, 10, J, Q, K, A)."""
        if not self.card or len(self.card) < 2:
            return None
        return self.card[0] if self.card[0] != '1' else '10'  # Posebno rukovanje za desetku
    
    def get_card_suit(self):
        """Vraća boju karte (S, H, D, C)."""
        if not self.card or len(self.card) < 2:
            return None
        
        # Za karte osim desetke, boja je drugi znak
        if self.card[0] != '1':
            return self.card[1]
        # Za desetku, boja je treći znak
        elif len(self.card) >= 3:
            return self.card[2]
        
        return None
    
    def get_card_points(self, trump_suit=None):
        """
        Izračunava bodovnu vrijednost karte prema pravilima Belota.
        
        Vrijednosti karata ovise o tome je li boja adutska:
        - Kada boja nije adut: A(11), 10(10), K(4), Q(3), J(2), 9-7(0)
        - Kada je boja adut: J(20), 9(14), A(11), 10(10), K(4), Q(3), 8-7(0)
        
        Args:
            trump_suit: Oznaka adutske boje ('S', 'H', 'D', 'C', 'no_trump', 'all_trump')
        
        Returns:
            int: Bodovna vrijednost karte
        """
        value = self.get_card_value()
        suit = self.get_card_suit()
        
        if not value or not suit:
            return 0
        
        # Provjeri je li karta adut
        is_trump = False
        if trump_suit in ['S', 'H', 'D', 'C']:
            is_trump = (suit == trump_suit)
        elif trump_suit == 'all_trump':
            is_trump = True
        elif trump_suit == 'no_trump':
            is_trump = False
        
        # Bodovi kad je adut
        if is_trump:
            if value == 'J':
                return 20
            elif value == '9':
                return 14
            elif value == 'A':
                return 11
            elif value == '10':
                return 10
            elif value == 'K':
                return 4
            elif value == 'Q':
                return 3
            else:
                return 0
        
        # Bodovi kad nije adut
        else:
            if value == 'A':
                return 11
            elif value == '10':
                return 10
            elif value == 'K':
                return 4
            elif value == 'Q':
                return 3
            elif value == 'J':
                return 2
            else:
                return 0
    
    def get_trick_number(self):
        """
        Vraća redni broj štiha kojem potez pripada.
        U Belotu, svaki štih ima 4 poteza (po jedan od svakog igrača).
        """
        return self.order // 4
    
    def is_first_in_trick(self):
        """Provjerava je li potez prvi u svom štihu."""
        return self.order % 4 == 0
    
    def get_trick_moves(self):
        """Vraća sve poteze istog štiha."""
        trick_number = self.get_trick_number()
        start_order = trick_number * 4
        end_order = start_order + 3
        
        return Move.objects.filter(
            round=self.round,
            order__gte=start_order,
            order__lte=end_order
        ).order_by('order')
    
    def is_following_suit(self):
        """
        Provjerava prati li potez boju prvog poteza u štihu,
        što je jedno od pravila Belota.
        """
        if self.is_first_in_trick():
            return True  # Prvi potez u štihu uvijek prati boju
        
        # Dohvaćanje prvog poteza u štihu
        trick_number = self.get_trick_number()
        first_order = trick_number * 4
        
        try:
            first_move = Move.objects.get(round=self.round, order=first_order)
            first_suit = first_move.get_card_suit()
            
            # Provjera prati li ovaj potez boju prvog poteza
            return self.get_card_suit() == first_suit
        except Move.DoesNotExist:
            return False
    
    def validate_move(self):
        """
        Provjerava je li potez validan prema pravilima Belota.
        
        Osnovna pravila:
        1. Igrač mora pratiti boju ako je može pratiti
        2. Ako ne može pratiti boju, mora baciti aduta ako ga ima
        3. Ako ne može ni jedno ni drugo, može baciti bilo koju kartu
        
        Ova metoda je pojednostavljena i ne implementira sve specifičnosti
        Belota, poput pravila da se mora baciti jača karta ako je moguće.
        """
        # Ako je prvi potez u štihu, uvijek je validan
        if self.is_first_in_trick():
            self.is_valid = True
            self.save()
            return True
        
        # Dohvaćanje prvog poteza u štihu
        trick_number = self.get_trick_number()
        first_order = trick_number * 4
        
        try:
            first_move = Move.objects.get(round=self.round, order=first_order)
            first_suit = first_move.get_card_suit()
            
            # Ako igrač prati boju, potez je validan
            if self.get_card_suit() == first_suit:
                self.is_valid = True
                self.save()
                return True
            
            # Ako ne prati boju, moramo provjeriti ima li igrač karte te boje
            # Ova provjera bi zahtijevala uvid u karte igrača, što je izvan
            # opsega ovog modela. U stvarnoj implementaciji, ova provjera
            # bi se radila u servisnom sloju na temelju stanja igre.
            
            # Za sada, pretpostavljamo da je potez validan
            self.is_valid = True
            self.save()
            return True
            
        except Move.DoesNotExist:
            # Ako ne možemo dohvatiti prvi potez, označimo ovaj kao nevalidan
            self.is_valid = False
            self.save()
            return False
    
    def determine_trick_winner(self):
        """
        Određuje pobjednika štiha i označava njegov potez kao pobjednički.
        
        Prema pravilima Belota:
        1. Najviša karta početne boje osvaja štih, osim ako je igran adut
        2. Ako je igran adut, najviši adut osvaja štih
        
        Ova metoda pretpostavlja da je štih gotov (sva 4 poteza su odigrana).
        """
        # Provjera je li štih gotov
        trick_moves = list(self.get_trick_moves())
        if len(trick_moves) < 4:
            return None  # Štih nije gotov
        
        # Dohvaćanje adutske boje
        trump_suit_code = self.round.trump_suit
        if trump_suit_code == 'spades':
            trump_suit = 'S'
        elif trump_suit_code == 'hearts':
            trump_suit = 'H'
        elif trump_suit_code == 'diamonds':
            trump_suit = 'D'
        elif trump_suit_code == 'clubs':
            trump_suit = 'C'
        else:
            trump_suit = None  # No trump ili all trump
        
        # Dohvaćanje početne boje
        first_move = trick_moves[0]
        lead_suit = first_move.get_card_suit()
        
        # Poredak jačine karata u adutskoj i ne-adutskoj boji
        non_trump_order = {'7': 0, '8': 1, '9': 2, 'J': 3, 'Q': 4, 'K': 5, '10': 6, 'A': 7}
        trump_order = {'7': 0, '8': 1, 'Q': 2, 'K': 3, '10': 4, 'A': 5, '9': 6, 'J': 7}
        
        winning_move = first_move
        highest_value = 0
        is_trump_played = False
        
        # Prolazak kroz sve poteze u štihu
        for move in trick_moves:
            move_suit = move.get_card_suit()
            move_value = move.get_card_value()
            
            # Provjeri je li potez adut
            is_move_trump = False
            if trump_suit and move_suit == trump_suit:
                is_move_trump = True
            elif trump_suit_code == 'all_trump':
                is_move_trump = True
            
            # Ako je već igran adut, samo drugi adut može pobijediti
            if is_trump_played and not is_move_trump:
                continue
            
            # Ako je ovo prvi adut u štihu, on postaje pobjednički
            if is_move_trump and not is_trump_played:
                winning_move = move
                highest_value = trump_order.get(move_value, 0)
                is_trump_played = True
                continue
            
            # Ako su oba adut, usporedi vrijednosti
            if is_move_trump and is_trump_played:
                move_rank = trump_order.get(move_value, 0)
                if move_rank > highest_value:
                    winning_move = move
                    highest_value = move_rank
                continue
            
            # Ako nema aduta, usporedi s početnom bojom
            if not is_trump_played:
                # Samo karte početne boje mogu pobijediti
                if move_suit == lead_suit:
                    move_rank = non_trump_order.get(move_value, 0)
                    if move == first_move or move_rank > highest_value:
                        winning_move = move
                        highest_value = move_rank
        
        # Označavanje pobjedničkog poteza
        for move in trick_moves:
            move.is_winning = (move.id == winning_move.id)
            move.save()
        
        return winning_move