"""
Serializatori za poteze, runde i zvanja u Belot igri.

Ovaj modul sadrži serializatore koji pretvaraju modele Move, Round i Declaration
u JSON format za API komunikaciju, kao i za deserijalizaciju i validaciju ulaznih
podataka. Ovi serializatori omogućuju praćenje tijeka igre, uključujući poteze
igrača, runde i zvanja.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from game.models import Game, Round, Move, Declaration
from game.serializers.game_serializers import UserSerializer

User = get_user_model()


class MoveSerializer(serializers.ModelSerializer):
    """
    Osnovni serializator za poteze u igri.
    
    Predstavlja jedan potez (igranje karte) u Belot igri.
    """
    player = UserSerializer(read_only=True)
    player_id = serializers.PrimaryKeyRelatedField(
        source='player',
        queryset=User.objects.all(),
        write_only=True
    )
    trick_number = serializers.SerializerMethodField()
    
    class Meta:
        model = Move
        fields = [
            'id', 'round', 'player', 'player_id', 'card', 'order',
            'is_winning', 'is_valid', 'created_at', 'trick_number'
        ]
        read_only_fields = ['id', 'is_winning', 'is_valid', 'created_at', 'trick_number']
    
    def get_trick_number(self, obj):
        """Izračunava broj štiha kojem pripada ovaj potez."""
        return obj.order // 4 if obj.order is not None else None


class MoveCreateSerializer(serializers.ModelSerializer):
    """
    Serializator za stvaranje novog poteza.
    
    Koristi se kada igrač igra kartu tijekom igre.
    """
    player = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Move
        fields = ['round', 'player', 'card']
    
    def validate(self, data):
        """
        Validira da potez poštuje pravila Belota.
        
        Provjerava:
        1. Je li igrač na potezu
        2. Je li karta valjana (format)
        3. Je li potez dozvoljen prema pravilima (prati boju, itd.)
        """
        round_obj = data['round']
        player = data['player']
        card = data['card']
        
        # Provjera je li igrač član igre
        game = round_obj.game
        if not game.players.filter(id=player.id).exists():
            raise serializers.ValidationError("Igrač nije član ove igre.")
        
        # Provjera je li igrač na potezu
        current_player = round_obj.get_current_player()
        if current_player != player:
            raise serializers.ValidationError("Nije tvoj red za potez.")
        
        # Validacija formata karte (npr. "7S", "AH")
        if not card or len(card) < 2:
            raise serializers.ValidationError("Nevažeći format karte.")
        
        # Provjera se radi na razini servisa/repozitorija jer zahtijeva
        # poznavanje karata u rukama igrača i trenutnog stanja igre
        
        return data


class MoveListSerializer(serializers.ModelSerializer):
    """
    Serializator za listu poteza.
    
    Koristi se za prikazivanje povijesti poteza u rundi.
    """
    player = UserSerializer(read_only=True)
    trick_number = serializers.SerializerMethodField()
    
    class Meta:
        model = Move
        fields = ['id', 'player', 'card', 'is_winning', 'order', 'created_at', 'trick_number']
    
    def get_trick_number(self, obj):
        """Izračunava broj štiha kojem pripada ovaj potez."""
        return obj.order // 4 if obj.order is not None else None


class DeclarationSerializer(serializers.ModelSerializer):
    """
    Serializator za zvanja u Belot igri.
    
    Predstavlja zvanja poput bele, četiri dečka, sekvence, itd.
    """
    player = UserSerializer(read_only=True)
    type_display = serializers.SerializerMethodField()
    suit_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Declaration
        fields = [
            'id', 'round', 'player', 'type', 'type_display', 'suit',
            'suit_display', 'cards', 'value', 'created_at'
        ]
        read_only_fields = ['id', 'value', 'created_at', 'type_display', 'suit_display']
    
    def get_type_display(self, obj):
        """Vraća ljudski čitljiv naziv tipa zvanja."""
        return obj.get_type_display()
    
    def get_suit_display(self, obj):
        """Vraća ljudski čitljiv naziv boje zvanja."""
        return obj.get_suit_display() if obj.suit else None


class DeclarationCreateSerializer(serializers.ModelSerializer):
    """
    Serializator za stvaranje novog zvanja.
    
    Koristi se kada igrač prijavljuje zvanje poput bele ili sekvence.
    """
    player = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Declaration
        fields = ['round', 'player', 'type', 'suit', 'cards']
    
    def validate(self, data):
        """
        Validira da zvanje poštuje pravila Belota.
        
        Provjerava:
        1. Je li tip zvanja valjan
        2. Jesu li karte valjane za taj tip zvanja
        3. Je li boja potrebna za određene tipove zvanja
        """
        round_obj = data['round']
        player = data['player']
        declaration_type = data['type']
        cards = data.get('cards', [])
        
        # Provjera je li igrač član igre
        game = round_obj.game
        if not game.players.filter(id=player.id).exists():
            raise serializers.ValidationError("Igrač nije član ove igre.")
        
        # Provjera je li zvanje valjano prema pravilima igre
        from game.services.scoring_service import ScoringService
        is_valid, message = ScoringService.validate_declaration(
            declaration_type, cards, round_obj)
        
        if not is_valid:
            raise serializers.ValidationError(message)
        
        # Provjera boje za zvanja koja je zahtijevaju
        if declaration_type in ['bela', 'sequence_3', 'sequence_4', 'sequence_5_plus', 'belot']:
            if 'suit' not in data or not data['suit']:
                raise serializers.ValidationError("Za ovaj tip zvanja potrebno je navesti boju.")
        
        return data


class RoundSerializer(serializers.ModelSerializer):
    """
    Osnovni serializator za rundu igre.
    
    Sadrži osnovne informacije o jednoj rundi Belot igre.
    """
    dealer = UserSerializer(read_only=True)
    caller = UserSerializer(read_only=True)
    trump_suit_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Round
        fields = [
            'id', 'game', 'number', 'dealer', 'trump_suit', 
            'trump_suit_display', 'calling_team', 'caller',
            'team_a_score', 'team_b_score', 'winner_team',
            'is_completed', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'trump_suit_display', 'team_a_score', 'team_b_score',
            'winner_team', 'is_completed', 'created_at', 'completed_at'
        ]
    
    def get_trump_suit_display(self, obj):
        """Vraća ljudski čitljiv naziv adutske boje."""
        return obj.get_trump_suit_display() if obj.trump_suit else None


class RoundDetailSerializer(serializers.ModelSerializer):
    """
    Detaljni serializator za rundu igre.
    
    Sadrži sve informacije o rundi, uključujući poteze i zvanja.
    """
    dealer = UserSerializer(read_only=True)
    caller = UserSerializer(read_only=True)
    trump_suit_display = serializers.SerializerMethodField()
    moves = MoveListSerializer(many=True, read_only=True)
    declarations = DeclarationSerializer(many=True, read_only=True)
    current_player = serializers.SerializerMethodField()
    tricks = serializers.SerializerMethodField()
    
    class Meta:
        model = Round
        fields = [
            'id', 'game', 'number', 'dealer', 'trump_suit', 'trump_suit_display',
            'calling_team', 'caller', 'team_a_score', 'team_b_score', 'winner_team',
            'is_completed', 'created_at', 'completed_at', 'moves', 'declarations',
            'current_player', 'tricks'
        ]
    
    def get_trump_suit_display(self, obj):
        """Vraća ljudski čitljiv naziv adutske boje."""
        return obj.get_trump_suit_display() if obj.trump_suit else None
    
    def get_current_player(self, obj):
        """Vraća igrača koji je trenutno na potezu."""
        player = obj.get_current_player()
        if player:
            return UserSerializer(player).data
        return None
    
    def get_tricks(self, obj):
        """
        Grupira poteze u štihove za lakši prikaz.
        
        Vraća listu štihova, gdje je svaki štih lista od 4 poteza.
        """
        moves = obj.moves.all().order_by('order')
        tricks = []
        current_trick = []
        
        for move in moves:
            current_trick.append(MoveListSerializer(move).data)
            if len(current_trick) == 4:
                tricks.append(current_trick)
                current_trick = []
        
        # Dodaj i nepotpuni zadnji štih ako postoji
        if current_trick:
            tricks.append(current_trick)
        
        return tricks


class TrickSerializer(serializers.Serializer):
    """
    Serializator za prikaz jednog štiha (4 poteza).
    
    Koristi se za grupiranje poteza u štihove za lakši prikaz i praćenje igre.
    """
    number = serializers.IntegerField()
    moves = MoveListSerializer(many=True)
    winner = UserSerializer(allow_null=True)
    points = serializers.IntegerField()
    
    class Meta:
        fields = ['number', 'moves', 'winner', 'points']