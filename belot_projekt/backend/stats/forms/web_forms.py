"""
Formulari za Django aplikaciju "stats".

Ovaj modul definira formulare koji se koriste za filtriranje i prikaz statistika,
kao i za administrativne funkcije vezane uz statistiku.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()


class DateRangeFilterForm(forms.Form):
    """
    Formular za filtriranje statistika po vremenskom razdoblju.
    """
    start_date = forms.DateField(
        label=_('Početni datum'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        label=_('Završni datum'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def clean(self):
        """Validira da je početni datum prije završnog."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError(_('Početni datum mora biti prije završnog.'))
        
        return cleaned_data


class UserStatsFilterForm(forms.Form):
    """
    Formular za filtriranje statistika po korisniku.
    """
    username = forms.CharField(
        label=_('Korisničko ime'),
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Unesite korisničko ime')
        })
    )
    
    def clean_username(self):
        """Validira da korisnik postoji."""
        username = self.cleaned_data.get('username')
        
        if username:
            try:
                User.objects.get(username=username)
            except User.DoesNotExist:
                raise forms.ValidationError(_('Korisnik s tim korisničkim imenom ne postoji.'))
        
        return username


class LeaderboardFilterForm(forms.Form):
    """
    Formular za filtriranje ljestvice najboljih.
    """
    TYPE_CHOICES = [
        ('wins', _('Pobjede')),
        ('games', _('Broj odigranih igara')),
        ('win_rate', _('Postotak pobjeda')),
        ('avg_score', _('Prosječni bodovi'))
    ]
    
    PERIOD_CHOICES = [
        ('all', _('Svih vremena')),
        ('month', _('Ovaj mjesec')),
        ('week', _('Ovaj tjedan')),
        ('day', _('Danas'))
    ]
    
    type = forms.ChoiceField(
        label=_('Tip ljestvice'),
        choices=TYPE_CHOICES,
        initial='wins',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    period = forms.ChoiceField(
        label=_('Razdoblje'),
        choices=PERIOD_CHOICES,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    limit = forms.IntegerField(
        label=_('Broj rezultata'),
        min_value=5,
        max_value=100,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )