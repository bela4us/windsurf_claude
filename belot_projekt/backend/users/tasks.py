"""
Asinkroni zadaci za Django aplikaciju "users".

Ovaj modul implementira Celery zadatke koji se izvršavaju u pozadini,
poput slanja emailova za verifikaciju, provjere postignuća, čišćenja
starih podataka i sl.
"""

import logging
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext as _
from celery import shared_task
from datetime import timedelta

from .models import Profile, Notification, Achievement, UserAchievement, Friendship

User = get_user_model()
logger = logging.getLogger('users.tasks')


@shared_task
def send_verification_email(user_id):
    """
    Šalje email za verifikaciju korisničkog računa.
    
    Args:
        user_id: ID korisnika kojem se šalje email
    """
    try:
        user = User.objects.get(id=user_id)
        
        if not user.is_email_verified and user.verification_token:
            # Ovdje bi poslali email (u pravoj implementaciji)
            logger.info(f"Poslao bih email za verifikaciju korisniku {user.username} na {user.email}")
            
            # U pravoj implementaciji, koristili bismo Django email backend
            # from django.core.mail import send_mail
            # send_mail(
            #     'Verifikacija email adrese',
            #     f'Poštovani {user.username},\n\n'
            #     f'Molimo vas da kliknete na sljedeći link kako biste verificirali svoju email adresu:\n'
            #     f'https://belot.example.com/verify-email/{user.verification_token}\n\n'
            #     f'S poštovanjem,\nVaš Belot tim',
            #     'noreply@belot.example.com',
            #     [user.email],
            #     fail_silently=False,
            # )
    except User.DoesNotExist:
        logger.error(f"Pokušaj slanja verifikacijskog emaila nepostojećem korisniku ID={user_id}")


@shared_task
def send_password_reset_email(user_id):
    """
    Šalje email za resetiranje lozinke.
    
    Args:
        user_id: ID korisnika kojem se šalje email
    """
    try:
        user = User.objects.get(id=user_id)
        
        if user.verification_token:
            # Ovdje bi poslali email (u pravoj implementaciji)
            logger.info(f"Poslao bih email za resetiranje lozinke korisniku {user.username} na {user.email}")
            
            # U pravoj implementaciji, koristili bismo Django email backend
            # from django.core.mail import send_mail
            # send_mail(
            #     'Resetiranje lozinke',
            #     f'Poštovani {user.username},\n\n'
            #     f'Zaprimili smo zahtjev za resetiranje Vaše lozinke. Kliknite na sljedeći link kako biste postavili novu lozinku:\n'
            #     f'https://belot.example.com/reset-password/{user.verification_token}\n\n'
            #     f'S poštovanjem,\nVaš Belot tim',
            #     'noreply@belot.example.com',
            #     [user.email],
            #     fail_silently=False,
            # )
    except User.DoesNotExist:
        logger.error(f"Pokušaj slanja emaila za resetiranje lozinke nepostojećem korisniku ID={user_id}")


@shared_task
def check_achievements_for_user(user_id):
    """
    Provjerava i dodjeljuje postignuća za korisnika.
    
    Provjerava je li korisnik ispunio uvjete za nova postignuća
    i dodjeljuje ih ako jesu.
    
    Args:
        user_id: ID korisnika za kojeg se provjeravaju postignuća
    """
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile
        
        # Dohvati sva postignuća koja korisnik još nema
        unlocked_achievement_ids = UserAchievement.objects.filter(
            user=profile
        ).values_list('achievement_id', flat=True)
        
        available_achievements = Achievement.objects.exclude(
            id__in=unlocked_achievement_ids
        )
        
        # Provjeri svako postignuće
        for achievement in available_achievements:
            if _check_achievement_conditions(user, achievement):
                # Dodijeli postignuće
                UserAchievement.objects.create(
                    user=profile,
                    achievement=achievement
                )
                
                # Stvori obavijest
                Notification.objects.create(
                    user=user,
                    notification_type='achievement',
                    title=_('Novo postignuće!'),
                    message=f'Otključali ste postignuće: {achievement.name}',
                    related_object_id=str(achievement.id)
                )
                
                logger.info(f"Korisnik {user.username} je otključao postignuće: {achievement.name}")
        
    except User.DoesNotExist:
        logger.error(f"Pokušaj provjere postignuća za nepostojećeg korisnika ID={user_id}")


def _check_achievement_conditions(user, achievement):
    """
    Provjerava je li korisnik ispunio uvjete za postignuće.
    
    Args:
        user: Korisnik za kojeg se provjerava
        achievement: Postignuće koje se provjerava
        
    Returns:
        bool: True ako je korisnik ispunio uvjete, False inače
    """
    # Ovisno o tipu postignuća
    if achievement.achievement_type == 'games_played':
        return user.games_played >= achievement.threshold
    
    elif achievement.achievement_type == 'games_won':
        return user.games_won >= achievement.threshold
    
    elif achievement.achievement_type == 'perfect_games':
        # Trebalo bi dohvatiti podatke iz Game modela
        # Za sad vraćamo False
        return False
    
    elif achievement.achievement_type == 'win_streak':
        # Trebalo bi dohvatiti podatke iz Game modela
        # Za sad vraćamo False
        return False
    
    elif achievement.achievement_type == 'rating':
        return user.rating >= achievement.threshold
    
    # Posebna postignuća
    elif achievement.achievement_type == 'first_login':
        return True  # Uvijek se dodjeljuje pri prvoj prijavi
    
    elif achievement.achievement_type == 'profile_complete':
        # Provjeri je li profil potpun
        return (
            user.first_name and 
            user.last_name and 
            user.nickname and 
            user.bio and 
            user.avatar and 
            user.date_of_birth
        )
    
    # Zadani slučaj
    return False


