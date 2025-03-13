"""
Definicije zadataka za Celery u Belot aplikaciji.

Ovaj modul sadrži opće zadatke koji se izvršavaju asinkrono putem
Celery worker-a. Ovi zadaci obuhvaćaju funkcionalnosti koje su zajedničke
za različite dijelove aplikacije ili zahtijevaju koordinaciju između više
aplikacija.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

# Postavi logger za ovaj modul
logger = logging.getLogger('celery_app.tasks')


@shared_task(name='core.tasks.send_email')
def send_email_task(subject: str, message: str, recipient_list: List[str],
                  html_message: Optional[str] = None, from_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Zadatak za slanje e-mail poruka.
    
    Ovaj zadatak omogućava asinkrono slanje e-mail poruka bez blokiranja
    glavne aplikacije.
    
    Args:
        subject: Naslov e-mail poruke
        message: Tekst poruke (obični tekst)
        recipient_list: Lista e-mail adresa primatelja
        html_message: Opcionalna HTML verzija poruke
        from_email: Opcionalna e-mail adresa pošiljatelja
    
    Returns:
        Dictionary s informacijama o rezultatu slanja
    """
    try:
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        logger.info(f"Šaljem e-mail na {recipient_list}")
        
        # Slanje e-maila
        send_count = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"E-mail uspješno poslan na {send_count} primatelja")
        
        return {
            'status': 'success',
            'send_count': send_count,
            'recipients': recipient_list
        }
        
    except Exception as e:
        logger.error(f"Greška prilikom slanja e-maila: {str(e)}")
        
        return {
            'status': 'error',
            'error': str(e),
            'recipients': recipient_list
        }


