"""
Model podataka za zvanja u Belot igri.

Ovaj modul definira Declaration model koji predstavlja zvanja u Belot
kartaškoj igri. Zvanja su posebne kombinacije karata koje igrači mogu
prijaviti tijekom igre za dodatne bodove, poput bele (kralj i dama iste
boje u adutu), sekvenci (3 ili više karata u nizu iste boje), ili
četiri karte iste vrijednosti (četiri dečka, četiri devetke, itd.).
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Declaration(models.Model):
    """
    Model koji predstavlja zvanje u Belot igri.
    
    Zvanja su posebne kombinacije karata koje donose dodatne bodove.
    Svako zvanje je vezano uz određenu rundu i igrača, ima svoj tip,
    vrijednost u bodovima, i podatke o kartama koje čine zvanje.
    """
    
    # Tipovi zvanja
    DECLARATION_TYPES = (
        ('bela', 'Bela (kralj i dama u adutu)'),
        ('belot', '8 karata u nizu'),
        ('four_jacks', 'Četiri dečka'),
        ('four_nines', 'Četiri devetke'),
        ('four_aces', 'Četiri asa'),
        ('four_tens', 'Četiri desetke'),
        ('four_kings', 'Četiri kralja'),
        ('four_queens', 'Četiri dame'),
        ('sequence_3', 'Tri karte u nizu'),
        ('sequence_4', 'Četiri karte u nizu'),
        ('sequence_5', 'Pet karata u nizu'),
        ('sequence_6', 'Šest karata u nizu'),
        ('sequence_7', 'Sedam karata u nizu'),
    )
    
    # Veza s rundom kojoj zvanje pripada
    round = models.ForeignKey('game.Round', on_delete=models.CASCADE, related_name='declarations',
                            help_text="Runda u kojoj je zvanje prijavljeno")
    
    # Igrač koji je prijavio zvanje
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='declarations',
                             help_text="Igrač koji je prijavio zvanje")
    
    # Tip zvanja
    type = models.CharField(max_length=15, choices=DECLARATION_TYPES,
                          help_text="Tip zvanja")
    
    # Boja za zvanja koja ovise o boji (bela, sekvence)
    suit = models.CharField(max_length=1, null=True, blank=True,
                          help_text="Boja zvanja (S, H, D, C) za zvanja koja ovise o boji")
    
    # Vrijednost zvanja u bodovima
    value = models.PositiveIntegerField(
        help_text="Vrijednost zvanja u bodovima"
    )
    
    # Karte koje čine zvanje u JSON formatu
    # Format: lista kodova karata, npr. ["KS", "QS"] za belu u piku
    cards = models.JSONField(default=list,
                           help_text="Karte koje čine zvanje u JSON formatu")
    
    # Je li zvanje potvrđeno (neki tipovi zvanja moraju se potvrditi)
    is_confirmed = models.BooleanField(default=True,
                                     help_text="Označava je li zvanje potvrđeno")
    
    # Vrijeme prijave zvanja
    timestamp = models.DateTimeField(auto_now_add=True,
                                   help_text="Vrijeme kada je zvanje prijavljeno")
    
    class Meta:
        verbose_name = "Zvanje"
        verbose_name_plural = "Zvanja"
        ordering = ['-value', 'timestamp']
        db_table = 'belot_declaration'
    
    def __str__(self):
        """Tekstualni prikaz zvanja."""
        suit_text = f" ({self.get_suit_display()})" if self.suit else ""
        return f"{self.get_type_display()}{suit_text} - {self.value} bodova ({self.player.username})"
    
    def get_suit_display(self):
        """Vraća tekstualni prikaz boje."""
        if not self.suit:
            return ""
        
        suit_map = {
            'S': 'Pik ♠',
            'H': 'Herc ♥',
            'D': 'Karo ♦',
            'C': 'Tref ♣',
        }
        return suit_map.get(self.suit, self.suit)
    
    def save(self, *args, **kwargs):
        """
        Nadglašena metoda za spremanje koja osigurava ispravnu vrijednost zvanja.
        Ako vrijednost nije eksplicitno postavljena, računa se prema tipu zvanja.
        """
        if not self.value:
            self.value = self.calculate_value()
        
        super().save(*args, **kwargs)
    
    def calculate_value(self):
        """
        Izračunava vrijednost zvanja prema njegovom tipu i pravilima Belota.
        
        Returns:
            int: Vrijednost zvanja u bodovima
        """
        # Vrijednosti zvanja prema pravilima Belota
        if self.type == 'bela':
            return 20  # Kralj i dama iste boje u adutu
        elif self.type == 'belot':
            return 1001  # 8 karata u nizu u istoj boji - automatska pobjeda
        elif self.type == 'four_jacks':
            return 200  # Četiri dečka
        elif self.type == 'four_nines':
            return 150  # Četiri devetke
        elif self.type == 'four_aces':
            return 100  # Četiri asa
        elif self.type == 'four_tens':
            return 100  # Četiri desetke
        elif self.type == 'four_kings':
            return 100  # Četiri kralja
        elif self.type == 'four_queens':
            return 100  # Četiri dame
        elif self.type == 'sequence_3':
            return 20  # Tri karte u nizu iste boje
        elif self.type == 'sequence_4':
            return 50  # Četiri karte u nizu iste boje
        elif self.type == 'sequence_5':
            return 100  # Pet karata u nizu iste boje
        elif self.type == 'sequence_6':
            return 100  # Šest karata u nizu iste boje
        elif self.type == 'sequence_7':
            return 100  # Sedam karata u nizu iste boje
        
        return 0  # Nepoznat tip zvanja
    
    @staticmethod
    def validate_declaration(declaration_type, cards, round_obj):
        """
        Provjerava je li zvanje valjano prema pravilima Belota.
        
        Args:
            declaration_type: Tip zvanja
            cards: Lista karata koje čine zvanje
            round_obj: Runda u kojoj se zvanje prijavljuje
        
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, poruka o grešci ako nije)
        """
        # Provjera tipa zvanja
        valid_types = dict(Declaration.DECLARATION_TYPES).keys()
        if declaration_type not in valid_types:
            return False, f"Nevažeći tip zvanja: {declaration_type}"
        
        # Provjera da su karte prisutne
        if not cards:
            return False, "Nisu navedene karte za zvanje"
        
        # Specifične provjere za različite tipove zvanja
        if declaration_type == 'bela':
            # Bela zahtijeva kralja i damu iste boje
            if len(cards) != 2:
                return False, "Bela zahtijeva točno dvije karte (kralj i dama iste boje)"
            
            # Provjera da su karte kralj i dama
            card_values = [card[0] for card in cards]
            if sorted(card_values) != ['K', 'Q']:
                return False, "Bela zahtijeva kralja i damu"
            
            # Provjera da su iste boje
            card_suits = set(card[1] for card in cards)
            if len(card_suits) != 1:
                return False, "Bela zahtijeva karte iste boje"
            
            # Provjera da je ta boja adut
            suit = list(card_suits)[0]
            trump_suit_mapping = {'spades': 'S', 'hearts': 'H', 'diamonds': 'D', 'clubs': 'C'}
            round_trump = trump_suit_mapping.get(round_obj.trump_suit)
            
            if round_trump != suit:
                return False, "Bela mora biti u adutskoj boji"
        
        elif declaration_type.startswith('four_'):
            # Zvanja s četiri jednake karte
            if len(cards) != 4:
                return False, f"{declaration_type} zahtijeva točno četiri karte"
            
            # Provjera da su sve karte iste vrijednosti
            expected_value = {'four_jacks': 'J', 'four_nines': '9', 'four_aces': 'A',
                             'four_tens': '10', 'four_kings': 'K', 'four_queens': 'Q'}
            
            card_values = [card[0] if len(card) == 2 else card[:2] for card in cards]
            if any(v != expected_value[declaration_type] for v in card_values):
                return False, f"{declaration_type} zahtijeva četiri karte vrijednosti {expected_value[declaration_type]}"
            
            # Provjera da su sve četiri boje zastupljene
            card_suits = [card[-1] for card in cards]
            if set(card_suits) != {'S', 'H', 'D', 'C'}:
                return False, f"{declaration_type} zahtijeva po jednu kartu od svake boje"
        
        elif declaration_type.startswith('sequence_'):
            # Zvanja za sekvence (niz karata iste boje)
            seq_length = int(declaration_type.split('_')[1])
            if len(cards) != seq_length:
                return False, f"{declaration_type} zahtijeva točno {seq_length} karata"
            
            # Provjera da su sve karte iste boje
            card_suits = set(card[-1] for card in cards)
            if len(card_suits) != 1:
                return False, f"{declaration_type} zahtijeva karte iste boje"
            
            # Provjera da čine niz
            card_values = [card[0] if len(card) == 2 else card[:2] for card in cards]
            value_order = {'7': 0, '8': 1, '9': 2, '10': 3, 'J': 4, 'Q': 5, 'K': 6, 'A': 7}
            sorted_values = sorted(card_values, key=lambda v: value_order.get(v, -1))
            
            for i in range(1, len(sorted_values)):
                prev_idx = value_order.get(sorted_values[i-1], -1)
                curr_idx = value_order.get(sorted_values[i], -1)
                
                if curr_idx - prev_idx != 1:
                    return False, f"{declaration_type} zahtijeva karte u nizu"
        
        elif declaration_type == 'belot':
            # Belot zahtijeva 8 karata u nizu iste boje
            if len(cards) != 8:
                return False, "Belot zahtijeva točno 8 karata"
            
            # Provjera da su sve karte iste boje
            card_suits = set(card[-1] for card in cards)
            if len(card_suits) != 1:
                return False, "Belot zahtijeva karte iste boje"
            
            # Provjera da čine niz od 7 do asa
            card_values = [card[0] if len(card) == 2 else card[:2] for card in cards]
            if set(card_values) != {'7', '8', '9', '10', 'J', 'Q', 'K', 'A'}:
                return False, "Belot zahtijeva sve karte od 7 do asa"
        
        return True, ""
    
    @staticmethod
    def compare_declarations(decl1, decl2):
        """
        Uspoređuje dva zvanja prema njihovoj snazi.
        
        Prema pravilima Belota, zvanja se uspoređuju prema bodovnoj vrijednosti.
        Ako su iste vrijednosti, pobjeđuje zvanje čiji je igrač bliži djelitelju.
        
        Args:
            decl1: Prvo zvanje (Declaration)
            decl2: Drugo zvanje (Declaration)
        
        Returns:
            int: 1 ako je prvo zvanje jače, -1 ako je drugo jače, 0 ako su jednaka
        """
        # Usporedba po vrijednosti
        if decl1.value > decl2.value:
            return 1
        elif decl1.value < decl2.value:
            return -1
        
        # Ako su jednake vrijednosti, trebalo bi provjeriti koji je igrač bliži djelitelju
        # Ovo zahtijeva znanje o rasporedu igrača, što bi trebalo biti implementirano
        # u servisnom sloju s više konteksta o igri
        
        return 0  # Privremeno - jednaka zvanja
    
    @staticmethod
    def get_highest_declaration(declarations):
        """
        Vraća najjače zvanje iz liste zvanja.
        
        Args:
            declarations: Lista zvanja (queryset ili lista Declaration objekata)
        
        Returns:
            Declaration: Najjače zvanje ili None ako je lista prazna
        """
        if not declarations:
            return None
        
        highest = declarations[0]
        for decl in declarations[1:]:
            if Declaration.compare_declarations(decl, highest) > 0:
                highest = decl
        
        return highest