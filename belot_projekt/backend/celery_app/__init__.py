"""
Inicijalizacijski modul za Celery aplikaciju.

Ovaj modul inicijalizira Celery instancu koja se koristi 
za asinkronu obradu zadataka u Belot aplikaciji.
"""

from celery_app.celery import app as celery_app

__all__ = ['celery_app']