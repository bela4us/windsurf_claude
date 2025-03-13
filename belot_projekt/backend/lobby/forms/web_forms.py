"""
Formulari za Django aplikaciju "lobby".

Ovaj modul definira formulare koji se koriste za unos i validaciju podataka
vezanih uz predvorje Belot igre, kao što su stvaranje sobe, slanje poruka
i pozivnica.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Promijenjen import - umjesto relativnog koristi apsolutni
from lobby.models import LobbyRoom, LobbyMessage, LobbyInvitation

User = get_user_model()


class LobbyRoomForm(forms.ModelForm):
    """
    Formular za stvaranje i uređivanje sobe u predvorju.
    """
    
    class Meta:
        model = LobbyRoom
        fields = ['name', 'is_private', 'max_players', 'use_quick_format']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ime sobe'}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_players': forms.Select(attrs={'class': 'form-control'}),
            'use_quick_format': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'name': _('Ime sobe'),
            'is_private': _('Privatna soba'),
            'max_players': _('Maksimalni broj igrača'),
            'use_quick_format': _('Brži format (701 bod)')
        }
        help_texts = {
            'is_private': _('Privatnim sobama mogu pristupiti samo pozvani igrači'),
            'use_quick_format': _('Koristi 701 bod za pobjedu umjesto standardnih 1001')
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Postavi izbor za maksimalni broj igrača
        self.fields['max_players'].choices = [(4, '4 igrača')]
        
        # Napravi ovo polje skrivenim jer je Belot uvijek za 4 igrača
        self.fields['max_players'].widget = forms.HiddenInput()
        
        # Postavi zadanu vrijednost
        self.fields['max_players'].initial = 4
    
    def clean_name(self):
        """Validira ime sobe."""
        name = self.cleaned_data.get('name')
        
        # Provjeri da ime nije prazno
        if not name.strip():
            raise ValidationError(_('Ime sobe ne može biti prazno.'))
        
        # Provjeri duljinu imena
        if len(name) < 3:
            raise ValidationError(_('Ime sobe mora imati barem 3 znaka.'))
        
        # Provjeri neprimjereni sadržaj (ovo bi trebalo biti sofisticirano u pravoj aplikaciji)
        forbidden_terms = ['admin', 'moderator', 'sistem', 'system']
        for term in forbidden_terms:
            if term.lower() in name.lower():
                raise ValidationError(_('Ime sobe sadrži zabranjeni izraz.'))
        
        return name


class LobbyMessageForm(forms.ModelForm):
    """
    Formular za slanje poruka u chatu sobe.
    """
    
    class Meta:
        model = LobbyMessage
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Unesite poruku...', 
                'autocomplete': 'off'
            })
        }
        labels = {
            'content': _('Poruka')
        }
    
    def clean_content(self):
        """Validira sadržaj poruke."""
        content = self.cleaned_data.get('content')
        
        # Provjeri da poruka nije prazna
        if not content.strip():
            raise ValidationError(_('Poruka ne može biti prazna.'))
        
        # Provjeri duljinu poruke
        if len(content) > 500:
            raise ValidationError(_('Poruka ne može biti dulja od 500 znakova.'))
        
        # Ovdje bi trebala biti provjera neprimjerenog sadržaja
        
        return content


class LobbyInvitationForm(forms.ModelForm):
    """
    Formular za slanje pozivnica u sobu.
    """
    recipient_username = forms.CharField(
        label=_('Korisničko ime'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Korisničko ime igrača'
        })
    )
    
    class Meta:
        model = LobbyInvitation
        fields = ['message', 'recipient_username']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Dodajte osobnu poruku (opcionalno)',
                'rows': 3
            })
        }
        labels = {
            'message': _('Poruka (opcionalno)')
        }
    
    def clean_recipient_username(self):
        """Validira korisničko ime primatelja."""
        username = self.cleaned_data.get('recipient_username')
        
        try:
            user = User.objects.get(username=username)
            self.recipient = user  # Spremi korisnika za kasnije
        except User.DoesNotExist:
            raise ValidationError(_('Korisnik s tim korisničkim imenom ne postoji.'))
        
        return username
    
    def save(self, commit=True):
        """Sprema pozivnicu s primateljem iz validacije."""
        invitation = super().save(commit=False)
        invitation.recipient = self.recipient
        
        if commit:
            invitation.save()
        
        return invitation


class JoinByCodeForm(forms.Form):
    """
    Formular za pridruživanje sobi putem koda.
    """
    room_code = forms.CharField(
        label=_('Kod sobe'),
        max_length=10,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': 'Unesite kod sobe', 
            'autocomplete': 'off',
            'style': 'text-transform: uppercase; letter-spacing: 3px;'
        })
    )
    
    def clean_room_code(self):
        """Validira kod sobe."""
        room_code = self.cleaned_data.get('room_code', '').strip().upper()
        
        # Provjeri postoji li soba s tim kodom
        try:
            room = LobbyRoom.objects.get(room_code=room_code)
            
            # Provjeri je li soba otvorena
            if room.status == 'closed':
                raise ValidationError(_('Ova soba je zatvorena i ne prima nove igrače.'))
            
            # Provjeri je li soba puna
            if room.status == 'full':
                raise ValidationError(_('Ova soba je puna i ne prima nove igrače.'))
            
            # Spremi sobu za kasnije
            self.room = room
            
        except LobbyRoom.DoesNotExist:
            raise ValidationError(_('Soba s tim kodom ne postoji.'))
        
        return room_code