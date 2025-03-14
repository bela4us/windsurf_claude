"""
Serializatori za autentikaciju korisnika u Belot igri.

Ovaj modul sadrži serializatore koji su odgovorni za autentikaciju
korisnika, uključujući registraciju, prijavu, obnavljanje tokena,
resetiranje lozinke i verifikaciju e-mail adrese.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MinLengthValidator, RegexValidator
import re

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializator za registraciju novih korisnika.
    
    Omogućuje korisnicima da se registriraju s korisničkim imenom,
    e-mail adresom i lozinkom.
    """
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'},
        validators=[
            MinLengthValidator(8, message=_("Lozinka mora imati najmanje 8 znakova."))
        ]
    )
    password_confirm = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email': {'required': True}
        }
    
    def validate_email(self, value):
        """Provjera je li e-mail adresa već u upotrebi i je li validna."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(_("Korisnik s ovom e-mail adresom već postoji."))
        
        # Dodatna provjera formata e-maila
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError(_("Unesite valjanu e-mail adresu."))
            
        return value.lower()  # Normalizacija e-maila na mala slova
    
    def validate_username(self, value):
        """Provjera je li korisničko ime već u upotrebi i je li validno."""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(_("Ovo korisničko ime je već zauzeto."))
        
        # Provjera da korisničko ime ne sadrži razmake
        if ' ' in value:
            raise serializers.ValidationError(_("Korisničko ime ne smije sadržavati razmake."))
            
        return value
    
    def validate_password(self, value):
        """Provjera zadovoljava li lozinka sigurnosne zahtjeve."""
        # Dodatne provjere kompleksnosti lozinke
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jednu brojku."))
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jedno veliko slovo."))
        if not any(char.islower() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jedno malo slovo."))
        if not any(char in '!@#$%^&*()_-+={}[]|:;"\'<>,.?/~`' for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jedan poseban znak."))
            
        validate_password(value)
        return value
    
    def validate(self, data):
        """Provjera podudaraju li se lozinke."""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": _("Lozinke se ne podudaraju.")})
        return data
    
    def create(self, validated_data):
        """Stvara novog korisnika s hashiranom lozinkom."""
        # Uklanjamo password_confirm jer nije dio modela
        validated_data.pop('password_confirm')
        
        # Stvaramo korisnika s hashiranom lozinkom
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializator za prijavu korisnika.
    
    Omogućuje korisnicima da se prijave s korisničkim imenom/e-mailom i lozinkom.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'}, write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)
    
    def validate(self, data):
        """Provjera korisničkih podataka za prijavu."""
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            # Prvo pokušaj autentikaciju s e-mailom (case-insensitive)
            try:
                user_obj = User.objects.get(email__iexact=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                # Ako ne postoji korisnik s tim e-mailom, pokušaj s korisničkim imenom
                user = authenticate(username=username, password=password)
            
            if not user:
                # Počekaj kratko da otežaš brute force napade
                import time
                time.sleep(0.5)
                raise serializers.ValidationError(_("Neispravno korisničko ime/e-mail ili lozinka."))
            
            if not user.is_active:
                raise serializers.ValidationError(_("Korisnički račun je deaktiviran."))
        else:
            raise serializers.ValidationError(_("Morate unijeti korisničko ime/e-mail i lozinku."))
        
        # Spremi broj neuspjelih pokušaja prijave
        user.failed_login_attempts = 0  # Resetiraj brojač ako je prijava uspješna
        user.save(update_fields=['failed_login_attempts'])
        
        data['user'] = user
        return data


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializator za resetiranje lozinke.
    
    Omogućuje korisnicima da zatraže resetiranje lozinke putem e-maila.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Provjera postoji li korisnik s navedenom e-mail adresom."""
        if not User.objects.filter(email__iexact=value).exists():
            # Ne otkrivamo da korisnik ne postoji zbog sigurnosti
            # Umjesto toga, pravimo se da je zahtjev uspješan
            return value
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializator za potvrdu resetiranja lozinke.
    
    Koristi se kada korisnik klikne na link za resetiranje lozinke u e-mailu.
    """
    token = serializers.CharField(required=True)
    uid = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True, 
        write_only=True, 
        style={'input_type': 'password'},
        validators=[
            MinLengthValidator(8, message=_("Lozinka mora imati najmanje 8 znakova."))
        ]
    )
    new_password_confirm = serializers.CharField(
        required=True, 
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_new_password(self, value):
        """Provjera zadovoljava li nova lozinka sigurnosne zahtjeve."""
        # Dodatne provjere kompleksnosti lozinke
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jednu brojku."))
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jedno veliko slovo."))
        
        try:
            # Ovdje ćemo dobiti korisnika iz tokena i uid-a kasnije u procesu
            # Za sada preskačemo validaciju s korisnikom
            validate_password(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value
    
    def validate(self, data):
        """Provjera podudaraju li se nove lozinke."""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": _("Lozinke se ne podudaraju.")})
        return data


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializator za promjenu lozinke.
    
    Omogućuje korisnicima da promijene svoju lozinku.
    """
    old_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(
        required=True, 
        style={'input_type': 'password'},
        validators=[
            MinLengthValidator(8, message=_("Lozinka mora imati najmanje 8 znakova."))
        ]
    )
    new_password_confirm = serializers.CharField(required=True, style={'input_type': 'password'})
    
    def validate_old_password(self, value):
        """Provjera je li stara lozinka ispravna."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Stara lozinka nije ispravna."))
        return value
    
    def validate_new_password(self, value):
        """Provjera zadovoljava li nova lozinka sigurnosne zahtjeve."""
        user = self.context['request'].user
        
        # Dodatne provjere kompleksnosti lozinke
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jednu brojku."))
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError(_("Lozinka mora sadržavati barem jedno veliko slovo."))
        
        # Provjera da nova lozinka nije ista kao stara
        if user.check_password(value):
            raise serializers.ValidationError(_("Nova lozinka ne smije biti ista kao stara."))
        
        validate_password(value, user)
        return value
    
    def validate(self, data):
        """Provjera podudaraju li se nove lozinke."""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": _("Lozinke se ne podudaraju.")})
        return data


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializator za obnavljanje pristupnog tokena.
    
    Omogućuje klijentima da obnove pristupni token pomoću refresh tokena.
    """
    refresh_token = serializers.CharField(required=True)
    
    def validate_refresh_token(self, value):
        """Provjera valjanosti refresh tokena."""
        # Implementacija provjere validnosti refresh tokena
        # Ovo će ovisiti o vašoj implementaciji autentikacije (npr. JWT, simple token itd.)
        return value


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializator za verifikaciju e-mail adrese.
    
    Koristi se za verifikaciju e-mail adrese korisnika.
    """
    token = serializers.CharField(required=True)
    
    def validate_token(self, value):
        """Provjera valjanosti tokena za verifikaciju e-maila."""
        # Implementacija provjere validnosti tokena za verifikaciju e-maila
        # Ovo će ovisiti o vašoj implementaciji verifikacije e-maila
        return value


class UserDeviceSerializer(serializers.Serializer):
    """
    Serializator za registraciju korisničkog uređaja za notifikacije.
    
    Koristi se za povezivanje uređaja s korisničkim računom za push notifikacije.
    """
    device_id = serializers.CharField(required=True)
    device_type = serializers.ChoiceField(choices=['android', 'ios', 'web'], required=True)
    push_token = serializers.CharField(required=True)
    app_version = serializers.CharField(required=False)
    
    def validate(self, data):
        """Provjera validnosti podataka o uređaju."""
        # Dodatne validacije po potrebi
        return data 