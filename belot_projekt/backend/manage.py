#!/usr/bin/env python
"""
Django naredbeni alat za administrativne zadatke.

Ova skripta omogućava izvršavanje različitih administrativnih zadataka
vezanih uz Django projekt, kao što su pokretanje razvojnog servera,
migracije baze podataka, stvaranje superkorisnika i sl.
"""
import os
import sys


def main():
    """
    Glavna funkcija koja postavlja Django okolinu i pokreće naredbeni alat.
    """
    # Postavi zadanu Django postavku okoline
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Nije moguće uvesti Django. Jeste li sigurni da je instaliran i "
            "dostupan u PYTHONPATH okružnoj varijabli? Jeste li zaboravili "
            "aktivirati virtualno okruženje?"
        ) from exc
    
    # Dodatna logika za razvojne postavke
    if sys.argv[1:2] == ['runserver'] and 'DJANGO_SETTINGS_MODULE' not in os.environ:
        print("Pokretanje razvojnog servera s razvojnim postavkama...")
    
    # Provjera argumenata
    if len(sys.argv) >= 2:
        if sys.argv[1] == 'runserver' and len(sys.argv) == 2:
            # Dodaj 0.0.0.0:8000 kao zadani host/port
            sys.argv.append('0.0.0.0:8000')
            print("Pokretanje servera na 0.0.0.0:8000...")
        
        elif sys.argv[1] == 'runserver_plus' and len(sys.argv) == 2:
            # Za django-extensions runserver_plus
            sys.argv.append('0.0.0.0:8000')
            print("Pokretanje runserver_plus na 0.0.0.0:8000...")
        
        elif sys.argv[1] == 'test':
            # Postavi testne postavke za test naredbu
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.testing')
            print("Pokretanje testova s testnim postavkama...")
        
        elif sys.argv[1] == 'migrate' and '--settings' not in ' '.join(sys.argv):
            print(f"Migriranje baze podataka s postavkama: {os.environ['DJANGO_SETTINGS_MODULE']}")
    
    # Pokreni Django naredbeni alat
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()