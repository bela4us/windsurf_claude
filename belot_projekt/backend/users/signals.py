"""
Signali za Django aplikaciju "users".

Ovaj modul implementira signal handlere koji reagiraju na događaje vezane uz
korisnike, poput stvaranja računa, ažuriranja profila, promjene lozinke i sl.
Signal handleri omogućuju izvršavanje dodatnog koda kao reakciju na te događaje.
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone

from .models import Profile, Notification, Achievement, UserAchievement

User = get_user_model()
logger = logging.getLogger('users.signals')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler koji stvara profil za novog korisnika.
    
    Poziva se nakon stvaranja novog User objekta.
    
    Args:
        sender: Model koji je poslao signal (User)
        instance: Konkretna instanca User modela
        created: Boolean koji označava je li objekt tek stvoren
    """
    if created:
        Profile.objects.create(user=instance)
        logger.info(f"Stvoren novi profil za korisnika {instance.username}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal handler koji sprema profil prilikom spremanja korisnika.
    
    Poziva se nakon spremanja User objekta.
    
    Args:
        sender: Model koji je poslao signal (User)
        instance: Konkretna instanca User modela
    """
    # Provjeri postoji li profil, ako ne, stvori ga
    if not hasattr(instance, 'profile'):
        Profile.objects.create(user=instance)
        logger.info(f"Naknadno stvoren profil za korisnika {instance.username}")
    
    # Spremi profil
    instance.profile.save()


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Signal handler koji se poziva kada se korisnik prijavi.
    
    Ažurira status korisnika i vrijeme posljednje aktivnosti.
    
    Args:
        sender: Klasa koja je poslala signal
        request: HTTP zahtjev
        user: Korisnik koji se prijavio
    """
    user.is_online = True
    user.last_activity = timezone.now()
    user.save(update_fields=['is_online', 'last_activity'])
    
    # Logiraj prijavu
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    logger.info(f"Korisnik {user.username} se prijavio s IP: {ip}, User-Agent: {user_agent}")
    
    # Provjeri postignuća
    check_login_achievements(user)


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Signal handler koji se poziva kada se korisnik odjavi.
    
    Ažurira status korisnika.
    
    Args:
        sender: Klasa koja je poslala signal
        request: HTTP zahtjev
        user: Korisnik koji se odjavio
    """
    if user:
        user.is_online = False
        user.last_activity = timezone.now()
        user.save(update_fields=['is_online', 'last_activity'])
        
        # Logiraj odjavu
        ip = get_client_ip(request)
        logger.info(f"Korisnik {user.username} se odjavio s IP: {ip}")


@receiver(user_login_failed)
def user_login_failed_handler(sender, credentials, request, **kwargs):
    """
    Signal handler koji se poziva kada prijava korisnika ne uspije.
    
    Logiraj neuspješne pokušaje prijave za sigurnosnu analizu.
    
    Args:
        sender: Klasa koja je poslala signal
        credentials: Vjerodajnice koje su korištene za prijavu
        request: HTTP zahtjev
    """
    ip = get_client_ip(request)
    username = credentials.get('username', '<nepoznato>')
    logger.warning(f"Neuspješna prijava za korisnika {username} s IP: {ip}")


@receiver(post_save, sender=Achievement)
def check_achievement_for_all_users(sender, instance, created, **kwargs):
    """
    Signal handler koji provjerava treba li dodijeliti novo postignuće svim korisnicima.
    
    Poziva se nakon stvaranja novog Achievement objekta.
    
    Args:
        sender: Model koji je poslao signal (Achievement)
        instance: Konkretna instanca Achievement modela
        created: Boolean koji označava je li objekt tek stvoren
    """
    if created:
        # Provjeri novo postignuće za sve korisnike
        from .tasks import check_achievement_for_users
        check_achievement_for_users.delay(instance.id)


@receiver(post_save, sender=User)
def check_user_achievements(sender, instance, created, **kwargs):
    """
    Signal handler koji provjerava postignuća za korisnika.
    
    Poziva se nakon spremanja User objekta.
    
    Args:
        sender: Model koji je poslao signal (User)
        instance: Konkretna instanca User modela
        created: Boolean koji označava je li objekt tek stvoren
    """
    if not created:
        # Za postojeće korisnike, provjeri postignuća nakon ažuriranja
        from .tasks import check_achievements_for_user
        check_achievements_for_user.delay(instance.id)


def check_login_achievements(user):
    """
    Provjerava i dodjeljuje postignuća vezana uz prijavu.
    
    Args:
        user: Korisnik za kojeg se provjeravaju postignuća
    """
    # Postignuće za prvi login (ako postoji)
    first_login = Achievement.objects.filter(achievement_type='first_login').first()
    if first_login and not UserAchievement.objects.filter(user__user=user, achievement=first_login).exists():
        UserAchievement.objects.create(user=user.profile, achievement=first_login)
        
        # Stvori obavijest
        Notification.objects.create(
            user=user,
            notification_type='achievement',
            title='Novo postignuće!',
            message=f'Otključali ste postignuće: {first_login.name}'
        )


def get_client_ip(request):
    """
    Dohvaća IP adresu klijenta iz zahtjeva.
    
    Args:
        request: HTTP zahtjev
        
    Returns:
        str: IP adresa klijenta
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


@receiver(pre_save, sender=User)
def handle_email_change(sender, instance, **kwargs):
    """
    Signal handler koji se poziva prije spremanja korisnika.
    
    Ako je promijenjena email adresa, postavlja is_email_verified na False
    i generira novi token za verifikaciju.
    
    Args:
        sender: Model koji je poslao signal (User)
        instance: Konkretna instanca User modela
    """
    try:
        # Dohvati trenutnog korisnika iz baze
        user = User.objects.get(pk=instance.pk)
        
        # Ako je email promijenjen, resetiraj verifikaciju
        if user.email != instance.email:
            import uuid
            import hashlib
            
            instance.is_email_verified = False
            instance.verification_token = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
            
            logger.info(f"Korisnik {instance.username} je promijenio email adresu, resetirana verifikacija")
            
            # Pošalji email za verifikaciju (u pravoj aplikaciji)
            # send_verification_email(instance.email, instance.verification_token)
    except User.DoesNotExist:
        # Ovo je novi korisnik, nema potrebe za provjerom promjene emaila
        pass