@shared_task
def check_achievement_for_users(achievement_id):
    """
    Provjerava postignuće za sve korisnike.
    
    Korisno kada se doda novo postignuće koje treba provjeriti za sve korisnike.
    
    Args:
        achievement_id: ID postignuća koje se provjerava
    """
    try:
        achievement = Achievement.objects.get(id=achievement_id)
        
        # Dohvati sve korisnike koji nemaju ovo postignuće
        users_with_achievement = UserAchievement.objects.filter(
            achievement=achievement
        ).values_list('user__user_id', flat=True)
        
        users_without_achievement = User.objects.exclude(
            id__in=users_with_achievement
        )
        
        # Provjeri za svakog korisnika
        for user in users_without_achievement:
            if _check_achievement_conditions(user, achievement):
                # Dodijeli postignuće
                UserAchievement.objects.create(
                    user=user.profile,
                    achievement=achievement
                )
                
                # Stvori obavijest
                Notification.objects.create(
                    user=user,
                    notification_type='achievement',
                    title=_('Novo postignuće!'),
                    message=f'Otključali ste postignuće: {achievement.name}',
                    related_object_id=str(achievement.id)
                )
                
                logger.info(f"Korisnik {user.username} je otključao postignuće: {achievement.name}")
        
    except Achievement.DoesNotExist:
        logger.error(f"Pokušaj provjere nepostojećeg postignuća ID={achievement_id}")


@shared_task
def clean_expired_tokens():
    """
    Čisti istekle verifikacijske tokene.
    
    Uklanja tokene starije od 48 sati kako bi se spriječilo gomilanje
    neiskorištenih tokena.
    """
    # Definiraj vremenski prag (48 sati)
    threshold = timezone.now() - timedelta(hours=48)
    
    # Dohvati korisnike s tokenima
    users_with_tokens = User.objects.filter(
        verification_token__isnull=False,
        verification_token__ne='',
        last_activity__lt=threshold
    )
    
    # Izbriši tokene
    count = users_with_tokens.update(verification_token='')
    
    logger.info(f"Očišćeno {count} isteklih tokena")


@shared_task
def update_online_status():
    """
    Ažurira online status korisnika.
    
    Označava korisnike kao offline ako nisu bili aktivni u posljednjih 15 minuta.
    """
    # Definiraj vremenski prag (15 minuta)
    threshold = timezone.now() - timedelta(minutes=15)
    
    # Dohvati korisnike koji su označeni kao online ali nisu bili aktivni
    inactive_users = User.objects.filter(
        is_online=True,
        last_activity__lt=threshold
    )
    
    # Označi ih kao offline
    count = inactive_users.update(is_online=False)
    
    logger.info(f"Označeno {count} korisnika kao offline")


@shared_task
def clean_old_notifications():
    """
    Čisti stare obavijesti.
    
    Uklanja pročitane obavijesti starije od 30 dana kako bi se spriječilo
    gomilanje podataka u bazi.
    """
    # Definiraj vremenski prag (30 dana)
    threshold = timezone.now() - timedelta(days=30)
    
    # Izbriši stare pročitane obavijesti
    deleted_count = Notification.objects.filter(
        is_read=True,
        created_at__lt=threshold
    ).delete()[0]
    
    logger.info(f"Izbrisano {deleted_count} starih obavijesti")


@shared_task
def clean_declined_friendships():
    """
    Čisti odbijene zahtjeve za prijateljstvo.
    
    Uklanja odbijene zahtjeve starije od 7 dana kako bi se spriječilo
    gomilanje podataka u bazi.
    """
    # Definiraj vremenski prag (7 dana)
    threshold = timezone.now() - timedelta(days=7)
    
    # Izbriši stare odbijene zahtjeve
    deleted_count = Friendship.objects.filter(
        status='declined',
        updated_at__lt=threshold
    ).delete()[0]
    
    logger.info(f"Izbrisano {deleted_count} starih odbijenih zahtjeva za prijateljstvo")


@shared_task
def send_friend_recommendations(user_id):
    """
    Šalje preporuke za prijatelje korisniku.
    
    Algoritam za preporuke se bazira na zajedničkim prijateljima
    i sličnim statistikama igre.
    
    Args:
        user_id: ID korisnika kojem se šalju preporuke
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Dohvati trenutne prijatelje
        friend_ids = Friendship.objects.filter(
            (Q(sender=user) | Q(receiver=user)),
            status='accepted'
        ).values_list(
            'sender', 'receiver'
        ).distinct()
        
        # Prebaci u flat listu ID-jeva prijatelja
        friend_ids_flat = []
        for sender_id, receiver_id in friend_ids:
            if sender_id != user.id:
                friend_ids_flat.append(sender_id)
            if receiver_id != user.id:
                friend_ids_flat.append(receiver_id)
        
        # Ovdje bi implementirali algoritam za preporuke
        # ...
        
        # Za sad ćemo samo logirat
        logger.info(f"Poslao bih preporuke za prijatelje korisniku {user.username}")
        
    except User.DoesNotExist:
        logger.error(f"Pokušaj slanja preporuka za prijatelje nepostojećem korisniku ID={user_id}")