"""
Celery zadaci za Django aplikaciju "users".

Ovaj modul definira asinkrone zadatke koji se izvršavaju u pozadini
za operacije vezane uz korisnike, poput slanja e-mailova i provjere postignuća.
"""

from celery import shared_task

@shared_task
def send_verification_email(user_id):
    """
    Zadatak koji šalje e-mail za verifikaciju korisničkog računa.
    
    Args:
        user_id: ID korisnika kojem se šalje e-mail.
    """
    # Stvarna implementacija bi dohvatila korisnika i poslala e-mail
    print(f"Simulacija slanja verifikacijskog e-maila korisniku {user_id}")
    return True

@shared_task
def check_achievements_for_user(user_id):
    """
    Zadatak koji provjerava je li korisnik ostvario nova postignuća.
    
    Args:
        user_id: ID korisnika za kojeg se provjeravaju postignuća.
    """
    # Stvarna implementacija bi dohvatila korisnika i njegove statistike,
    # te provjerila uvjete za postignuća
    print(f"Simulacija provjere postignuća za korisnika {user_id}")
    return True 