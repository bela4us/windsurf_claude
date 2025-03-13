"""
Formulari za Django aplikaciju "users".

Ovaj modul definira formulare za rad s korisničkim podacima,
uključujući registraciju, prijavu, promjenu lozinke, uređivanje
profila i druge korisničke akcije.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, PasswordResetForm
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from ..models import Profile, Friendship

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Prilagođeni formular za registraciju novih korisnika.
    
    Proširuje standardni Django UserCreationForm s dodatnim
    poljima specifičnim za Belot aplikaciju.
    """
    
    email = forms.EmailField(
        label=_('Email adresa'),
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email adresa'})
    )
    first_name = forms.CharField(
        label=_('Ime'),
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ime'})
    )
    last_name = forms.CharField(
        label=_('Prezime'),
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prezime'})
    )
    nickname = forms.CharField(
        label=_('Nadimak'),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nadimak u igri'})
    )
    date_of_birth = forms.DateField(
        label=_('Datum rođenja'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'YYYY-MM-DD'
        })
    )
    agree_terms = forms.BooleanField(
        label=_('Prihvaćam uvjete korištenja'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'nickname', 'date_of_birth', 'password1', 'password2',
            'agree_terms'
        )
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Korisničko ime'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prilagodi help_text za username polje
        self.fields['username'].help_text = _('Potrebno 4-30 znakova. Dozvoljena slova, brojevi i @/./+/-/_.')
        
        # Prilagodi help_text za password polja
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Lozinka'
        })
        self.fields['password1'].help_text = _('Lozinka mora sadržavati najmanje 8 znakova.')
        
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Potvrda lozinke'
        })
    
    def clean_email(self):
        """Provjerava jedinstvenost email adrese."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_('Korisnik s ovom email adresom već postoji.'))
        return email
    
    def clean_username(self):
        """Dodatne provjere za korisničko ime."""
        username = self.cleaned_data.get('username')
        
        # Provjeri duljinu
        if len(username) < 4:
            raise ValidationError(_('Korisničko ime mora imati najmanje 4 znaka.'))
        
        # Provjeri neprimjereni sadržaj (trebalo bi biti sofisticirano u produkciji)
        forbidden_usernames = ['admin', 'administrator', 'mod', 'moderator', 'system']
        if username.lower() in forbidden_usernames:
            raise ValidationError(_('Ovo korisničko ime nije dopušteno.'))
        
        return username


class CustomAuthenticationForm(AuthenticationForm):
    """
    Prilagođeni formular za prijavu korisnika.
    
    Proširuje standardni Django AuthenticationForm s prilagođenim
    widgetima i validacijom.
    """
    
    username = forms.CharField(
        label=_('Korisničko ime ili email'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Korisničko ime ili email'
        })
    )
    password = forms.CharField(
        label=_('Lozinka'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Lozinka'
        })
    )
    remember_me = forms.BooleanField(
        label=_('Zapamti me'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Prilagođeni formular za promjenu lozinke.
    
    Proširuje standardni Django PasswordChangeForm s prilagođenim
    widgetima i validacijom.
    """
    
    old_password = forms.CharField(
        label=_('Trenutna lozinka'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Trenutna lozinka'
        })
    )
    new_password1 = forms.CharField(
        label=_('Nova lozinka'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nova lozinka'
        })
    )
    new_password2 = forms.CharField(
        label=_('Potvrda nove lozinke'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Potvrda nove lozinke'
        })
    )


class CustomPasswordResetForm(PasswordResetForm):
    """
    Prilagođeni formular za resetiranje lozinke.
    
    Proširuje standardni Django PasswordResetForm s prilagođenim
    widgetima i validacijom.
    """
    
    email = forms.EmailField(
        label=_('Email adresa'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email adresa'
        })
    )


class UserProfileForm(forms.ModelForm):
    """
    Formular za uređivanje osnovnih korisničkih podataka.
    
    Omogućuje ažuriranje osnovnih podataka korisničkog računa.
    """
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'nickname', 'email', 'bio', 'date_of_birth', 'avatar')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control-file'})
        }
    
    def clean_email(self):
        """Provjerava jedinstvenost email adrese pri ažuriranju."""
        email = self.cleaned_data.get('email')
        # Provjeri jedinstvenost email adrese, ignorirajući trenutnog korisnika
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_('Korisnik s ovom email adresom već postoji.'))
        return email


class ProfileSettingsForm(forms.ModelForm):
    """
    Formular za uređivanje postavki korisničkog profila.
    
    Omogućuje ažuriranje postavki igre, zvuka i vizualnih preferencija.
    """
    
    class Meta:
        model = Profile
        fields = (
            'preferred_game_type', 'preferred_card_deck',
            'sound_enabled', 'music_enabled', 'animation_speed',
            'language', 'auto_ready', 'show_game_tips'
        )
        widgets = {
            'preferred_game_type': forms.Select(attrs={'class': 'form-control'}),
            'preferred_card_deck': forms.Select(attrs={'class': 'form-control'}),
            'sound_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'music_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'animation_speed': forms.Select(attrs={'class': 'form-control'}),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'auto_ready': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_game_tips': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class PrivacySettingsForm(forms.ModelForm):
    """
    Formular za uređivanje postavki privatnosti.
    
    Omogućuje ažuriranje postavki privatnosti i obavijesti.
    """
    
    class Meta:
        model = User
        fields = (
            'is_profile_public', 'show_online_status',
            'receive_email_notifications', 'receive_game_invites',
            'receive_friend_requests'
        )
        widgets = {
            'is_profile_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_online_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_game_invites': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_friend_requests': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class FriendRequestForm(forms.ModelForm):
    """
    Formular za slanje zahtjeva za prijateljstvo.
    """
    
    class Meta:
        model = Friendship
        fields = ['receiver']
        widgets = {
            'receiver': forms.HiddenInput()
        }
    
    def clean(self):
        """Dodatne provjere za zahtjev za prijateljstvo."""
        cleaned_data = super().clean()
        sender = self.instance.sender
        receiver = cleaned_data.get('receiver')
        
        # Provjeri da korisnik ne šalje zahtjev samom sebi
        if sender == receiver:
            raise ValidationError(_('Ne možete poslati zahtjev za prijateljstvo sami sebi.'))
        
        # Provjeri postojeće prijateljstvo ili zahtjev
        existing = Friendship.objects.filter(
            (models.Q(sender=sender, receiver=receiver) | 
             models.Q(sender=receiver, receiver=sender))
        ).first()
        
        if existing:
            if existing.status == 'accepted':
                raise ValidationError(_('Već ste prijatelji s ovim korisnikom.'))
            elif existing.status == 'pending':
                raise ValidationError(_('Zahtjev za prijateljstvo je već poslan.'))
            elif existing.status == 'blocked':
                raise ValidationError(_('Ne možete poslati zahtjev ovom korisniku.'))
        
        return cleaned_data


class SearchUsersForm(forms.Form):
    """
    Formular za pretraživanje korisnika.
    """
    
    query = forms.CharField(
        label=_('Pretraži korisnike'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pretraži po korisničkom imenu ili nadimku'
        })
    )
    
    show_only_online = forms.BooleanField(
        label=_('Prikaži samo online korisnike'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    sort_by = forms.ChoiceField(
        label=_('Sortiraj po'),
        choices=[
            ('username', _('Korisničko ime')),
            ('rating', _('Rejting')),
            ('games_played', _('Broj igara')),
            ('date_joined', _('Datum registracije'))
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )