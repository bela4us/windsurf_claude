"""
Forme za Belot igru.

Ovaj modul definira Django forme koje se koriste za stvaranje
novih igara, pridruživanje igrama i upravljanje igrama.
"""

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from ..models import Game


class GameCreateForm(forms.ModelForm):
    """
    Forma za stvaranje nove igre.
    
    Omogućuje korisniku postavljanje osnovnih parametara igre,
    kao što su privatnost igre i broj bodova potrebnih za pobjedu.
    """
    
    points_to_win = forms.IntegerField(
        label=_('Bodovi za pobjedu'),
        initial=1001,
        validators=[
            MinValueValidator(501, message=_('Minimalan broj bodova je 501')),
            MaxValueValidator(2001, message=_('Maksimalan broj bodova je 2001'))
        ],
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    is_private = forms.BooleanField(
        label=_('Privatna igra'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Game
        fields = ['points_to_win', 'is_private']
        labels = {
            'points_to_win': _('Bodovi za pobjedu'),
            'is_private': _('Privatna igra')
        }
        help_texts = {
            'points_to_win': _('Broj bodova potreban za pobjedu (standard je 1001)'),
            'is_private': _('Ako je označeno, samo pozvani igrači mogu se pridružiti igri')
        }


class GameJoinForm(forms.Form):
    """
    Forma za pridruživanje postojećoj igri.
    
    Omogućuje korisniku pridruživanje igri putem koda sobe.
    """
    
    room_code = forms.CharField(
        label=_('Kod sobe'),
        max_length=8,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Unesite kod sobe za pridruživanje')
        })
    )
    
    game_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    def clean_room_code(self):
        """Validacija koda sobe."""
        room_code = self.cleaned_data.get('room_code')
        
        # Provjeri postoji li igra s tim kodom
        if room_code and not Game.objects.filter(room_code=room_code).exists():
            raise forms.ValidationError(_('Igra s ovim kodom ne postoji'))
            
        # Provjeri je li igra otvorena za pridruživanje
        try:
            game = Game.objects.get(room_code=room_code)
            if game.status not in ['waiting', 'ready']:
                raise forms.ValidationError(_('Igra je već u tijeku ili je završena'))
                
            if game.players.count() >= 4:
                raise forms.ValidationError(_('Igra je popunjena'))
                
        except Game.DoesNotExist:
            pass
            
        return room_code