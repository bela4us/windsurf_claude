"""
Serializatori za User model i povezane entitete u Belot igri.

Ovaj modul sadrži serializatore koji su odgovorni za pretvaranje
User modela i povezanih podataka u JSON format za API komunikaciju,
kao i za validaciju ulaznih podataka kod stvaranja i ažuriranja korisnika.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, F, Q, Avg
from django.core.validators import MinLengthValidator, RegexValidator

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Osnovni serializator za korisničke podatke.
    
    Sadrži samo osnovne informacije o korisniku koje su potrebne
    u većini konteksta (npr. prikaz u listi igrača, prikaz u igri).
    """
    win_rate = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'display_name',
            'avatar', 'elo_rating', 'total_games', 'games_won', 'win_rate'
        ]
        read_only_fields = fields
    
    def get_win_rate(self, obj):
        """Izračunava postotak pobjeda za korisnika."""
        if obj.total_games > 0:
            return round((obj.games_won / obj.total_games) * 100, 1)
        return 0
    
    def get_display_name(self, obj):
        """Vraća ime za prikaz (puno ime ako postoji, inače korisničko ime)."""
        full_name = obj.get_full_name()
        return full_name if full_name.strip() else obj.username


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detaljni serializator za korisničke podatke.
    
    Sadrži sve informacije o korisniku koje su dostupne
    za prikaz na profilu korisnika.
    """
    win_rate = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name',
            'avatar', 'bio', 'date_of_birth', 'date_joined', 'is_online',
            'elo_rating', 'total_games', 'games_won', 'win_rate',
            'theme_preference', 'email_notifications'
        ]
        read_only_fields = [
            'id', 'username', 'email', 'date_joined', 'is_online',
            'elo_rating', 'total_games', 'games_won', 'win_rate'
        ]
    
    def get_win_rate(self, obj):
        """Izračunava postotak pobjeda za korisnika."""
        if obj.total_games > 0:
            return round((obj.games_won / obj.total_games) * 100, 1)
        return 0
    
    def get_display_name(self, obj):
        """Vraća ime za prikaz (puno ime ako postoji, inače korisničko ime)."""
        full_name = obj.get_full_name()
        return full_name if full_name.strip() else obj.username
    
    def get_is_online(self, obj):
        """Provjerava je li korisnik trenutno online."""
        # Ova implementacija će ovisiti o vašem sustavu za praćenje online statusa
        # Ovdje je pojednostavljena verzija koja uvijek vraća False
        return False


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializator za stvaranje novog korisnika.
    
    Koristi se za registraciju novih korisnika.
    """
    password = serializers.CharField(
        write_only=True, 
        style={'input_type': 'password'},
        validators=[
            MinLengthValidator(8, message="Lozinka mora imati najmanje 8 znakova.")
        ]
    )
    password_confirm = serializers.CharField(
        write_only=True, 
        style={'input_type': 'password'}
    )
    username = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r'^[\w.@+-]+$',
                message="Korisničko ime može sadržavati samo slova, brojeve i znakove @/./+/-/_."
            )
        ]
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name'
        ]
        extra_kwargs = {
            'email': {'required': True}
        }
    
    def validate_username(self, value):
        """Provjera je li korisničko ime već zauzeto."""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ovo korisničko ime je već zauzeto.")
        return value
    
    def validate_email(self, value):
        """Provjera je li email već zauzet."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Korisnik s ovom e-mail adresom već postoji.")
        return value
    
    def validate(self, data):
        """Provjera podudaraju li se lozinke."""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Lozinke se ne podudaraju."})
        return data
    
    def create(self, validated_data):
        """Stvara novog korisnika s hashiranom lozinkom."""
        # Uklanjamo password_confirm jer nije dio modela
        validated_data.pop('password_confirm')
        
        # Stvaramo korisnika s hashiranom lozinkom
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializator za ažuriranje korisničkih podataka.
    
    Omogućuje korisniku da ažurira svoje osobne podatke i postavke.
    """
    current_password = serializers.CharField(
        write_only=True, 
        required=False,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'avatar', 'bio', 
            'date_of_birth', 'theme_preference', 'email_notifications',
            'current_password'
        ]
    
    def validate_bio(self, value):
        """Provjera duljine biografije."""
        if len(value) > 500:
            raise serializers.ValidationError("Biografija ne smije biti duža od 500 znakova.")
        return value
    
    def validate(self, data):
        """Ako korisnik pokušava promijeniti osjetljive podatke, tražimo trenutnu lozinku."""
        request = self.context.get('request')
        if request and request.user and any(field in data for field in ['email']):
            current_password = data.get('current_password')
            if not current_password:
                raise serializers.ValidationError({"current_password": "Za promjenu osjetljivih podataka potrebna je trenutna lozinka."})
            if not request.user.check_password(current_password):
                raise serializers.ValidationError({"current_password": "Netočna lozinka."})
        
        # Uklanjamo current_password iz validated_data ako postoji
        if 'current_password' in data:
            data.pop('current_password')
            
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializator za korisničke profile.
    
    Sadrži informacije koje se prikazuju na profilu korisnika.
    """
    win_rate = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    activity_level = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'display_name',
            'avatar', 'bio', 'date_joined',
            'elo_rating', 'total_games', 'games_won', 'win_rate',
            'activity_level'
        ]
        read_only_fields = fields
    
    def get_win_rate(self, obj):
        """Izračunava postotak pobjeda za korisnika."""
        if obj.total_games > 0:
            return round((obj.games_won / obj.total_games) * 100, 1)
        return 0
    
    def get_display_name(self, obj):
        """Vraća ime za prikaz (puno ime ako postoji, inače korisničko ime)."""
        full_name = obj.get_full_name()
        return full_name if full_name.strip() else obj.username
    
    def get_activity_level(self, obj):
        """Vraća razinu aktivnosti korisnika (visoka, srednja, niska)."""
        # Logika za određivanje razine aktivnosti temeljem broja odigranih igara u posljednjih X dana
        # Ovo je pojednostavljena implementacija
        if obj.total_games > 100:
            return "visoka"
        elif obj.total_games > 20:
            return "srednja"
        else:
            return "niska"


class UserStatsSerializer(serializers.ModelSerializer):
    """
    Serializator za korisničke statistike.
    
    Sadrži statistike o igrama korisnika.
    """
    win_rate = serializers.SerializerMethodField()
    avg_points_per_game = serializers.SerializerMethodField()
    highest_score = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'elo_rating', 
            'total_games', 'games_won', 'win_rate',
            'avg_points_per_game', 'highest_score', 'rank'
        ]
        read_only_fields = fields
    
    def get_win_rate(self, obj):
        """Izračunava postotak pobjeda za korisnika."""
        if obj.total_games > 0:
            return round((obj.games_won / obj.total_games) * 100, 1)
        return 0
    
    def get_avg_points_per_game(self, obj):
        """Izračunava prosječne bodove po igri."""
        # Implementacija će ovisiti o strukturi podataka u vašem modelu
        # Ovo je pojednostavljena verzija koja vraća fiksan broj
        return 162
    
    def get_highest_score(self, obj):
        """Vraća najviši ikad postignuti rezultat."""
        # Implementacija će ovisiti o strukturi podataka u vašem modelu
        # Ovo je pojednostavljena verzija koja vraća fiksan broj
        return 1001
    
    def get_rank(self, obj):
        """Vraća rang korisnika na ljestvici."""
        # Implementacija će ovisiti o izračunu ranga u vašem sustavu
        # Ovo je pojednostavljena verzija koja koristi elo_rating
        higher_rated_count = User.objects.filter(elo_rating__gt=obj.elo_rating).count()
        return higher_rated_count + 1


class UserPreferencesSerializer(serializers.ModelSerializer):
    """
    Serializator za korisničke postavke.
    
    Omogućuje korisniku da ažurira svoje postavke.
    """
    class Meta:
        model = User
        fields = [
            'theme_preference', 
            'email_notifications',
            # Dodajte ostale postavke po potrebi
        ]
        
    def validate(self, data):
        """Provjera validnosti postavki."""
        if 'theme_preference' in data and data['theme_preference'] not in ['light', 'dark', 'system']:
            raise serializers.ValidationError({"theme_preference": "Nevažeća tema. Odaberite između 'light', 'dark' ili 'system'."})
        return data 