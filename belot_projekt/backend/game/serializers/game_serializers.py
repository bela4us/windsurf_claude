"""
Serializatori za Game model i povezane entitete u Belot igri.

Ovaj modul sadrži serializatore koji su odgovorni za pretvaranje
Game modela i povezanih podataka u JSON format za API komunikaciju,
kao i za validaciju ulaznih podataka kod stvaranja i ažuriranja igre.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, F, Q

from game.models import Game, Round, Move, Declaration

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializator za osnovne korisničke podatke potrebne u kontekstu igre."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_image']
        read_only_fields = fields


class GameCreateSerializer(serializers.ModelSerializer):
    """
    Serializator za stvaranje nove igre. 
    
    Omogućuje korisniku da postavi osnovne postavke nove igre,
    kao što su privatnost i broj bodova potreban za pobjedu.
    """
    creator = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Game
        fields = ['creator', 'is_private', 'points_to_win']
        
    def validate_points_to_win(self, value):
        """Provjera je li broj bodova za pobjedu valjan."""
        if value < 501 or value > 2001:
            raise serializers.ValidationError("Broj bodova za pobjedu mora biti između 501 i 2001.")
        if value % 10 != 1:  # Mora završavati na 1 (npr. 1001, 701, itd.)
            raise serializers.ValidationError("Broj bodova za pobjedu mora završavati s 1 (npr. 501, 701, 1001).")
        return value
    
    def create(self, validated_data):
        """Stvara novu igru i dodaje kreatora kao prvog igrača."""
        game = Game.objects.create(**validated_data)
        # Dodaj kreatora kao prvog igrača
        game.players.add(validated_data['creator'])
        game.active_players.add(validated_data['creator'])
        return game


class GameListSerializer(serializers.ModelSerializer):
    """
    Serializator za prikaz liste igara.
    
    Sadrži samo osnovne informacije potrebne za prikaz igre u listi.
    """
    creator = UserSerializer(read_only=True)
    player_count = serializers.SerializerMethodField()
    is_joinable = serializers.SerializerMethodField()
    
    class Meta:
        model = Game
        fields = [
            'id', 'room_code', 'creator', 'status', 'created_at',
            'player_count', 'points_to_win', 'is_private', 'is_joinable'
        ]
    
    def get_player_count(self, obj):
        """Vraća broj igrača u igri."""
        return obj.players.count()
    
    def get_is_joinable(self, obj):
        """Provjerava može li se trenutni korisnik pridružiti igri."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Provjera je li igra u statusu čekanja i ima li mjesta
        if obj.status != 'waiting' or obj.players.count() >= 4:
            return False
        
        # Provjera je li korisnik već u igri
        return not obj.players.filter(id=request.user.id).exists()


class RoundSummarySerializer(serializers.ModelSerializer):
    """
    Serializator za sažetak runde u kontekstu igre.
    
    Sadrži osnovne informacije o rundi, ali ne uključuje detalje poteza.
    """
    dealer = UserSerializer(read_only=True)
    caller = UserSerializer(read_only=True)
    
    class Meta:
        model = Round
        fields = [
            'id', 'number', 'dealer', 'trump_suit', 'calling_team',
            'caller', 'team_a_score', 'team_b_score', 'winner_team',
            'is_completed', 'created_at', 'completed_at'
        ]


class GameDetailSerializer(serializers.ModelSerializer):
    """
    Serializator za detaljni prikaz igre.
    
    Sadrži sve relevantne informacije o igri, uključujući igrače i runde.
    """
    creator = UserSerializer(read_only=True)
    players = UserSerializer(many=True, read_only=True)
    active_players = UserSerializer(many=True, read_only=True)
    team_a_players = UserSerializer(many=True, read_only=True)
    team_b_players = UserSerializer(many=True, read_only=True)
    rounds = RoundSummarySerializer(many=True, read_only=True)
    current_round = serializers.SerializerMethodField()
    
    class Meta:
        model = Game
        fields = [
            'id', 'room_code', 'creator', 'status', 'created_at',
            'started_at', 'finished_at', 'players', 'active_players',
            'team_a_players', 'team_b_players', 'team_a_score', 'team_b_score',
            'winner_team', 'points_to_win', 'is_private', 'rounds',
            'current_round'
        ]
    
    def get_current_round(self, obj):
        """Vraća trenutnu rundu igre."""
        current_round = obj.get_current_round()
        if current_round:
            return RoundSummarySerializer(current_round).data
        return None


