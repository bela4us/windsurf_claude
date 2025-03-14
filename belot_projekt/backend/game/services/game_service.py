"""
Servis za upravljanje igrom belota.

Ovaj modul implementira servisni sloj za operacije vezane uz igru,
odvajajući poslovnu logiku od ostalih komponenti aplikacije i pružajući
jedinstveno sučelje za repository i API/consumer komponente.
"""

import logging
import uuid
import time
import functools
import json
from copy import deepcopy
from datetime import datetime, timedelta

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from game.models import Game, Round, Move, Declaration, GameHistory
from game.repositories.game_repository import GameRepository
from game.repositories.move_repository import MoveRepository
from game.game_logic.card import Card
from game.game_logic.deck import Deck
from game.game_logic.rules import Rules
from game.game_logic.scoring import Scoring
from utils.decorators import track_execution_time

# Inicijalizacija loggera
logger = logging.getLogger('game.services')
User = get_user_model()

# Konstante za keširanja
GAME_CACHE_PREFIX = 'game_service:game:'
GAME_STATE_CACHE_PREFIX = 'game_service:state:'
GAME_CACHE_TIMEOUT = 60 * 30  # 30 minuta


def game_state_cache(timeout=300):
    """
    Dekorator za keširanje stanja igre.
    
    Kešira rezultate metoda koje dohvaćaju stanje igre kako bi se
    smanjio broj upita prema bazi podataka.
    
    Args:
        timeout: Vrijeme trajanja keša u sekundama (zadano: 5 minuta)
        
    Returns:
        Dekorirana funkcija
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generiraj ključ za keš
            game = self.get_game(check_exists=True)
            if not game:
                return func(self, *args, **kwargs)
                
            # Ako je igra završena, ne keširamo rezultate
            if game.status in ['finished', 'abandoned']:
                return func(self, *args, **kwargs)
                
            # Za različite korisnike imamo različite poglede na igru
            user_id = args[0] if args else kwargs.get('user_id')
            cache_key = f"{GAME_STATE_CACHE_PREFIX}{game.id}:{user_id}"
            
            # Provjeri postoji li rezultat u kešu
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
                
            # Dohvati rezultat iz funkcije
            result = func(self, *args, **kwargs)
            
            # Spremi rezultat u keš
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def invalidate_game_cache(game_id):
    """
    Poništava keš vezan uz igru.
    
    Args:
        game_id: ID igre
        
    Returns:
        None
    """
    # Poništi keš za igru
    cache_key = f"{GAME_CACHE_PREFIX}{game_id}"
    cache.delete(cache_key)
    
    # Poništi keš za stanje igre
    # Budući da ne znamo točno koji korisnici imaju keširane podatke,
    # koristi wildcard za sve ključeve koji se odnose na igru
    cache.delete_pattern(f"{GAME_STATE_CACHE_PREFIX}{game_id}:*")


class GameService:
    """
    Servisni sloj za Belot igru koji enkapsulira poslovnu logiku igre.
    
    Pruža metode za upravljanje stanjem igre, obradu poteza i
    implementaciju pravila igre. Koristi repository sloj za pristup podacima.
    
    Ključne funkcionalnosti:
    - Stvaranje i povezivanje s igrama
    - Upravljanje igračima i timovima
    - Obrada poteza i pravila igre
    - Izračun rezultata i bodovanja
    - Praćenje stanja igre
    """
    
    def __init__(self, game_id=None, room_code=None):
        """
        Inicijalizira GameService za određenu igru.
        
        Args:
            game_id: ID igre ako je poznato
            room_code: Kod sobe ako se igra dohvaća prema kodu
        """
        self.game_id = game_id
        self.room_code = room_code
        self.rules = Rules()
        self.scoring = Scoring()
        self._game_cache = None
        self._cache_timestamp = None
    
    @track_execution_time
    def get_game(self, check_exists=True, use_cache=True):
        """
        Dohvaća instancu igre prema ID-u ili kodu sobe.
        
        Koristi keširane podatke kada je to moguće kako bi se
        smanjilo opterećenje baze podataka.
        
        Args:
            check_exists: Postavka za provjeru postoji li igra
            use_cache: Postavka za korištenje keša
            
        Returns:
            Game: Instanca igre ili None ako igra nije pronađena
            
        Raises:
            ValueError: Ako nije specificiran ni game_id ni room_code
        """
        # Prvo provjeri lokalni keš
        if use_cache and self._game_cache is not None and self._cache_timestamp is not None:
            # Ako je keš noviji od 5 sekundi, vrati ga
            if time.time() - self._cache_timestamp < 5:
                return self._game_cache
        
        # Ako nema lokalnog keša, provjeri Redis keš
        if use_cache and self.game_id:
            cache_key = f"{GAME_CACHE_PREFIX}{self.game_id}"
            cached_game = cache.get(cache_key)
            if cached_game:
                # Ažuriraj lokalni keš
                self._game_cache = cached_game
                self._cache_timestamp = time.time()
                return cached_game
        
        # Ako nema keša, dohvati iz baze
        if self.game_id:
            game = GameRepository.get_game_by_id(self.game_id)
        elif self.room_code:
            game = GameRepository.get_game_by_room_code(self.room_code)
        else:
            if check_exists:
                raise ValueError("Mora biti specificiran ili game_id ili room_code")
            return None
            
        if game is None and check_exists:
            logger.warning(f"Igra nije pronađena: game_id={self.game_id}, room_code={self.room_code}")
            return None
        
        # Ažuriraj lokalni i Redis keš
        if game:
            self._game_cache = game
            self._cache_timestamp = time.time()
            
            # Spremi u Redis keš
            if self.game_id:
                cache_key = f"{GAME_CACHE_PREFIX}{self.game_id}"
                cache.set(cache_key, game, GAME_CACHE_TIMEOUT)
        
        # Ako nismo našli igru, a imamo room_code, postavi game_id na None
        # kako bismo izbjegli buduće pokušaje dohvata
        if game is None and self.room_code and self.game_id is None:
            self.game_id = None
        
        return game
    
    @track_execution_time
    def create_game(self, creator_id, is_private=False, points_to_win=1001):
        """
        Stvara novu igru.
        
        Ova metoda stvara novu igru i povezuje kreatora s igrom. Također
        generira jedinstveni kod sobe za pridruživanje i postavlja početne
        vrijednosti za igru.
        
        Args:
            creator_id: ID korisnika koji stvara igru
            is_private: Označava je li igra privatna
            points_to_win: Broj bodova potrebnih za pobjedu (zadano 1001)
            
        Returns:
            dict: Rezultat s ID-om stvorene igre i ostalim podacima
            
        Raises:
            ValueError: Ako su parametri neispravni
        """
        try:
            # Provjeri postojanje korisnika
            try:
                creator = User.objects.select_related('profile').get(id=creator_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj stvaranja igre od strane nepostojećeg korisnika: {creator_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not creator.is_active:
                logger.warning(f"Pokušaj stvaranja igre od strane neaktivnog korisnika: {creator_id}")
                return {'valid': False, 'message': 'Korisnički račun nije aktivan'}
            
            # Provjeri jesu li parametri ispravni
            if points_to_win < 501 or points_to_win > 2001:
                return {'valid': False, 'message': 'Broj bodova za pobjedu mora biti između 501 i 2001'}
            
            if points_to_win % 10 != 1:  # Mora završavati na 1 (npr. 1001, 701, itd.)
                return {'valid': False, 'message': 'Broj bodova za pobjedu mora završavati s 1 (npr. 501, 701, 1001)'}
            
            # Provjeri je li korisnik već stvorio ili sudjeluje u aktivnoj igri
            active_games = GameRepository.get_active_games_for_player(creator_id)
            if active_games.exists():
                # Možemo dozvoliti stvaranje nove igre, ali obavijestiti korisnika
                logger.info(f"Korisnik {creator_id} stvara novu igru, iako već sudjeluje u {active_games.count()} aktivnih igara")
            
            # Stvori igru unutar transakcije
            with transaction.atomic():
                game = GameRepository.create_game(
                    creator=creator, 
                    private=is_private, 
                    points_to_win=points_to_win
                )
                
                # Dodaj kreatora kao igrača i u listu aktivnih igrača
                GameRepository.add_player_to_game(game, creator)
                
                # Ažuriraj statistiku kreatora
                try:
                    creator.stats.games_created += 1
                    creator.stats.save(update_fields=['games_created'])
                except:
                    # Ignoriraj grešku ako statistika ne postoji
                    pass
                    
                # Spremi za buduće pozive
                self.game_id = str(game.id)
                self.room_code = game.room_code
                
                # Poništi lokalni keš
                self._game_cache = game
                self._cache_timestamp = time.time()
                
                # Keširaj novu igru
                cache_key = f"{GAME_CACHE_PREFIX}{game.id}"
                cache.set(cache_key, game, GAME_CACHE_TIMEOUT)
                
                logger.info(f"Stvorena nova igra: {game.id}, kreator: {creator_id}, privatna: {is_private}, bodovi: {points_to_win}")
                
                # Vrati rezultat
                return {
                    'valid': True,
                    'game_id': str(game.id),
                    'room_code': game.room_code,
                    'created_at': game.created_at.isoformat(),
                    'is_private': game.is_private,
                    'points_to_win': game.points_to_win,
                    'status': game.status
                }
                
        except Exception as e:
            logger.error(f"Greška pri stvaranju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri stvaranju igre: {str(e)}"}
    
    @track_execution_time
    def join_game(self, user_id, room_code=None):
        """
        Pridružuje korisnika igri.
        
        Ova metoda omogućuje korisniku da se pridruži postojećoj igri
        koja je u statusu čekanja i nije popunjena. Ako je igra puna,
        automatski se dodjeljuju timovi.
        
        Args:
            user_id: ID korisnika koji se pridružuje
            room_code: Kod sobe (opcija) ako nije prethodno postavljen
            
        Returns:
            dict: Rezultat s podacima o igri i pozicijom igrača
            
        Raises:
            ValueError: Ako igra nije pronađena ili korisnik ne može pristupiti
        """
        try:
            # Ako je naveden novi kod sobe, postavi ga
            if room_code:
                self.room_code = room_code
                
                # Poništi lokalni keš jer smo promijenili sobu
                self._game_cache = None
                self._cache_timestamp = None
            
            # Dohvati igru
            game = self.get_game(check_exists=True)
            if not game:
                return {'valid': False, 'message': f"Igra s kodom {self.room_code or '-'} nije pronađena"}
            
            # Dohvati korisnika
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj pridruživanja igri od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                logger.warning(f"Pokušaj pridruživanja igri od strane neaktivnog korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnički račun nije aktivan'}
            
            # Provjeri je li privatna igra
            if game.is_private and not game.players.filter(id=user_id).exists() and user_id != game.creator_id:
                return {
                    'valid': False,
                    'message': 'Ova igra je privatna i potrebna je pozivnica'
                }
            
            # Provjeri je li već član igre
            if game.players.filter(id=user_id).exists():
                # Provjeri je li aktivan igrač
                if not game.active_players.filter(id=user_id).exists():
                    # Korisnik je napustio igru i vraća se
                    with transaction.atomic():
                        game.active_players.add(user)
                        
                        # Poništi keš
                        invalidate_game_cache(game.id)
                        self._game_cache = None
                        
                        logger.info(f"Igrač {user_id} se vratio u igru {game.id}")
                        
                return {
                    'valid': True,
                    'message': 'Već ste član ove igre',
                    'game_id': str(game.id),
                    'room_code': game.room_code,
                    'status': game.status,
                    'player_count': game.players.count(),
                    'active_players': list(game.active_players.values_list('id', flat=True)),
                    'team': self._get_player_team(game, user_id)
                }
            
            # Provjeri može li se pridružiti
            if game.status != 'waiting':
                return {
                    'valid': False,
                    'message': 'Nije moguće pridružiti se igri koja je već započela'
                }
                
            if game.players.count() >= 4:
                return {
                    'valid': False,
                    'message': 'Igra je već popunjena s maksimalnih 4 igrača'
                }
            
            # Dodaj igrača unutar transakcije
            with transaction.atomic():
                # Dodaj igrača
                GameRepository.add_player_to_game(game, user)
                
                # Označi ga kao aktivnog
                game.active_players.add(user)
                
                # Ako je igra puna, automatski dodijeli timove ako već nisu dodijeljeni
                if game.players.count() == 4:
                    if game.team_a_players.count() == 0 or game.team_b_players.count() == 0:
                        self._assign_teams(game)
                    
                    # Promijeni status u 'ready' ako su 4 igrača
                    if game.status == 'waiting':
                        game.status = 'ready'
                        game.save(update_fields=['status'])
                
                # Poništi keš
                invalidate_game_cache(game.id)
                self._game_cache = None
                
                # Ažuriraj statistiku igrača
                try:
                    user.stats.games_joined += 1
                    user.stats.save(update_fields=['games_joined'])
                except:
                    # Ignoriraj grešku ako statistika ne postoji
                    pass
                
                logger.info(f"Igrač {user_id} se pridružio igri {game.id}")
            
            # Dohvati svježe podatke o igri
            game.refresh_from_db()
            
            return {
                'valid': True, 
                'game_id': str(game.id),
                'room_code': game.room_code,
                'status': game.status,
                'player_count': game.players.count(),
                'active_players': list(game.active_players.values_list('id', flat=True)),
                'team': self._get_player_team(game, user_id)
            }
            
        except Exception as e:
            logger.error(f"Greška pri pridruživanju igri: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri pridruživanju igri: {str(e)}"}
    
    def _get_player_team(self, game, user_id):
        """
        Vraća tim kojem pripada igrač.
        
        Args:
            game: Instanca igre
            user_id: ID igrača
            
        Returns:
            str: 'A', 'B' ili None
        """
        if game.team_a_players.filter(id=user_id).exists():
            return 'A'
        elif game.team_b_players.filter(id=user_id).exists():
            return 'B'
        return None
        
    def _assign_teams(self, game):
        """
        Dodjeljuje igrače timovima.
        
        Args:
            game: Instanca igre
            
        Returns:
            None
        """
        # Dohvati sve igrače
        players = list(game.players.all())
        
        # Promiješaj igrače za nasumičan raspored
        import random
        random.shuffle(players)
        
        # Podijeli igrače u dva tima
        team_a = players[:2]
        team_b = players[2:]
        
        # Dodijeli timove
        game.team_a_players.set(team_a)
        game.team_b_players.set(team_b)
        
        # Ažuriraj podatke o dealeru i prvom igraču
        game.current_dealer = players[0]
        game.first_player = players[0]
        game.save(update_fields=['current_dealer', 'first_player'])
    
    @track_execution_time
    def leave_game(self, user_id, reason="voluntary"):
        """
        Uklanja korisnika iz igre.
        
        Ova metoda omogućuje korisniku da napusti igru. Ako je igra u tijeku,
        to se smatra predajom i rezultira pobjedom drugog tima. Ako kreator
        napusti igru, vlasništvo se prebacuje na drugog igrača ili se igra briše
        ako više nema igrača.
        
        Args:
            user_id: ID korisnika koji napušta igru
            reason: Razlog napuštanja (voluntary/inactivity/disconnected)
            
        Returns:
            dict: Rezultat s podacima o igri nakon napuštanja
            
        Raises:
            ValueError: Ako korisnik ili igra ne postoje
        """
        try:
            # Dohvati igru s provjerom postojanja
            game = self.get_game(check_exists=True)
            if not game:
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Dohvati korisnika s optimizacijom za profile
            try:
                user = User.objects.select_related('profile', 'stats').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj napuštanja igre od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li član igre
            if not game.players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava napustiti igru {game.id} u kojoj nije član")
                return {
                    'valid': False,
                    'message': 'Niste član ove igre'
                }
                
            # Započni transakciju za konzistentnost podataka
            with transaction.atomic():
                # Ako je igra u tijeku, to je predaja i rezultira pobjedom drugog tima
                if game.status == 'in_progress':
                    # Odredi tim igrača koji napušta
                    player_team = None
                    if user in game.team_a_players.all():
                        player_team = 'a'
                        # Tim B pobjeđuje
                        game.winner_team = 'b'
                        logger.info(f"Tim A predaje (igrač {user_id} napušta), pobjeđuje tim B")
                    elif user in game.team_b_players.all():
                        player_team = 'b'
                        # Tim A pobjeđuje
                        game.winner_team = 'a'
                        logger.info(f"Tim B predaje (igrač {user_id} napušta), pobjeđuje tim A")
                    
                    # Postavi podatke o završetku
                    game.status = 'completed'
                    game.ended_at = timezone.now()
                    game.end_reason = f'player_left_{reason}'
                    game.save(update_fields=['status', 'ended_at', 'winner_team', 'end_reason'])
                    
                    # Ažuriraj statistiku igrača
                    try:
                        user.stats.games_quit += 1
                        user.stats.save(update_fields=['games_quit'])
                    except:
                        pass
                    
                    # Ažuriraj povijesne podatke za statistiku
                    self._update_game_history(game, f'Igrač {user.username} napustio igru ({reason})')
                    
                    # Poništi keš
                    invalidate_game_cache(game.id)
                    self._game_cache = None
                    
                    # Obavijesti o napuštanju igre
                    return {
                        'valid': True,
                        'game_status': 'completed',
                        'winner_team': game.winner_team,
                        'reason': reason,
                        'message': f'Napustili ste igru, tim {game.winner_team.upper()} pobjeđuje'
                    }
                
                # Ako igra nije u tijeku, samo ukloni igrača
                GameRepository.remove_player_from_game(game, user)
                
                # Označi ga kao neaktivnog
                game.active_players.remove(user)
                
                # Ako je kreator napustio igru, a nitko nije ostao, izbriši igru
                if user.id == game.creator_id and game.players.count() == 0:
                    logger.info(f"Kreator {user_id} napustio igru {game.id}, nema više igrača, igra se briše")
                    GameRepository.delete_game(game)
                    
                    return {
                        'valid': True, 
                        'game_status': 'deleted',
                        'reason': reason,
                        'message': 'Napustili ste igru, igra je obrisana'
                    }
                # Ako je kreator napustio igru, a ima još igrača, prebaci vlasništvo
                elif user.id == game.creator_id and game.players.count() > 0:
                    # Odaberi novog kreatora (prvi aktivni igrač)
                    new_creator = game.active_players.first() or game.players.first()
                    game.creator = new_creator
                    game.save(update_fields=['creator'])
                    
                    logger.info(f"Kreator {user_id} napustio igru {game.id}, novi kreator je {new_creator.id}")
                    
                # Poništi keš
                invalidate_game_cache(game.id)
                self._game_cache = None
                
                # Ažuriraj statistiku igrača
                try:
                    if game.status != 'completed':
                        user.stats.games_quit += 1
                        user.stats.save(update_fields=['games_quit'])
                except:
                    pass
            
            # Dohvati svježe podatke o igri (izvan transakcije)
            if game.id:  # Ako igra nije izbrisana
                try:
                    game.refresh_from_db()
                except:
                    pass
            
            return {
                'valid': True, 
                'game_id': str(game.id) if game.id else None,
                'game_status': game.status if game.id else 'deleted',
                'player_count': game.players.count() if game.id else 0,
                'active_players': list(game.active_players.values_list('id', flat=True)) if game.id else [],
                'reason': reason,
                'message': 'Uspješno ste napustili igru'
            }
            
        except Exception as e:
            logger.error(f"Greška pri napuštanju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri napuštanju igre: {str(e)}"}
    
    def _update_game_history(self, game, event_description):
        """
        Ažurira povijest igre dodavanjem novog događaja
        
        Args:
            game: Instanca igre
            event_description: Opis događaja
        """
        try:
            GameHistory.objects.create(
                game=game,
                event_type='game_event',
                description=event_description,
                timestamp=timezone.now()
            )
        except Exception as e:
            logger.error(f"Greška pri ažuriranju povijesti igre: {str(e)}", exc_info=True)
    
    @track_execution_time
    def start_game(self, user_id):
        """
        Pokreće igru.
        
        Ova metoda započinje igru stvaranjem inicijalnog stanja, dodjeljuje
        timove ako već nisu dodijeljeni, stvara prvu rundu, dijeli karte
        igračima i određuje redoslijed igranja.
        
        Args:
            user_id: ID korisnika koji pokreće igru
            
        Returns:
            dict: Rezultat s podacima o pokrenutoj igri, uključujući karte
                  za svakog igrača i informacije o redoslijedu
                  
        Raises:
            ValueError: Ako korisnik ili igra ne postoje ili nisu zadovoljeni
                       uvjeti za početak igre
        """
        try:
            # Dohvati igru
            game = self.get_game(check_exists=True)
            if not game:
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Dohvati korisnika
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj pokretanja igre od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                return {
                    'valid': False,
                    'message': 'Korisnički račun nije aktivan'
                }
            
            # Provjeri je li kreator igre
            if user.id != game.creator_id:
                logger.warning(f"Korisnik {user_id} pokušava pokrenuti igru {game.id} koju nije stvorio")
                return {
                    'valid': False,
                    'message': 'Samo kreator igre može pokrenuti igru'
                }
            
            # Provjeri može li se igra pokrenuti
            if game.status != 'waiting' and game.status != 'ready':
                return {
                    'valid': False,
                    'message': f'Nije moguće pokrenuti igru u statusu {game.status}'
                }
                
            if game.players.count() != 4:
                return {
                    'valid': False,
                    'message': f'Potrebna su 4 igrača za početak (trenutno {game.players.count()})'
                }
            
            # Provjeri jesu li svi igrači aktivni
            active_count = game.active_players.count()
            if active_count != 4:
                return {
                    'valid': False,
                    'message': f'Svi igrači moraju biti aktivni (trenutno {active_count}/4)'
                }
            
            # Provjeri jesu li timovi dodijeljeni
            if game.team_a_players.count() != 2 or game.team_b_players.count() != 2:
                # Automatski dodijeli timove ako nisu
                self._assign_teams(game)
                game.refresh_from_db()
            
            # Započni igru unutar transakcije
            with transaction.atomic():
                # Postavi početni status igre na "in_progress"
                game.status = 'in_progress'
                game.started_at = timezone.now()
                game.save(update_fields=['status', 'started_at'])
                
                # Stvori prvu rundu
                current_round = GameRepository.get_or_create_round(game)
                
                # Podijeli karte
                cards_by_player = self._deal_cards(current_round)
                
                # Dohvati djelitelja
                dealer = current_round.dealer
                if not dealer:
                    # Postavi dealer-a ako nije postavljen
                    players = list(game.players.all())
                    dealer = random.choice(players)
                    current_round.dealer = dealer
                
                # Odredi prvog igrača za zvanje aduta (nakon djelitelja)
                players = list(game.players.all())
                dealer_index = players.index(dealer)
                first_bidder_index = (dealer_index + 1) % 4
                first_bidder = players[first_bidder_index]
                
                # Ažuriraj rundu
                current_round.current_player = first_bidder
                current_round.save(update_fields=['current_player', 'dealer'])
                
                # Resetiraj spreman status
                game.ready_players.clear()
                
                # Ažuriraj statistiku
                for player in game.players.all():
                    try:
                        # Povećaj broj odigranih igara
                        player.stats.games_played += 1
                        player.stats.save(update_fields=['games_played'])
                    except:
                        pass
                
                # Dodaj zapis u povijest igre
                self._update_game_history(
                    game, 
                    f"Igra je započela. Timovi: Tim A ({', '.join(p.username for p in game.team_a_players.all())}), "
                    f"Tim B ({', '.join(p.username for p in game.team_b_players.all())})"
                )
                
                # Poništi keš
                invalidate_game_cache(game.id)
                self._game_cache = None
                
                # Pripremi karte za svakog igrača
                player_cards = {}
                for player in players:
                    cards = cards_by_player.get(str(player.id), [])
                    if not cards:  # Ako nismo dobili karte iz _deal_cards
                        cards = MoveRepository.get_player_cards(current_round, player)
                        cards = [card.get_code() for card in cards]
                    player_cards[str(player.id)] = cards
                
                # Pripremi podatke o igračima i timovima
                team_a = [{
                    'id': str(p.id),
                    'username': p.username,
                    'avatar': p.profile.avatar_url if hasattr(p, 'profile') and p.profile else None
                } for p in game.team_a_players.all()]
                
                team_b = [{
                    'id': str(p.id),
                    'username': p.username,
                    'avatar': p.profile.avatar_url if hasattr(p, 'profile') and p.profile else None
                } for p in game.team_b_players.all()]
                
                return {
                    'valid': True,
                    'game_id': str(game.id),
                    'status': game.status,
                    'round_id': str(current_round.id),
                    'round_number': current_round.round_number,
                    'dealer': {
                        'id': str(dealer.id),
                        'username': dealer.username
                    },
                    'next_player': {
                        'id': str(first_bidder.id),
                        'username': first_bidder.username
                    },
                    'player_cards': player_cards,
                    'team_a': team_a,
                    'team_b': team_b,
                    'action': 'bidding'  # Prva akcija je uvijek licitiranje
                }
            
        except Exception as e:
            logger.error(f"Greška pri pokretanju igre: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri pokretanju igre: {str(e)}"}
            
    def _deal_cards(self, game_round):
        """
        Dijeli karte igračima za novu rundu.
        
        Args:
            game_round: Instanca runde za koju se dijele karte
            
        Returns:
            dict: Karte podijeljene po igračima (id_igrača -> lista karti)
        """
        try:
            # Dohvati igru i igrače
            game = game_round.game
            players = list(game.players.all())
            
            # Provjeri je li dealer postavljen, ako nije postavi nasumičnog igrača
            if not game_round.dealer:
                dealer = random.choice(players)
                game_round.dealer = dealer
                game_round.save(update_fields=['dealer'])
            
            # Koristi CardService za dijeljenje karata
            from game.services.card_service import CardService
            return CardService.deal_cards(game_round, players)
            
        except Exception as e:
            logger.error(f"Greška pri dijeljenju karata: {str(e)}", exc_info=True)
            return {}
    
    @track_execution_time
    def mark_player_ready(self, user_id):
        """
        Označava igrača kao spremnog za početak igre.
        
        Ova metoda omogućuje korisniku da označi svoju spremnost za sudjelovanje u igri.
        Kada su svi igrači spremni i ima ih ukupno 4, igra se automatski pokreće.
        
        Args:
            user_id: ID korisnika koji se označava kao spreman
            
        Returns:
            dict: Rezultat s podacima o spremnosti svih igrača i statusom operacije
            
        Raises:
            ValueError: Ako korisnik ili igra ne postoje
        """
        try:
            # Dohvati igru s provjerom postojanja
            game = self.get_game(check_exists=True)
            if not game:
                logger.warning(f"Igra nije pronađena pri označavanju spremnosti igrača {user_id}")
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Dohvati korisnika s optimizacijom
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj označavanja spremnosti od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                logger.warning(f"Pokušaj označavanja spremnosti od strane neaktivnog korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnički račun nije aktivan'}
            
            # Provjeri je li član igre
            if not game.players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava označiti spremnost u igri {game.id} u kojoj nije član")
                return {
                    'valid': False,
                    'message': 'Niste član ove igre'
                }
            
            # Provjeri je li korisnik aktivan u igri
            if not game.active_players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava označiti spremnost, ali nije aktivan u igri {game.id}")
                return {
                    'valid': False, 
                    'message': 'Morate biti aktivni u igri da biste se označili kao spremni'
                }
            
            # Provjeri je li igra u odgovarajućem statusu
            if game.status != 'waiting':
                logger.info(f"Korisnik {user_id} pokušava označiti spremnost u igri {game.id} koja nije u statusu čekanja (trenutni status: {game.status})")
                return {
                    'valid': False,
                    'message': f'Igra nije u statusu čekanja (trenutni status: {game.status})'
                }
            
            # Provjeri je li igrač već označen kao spreman
            if game.ready_players.filter(id=user_id).exists():
                return {
                    'valid': True,
                    'message': 'Već ste označeni kao spremni',
                    'all_ready': game.ready_players.count() == game.players.count(),
                    'ready_count': game.ready_players.count(),
                    'player_count': game.players.count(),
                    'ready_players': list(game.ready_players.values_list('id', flat=True))
                }
            
            # Označi igrača kao spremnog unutar transakcije
            with transaction.atomic():
                # Označi igrača kao spremnog
                game.ready_players.add(user)
                
                # Poništi keš
                invalidate_game_cache(game.id)
                self._game_cache = None
                
                logger.info(f"Igrač {user_id} označen kao spreman u igri {game.id}. Spremnih igrača: {game.ready_players.count()}/{game.players.count()}")
                
                # Osvježi podatke o igri
                game.refresh_from_db()
                
                # Provjeri jesu li svi igrači spremni i ima li ih 4
                all_ready = game.ready_players.count() == game.players.count()
                
                # Ako su svi spremni i ima ih 4, automatski pokreni igru
                if all_ready and game.players.count() == 4:
                    logger.info(f"Svi igrači spremni u igri {game.id}, automatsko pokretanje igre")
                    return self.start_game(game.creator.id)
            
            # Vrati rezultat
            return {
                'valid': True,
                'message': 'Uspješno ste označeni kao spremni',
                'all_ready': all_ready,
                'ready_count': game.ready_players.count(),
                'player_count': game.players.count(),
                'ready_players': list(game.ready_players.values_list('id', flat=True))
            }
            
        except Exception as e:
            logger.error(f"Greška pri označavanju spremnosti: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri označavanju spremnosti: {str(e)}"}
    
    @track_execution_time
    def process_move(self, user_id, card):
        """
        Obrađuje potez igrača.
        
        Args:
            user_id: ID korisnika koji igra potez
            card: Karta koju igrač igra (string ili Card objekt)
            
        Returns:
            dict: Rezultat poteza sa statusom i porukom
        """
        try:
            # Dohvati igru
            game = self.get_game()
            if not game:
                logger.error(f"Igra ne postoji za potez korisnika {user_id}")
                return {
                    'valid': False,
                    'message': 'Igra nije pronađena'
                }
            
            # Provjeri postoji li korisnik
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Korisnik {user_id} ne postoji")
                return {
                    'valid': False,
                    'message': 'Korisnik ne postoji'
                }
            
            # Provjeri je li korisnik dio igre
            if not game.players.filter(id=user_id).exists():
                logger.warning(f"Korisnik {user_id} nije dio igre {game.id}")
                return {
                    'valid': False,
                    'message': 'Korisnik nije dio ove igre'
                }
            
            # Provjeri je li igrač aktivan
            if not game.is_player_active(user_id):
                logger.warning(f"Korisnik {user_id} nije aktivan igrač u igri {game.id}")
                return {
                    'valid': False,
                    'message': 'Korisnik nije aktivan igrač u ovoj igri'
                }
            
            # Provjeri je li stanje igre validno za potez
            if game.status != 'in_progress':
                logger.warning(f"Igra {game.id} nije u tijeku, trenutni status: {game.status}")
                return {
                    'valid': False,
                    'message': 'Igra nije u tijeku'
                }
            
            # Dohvati trenutnu rundu
            current_round = Round.objects.filter(
                game=game, 
                status__in=['in_progress', 'bidding']
            ).order_by('-number').first()
            
            if not current_round:
                logger.error(f"Nema aktivne runde za igru {game.id}")
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li faza za igranje karata
            if current_round.status != 'in_progress':
                logger.warning(f"Runda {current_round.id} nije u fazi igranja, trenutni status: {current_round.status}")
                return {
                    'valid': False,
                    'message': 'Runda nije u fazi igranja karata'
                }
            
            # Provjeri je li na redu igrač koji pokušava igrati potez
            if current_round.current_player_id != user_id:
                logger.warning(f"Nije red korisnika {user_id} u rundi {current_round.id}, trenutni igrač: {current_round.current_player_id}")
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za igranje'
                }
            
            # Provjeri ima li igrač tu kartu u ruci
            player_cards = MoveRepository.get_player_cards(current_round, user)
            
            # Pretvori karte u objekte za lakšu usporedbu
            if isinstance(card, str):
                try:
                    card = Card.from_code(card)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {str(e)}")
                    return {'valid': False, 'message': 'Nevažeća karta'}
            
            # Dohvati trenutni štih
            current_trick_cards = current_round.current_trick_cards or []
            
            # Provjeri je li potez valjan prema pravilima
            from game.services.card_service import CardService
            is_valid, error_message = CardService.is_valid_move(card, player_cards, current_trick_cards, current_round.trump_suit)
            
            if not is_valid:
                logger.info(f"Nevažeći potez igrača {user_id}: karta {card.get_code()}, adut: {current_round.trump_suit}, razlog: {error_message}")
                return {
                    'valid': False,
                    'message': error_message or 'Nevažeći potez prema pravilima igre'
                }
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Izračunaj trenutni broj štiha i redoslijed poteza unutar štiha
                trick_number = current_round.trick_number or 0
                trick_move_count = len(current_trick_cards)
                
                # Ako je prvi potez u novom štihu, povećaj broj štiha
                if trick_move_count == 0:
                    trick_number += 1
                
                # Stvori novi potez
                move = Move.objects.create(
                    round=current_round,
                    player=user,
                    card_code=card.get_code(),
                    trick_number=trick_number,
                    order=trick_move_count + 1,
                    is_winning_card=False  # Postavit će se kasnije ako je pobjednički
                )
                
                # Ukloni kartu iz ruke igrača
                CardService.remove_card_from_player(current_round, user, card)
                
                # Dodaj kartu u trenutni štih
                current_trick_cards.append({
                    'player': str(user.id),
                    'card': card.get_code(),
                    'username': user.username
                })
                
                # Ažuriraj rundu s novim štihom
                current_round.current_trick_cards = current_trick_cards
                current_round.trick_number = trick_number
                
                # Rezultat poteza
                result = {
                    'valid': True,
                    'card': card.get_code(),
                    'trick_number': trick_number,
                    'trick_completed': False,
                    'round_completed': False,
                    'game_completed': False
                }
                
                # Ako je štih kompletan (4 karte), odredi pobjednika štiha
                if len(current_trick_cards) == 4:
                    # Izračunaj pobjednika štiha
                    winner_info = CardService.calculate_trick_winner(current_trick_cards, current_round.trump_suit)
                    
                    if winner_info:
                        winning_player_id = winner_info.get('player')
                        winning_move_idx = winner_info.get('index', 0)
                        
                        # Dohvati pobjednički potez iz baze i označi ga kao pobjednički
                        if winning_player_id:
                            try:
                                winning_player = User.objects.get(id=winning_player_id)
                                winning_moves = Move.objects.filter(
                                    round=current_round,
                                    trick_number=trick_number,
                                    player=winning_player
                                )
                                if winning_moves.exists():
                                    winning_move = winning_moves.first()
                                    winning_move.is_winning_card = True
                                    winning_move.save(update_fields=['is_winning_card'])
                            except (User.DoesNotExist, Exception) as e:
                                logger.error(f"Greška pri označavanju pobjedničkog poteza: {str(e)}")
                        
                        # Postavi sljedećeg igrača (pobjednik štiha)
                        current_round.current_player_id = winning_player_id
                        
                        # Postavi da je štih završen i počni novi
                        current_round.current_trick_cards = []
                        
                        result['trick_completed'] = True
                        result['next_player'] = winning_player_id
                        
                        # Izračunaj ukupan broj odigranih štihova
                        total_tricks = Move.objects.filter(
                            round=current_round,
                            is_winning_card=True
                        ).count()
                        
                        # Ako je odigrano 8 štihova, runda je završena
                        if total_tricks == 7:  # Nakon 8. štiha (0-7)
                            # Označi zadnji odigrani potez kao pobjednički (dodatni bodovi za zadnji štih)
                            move.is_winning_card = True
                            move.save(update_fields=['is_winning_card'])
                            
                            # Završi rundu
                            current_round.status = 'completed'
                            current_round.end_time = timezone.now()
                            
                            # Izračunaj rezultat runde
                            round_result = self._calculate_round_result(current_round)
                            
                            # Spremi rezultat runde
                            current_round.team_a_points = round_result.get('team_a_points', 0)
                            current_round.team_b_points = round_result.get('team_b_points', 0)
                            current_round.team_a_declaration_points = round_result.get('team_a_declaration_points', 0)
                            current_round.team_b_declaration_points = round_result.get('team_b_declaration_points', 0)
                            current_round.team_a_trick_points = round_result.get('team_a_trick_points', 0)
                            current_round.team_b_trick_points = round_result.get('team_b_trick_points', 0)
                            
                            # Označi je li tim koji je zvao adut prošao
                            current_round.calling_team_passed = round_result.get('passed', False)
                            
                            # Spremi izmjene
                            current_round.save()
                            
                            # Ažuriraj rezultat poteza
                            result['round_completed'] = True
                            result['round_result'] = round_result
                            
                            # Provjeri je li igra završena (dosegnut potreban broj bodova)
                            from game.services.scoring_service import ScoringService
                            winner = ScoringService.check_game_winner(game)
                            
                            if winner:
                                # Završi igru
                                game.status = 'completed'
                                game.end_time = timezone.now()
                                game.winner = winner
                                
                                # Izračunaj konačni rezultat
                                final_score = ScoringService.calculate_final_score(game)
                                
                                # Spremi konačni rezultat
                                game.team_a_score = final_score.get('team_a_score', 0)
                                game.team_b_score = final_score.get('team_b_score', 0)
                                game.save()
                                
                                # Ažuriraj statistiku igrača
                                self._update_player_statistics(game)
                                
                                # Ažuriraj rezultat poteza
                                result['game_completed'] = True
                                result['final_score'] = final_score
                            else:
                                # Započni novu rundu
                                next_dealer = self._get_next_dealer(current_round.dealer, game)
                                
                                new_round = Round.objects.create(
                                    game=game,
                                    number=current_round.number + 1,
                                    dealer=next_dealer,
                                    current_player=next_dealer,  # Prvi na potezu je igrač koji sjedi nakon djelitelja
                                    status='waiting',
                                    trump_suit=None,
                                    calling_team=None
                                )
                                
                                # Podijeli karte za novu rundu
                                player_cards = self._deal_cards(new_round)
                                
                                # Ažuriraj rezultat poteza s novom rundom
                                result['new_round'] = {
                                    'round_number': new_round.number,
                                    'dealer': {
                                        'id': str(next_dealer.id),
                                        'username': next_dealer.username
                                    },
                                    'player_cards': player_cards.get(str(user_id), [])
                                }
                    else:
                        logger.error(f"Nije moguće odrediti pobjednika štiha u rundi {current_round.id}")
                        return {
                            'valid': False,
                            'message': 'Greška pri određivanju pobjednika štiha'
                        }
                else:
                    # Ako štih nije kompletan, postavi sljedećeg igrača
                    # Dohvati redoslijed igrača
                    player_order = list(game.players.all())
                    current_index = player_order.index(user)
                    next_index = (current_index + 1) % len(player_order)
                    next_player = player_order[next_index]
                    
                    # Postavi sljedećeg igrača
                    current_round.current_player = next_player
                    
                    result['next_player'] = str(next_player.id)
                
                # Spremi izmjene na rundi
                current_round.save()
                
                # Ažuriraj povijest igre
                self._update_game_history(game, f"Igrač {user.username} je odigrao kartu {card.get_code()}")
                
                return result
                
        except Exception as e:
            logger.error(f"Greška pri obradi poteza korisnika {user_id}: {str(e)}", exc_info=True)
            return {
                'valid': False,
                'message': f'Greška pri obradi poteza: {str(e)}'
            }
    
    @track_execution_time
    def process_trump_call(self, user_id, suit):
        """
        Obrađuje zvanje aduta.
        
        Ova metoda se poziva kada igrač odluči zvati adut (odabrati boju koja
        će biti adut za trenutnu rundu). Nakon uspješnog zvanja aduta,
        runda prelazi u fazu igranja i igra započinje.
        
        Args:
            user_id: ID korisnika koji zove aduta
            suit: Boja aduta ('S', 'H', 'D', 'C') - srce, pik, karo, tref
            
        Returns:
            dict: Rezultat s podacima o zvanom adutu, timu koji je zvao, 
                  sljedećem igraču i kartama svih igrača
                  
        Raises:
            ValueError: Ako korisnik ili igra ne postoje ili nisu zadovoljeni
                       uvjeti za zvanje aduta
        """
        try:
            # Dohvati igru s provjerom postojanja
            game = self.get_game(check_exists=True)
            if not game:
                logger.warning(f"Igra nije pronađena pri zvanju aduta")
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Dohvati korisnika s optimizacijom
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj zvanja aduta od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                logger.warning(f"Pokušaj zvanja aduta od strane neaktivnog korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnički račun nije aktivan'}
            
            # Provjeri je li korisnik član igre
            if not game.players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava zvati adut u igri {game.id} u kojoj nije član")
                return {'valid': False, 'message': 'Niste član ove igre'}
            
            # Provjeri je li korisnik aktivan u igri
            if not game.active_players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava zvati adut, ali nije aktivan u igri {game.id}")
                return {'valid': False, 'message': 'Morate biti aktivni u igri da biste zvali adut'}
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                logger.warning(f"Nema aktivne runde za igru {game.id}")
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li igrač na potezu
            if current_round.current_player != user:
                logger.info(f"Korisnik {user_id} pokušava zvati adut, ali nije na redu (trenutni igrač: {current_round.current_player.id})")
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za zvanje aduta'
                }
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                logger.info(f"Korisnik {user_id} pokušava zvati adut, ali runda {current_round.id} nije u fazi zvanja aduta (trenutni status: {current_round.status})")
                return {
                    'valid': False,
                    'message': f'Runda nije u fazi zvanja aduta (trenutni status: {current_round.status})'
                }
            
            # Provjeri je li boja aduta valjana
            valid_suits = ['S', 'H', 'D', 'C']
            if suit not in valid_suits:
                logger.warning(f"Korisnik {user_id} pokušava zvati nevažeću boju aduta: {suit}")
                return {
                    'valid': False,
                    'message': f'Nevažeća boja aduta. Dozvoljena samo: {", ".join(valid_suits)}'
                }
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Postavi adut i status
                current_round.trump_suit = suit
                current_round.caller = user
                current_round.status = 'playing'
                
                # Odredi tim koji je zvao adut
                calling_team = 'a' if user in game.team_a_players.all() else 'b'
                current_round.calling_team = calling_team
                
                # Prvi igrač nakon djelitelja započinje igru
                players = list(game.players.all())
                dealer_index = players.index(current_round.dealer)
                first_player_index = (dealer_index + 1) % 4
                first_player = players[first_player_index]
                
                current_round.current_player = first_player
                current_round.save(update_fields=['trump_suit', 'caller', 'status', 'calling_team', 'current_player'])
                
                # Dodaj zapis u povijest igre
                self._update_game_history(
                    game, 
                    f"Igrač {user.username} zvao adut: {suit} za tim {calling_team.upper()}"
                )
                
                # Pripremi karte za svakog igrača (možda ima novih)
                player_cards = {}
                for player in players:
                    cards = MoveRepository.get_player_cards(current_round, player)
                    player_cards[str(player.id)] = [card.get_code() for card in cards]
                
                # Prijevodi boja za lakše čitanje
                suit_translations = {
                    'S': 'pik',
                    'H': 'srce',
                    'D': 'karo', 
                    'C': 'tref'
                }
                
                # Poništi keš
                invalidate_game_cache(game.id)
                self._game_cache = None
                
                # Logiraj uspješno zvanje aduta
                logger.info(f"Igrač {user_id} zvao adut {suit} ({suit_translations.get(suit, suit)}) u igri {game.id}, runda {current_round.round_number}")
                
                return {
                    'valid': True,
                    'suit': suit,
                    'suit_name': suit_translations.get(suit, suit),
                    'calling_team': calling_team,
                    'caller': {
                        'id': str(user.id),
                        'username': user.username
                    },
                    'round_number': current_round.round_number,
                    'next_player': {
                        'id': str(first_player.id),
                        'username': first_player.username
                    },
                    'player_cards': player_cards
                }
                
        except User.DoesNotExist:
            logger.warning(f"Pokušaj zvanja aduta od strane nepostojećeg korisnika: {user_id}")
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri zvanju aduta: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri zvanju aduta: {str(e)}"}
    
    @track_execution_time
    def process_trump_pass(self, user_id):
        """
        Obrađuje propuštanje zvanja aduta.
        
        Ova metoda se poziva kada igrač odluči propustiti zvanje aduta.
        Nakon propuštanja, sljedeći igrač dobiva priliku zvati adut.
        Ako svi igrači propuste, automatski se određuje adut.
        
        Args:
            user_id: ID korisnika koji propušta zvanje
            
        Returns:
            dict: Rezultat s podacima o sljedećem igraču za zvanje ili
                 automatski određenom adutu ako su svi propustili
                 
        Raises:
            ValueError: Ako korisnik ili igra ne postoje ili nisu zadovoljeni
                       uvjeti za propuštanje zvanja aduta
        """
        try:
            # Dohvati igru s provjerom postojanja
            game = self.get_game(check_exists=True)
            if not game:
                logger.warning(f"Igra nije pronađena pri propuštanju zvanja aduta")
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Dohvati korisnika s optimizacijom
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj propuštanja zvanja aduta od strane nepostojećeg korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                logger.warning(f"Pokušaj propuštanja zvanja aduta od strane neaktivnog korisnika: {user_id}")
                return {'valid': False, 'message': 'Korisnički račun nije aktivan'}
            
            # Provjeri je li korisnik član igre
            if not game.players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava propustiti zvanje aduta u igri {game.id} u kojoj nije član")
                return {'valid': False, 'message': 'Niste član ove igre'}
            
            # Provjeri je li korisnik aktivan u igri
            if not game.active_players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava propustiti zvanje aduta, ali nije aktivan u igri {game.id}")
                return {'valid': False, 'message': 'Morate biti aktivni u igri da biste propustili zvanje aduta'}
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                logger.warning(f"Nema aktivne runde za igru {game.id}")
                return {
                    'valid': False,
                    'message': 'Nema aktivne runde'
                }
            
            # Provjeri je li igrač na potezu
            if current_round.current_player != user:
                logger.info(f"Korisnik {user_id} pokušava propustiti zvanje aduta, ali nije na redu (trenutni igrač: {current_round.current_player.id})")
                return {
                    'valid': False,
                    'message': 'Nije tvoj red za zvanje aduta'
                }
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                logger.info(f"Korisnik {user_id} pokušava propustiti zvanje aduta, ali runda {current_round.id} nije u fazi zvanja aduta (trenutni status: {current_round.status})")
                return {
                    'valid': False,
                    'message': f'Runda nije u fazi zvanja aduta (trenutni status: {current_round.status})'
                }
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Odredi sljedećeg igrača
                players = list(game.players.all())
                current_index = players.index(user)
                next_index = (current_index + 1) % 4
                next_player = players[next_index]
                
                # Označi da je korisnik propustio zvanje
                if not hasattr(current_round, 'passed_players'):
                    current_round.passed_players = []
                
                # Dodaj korisnika u listu onih koji su propustili
                passed_players = current_round.passed_players
                if str(user.id) not in passed_players:
                    passed_players.append(str(user.id))
                current_round.passed_players = passed_players
                
                # Dodaj zapis u povijest igre
                self._update_game_history(
                    game, 
                    f"Igrač {user.username} propustio zvanje aduta"
                )
                
                # Provjeri jesu li svi propustili
                if len(passed_players) == 4:
                    # Automatski odredi adut (npr. prva karta djelitelja)
                    dealer_cards = MoveRepository.get_player_cards(current_round, current_round.dealer)
                    if dealer_cards:
                        auto_trump_suit = dealer_cards[0].suit
                    else:
                        # Ako nema karata, odaberi nasumično
                        auto_trump_suit = random.choice(['S', 'H', 'D', 'C'])
                    
                    # Postavi adut i status
                    current_round.trump_suit = auto_trump_suit
                    current_round.caller = current_round.dealer  # Djelitelj je "zvao" adut
                    current_round.status = 'playing'
                    
                    # Odredi tim koji je "zvao" adut
                    calling_team = 'a' if current_round.dealer in game.team_a_players.all() else 'b'
                    current_round.calling_team = calling_team
                    
                    # Prvi igrač nakon djelitelja započinje igru
                    dealer_index = players.index(current_round.dealer)
                    first_player_index = (dealer_index + 1) % 4
                    first_player = players[first_player_index]
                    
                    current_round.current_player = first_player
                    current_round.save(update_fields=['trump_suit', 'caller', 'status', 'calling_team', 'current_player', 'passed_players'])
                    
                    # Pripremi karte za svakog igrača
                    player_cards = {}
                    for player in players:
                        cards = MoveRepository.get_player_cards(current_round, player)
                        player_cards[str(player.id)] = [card.get_code() for card in cards]
                    
                    # Prijevodi boja za lakše čitanje
                    suit_translations = {
                        'S': 'pik',
                        'H': 'srce',
                        'D': 'karo', 
                        'C': 'tref'
                    }
                    
                    # Logiraj automatsko određivanje aduta
                    logger.info(f"Automatski određen adut {auto_trump_suit} ({suit_translations.get(auto_trump_suit, auto_trump_suit)}) u igri {game.id}, runda {current_round.round_number}")
                    
                    # Dodaj zapis u povijest igre
                    self._update_game_history(
                        game, 
                        f"Automatski određen adut: {auto_trump_suit} ({suit_translations.get(auto_trump_suit, auto_trump_suit)})"
                    )
                    
                    # Poništi keš
                    invalidate_game_cache(game.id)
                    self._game_cache = None
                    
                    return {
                        'valid': True,
                        'all_passed': True,
                        'auto_trump': True,
                        'suit': auto_trump_suit,
                        'suit_name': suit_translations.get(auto_trump_suit, auto_trump_suit),
                        'calling_team': calling_team,
                        'caller': {
                            'id': str(current_round.dealer.id),
                            'username': current_round.dealer.username
                        },
                        'round_number': current_round.round_number,
                        'next_player': {
                            'id': str(first_player.id),
                            'username': first_player.username
                        },
                        'player_cards': player_cards
                    }
                else:
                    # Postavi sljedećeg igrača
                    current_round.current_player = next_player
                    current_round.save(update_fields=['current_player', 'passed_players'])
                    
                    # Logiraj propuštanje zvanja aduta
                    logger.info(f"Igrač {user_id} propustio zvanje aduta u igri {game.id}, runda {current_round.round_number}. Sljedeći igrač: {next_player.id}")
                    
                    # Poništi keš
                    invalidate_game_cache(game.id)
                    self._game_cache = None
                    
                    return {
                        'valid': True,
                        'all_passed': False,
                        'passed_player': {
                            'id': str(user.id),
                            'username': user.username
                        },
                        'next_player': {
                            'id': str(next_player.id),
                            'username': next_player.username
                        },
                        'passed_count': len(passed_players)
                    }
                
        except User.DoesNotExist:
            logger.warning(f"Pokušaj propuštanja zvanja aduta od strane nepostojećeg korisnika: {user_id}")
            return {'valid': False, 'message': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri propuštanju zvanja aduta: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f"Greška pri propuštanju zvanja aduta: {str(e)}"}
    
    @track_execution_time
    def process_declaration(self, user_id, declaration_type, cards):
        """
        Obrađuje prijavu zvanja u igri.
        
        Args:
            user_id: ID korisnika koji prijavljuje zvanje
            declaration_type: Tip zvanja ('four_jacks', 'sequence_3', itd.)
            cards: Lista kodova karata za zvanje
            
        Returns:
            dict: Rezultat sa statusom i detaljima zvanja
        """
        try:
            # Dohvati igru
            game = self.get_game()
            if not game:
                logger.error(f"Igra ne postoji za zvanje korisnika {user_id}")
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Provjeri postoji li korisnik
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Korisnik {user_id} ne postoji")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik dio igre
            if not game.players.filter(id=user_id).exists():
                logger.warning(f"Korisnik {user_id} nije dio igre {game.id}")
                return {'valid': False, 'message': 'Korisnik nije dio ove igre'}
            
            # Provjeri je li igrač aktivan
            if not game.is_player_active(user_id):
                logger.warning(f"Korisnik {user_id} nije aktivan igrač u igri {game.id}")
                return {'valid': False, 'message': 'Korisnik nije aktivan igrač u ovoj igri'}
            
            # Provjeri je li stanje igre validno za zvanje
            if game.status != 'in_progress':
                logger.warning(f"Igra {game.id} nije u tijeku, trenutni status: {game.status}")
                return {'valid': False, 'message': 'Igra nije u tijeku'}
            
            # Dohvati trenutnu rundu
            current_round = Round.objects.filter(
                game=game, 
                status='in_progress'
            ).order_by('-number').first()
            
            if not current_round:
                logger.error(f"Nema aktivne runde za igru {game.id}")
                return {'valid': False, 'message': 'Nema aktivne runde'}
            
            # Provjeri ima li igrač karte za zvanje
            player_cards = MoveRepository.get_player_cards(current_round, user)
            
            # Pretvori string kodove u objekte Card
            try:
                card_objs = [Card.from_code(card) if isinstance(card, str) else card for card in cards]
            except ValueError as e:
                logger.error(f"Nevažeći kod karte: {e}")
                return {'valid': False, 'message': f'Nevažeći kod karte: {str(e)}'}
            
            # Provjeri ima li igrač karte koje prijavljuje
            for card in card_objs:
                if card.get_code() not in [c.get_code() if isinstance(c, Card) else c for c in player_cards]:
                    logger.warning(f"Korisnik {user_id} nema kartu {card.get_code()} za zvanje")
                    return {'valid': False, 'message': f'Nemate kartu {card.get_code()} za zvanje'}
            
            # Validiraj zvanje pomoću CardService
            from game.services.card_service import CardService
            is_valid, error_message = CardService.validate_declaration(declaration_type, card_objs, current_round)
            
            if not is_valid:
                logger.info(f"Nevažeće zvanje {declaration_type}: {error_message}")
                return {'valid': False, 'message': error_message}
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Dohvati vrijednost zvanja
                from game.services.scoring_service import ScoringService
                declaration_value = ScoringService.get_declaration_value(declaration_type)
                
                # Stvori objekt zvanja
                declaration = Declaration.objects.create(
                    round=current_round,
                    player=user,
                    declaration_type=declaration_type,
                    cards_json=[card.get_code() for card in card_objs],
                    value=declaration_value
                )
                
                # Ažuriraj povijest igre
                self._update_game_history(game, f"Igrač {user.username} je zvao {declaration_type} vrijednosti {declaration_value}")
                
                # Vrati rezultat zvanja
                return {
                    'valid': True,
                    'declaration_id': str(declaration.id),
                    'declaration_type': declaration_type,
                    'value': declaration_value,
                    'cards': [card.get_code() for card in card_objs],
                    'message': 'Zvanje uspješno prijavljeno'
                }
                
        except Exception as e:
            logger.error(f"Greška pri obradi zvanja korisnika {user_id}: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f'Greška pri obradi zvanja: {str(e)}'}
    
    @track_execution_time
    def process_bela(self, user_id):
        """
        Obrađuje zvanje bele (kralj i dama u adutu).
        
        Args:
            user_id: ID korisnika koji zove belu
            
        Returns:
            dict: Rezultat zvanja s informacijama o uspjehu i vrijednosti zvanja
        """
        try:
            # Dohvati igru i provjeri postojanje
            game = self.get_game()
            if not game:
                logger.error(f"Igra ne postoji za zvanje bele korisnika {user_id}")
                return {'valid': False, 'message': 'Igra nije pronađena'}
            
            # Provjeri postoji li korisnik
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Korisnik {user_id} ne postoji")
                return {'valid': False, 'message': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik dio igre
            if not game.players.filter(id=user_id).exists():
                logger.warning(f"Korisnik {user_id} nije dio igre {game.id}")
                return {'valid': False, 'message': 'Korisnik nije dio ove igre'}
            
            # Provjeri je li igrač aktivan
            if not game.is_player_active(user_id):
                logger.warning(f"Korisnik {user_id} nije aktivan igrač u igri {game.id}")
                return {'valid': False, 'message': 'Korisnik nije aktivan igrač u ovoj igri'}
            
            # Provjeri je li stanje igre validno za zvanje
            if game.status != 'in_progress':
                logger.warning(f"Igra {game.id} nije u tijeku, trenutni status: {game.status}")
                return {'valid': False, 'message': 'Igra nije u tijeku'}
            
            # Dohvati trenutnu rundu
            current_round = Round.objects.filter(
                game=game, 
                status='in_progress'
            ).order_by('-number').first()
            
            if not current_round:
                logger.error(f"Nema aktivne runde za igru {game.id}")
                return {'valid': False, 'message': 'Nema aktivne runde'}
            
            # Provjeri je li adut postavljen
            if not current_round.trump_suit:
                logger.warning(f"Adut nije određen u rundi {current_round.id}")
                return {'valid': False, 'message': 'Adut mora biti određen za zvanje bele'}
            
            # Provjeri ima li igrač kralja i damu aduta
            player_cards = MoveRepository.get_player_cards(current_round, user)
            
            # Pretvori karte u objekte Card
            trump_cards = []
            for card in player_cards:
                card_obj = card if isinstance(card, Card) else Card.from_code(card)
                if card_obj.suit == current_round.trump_suit:
                    trump_cards.append(card_obj)
            
            # Provjeri ima li kraljevski par (kralj i dama) u adutu
            has_king = any(card.value == 'K' for card in trump_cards)
            has_queen = any(card.value == 'Q' for card in trump_cards)
            
            if not (has_king and has_queen):
                logger.info(f"Korisnik {user_id} nema kraljevski par u adutu {current_round.trump_suit}")
                return {'valid': False, 'message': 'Nemate kralja i damu u adutu'}
            
            # Pronađi kralja i damu za zvanje
            king_card = next((card for card in trump_cards if card.value == 'K'), None)
            queen_card = next((card for card in trump_cards if card.value == 'Q'), None)
            
            if not king_card or not queen_card:
                logger.error(f"Nekonzistentno stanje: kralj ili dama ne postoje iako su prethodno provjereni")
                return {'valid': False, 'message': 'Greška pri pronalaženju karata'}
            
            # Karte za zvanje
            belot_cards = [king_card.get_code(), queen_card.get_code()]
            
            # Validiraj zvanje pomoću CardService
            from game.services.card_service import CardService
            is_valid, error_message = CardService.validate_declaration('belot', belot_cards, current_round)
            
            if not is_valid:
                logger.info(f"Nevažeće zvanje bele: {error_message}")
                return {'valid': False, 'message': error_message}
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Dohvati vrijednost zvanja
                from game.services.scoring_service import ScoringService
                declaration_value = ScoringService.get_declaration_value('belot')
                
                # Stvori objekt zvanja
                declaration = Declaration.objects.create(
                    round=current_round,
                    player=user,
                    declaration_type='belot',
                    cards_json=belot_cards,
                    value=declaration_value
                )
                
                # Ažuriraj povijest igre
                self._update_game_history(game, f"Igrač {user.username} je zvao belu")
                
                # Vrati rezultat zvanja
                return {
                    'valid': True,
                    'declaration_id': str(declaration.id),
                    'declaration_type': 'belot',
                    'value': declaration_value,
                    'cards': belot_cards,
                    'message': 'Bela uspješno zvana'
                }
                
        except Exception as e:
            logger.error(f"Greška pri obradi zvanja bele korisnika {user_id}: {str(e)}", exc_info=True)
            return {'valid': False, 'message': f'Greška pri obradi zvanja bele: {str(e)}'}
    
    @track_execution_time
    def is_player_turn(self, user_id):
        """
        Provjerava je li igrač na potezu.
        
        Ova metoda provjerava je li određeni igrač trenutno na potezu
        u aktivnoj rundi igre.
        
        Args:
            user_id: ID korisnika za kojeg se provjerava
            
        Returns:
            bool: True ako je igrač na potezu, inače False
        """
        try:
            # Dohvati igru s kešom
            game = self.get_game(check_exists=True, use_cache=True)
            if not game:
                logger.debug(f"Provjera is_player_turn: igra nije pronađena za korisnika {user_id}")
                return False
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                logger.debug(f"Provjera is_player_turn: nema aktivne runde za igru {game.id}")
                return False
            
            # Provjeri je li korisnik aktivan u igri
            if not game.active_players.filter(id=user_id).exists():
                logger.debug(f"Provjera is_player_turn: korisnik {user_id} nije aktivan u igri {game.id}")
                return False
            
            # Provjeri je li igrač na potezu
            is_turn = current_round.current_player_id == user_id
            logger.debug(f"Provjera is_player_turn za korisnika {user_id} u igri {game.id}: {is_turn}")
            return is_turn
            
        except Exception as e:
            logger.error(f"Greška pri provjeri je li igrač na potezu: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def can_call_trump(self, user_id):
        """
        Provjerava može li igrač zvati aduta.
        
        Ova metoda provjerava je li igrač na potezu u fazi zvanja aduta,
        što znači da može zvati aduta.
        
        Args:
            user_id: ID korisnika za kojeg se provjerava
            
        Returns:
            bool: True ako igrač može zvati aduta, inače False
        """
        try:
            # Dohvati igru s kešom
            game = self.get_game(check_exists=True, use_cache=True)
            if not game:
                logger.debug(f"Provjera can_call_trump: igra nije pronađena za korisnika {user_id}")
                return False
            
            # Provjeri je li korisnik aktivan u igri
            if not game.active_players.filter(id=user_id).exists():
                logger.debug(f"Provjera can_call_trump: korisnik {user_id} nije aktivan u igri {game.id}")
                return False
            
            # Dohvati trenutnu rundu
            current_round = GameRepository.get_current_round(game)
            if not current_round:
                logger.debug(f"Provjera can_call_trump: nema aktivne runde za igru {game.id}")
                return False
            
            # Provjeri je li status runde 'bidding'
            if current_round.status != 'bidding':
                logger.debug(f"Provjera can_call_trump: runda {current_round.id} nije u fazi zvanja aduta (status: {current_round.status})")
                return False
            
            # Provjeri je li igrač na potezu
            can_call = current_round.current_player_id == user_id
            logger.debug(f"Provjera can_call_trump za korisnika {user_id} u igri {game.id}: {can_call}")
            return can_call
            
        except Exception as e:
            logger.error(f"Greška pri provjeri može li igrač zvati adut: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def can_start_game(self, user_id):
        """
        Provjerava može li igrač pokrenuti igru.
        
        Ova metoda provjerava je li igrač kreator igre, je li igra u statusu
        čekanja i ima li dovoljno igrača (4) da se igra može pokrenuti.
        
        Args:
            user_id: ID korisnika za kojeg se provjerava
            
        Returns:
            bool: True ako igrač može pokrenuti igru, inače False
        """
        try:
            # Dohvati igru s kešom
            game = self.get_game(check_exists=True, use_cache=True)
            if not game:
                logger.debug(f"Provjera can_start_game: igra nije pronađena za korisnika {user_id}")
                return False
            
            # Provjeri je li korisnik aktivan
            try:
                user = User.objects.get(id=user_id)
                if not user.is_active:
                    logger.debug(f"Provjera can_start_game: korisnik {user_id} nije aktivan")
                    return False
            except User.DoesNotExist:
                logger.debug(f"Provjera can_start_game: korisnik {user_id} ne postoji")
                return False
            
            # Provjeri je li kreator igre
            if game.creator_id != user_id:
                logger.debug(f"Provjera can_start_game: korisnik {user_id} nije kreator igre {game.id}")
                return False
            
            # Provjeri je li status igre 'waiting'
            if game.status != 'waiting':
                logger.debug(f"Provjera can_start_game: igra {game.id} nije u statusu čekanja (status: {game.status})")
                return False
            
            # Provjeri ima li dovoljno igrača i jesu li svi aktivni
            player_count = game.players.count()
            active_player_count = game.active_players.count()
            
            # Svi igrači moraju biti aktivni
            if active_player_count < player_count:
                logger.debug(f"Provjera can_start_game: igra {game.id} ima neaktivne igrače (aktivnih: {active_player_count}, ukupno: {player_count})")
                return False
            
            # Mora biti točno 4 igrača
            if player_count != 4:
                logger.debug(f"Provjera can_start_game: igra {game.id} nema potrebna 4 igrača (ima: {player_count})")
                return False
            
            # Provjeri jesu li svi igrači spremni
            all_ready = hasattr(game, 'ready_players') and game.ready_players.count() == 4
            
            if not all_ready:
                logger.debug(f"Provjera can_start_game: nisu svi igrači spremni u igri {game.id}")
                return False
            
            logger.debug(f"Provjera can_start_game za korisnika {user_id} u igri {game.id}: True")
            return True
            
        except Exception as e:
            logger.error(f"Greška pri provjeri može li igrač pokrenuti igru: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    @game_state_cache(timeout=60)  # Keširaj rezultat na 60 sekundi
    def get_game_state(self, user_id):
        """
        Dohvaća trenutno stanje igre za specifičnog igrača.
        
        Ova metoda dohvaća kompletno stanje igre prilagođeno za određenog igrača,
        uključujući podatke o igri, igračima, timovima, trenutnoj rundi, kartama
        igrača, trenutnom štihu, zvanjima i povijesti poteza.
        
        Args:
            user_id: ID korisnika za kojeg se dohvaća stanje
            
        Returns:
            dict: Stanje igre prilagođeno za igrača, ili poruka o grešci
            
        Raises:
            ValueError: Ako korisnik ili igra ne postoje
        """
        try:
            # Dohvati igru s kešom
            game = self.get_game(check_exists=True, use_cache=True)
            if not game:
                logger.warning(f"Igra nije pronađena pri dohvaćanju stanja za korisnika {user_id}")
                return {'error': 'Igra nije pronađena'}
            
            # Dohvati korisnika s optimizacijom
            try:
                user = User.objects.select_related('profile').get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"Pokušaj dohvaćanja stanja igre od strane nepostojećeg korisnika: {user_id}")
                return {'error': 'Korisnik ne postoji'}
            
            # Provjeri je li korisnik aktivan
            if not user.is_active:
                logger.warning(f"Pokušaj dohvaćanja stanja igre od strane neaktivnog korisnika: {user_id}")
                return {'error': 'Korisnički račun nije aktivan'}
            
            # Provjeri je li korisnik član igre
            if not game.players.filter(id=user_id).exists():
                logger.info(f"Korisnik {user_id} pokušava dohvatiti stanje igre {game.id} u kojoj nije član")
                return {'error': 'Niste član ove igre'}
            
            # Osnovni podaci o igri
            game_state = {
                'game_id': str(game.id),
                'room_code': game.room_code,
                'is_private': game.is_private,
                'status': game.status,
                'creator_id': str(game.creator_id) if game.creator_id else None,
                'scores': {
                    'team_a': game.team_a_score,
                    'team_b': game.team_b_score
                },
                'points_to_win': game.points_to_win,
                'created_at': game.created_at.isoformat() if game.created_at else None,
                'started_at': game.started_at.isoformat() if game.started_at else None,
                'ended_at': game.ended_at.isoformat() if game.ended_at else None,
                'updated_at': game.updated_at.isoformat() if hasattr(game, 'updated_at') and game.updated_at else None
            }
            
            # Podaci o igračima - optimiziraj s prefetch_related za aktivne i spremne igrače
            game = Game.objects.prefetch_related(
                'players', 'active_players', 'ready_players',
                'team_a_players', 'team_b_players'
            ).get(id=game.id)
            
            active_players = set(player.id for player in game.active_players.all())
            ready_players = set(player.id for player in game.ready_players.all()) if hasattr(game, 'ready_players') else set()
            
            players_data = []
            for player in game.players.all():
                is_active = player.id in active_players
                is_ready = player.id in ready_players
                
                player_data = {
                    'id': str(player.id),
                    'username': player.username,
                    'is_active': is_active,
                    'is_ready': is_ready,
                    'is_you': player.id == user_id
                }
                players_data.append(player_data)
            
            game_state['players'] = players_data
            
            # Podaci o timovima
            teams = {}
            for player in game.team_a_players.all():
                teams[str(player.id)] = 'a'
            for player in game.team_b_players.all():
                teams[str(player.id)] = 'b'
            
            game_state['teams'] = teams
            game_state['your_team'] = teams.get(str(user_id))
            
            # Trenutna runda
            current_round = GameRepository.get_current_round(game)
            if current_round:
                round_data = {
                    'id': str(current_round.id),
                    'number': current_round.round_number,
                    'status': current_round.status,
                    'trump_suit': current_round.trump_suit,
                    'calling_team': current_round.calling_team,
                    'current_player': str(current_round.current_player_id) if current_round.current_player else None,
                    'created_at': current_round.created_at.isoformat() if current_round.created_at else None,
                    'completed_at': current_round.completed_at.isoformat() if current_round.completed_at else None
                }
                
                # Prijevodi boja za lakše čitanje
                if current_round.trump_suit:
                    suit_translations = {
                        'S': 'pik',
                        'H': 'srce',
                        'D': 'karo', 
                        'C': 'tref'
                    }
                    round_data['trump_suit_name'] = suit_translations.get(current_round.trump_suit, current_round.trump_suit)
                
                game_state['round'] = round_data
                game_state['your_turn'] = current_round.current_player_id == user_id
                
                # Karte igrača - koristi keširanje
                user_cards = MoveRepository.get_player_cards(current_round, user)
                game_state['your_cards'] = [card.get_code() for card in user_cards]
                
                # Trenutni štih
                game_state['current_trick'] = current_round.current_trick_cards or []
                
                # Zvanja u rundi - optimiziraj s prefetch_related
                declarations = []
                declaration_objs = Declaration.objects.select_related('player').filter(
                    round=current_round
                ).order_by('-created_at')
                
                for declaration in declaration_objs:
                    declaration_data = {
                        'id': str(declaration.id),
                        'player_id': str(declaration.player_id),
                        'player_username': declaration.player.username,
                        'type': declaration.declaration_type,
                        'value': declaration.value,
                        'cards': declaration.cards_json,
                        'created_at': declaration.created_at.isoformat() if declaration.created_at else None
                    }
                    declarations.append(declaration_data)
                
                game_state['declarations'] = declarations
                
                # Povijest poteza u rundi - optimiziraj s select_related
                moves_history = []
                move_objs = Move.objects.select_related('player').filter(
                    round=current_round
                ).order_by('trick_number', 'order')
                
                for move in move_objs:
                    move_data = {
                        'player_id': str(move.player_id),
                        'player_username': move.player.username,
                        'card': move.card_code,
                        'trick_number': move.trick_number,
                        'order': move.order,
                        'is_winning': move.is_winning_card,
                        'created_at': move.created_at.isoformat() if hasattr(move, 'created_at') and move.created_at else None
                    }
                    moves_history.append(move_data)
                
                game_state['history'] = moves_history
                
                # Grupa štihova po broju za lakšu obradu na frontendu
                tricks = {}
                for move in moves_history:
                    trick_num = move['trick_number']
                    if trick_num not in tricks:
                        tricks[trick_num] = []
                    tricks[trick_num].append(move)
                
                game_state['tricks'] = tricks
                
            else:
                game_state['round'] = None
                game_state['your_turn'] = False
                game_state['your_cards'] = []
                game_state['current_trick'] = []
                game_state['declarations'] = []
                game_state['history'] = []
                game_state['tricks'] = {}
            
            # Logiraj uspješno dohvaćanje stanja
            logger.debug(f"Stanje igre {game.id} uspješno dohvaćeno za korisnika {user_id}")
            
            return game_state
            
        except User.DoesNotExist:
            logger.warning(f"Pokušaj dohvaćanja stanja igre od strane nepostojećeg korisnika: {user_id}")
            return {'error': 'Korisnik ne postoji'}
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju stanja igre: {str(e)}", exc_info=True)
            return {'error': f"Greška pri dohvaćanju stanja igre: {str(e)}"}
    
    # Pomoćne metode
    
    def _get_next_dealer(self, current_dealer, game):
        """
        Određuje sljedećeg djelitelja.
        
        Ova metoda određuje sljedećeg djelitelja na temelju trenutnog djelitelja.
        Sljedeći djelitelj je igrač koji sjedi desno od trenutnog djelitelja.
        
        Args:
            current_dealer: Trenutni djelitelj (User instanca)
            game: Instanca igre (Game instanca)
            
        Returns:
            User: Sljedeći djelitelj
            
        Raises:
            ValueError: Ako trenutni djelitelj nije član igre
        """
        try:
            players = list(game.players.all())
            if current_dealer not in players:
                logger.error(f"Pokušaj određivanja sljedećeg djelitelja za igrača {current_dealer.id} koji nije član igre {game.id}")
                raise ValueError(f"Djelitelj {current_dealer.id} nije član igre {game.id}")
                
            current_index = players.index(current_dealer)
            next_index = (current_index + 1) % 4
            next_dealer = players[next_index]
            
            logger.debug(f"Sljedeći djelitelj nakon {current_dealer.id} je {next_dealer.id} u igri {game.id}")
            return next_dealer
            
        except Exception as e:
            # U slučaju greške, vrati prvog igrača
            logger.error(f"Greška pri određivanju sljedećeg djelitelja: {str(e)}", exc_info=True)
            if players:
                logger.info(f"Vraćanje prvog igrača kao sljedećeg djelitelja zbog greške")
                return players[0]
            raise
    
    def _calculate_round_result(self, round_obj):
        """
        Izračunava rezultat runde.
        
        Ova metoda izračunava bodove za oba tima na temelju osvojenih štihova
        i zvanja u rundi. Uzima u obzir specifična pravila belota kao što je
        padanje tima koji je zvao adut ako nije osvojio više bodova od protivnika.
        
        Args:
            round_obj: Runda za koju se računa rezultat (Round instanca)
            
        Returns:
            dict: Rezultat runde s bodovima za oba tima i detaljima izračuna
            
        Raises:
            ValueError: Ako runda nije valjana ili nema potrebne podatke
        """
        try:
            game = round_obj.game
            
            # Dohvati poteze i zvanja s optimizacijom
            moves = Move.objects.select_related('player').filter(round=round_obj)
            declarations = Declaration.objects.select_related('player').filter(round=round_obj)
            
            if not round_obj.trump_suit:
                logger.warning(f"Pokušaj izračuna rezultata runde {round_obj.id} bez određenog aduta")
            
            # Grupiraj poteze po štihu za učinkovitiji izračun
            tricks = {}
            for move in moves:
                trick_num = move.trick_number
                if trick_num not in tricks:
                    tricks[trick_num] = []
                tricks[trick_num].append(move)
            
            # Izračunaj bodove za štihove
            team_a_trick_points = 0
            team_b_trick_points = 0
            
            team_a_players = set(p.id for p in game.team_a_players.all())
            team_b_players = set(p.id for p in game.team_b_players.all())
            
            winning_tricks_team_a = 0
            winning_tricks_team_b = 0
            
            for trick_num, trick_moves in tricks.items():
                # Odredi pobjednika štiha
                winning_move = next((move for move in trick_moves if move.is_winning_card), None)
                
                if winning_move:
                    winning_player = winning_move.player
                    winning_player_id = winning_player.id
                    
                    # Odredi pobjednički tim
                    if winning_player_id in team_a_players:
                        winning_team = 'a'
                        winning_tricks_team_a += 1
                    else:
                        winning_team = 'b'
                        winning_tricks_team_b += 1
                    
                    # Izračunaj bodove za štih
                    trick_points = sum(self._get_card_value(move.card_code, round_obj.trump_suit) for move in trick_moves)
                    
                    # Dodatni bodovi za zadnji štih
                    if trick_num == 8:
                        trick_points += 10
                    
                    # Dodaj bodove pobjedničkom timu
                    if winning_team == 'a':
                        team_a_trick_points += trick_points
                    else:
                        team_b_trick_points += trick_points
                    
                    logger.debug(f"Štih {trick_num}: pobjednik tim {winning_team}, bodovi: {trick_points}")
            
            # Izračunaj bodove za zvanja
            team_a_declarations = [d for d in declarations if d.player_id in team_a_players]
            team_b_declarations = [d for d in declarations if d.player_id in team_b_players]
            
            # Sortiraj zvanja po vrijednosti od najveće do najmanje
            team_a_declarations.sort(key=lambda d: d.value, reverse=True)
            team_b_declarations.sort(key=lambda d: d.value, reverse=True)
            
            # Odredi koji tim ima prioritet za zvanja
            max_team_a_value = team_a_declarations[0].value if team_a_declarations else 0
            max_team_b_value = team_b_declarations[0].value if team_b_declarations else 0
            
            if max_team_a_value > max_team_b_value:
                declaration_winner = 'a'
            elif max_team_b_value > max_team_a_value:
                declaration_winner = 'b'
            else:
                # Ako su jednake vrijednosti, prednost ima tim koji je zvao aduta
                declaration_winner = round_obj.calling_team
                
            team_a_declaration_points = sum(d.value for d in team_a_declarations) if declaration_winner == 'a' else 0
            team_b_declaration_points = sum(d.value for d in team_b_declarations) if declaration_winner == 'b' else 0
            
            # Stvori detaljne podatke o zvanjima
            declaration_details = {
                'team_a': [
                    {
                        'type': d.declaration_type,
                        'value': d.value,
                        'player_id': str(d.player_id),
                        'player_username': d.player.username,
                        'cards': d.cards_json
                    } for d in team_a_declarations
                ],
                'team_b': [
                    {
                        'type': d.declaration_type,
                        'value': d.value,
                        'player_id': str(d.player_id),
                        'player_username': d.player.username,
                        'cards': d.cards_json
                    } for d in team_b_declarations
                ],
                'winner': declaration_winner,
                'team_a_points': team_a_declaration_points,
                'team_b_points': team_b_declaration_points
            }
            
            logger.debug(f"Bodovi za zvanja: tim A: {team_a_declaration_points}, tim B: {team_b_declaration_points}, pobjednik: {declaration_winner}")
            
            # Izračunaj ukupne bodove
            team_a_total = team_a_trick_points + team_a_declaration_points
            team_b_total = team_b_trick_points + team_b_declaration_points
            
            # Odredi je li tim koji je zvao aduta prošao ili pao
            calling_team = round_obj.calling_team
            
            passed = (calling_team == 'a' and team_a_total > team_b_total) or (calling_team == 'b' and team_b_total > team_a_total)
            
            logger.debug(f"Bodovi prije određivanja pada: tim A: {team_a_total}, tim B: {team_b_total}, tim koji je zvao: {calling_team}, prošao: {passed}")
            
            if calling_team == 'a':
                if team_a_total <= team_b_total:
                    # Tim A je pao, svi bodovi idu timu B
                    team_b_final = team_a_total + team_b_total
                    team_a_final = 0
                    
                    logger.info(f"Tim A pao pri zvanju aduta. Svi bodovi ({team_b_final}) idu timu B.")
                else:
                    # Tim A je prošao
                    team_a_final = team_a_total
                    team_b_final = team_b_total
                    
                    logger.info(f"Tim A prošao pri zvanju aduta. Bodovi A: {team_a_final}, B: {team_b_final}")
            else:  # calling_team == 'b'
                if team_b_total <= team_a_total:
                    # Tim B je pao, svi bodovi idu timu A
                    team_a_final = team_a_total + team_b_total
                    team_b_final = 0
                    
                    logger.info(f"Tim B pao pri zvanju aduta. Svi bodovi ({team_a_final}) idu timu A.")
                else:
                    # Tim B je prošao
                    team_a_final = team_a_total
                    team_b_final = team_b_total
                    
                    logger.info(f"Tim B prošao pri zvanju aduta. Bodovi A: {team_a_final}, B: {team_b_final}")
            
            # Ažuriraj bodove runde
            round_obj.team_a_score = team_a_final
            round_obj.team_b_score = team_b_final
            round_obj.save(update_fields=['team_a_score', 'team_b_score'])
            
            # Vrati detaljan rezultat
            return {
                'team_a_points': team_a_final,
                'team_b_points': team_b_final,
                'team_a_trick_points': team_a_trick_points,
                'team_b_trick_points': team_b_trick_points,
                'team_a_declaration_points': team_a_declaration_points,
                'team_b_declaration_points': team_b_declaration_points,
                'calling_team': calling_team,
                'declaration_winner': declaration_winner,
                'passed': passed,
                'team_a_tricks_won': winning_tricks_team_a,
                'team_b_tricks_won': winning_tricks_team_b,
                'declarations': declaration_details,
                'last_trick_bonus': 10  # Bonus za zadnji štih
            }
            
        except Exception as e:
            logger.error(f"Greška pri izračunu rezultata runde {round_obj.id}: {str(e)}", exc_info=True)
            # Vrati osnovni rezultat u slučaju greške
            return {
                'team_a_points': 0,
                'team_b_points': 0,
                'error': str(e)
            }
    
    def _get_card_value(self, card_code, trump_suit):
        """
        Vraća vrijednost karte u bodovima.
        
        Args:
            card_code: Kod karte (npr. 'AH')
            trump_suit: Boja aduta
            
        Returns:
            int: Vrijednost karte u bodovima
        """
        card = Card.from_code(card_code)
        return card.get_value(trump_suit)
    
    def _update_player_statistics(self, game):
        """
        Ažurira statistiku igrača nakon završene igre.
        
        Ova metoda se poziva kada je igra završena i ažurira statistiku za sve
        igrače koji su sudjelovali u igri (broj pobjeda, poraza, i odigranih igara).
        
        Args:
            game: Instanca igre
        
        Returns:
            None
        """
        try:
            # Dohvati timove
            team_a_players = list(game.team_a_players.select_related('stats').all())
            team_b_players = list(game.team_b_players.select_related('stats').all())
            
            # Odredi pobjednike i gubitnike
            winners = team_a_players if game.winner_team == 'a' else team_b_players
            losers = team_b_players if game.winner_team == 'a' else team_a_players
            
            # Ažuriraj statistiku pobjednika
            for player in winners:
                try:
                    if hasattr(player, 'stats'):
                        player.stats.games_won += 1
                        player.stats.save(update_fields=['games_won'])
                        logger.info(f"Ažurirana statistika za pobjednika {player.id}: +1 pobjeda")
                except Exception as e:
                    logger.error(f"Greška pri ažuriranju statistike pobjednika {player.id}: {str(e)}")
            
            # Ažuriraj statistiku gubitnika
            for player in losers:
                try:
                    if hasattr(player, 'stats'):
                        player.stats.games_lost += 1
                        player.stats.save(update_fields=['games_lost'])
                        logger.info(f"Ažurirana statistika za gubitnika {player.id}: +1 poraz")
                except Exception as e:
                    logger.error(f"Greška pri ažuriranju statistike gubitnika {player.id}: {str(e)}")
            
            # Dodaj zapis u povijest igre
            self._update_game_history(
                game, 
                f"Statistika igrača ažurirana nakon završetka igre"
            )
            
        except Exception as e:
            logger.error(f"Greška pri ažuriranju statistike igrača: {str(e)}", exc_info=True)
    
    @track_execution_time
    def process_end_round(self, user_id):
        """
        Obrađuje završetak runde.
        
        Args:
            user_id (str): ID korisnika koji inicira završetak runde
            
        Returns:
            dict: Rezultat runde s detaljima o bodovima i statusu
        """
        try:
            # Dohvati igru
            game = self.get_game()
            if not game:
                logger.error(f"Igra ne postoji za završetak runde korisnika {user_id}")
                return {'success': False, 'message': 'Igra nije pronađena'}
                
            # Provjeri postoji li korisnik
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Korisnik {user_id} ne postoji")
                return {'success': False, 'message': 'Korisnik ne postoji'}
                
            # Provjeri je li korisnik dio igre
            if not game.players.filter(id=user_id).exists():
                logger.warning(f"Korisnik {user_id} nije dio igre {game.id}")
                return {'success': False, 'message': 'Korisnik nije dio ove igre'}
                
            # Provjeri je li igrač aktivan
            if not game.is_player_active(user_id):
                logger.warning(f"Korisnik {user_id} nije aktivan igrač u igri {game.id}")
                return {'success': False, 'message': 'Korisnik nije aktivan igrač u ovoj igri'}
                
            # Provjeri je li stanje igre validno
            if game.status != 'in_progress':
                logger.warning(f"Igra {game.id} nije u tijeku, trenutni status: {game.status}")
                return {'success': False, 'message': 'Igra nije u tijeku'}
            
            # Dohvati trenutnu rundu
            current_round = Round.objects.filter(
                game=game, 
                status='in_progress'
            ).order_by('-number').first()
            
            if not current_round:
                logger.error(f"Nema aktivne runde za igru {game.id}")
                return {'success': False, 'message': 'Nema aktivne runde'}
            
            # Provjeri jesu li svi potezi odigrani
            from game.services.card_service import CardService
            remaining_cards = CardService.get_remaining_cards(current_round)
            
            if remaining_cards > 0:
                logger.warning(f"Pokušaj završetka runde {current_round.id} s preostalih {remaining_cards} karata")
                return {
                    'success': False, 
                    'message': f'Runda nije završena, preostalo je još {remaining_cards} karata'
                }
            
            # Započni transakciju za očuvanje konzistentnosti podataka
            with transaction.atomic():
                # Izračunaj rezultat runde
                round_result = self._calculate_round_result(current_round)
                
                # Ažuriraj bodove ekipa
                team1_points = game.team1_points + round_result['team1_points']
                team2_points = game.team2_points + round_result['team2_points']
                
                # Ažuriraj rundu
                current_round.status = 'finished'
                current_round.team1_points = round_result['team1_points']
                current_round.team2_points = round_result['team2_points']
                current_round.team1_tricks_points = round_result['team1_tricks_points']
                current_round.team2_tricks_points = round_result['team2_tricks_points']
                current_round.team1_declarations_points = round_result['team1_declarations_points']
                current_round.team2_declarations_points = round_result['team2_declarations_points']
                current_round.save()
                
                # Provjeri je li igra završena
                is_game_finished = max(team1_points, team2_points) >= game.points_to_win
                
                # Ažuriraj igru
                game.team1_points = team1_points
                game.team2_points = team2_points
                
                if is_game_finished:
                    game.status = 'finished'
                    game.winner_team = 1 if team1_points > team2_points else 2
                    winner_team_str = "Tim 1" if game.winner_team == 1 else "Tim 2"
                    self._update_game_history(game, f"Igra završena. Pobjednik: {winner_team_str} ({max(team1_points, team2_points)} bodova)")
                else:
                    # Postavi novog djelitelja i stvori novu rundu
                    next_dealer = self._get_next_dealer(game, current_round.dealer)
                    new_round_number = current_round.number + 1
                    
                    new_round = Round.objects.create(
                        game=game,
                        number=new_round_number,
                        dealer=next_dealer,
                        status='created'
                    )
                    
                    self._update_game_history(game, f"Runda {current_round.number} završena. " +
                                               f"Tim 1: {round_result['team1_points']} bodova, " +
                                               f"Tim 2: {round_result['team2_points']} bodova. " +
                                               f"Nova runda {new_round_number} započeta.")
                
                game.save()
                
                # Vrati rezultat
                response = {
                    'success': True,
                    'round_number': current_round.number,
                    'team1_points': round_result['team1_points'],
                    'team2_points': round_result['team2_points'],
                    'team1_tricks_points': round_result['team1_tricks_points'],
                    'team2_tricks_points': round_result['team2_tricks_points'],
                    'team1_declarations_points': round_result['team1_declarations_points'],
                    'team2_declarations_points': round_result['team2_declarations_points'],
                    'team1_total_points': team1_points,
                    'team2_total_points': team2_points,
                    'is_game_finished': is_game_finished
                }
                
                if is_game_finished:
                    response['winner_team'] = game.winner_team
                else:
                    response['next_round_number'] = new_round_number
                    response['next_dealer'] = next_dealer.username
                
                return response
                
        except Exception as e:
            logger.error(f"Greška pri završetku runde za korisnika {user_id}: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Greška pri završetku runde: {str(e)}'}