@shared_task(name='core.tasks.cleanup_expired_items')
def cleanup_expired_items(max_age_days: int = 30) -> Dict[str, Any]:
    """
    Zadatak za čišćenje isteklih stavki iz baze podataka.
    
    Ovaj zadatak čisti različite privremene i istekle stavke iz baze podataka
    kako bi se održavala optimalna performansa.
    
    Args:
        max_age_days: Maksimalna starost stavki u danima
    
    Returns:
        Dictionary s informacijama o broju obrisanih stavki
    """
    from lobby.models import LobbyRoom, LobbyInvitation, LobbyMessage
    from game.models import Game
    
    cutoff_date = timezone.now() - timedelta(days=max_age_days)
    results = {}
    
    try:
        # Čišćenje starih zatvorenih soba
        with transaction.atomic():
            old_rooms = LobbyRoom.objects.filter(
                status='closed',
                updated_at__lt=cutoff_date,
                game__isnull=True  # Ne briši sobe povezane s igrama
            )
            room_count = old_rooms.count()
            old_rooms.delete()
            results['rooms'] = room_count
            
            logger.info(f"Obrisano {room_count} starih soba")
        
        # Čišćenje isteklih pozivnica
        with transaction.atomic():
            old_invitations = LobbyInvitation.objects.filter(
                status__in=['expired', 'declined'],
                created_at__lt=cutoff_date
            )
            invitation_count = old_invitations.count()
            old_invitations.delete()
            results['invitations'] = invitation_count
            
            logger.info(f"Obrisano {invitation_count} starih pozivnica")
        
        # Čišćenje starih poruka iz zatvorenih soba
        with transaction.atomic():
            old_messages = LobbyMessage.objects.filter(
                room__status='closed',
                created_at__lt=cutoff_date
            )
            message_count = old_messages.count()
            old_messages.delete()
            results['messages'] = message_count
            
            logger.info(f"Obrisano {message_count} starih poruka")
        
        # Čišćenje završenih igara (opcionalno, ovisno o potrebama)
        if settings.CLEANUP_COMPLETED_GAMES:
            with transaction.atomic():
                old_games = Game.objects.filter(
                    status__in=['completed', 'aborted'],
                    updated_at__lt=cutoff_date
                )
                game_count = old_games.count()
                old_games.delete()
                results['games'] = game_count
                
                logger.info(f"Obrisano {game_count} starih igara")
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Greška prilikom čišćenja isteklih stavki: {str(e)}")
        
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='core.tasks.generate_system_report')
def generate_system_report() -> Dict[str, Any]:
    """
    Zadatak za generiranje sistemskog izvještaja.
    
    Generira izvještaj o stanju sustava, uključujući broj aktivnih korisnika,
    igara, soba, korištenje resursa i druge metrike.
    
    Returns:
        Dictionary s informacijama o stanju sustava
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Avg, Sum
    from lobby.models import LobbyRoom
    from game.models import Game
    
    User = get_user_model()
    report = {}
    
    try:
        # Informacije o korisnicima
        report['users'] = {
            'total': User.objects.count(),
            'active_today': User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=1)
            ).count(),
            'active_week': User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'new_today': User.objects.filter(
                date_joined__gte=timezone.now() - timedelta(days=1)
            ).count(),
            'new_week': User.objects.filter(
                date_joined__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }
        
        # Informacije o sobama
        report['lobby'] = {
            'active_rooms': LobbyRoom.objects.exclude(status='closed').count(),
            'rooms_by_status': {
                status: count for status, count in 
                LobbyRoom.objects.values('status').annotate(count=Count('status')).values_list('status', 'count')
            }
        }
        
        # Informacije o igrama
        report['games'] = {
            'active_games': Game.objects.filter(status__in=['waiting', 'in_progress']).count(),
            'completed_today': Game.objects.filter(
                status='completed',
                updated_at__gte=timezone.now() - timedelta(days=1)
            ).count(),
            'completed_week': Game.objects.filter(
                status='completed',
                updated_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'games_by_status': {
                status: count for status, count in 
                Game.objects.values('status').annotate(count=Count('status')).values_list('status', 'count')
            }
        }
        
        # Informacije o sistemu
        report['system'] = {
            'timestamp': timezone.now().isoformat(),
            'memory_usage': get_memory_usage(),
            'disk_usage': get_disk_usage(),
            'cpu_usage': get_cpu_usage(),
        }
        
        # Zapisivanje izvještaja u log
        logger.info(f"Sistemski izvještaj generiran: {report}")
        
        # Opcionalno spremanje izvještaja u bazu ili slanje e-maila
        if settings.SEND_SYSTEM_REPORTS_EMAIL:
            send_email_task.delay(
                subject=f"Belot sistemski izvještaj - {timezone.now().strftime('%Y-%m-%d')}",
                message=f"Sistemski izvještaj: {report}",
                recipient_list=[settings.ADMIN_EMAIL],
            )
        
        return {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Greška prilikom generiranja sistemskog izvještaja: {str(e)}")
        
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def get_memory_usage() -> Dict[str, Any]:
    """
    Dohvaća informacije o korištenju memorije.
    
    Returns:
        Dictionary s informacijama o korištenju memorije
    """
    try:
        # Za Linux
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
            
            # Parsiranje meminfo
            total = int([line for line in meminfo.split('\n') if 'MemTotal' in line][0].split()[1])
            free = int([line for line in meminfo.split('\n') if 'MemFree' in line][0].split()[1])
            available = int([line for line in meminfo.split('\n') if 'MemAvailable' in line][0].split()[1])
            
            return {
                'total': total,
                'free': free,
                'available': available,
                'used_percent': round((total - available) / total * 100, 2)
            }
        
        # Za macOS ili druge platforme
        else:
            import psutil
            memory = psutil.virtual_memory()
            
            return {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'used_percent': memory.percent
            }
    
    except Exception as e:
        logger.error(f"Greška prilikom dohvaćanja informacija o memoriji: {str(e)}")
        return {'error': str(e)}


def get_disk_usage() -> Dict[str, Any]:
    """
    Dohvaća informacije o korištenju diska.
    
    Returns:
        Dictionary s informacijama o korištenju diska
    """
    try:
        import shutil
        
        # Provjeri disk na kojem je projekt
        disk_usage = shutil.disk_usage(settings.BASE_DIR)
        
        return {
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'used_percent': round(disk_usage.used / disk_usage.total * 100, 2)
        }
    
    except Exception as e:
        logger.error(f"Greška prilikom dohvaćanja informacija o disku: {str(e)}")
        return {'error': str(e)}


def get_cpu_usage() -> Dict[str, Any]:
    """
    Dohvaća informacije o korištenju CPU-a.
    
    Returns:
        Dictionary s informacijama o korištenju CPU-a
    """
    try:
        import psutil
        
        # Dohvati CPU korištenje u postotcima
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Dohvati broj CPU jezgri
        cpu_count = psutil.cpu_count()
        
        return {
            'percent': cpu_percent,
            'cores': cpu_count,
            'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    
    except Exception as e:
        logger.error(f"Greška prilikom dohvaćanja informacija o CPU-u: {str(e)}")
        return {'error': str(e)}


@shared_task(name='core.tasks.backup_database')
def backup_database(backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Zadatak za izradu sigurnosne kopije baze podataka.
    
    Napomena: Ovaj zadatak koristi vanjsku skriptu za izradu sigurnosne kopije.
    
    Args:
        backup_dir: Opcionalni direktorij za spremanje sigurnosne kopije
    
    Returns:
        Dictionary s informacijama o statusu sigurnosne kopije
    """
    import subprocess
    import datetime
    
    try:
        # Koristi skriptu za backup koju smo već implementirali
        backup_script = os.path.join(settings.BASE_DIR, 'scripts', 'backup_db.sh')
        
        # Izvrši skriptu
        env = os.environ.copy()
        if backup_dir:
            env['BACKUP_DIR'] = backup_dir
        
        # Postavi okolinu
        environment = settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else 'dev'
        
        # Pripremi naredbu
        command = [
            'bash',
            backup_script,
            environment
        ]
        
        # Izvrši skriptu
        process = subprocess.run(
            command,
            env=env,
            check=True,
            capture_output=True,
            text=True
        )
        
        logger.info(f"Sigurnosna kopija baze podataka uspješno izrađena: {process.stdout}")
        
        return {
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'output': process.stdout,
            'environment': environment
        }
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Greška prilikom izrade sigurnosne kopije baze podataka: {e.stderr}")
        
        return {
            'status': 'error',
            'error': str(e),
            'stderr': e.stderr
        }
    
    except Exception as e:
        logger.error(f"Greška prilikom izrade sigurnosne kopije baze podataka: {str(e)}")
        
        return {
            'status': 'error',
            'error': str(e)
        }