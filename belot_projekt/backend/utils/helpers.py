"""
Pomoćne funkcije za Belot aplikaciju.

Ovaj modul sadrži različite pomoćne funkcije koje se mogu koristiti
u različitim dijelovima aplikacije. Funkcije su općenite prirode
i nisu specifične za pojedine aplikacijske module.
"""

import json
import random
import re
import string
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, TypeVar, cast

import shortuuid
from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _


def generate_unique_code(length: int = 6, prefix: str = '', suffix: str = '') -> str:
    """
    Generira jedinstveni alfanumerički kod određene duljine.
    
    Args:
        length: Duljina koda (zadano: 6)
        prefix: Prefiks koji se dodaje na početak koda
        suffix: Sufiks koji se dodaje na kraj koda
    
    Returns:
        Jedinstveni alfanumerički kod
    """
    # Koristi samo velika slova i brojeve za čitljivost
    characters = string.ascii_uppercase + string.digits
    
    # Generiraj slučajni kod
    code = ''.join(random.choices(characters, k=length))
    
    # Dodaj prefiks i sufiks
    return f"{prefix}{code}{suffix}"


def format_time_ago(dt: datetime) -> str:
    """
    Formatira prošlo vrijeme u ljudski čitljiv oblik.
    
    Npr. "prije 5 minuta", "prije 2 sata", "jučer", "prije 3 dana"
    
    Args:
        dt: Vrijeme koje se formatira
    
    Returns:
        Formatirani string s vremenom
    """
    now = timezone.now()
    diff = now - dt
    
    # Konvertiramo u sekunde
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return _("upravo sada")
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return _("prije {0} minuta").format(minutes) if minutes > 1 else _("prije 1 minute")
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return _("prije {0} sati").format(hours) if hours > 1 else _("prije 1 sat")
    elif seconds < 172800:
        return _("jučer")
    elif seconds < 604800:
        days = int(seconds // 86400)
        return _("prije {0} dana").format(days)
    elif seconds < 2592000:
        weeks = int(seconds // 604800)
        return _("prije {0} tjedana").format(weeks) if weeks > 1 else _("prije 1 tjedan")
    elif seconds < 31536000:
        months = int(seconds // 2592000)
        return _("prije {0} mjeseci").format(months) if months > 1 else _("prije 1 mjesec")
    else:
        years = int(seconds // 31536000)
        return _("prije {0} godina").format(years) if years > 1 else _("prije 1 godinu")


def get_client_ip(request: HttpRequest) -> str:
    """
    Dohvaća IP adresu klijenta iz zahtjeva.
    
    Podržava i proxy/load balancer scenarije.
    
    Args:
        request: Django HTTP zahtjev
    
    Returns:
        IP adresa klijenta
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Uzmemo prvu IP adresu iz X-Forwarded-For zaglavlja
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def truncate_string(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Skraćuje tekst na zadanu duljinu i dodaje sufiks.
    
    Args:
        text: Tekst koji se skraćuje
        max_length: Maksimalna duljina teksta
        suffix: Sufiks koji se dodaje na kraj skraćenog teksta
    
    Returns:
        Skraćeni tekst
    """
    if len(text) <= max_length:
        return text
    
    # Osiguraj da ne prekidamo riječ
    truncated = text[:max_length].rsplit(' ', 1)[0]
    
    return truncated + suffix


T = TypeVar('T')

def safe_json_loads(json_str: str, default: T = None) -> Union[Any, T]:
    """
    Sigurno parsira JSON string, vraća zadanu vrijednost u slučaju greške.
    
    Args:
        json_str: JSON string koji se parsira
        default: Zadana vrijednost koja se vraća u slučaju greške
    
    Returns:
        Parsirani JSON objekt ili zadana vrijednost
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def slugify_unicode(text: str) -> str:
    """
    Pretvara unicode tekst u slug (URL-friendly string).
    
    Proširena verzija Django slugify-a koja podržava i hrvatske znakove.
    
    Args:
        text: Tekst koji se pretvara u slug
    
    Returns:
        Slug
    """
    # Napravimo mapping hrvatskih znakova
    hr_map = {
        'č': 'c', 'ć': 'c', 'đ': 'd', 'š': 's', 'ž': 'z',
        'Č': 'C', 'Ć': 'C', 'Đ': 'D', 'Š': 'S', 'Ž': 'Z'
    }
    
    # Zamijenimo hrvatske znakove
    for char, replacement in hr_map.items():
        text = text.replace(char, replacement)
    
    # Koristimo Django slugify
    return slugify(text)


def generate_uuid() -> str:
    """
    Generira UUID (universally unique identifier).
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def generate_short_uuid() -> str:
    """
    Generira kratki UUID pomoću shortuuid biblioteke.
    
    Returns:
        Kratki UUID string
    """
    return shortuuid.uuid()


def is_valid_uuid(val: str) -> bool:
    """
    Provjerava je li string valjani UUID.
    
    Args:
        val: String koji se provjerava
    
    Returns:
        True ako je string valjani UUID, False inače
    """
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


def extract_digits(text: str) -> str:
    """
    Izvlači samo brojeve iz teksta.
    
    Args:
        text: Tekst iz kojeg se izvlače brojevi
    
    Returns:
        String koji sadrži samo brojeve iz teksta
    """
    return ''.join(filter(str.isdigit, text))


def normalize_phone_number(phone: str) -> str:
    """
    Normalizira telefonski broj u standardni format.
    
    Args:
        phone: Telefonski broj koji se normalizira
    
    Returns:
        Normalizirani telefonski broj
    """
    # Ukloni sve što nije broj
    digits = extract_digits(phone)
    
    # Ako broj počinje s '0', zamijeni ga s međunarodnim prefiksom '385'
    if digits.startswith('0'):
        digits = '385' + digits[1:]
    
    # Ako broj ne počinje s '385', dodaj ga
    if not digits.startswith('385'):
        digits = '385' + digits
    
    return digits


def get_random_sentence(num_words: int = 5) -> str:
    """
    Generira slučajnu rečenicu određene duljine.
    
    Koristi se za generiranje testnih podataka.
    
    Args:
        num_words: Broj riječi u rečenici
    
    Returns:
        Slučajna rečenica
    """
    words = [
        'igra', 'karta', 'belot', 'adut', 'zvanje', 'štih', 'kralj', 'dama',
        'dečko', 'as', 'desetka', 'devetka', 'osmica', 'sedmica', 'igrač',
        'tim', 'pobjednik', 'pravila', 'poeni', 'tref', 'pik', 'herc', 'karo'
    ]
    
    sentence = ' '.join(random.choices(words, k=num_words))
    
    # Prvo slovo veliko i točka na kraju
    return sentence[0].upper() + sentence[1:] + '.'


def is_valid_email(email: str) -> bool:
    """
    Provjerava je li email adresa validna.
    
    Args:
        email: Email adresa koja se provjerava
    
    Returns:
        True ako je email validna, False inače
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def get_hostname(request: HttpRequest) -> str:
    """
    Dohvaća hostname iz zahtjeva.
    
    Args:
        request: Django HTTP zahtjev
    
    Returns:
        Hostname
    """
    return request.get_host().split(':')[0]


def get_full_url(request: HttpRequest) -> str:
    """
    Dohvaća puni URL iz zahtjeva.
    
    Args:
        request: Django HTTP zahtjev
    
    Returns:
        Puni URL
    """
    return request.build_absolute_uri()


def get_base_url(request: HttpRequest) -> str:
    """
    Dohvaća bazni URL iz zahtjeva.
    
    Args:
        request: Django HTTP zahtjev
    
    Returns:
        Bazni URL (protokol + domena)
    """
    return f"{request.scheme}://{request.get_host()}"


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Provjerava snagu lozinke prema zadanim pravilima.
    
    Args:
        password: Lozinka koja se provjerava
    
    Returns:
        Dictionary s rezultatima provjere (valid, errors, score)
    """
    errors: List[str] = []
    
    # Minimalna duljina
    if len(password) < 8:
        errors.append(_("Lozinka mora sadržavati najmanje 8 znakova."))
    
    # Mora sadržavati barem jedan broj
    if not any(c.isdigit() for c in password):
        errors.append(_("Lozinka mora sadržavati barem jedan broj."))
    
    # Mora sadržavati barem jedno veliko slovo
    if not any(c.isupper() for c in password):
        errors.append(_("Lozinka mora sadržavati barem jedno veliko slovo."))
    
    # Mora sadržavati barem jedno malo slovo
    if not any(c.islower() for c in password):
        errors.append(_("Lozinka mora sadržavati barem jedno malo slovo."))
    
    # Mora sadržavati barem jedan specijalni znak
    special_chars = set('@#$%^&+=!?')
    if not any(c in special_chars for c in password):
        errors.append(_("Lozinka mora sadržavati barem jedan specijalni znak (@#$%^&+=!?)."))
    
    # Izračunaj score (0-5)
    score = 5 - len(errors)
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'score': max(0, score)
    }