#!/usr/bin/env python
"""
Skripta za postavljanje baze podataka za Belot projekt.

Ova skripta izvršava migracije, stvara potrebne tablice i
dodaje osnovne podatke potrebne za testiranje.
"""

import os
import sys
import django
import logging
from django.core.management import call_command

# Postavljanje Django okruženja
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')
django.setup()

# Konfiguracija logging sustava
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Glavna funkcija koja pokreće inicijalizaciju baze podataka."""
    try:
        # Provjera povezivanja s bazom podataka
        from django.db import connections
        from django.db.utils import OperationalError
        
        db_conn = connections['default']
        try:
            db_conn.cursor()
            logger.info("✅ Uspješno povezivanje s bazom podataka")
        except OperationalError:
            logger.error("❌ Greška pri povezivanju s bazom podataka")
            return False
        
        # Izvršavanje migracija
        logger.info("Izvršavam migracije...")
        call_command('migrate')
        logger.info("✅ Migracije uspješno izvršene")
        
        # Provjera jesu li stvorene tablice
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in cursor.fetchall()]
            logger.info(f"Stvorene tablice: {tables}")
        
        # Stvaranje osnovnih testnih podataka
        create_test_data()
        
        logger.info("✅ Postavljanje baze podataka uspješno završeno")
        return True
    
    except Exception as e:
        logger.error(f"❌ Greška pri postavljanju baze podataka: {str(e)}")
        return False

def create_test_data():
    """Stvara osnovne testne podatke u bazi."""
    logger.info("Stvaram testne podatke...")
    
    # Stvaranje testnih korisnika
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Provjeri postoje li već korisnici
    if User.objects.count() == 0:
        logger.info("Stvaram testne korisnike...")
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        for i in range(1, 5):
            User.objects.create_user(
                username=f'player{i}',
                email=f'player{i}@example.com',
                password=f'playerpass{i}'
            )
        
        logger.info(f"✅ Stvoreno {User.objects.count()} testnih korisnika")
    else:
        logger.info(f"✅ Korisnici već postoje ({User.objects.count()})")
    
    # Stvaranje testnih statistika
    try:
        from stats.models import GlobalStats, PlayerStats
        
        # Provjeri postoje li već globalne statistike
        if not GlobalStats.objects.exists():
            logger.info("Stvaram globalnu statistiku...")
            GlobalStats.objects.create()
            logger.info("✅ Stvorena globalna statistika")
        else:
            logger.info("✅ Globalna statistika već postoji")
        
        # Provjeri postoje li statistike igrača
        if PlayerStats.objects.count() < User.objects.count():
            logger.info("Stvaram statistike igrača...")
            for user in User.objects.all():
                if not PlayerStats.objects.filter(user=user).exists():
                    PlayerStats.objects.create(user=user)
            
            logger.info(f"✅ Stvoreno {PlayerStats.objects.count()} statistika igrača")
        else:
            logger.info("✅ Statistike igrača već postoje")
    
    except ImportError:
        logger.warning("⚠️ Modeli statistike nisu dostupni, preskačem stvaranje statistika")
    
    # Stvaranje testne igre
    try:
        from game.models import Game
        
        # Provjeri postoje li već igre
        if Game.objects.count() == 0:
            logger.info("Stvaram testnu igru...")
            users = User.objects.all()
            if users.count() >= 4:
                game = Game.objects.create(
                    name="Test Game",
                    status=Game.STATUS_WAITING,
                    player_a1=users[0],
                    player_a2=users[1],
                    player_b1=users[2],
                    player_b2=users[3]
                )
                logger.info(f"✅ Stvorena testna igra ID={game.id}")
            else:
                logger.warning("⚠️ Nema dovoljno korisnika za stvaranje testne igre")
        else:
            logger.info(f"✅ Igre već postoje ({Game.objects.count()})")
    
    except ImportError:
        logger.warning("⚠️ Modeli igre nisu dostupni, preskačem stvaranje igre")
    
    logger.info("✅ Stvaranje testnih podataka završeno")

if __name__ == "__main__":
    success = main()
    if success:
        sys.exit(0)
    else:
        sys.exit(1) 