class GameStateSerializer(serializers.Serializer):
    """
    Serializator za trenutno stanje igre prilagođeno za specifičnog igrača.
    
    Ovaj serializator se koristi za pripremu podataka koji će se poslati
    kroz WebSocket ili API. Prikazuje različite podatke ovisno o igraču koji
    ih dohvaća (npr. različiti igrači vide različite karte).
    """
    game_id = serializers.UUIDField()
    status = serializers.CharField()
    players = serializers.ListField(child=serializers.DictField())
    teams = serializers.DictField()
    scores = serializers.DictField()
    your_team = serializers.CharField(allow_null=True)
    round = serializers.DictField(allow_null=True)
    your_turn = serializers.BooleanField()
    current_trick = serializers.ListField(child=serializers.DictField())
    declarations = serializers.ListField(child=serializers.DictField())
    history = serializers.ListField(child=serializers.DictField())
    your_cards = serializers.ListField(child=serializers.CharField())
    
    def to_representation(self, instance):
        """
        Prilagođavanje prikaza stanja igre ovisno o trenutnom igraču.
        
        Ova metoda se poziva automatski i primjenjuje dodatnu logiku za
        filtriranje podataka koje pojedini igrač smije vidjeti.
        """
        # Instance je već pripremljena struktura od GameRepository.get_game_state_for_player
        return instance


class GameSerializer(serializers.ModelSerializer):
    """
    Osnovni serializator za Game model.
    
    Sadrži osnovna polja koja su relevantna za većinu operacija na Game modelu.
    """
    class Meta:
        model = Game
        fields = [
            'id', 'room_code', 'creator', 'status', 'created_at',
            'started_at', 'finished_at', 'team_a_score', 'team_b_score',
            'winner_team', 'points_to_win', 'is_private'
        ]
        read_only_fields = ['id', 'room_code', 'creator', 'status', 'created_at',
                           'started_at', 'finished_at', 'team_a_score', 'team_b_score',
                           'winner_team']


class GameActionSerializer(serializers.Serializer):
    """
    Serializator za izvršavanje akcija na igri.
    
    Koristi se za obradu različitih akcija koje igrač može izvršiti,
    kao što su pridruživanje igri, napuštanje igre, itd.
    """
    action = serializers.CharField(required=True)
    
    # Dodatna polja koja mogu biti potrebna ovisno o akciji
    card = serializers.CharField(required=False, allow_null=True)
    trump_suit = serializers.CharField(required=False, allow_null=True)
    declaration_type = serializers.CharField(required=False, allow_null=True)
    cards = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_null=True)
    
    def validate_action(self, value):
        """Provjera je li akcija podržana."""
        valid_actions = [
            'join_game', 'leave_game', 'start_game', 'ready',
            'make_move', 'call_trump', 'pass_trump', 'declare', 'bela',
            'chat_message'
        ]
        if value not in valid_actions:
            raise serializers.ValidationError(f"Nepodržana akcija: {value}")
        return value
    
    def validate(self, data):
        """Validacija ovisno o vrsti akcije."""
        action = data.get('action')
        
        # Provjera potrebnih polja za određene akcije
        if action == 'make_move' and 'card' not in data:
            raise serializers.ValidationError("Za akciju 'make_move' potrebno je polje 'card'.")
        elif action == 'call_trump' and 'trump_suit' not in data:
            raise serializers.ValidationError("Za akciju 'call_trump' potrebno je polje 'trump_suit'.")
        elif action == 'declare':
            if 'declaration_type' not in data:
                raise serializers.ValidationError("Za akciju 'declare' potrebno je polje 'declaration_type'.")
            if 'cards' not in data:
                raise serializers.ValidationError("Za akciju 'declare' potrebno je polje 'cards'.")
        elif action == 'chat_message' and 'message' not in data:
            raise serializers.ValidationError("Za akciju 'chat_message' potrebno je polje 'message'.")
        
        return data


class GameJoinSerializer(serializers.Serializer):
    """
    Serializator za pridruživanje igri.
    
    Koristi se za validaciju zahtjeva za pridruživanje igri,
    bilo putem ID-a igre ili koda sobe.
    """
    game_id = serializers.UUIDField(required=False)
    room_code = serializers.CharField(required=False)
    
    def validate(self, data):
        """Provjera je li naveden ID igre ili kod sobe."""
        if 'game_id' not in data and 'room_code' not in data:
            raise serializers.ValidationError("Potrebno je navesti 'game_id' ili 'room_code'.")
        return data


class GameStatisticsSerializer(serializers.Serializer):
    """
    Serializator za statistiku igre.
    
    Prikazuje različite statističke podatke o igrama,
    poput broja odigranih igara, prosječnog trajanja, itd.
    """
    total_games = serializers.IntegerField()
    games_in_progress = serializers.IntegerField()
    completed_games = serializers.IntegerField()
    average_duration = serializers.DurationField()
    average_points = serializers.FloatField()
    most_active_players = serializers.ListField(child=serializers.DictField())
    
    def to_representation(self, instance):
        """Prilagođava prikaz statistike."""
        return instance