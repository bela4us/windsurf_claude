"""
WebSocket potrošači (consumers) za Belot igru.

Ovaj modul implementira WebSocket potrošače koristeći Django Channels
koji omogućuju komunikaciju u stvarnom vremenu između igrača. Potrošači
obrađuju različite događaje igre (potezi, zvanja, predaja/napuštanje)
i šalju ažuriranja svim igračima u sobi.

Glavni consumer (GameConsumer) upravlja WebSocket vezama za igrače
koji sudjeluju u istoj igri, omogućujući:
- Pridruživanje igri i inicijalno učitavanje stanja
- Primanje obavijesti o potezima drugih igrača
- Slanje vlastitih poteza
- Zvanje aduta i prijavljivanje zvanja
- Primanje ažuriranja o rezultatu i promjenama stanja
"""

import json
import logging
import asyncio
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

# Uvoz potrebnih servisnih slojeva i modela
from game.models.game import Game
from game.models.round import Round
from game.models.move import Move
from game.services.game_service import GameService
from game.services.scoring_service import ScoringService
from game.game_logic.card import Card
from game.game_logic.deck import Deck

# Postavljanje loggera za praćenje događaja u igri
logger = logging.getLogger('game.consumers')
User = get_user_model()

class GameConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket potrošač za komunikaciju između igrača tijekom Belot igre.
    Obrađuje povezivanje/odspajanje igrača i razmjenu poruka tijekom igre.
    """
    
    async def connect(self):
        """
        Obrada zahtjeva za povezivanje - provjerava autentikaciju i
        pridružuje korisnika grupi za određenu igru.
        """
        # Provjera je li korisnik autentificiran
        if self.scope["user"].is_anonymous:
            await self.close(code=4001)  # Odbijanje konekcije za neprijavljene korisnike
            return
        
        # Dohvaćanje identifikatora igre iz URL parametara
        if 'game_id' in self.scope['url_route']['kwargs']:
            self.game_id = self.scope['url_route']['kwargs']['game_id']
        elif 'room_code' in self.scope['url_route']['kwargs']:
            # Dohvati game_id iz room_code
            room_code = self.scope['url_route']['kwargs']['room_code']
            game = await self.get_game_by_room_code(room_code)
            if game:
                self.game_id = str(game.id)
            else:
                await self.close(code=4003)  # Igra ne postoji
                return
        else:
            await self.close(code=4003)  # Nedostaje identifikator igre
            return

        self.user_id = self.scope["user"].id
        self.username = self.scope["user"].username
        self.room_group_name = f'game_{self.game_id}'
        
        # Provjera postoji li igra i je li korisnik član igre
        try:
            if not await self.is_user_in_game(self.user_id, self.game_id):
                await self.close(code=4002)  # Korisnik nije član ove igre
                return
        except ObjectDoesNotExist:
            await self.close(code=4003)  # Igra ne postoji
            return
        
        # Pridruživanje korisnika WebSocket grupi za ovu igru
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Prihvaćanje WebSocket konekcije
        await self.accept()
        
        # Označavanje korisnika kao aktivnog/povezanog u igri
        await self.set_user_active(True)
        
        # Slanje trenutnog stanja igre novopovezanom korisniku
        await self.send_game_state()
        
        # Obavještavanje ostalih igrača o povezivanju ovog korisnika
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_status',
                'user_id': self.user_id,
                'username': self.username,
                'status': 'connected'
            }
        )
        
        logger.info(f"Korisnik {self.username} (ID: {self.user_id}) povezan na igru {self.game_id}")

    @database_sync_to_async
    def get_game_by_room_code(self, room_code):
        """Dohvaća igru prema kodu sobe."""
        try:
            return Game.objects.get(room_code=room_code)
        except Game.DoesNotExist:
            return None
    
    async def disconnect(self, close_code):
        """
        Obrada odspajanja korisnika - uklanja korisnika iz grupe
        i ažurira njegov status u igri.
        """
        if hasattr(self, 'room_group_name'):
            # Označavanje korisnika kao neaktivnog u igri
            await self.set_user_active(False)
            
            # Obavještavanje ostalih igrača o odspajanju
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_status',
                    'user_id': self.user_id,
                    'username': self.username,
                    'status': 'disconnected'
                }
            )
            
            # Uklanjanje korisnika iz WebSocket grupe
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"Korisnik {self.username} (ID: {self.user_id}) odspojen iz igre {self.game_id}, kod: {close_code}")
            
            # Ako je igra u tijeku, pokreni timer za auto-napuštanje igre
            # nakon određenog perioda neaktivnosti
            if await self.is_game_in_progress():
                await self.start_inactivity_timer()

    async def receive_json(self, content):
        """
        Obrada dolaznih WebSocket poruka od klijenata.
        Usmjerava poruke na temelju njihovog tipa (akcije).
        """
        action = content.get('action')
        
        # Resetiranje timera za neaktivnost ako je igra u tijeku
        if await self.is_game_in_progress():
            if hasattr(self, 'inactivity_task') and self.inactivity_task:
                self.inactivity_task.cancel()
            
            # Ako je korisnik aktivan i igra u tijeku, pokreni novi timer
            await self.start_inactivity_timer()
        
        # Usmjeravanje prema tipu akcije
        if action == 'make_move':
            await self.make_move(content)
        elif action == 'call_trump':
            await self.call_trump(content)
        elif action == 'pass_trump':
            await self.pass_trump(content)
        elif action == 'declare':
            await self.declare(content)
        elif action == 'bela':
            await self.declare_bela(content)
        elif action == 'chat_message':
            await self.chat_message(content)
        elif action == 'leave_game':
            await self.leave_game()
        elif action == 'start_game':
            await self.start_game()
        elif action == 'ready':
            await self.mark_ready()
        elif action == 'get_game_state':
            await self.send_game_state()
        else:
            await self.send_json({
                'type': 'error',
                'message': f'Nepoznata akcija: {action}'
            })
            logger.warning(f"Korisnik {self.username} poslao nepoznatu akciju: {action}")

    # Dopune postojeće klase GameConsumer

# Dodajte ove metode unutar klase GameConsumer

    async def play_card(self, content):
        """
        Obrada igranja karte.
        
        Ova metoda se poziva kada igrač igra kartu putem WebSocketa.
        Validira potez i obavještava sve igrače o potrezu.
        """
        try:
            card_code = content.get('card')
            
            # Provjera je li igrač na potezu
            if not await self.is_player_turn():
                await self.send_json({
                    'type': 'error',
                    'message': 'Nije tvoj red za potez'
                })
                return
            
            # Validacija i izvršavanje poteza kroz game_service
            card = Card.from_code(card_code)
            move_data = await self.process_move(card)
            
            if not move_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': move_data.get('message', 'Nevažeći potez')
                })
                return
            
            # Obavještavanje svih igrača o potrezu
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_move',
                    'user_id': self.user_id,
                    'username': self.username,
                    'card': card_code,
                    'trick_completed': move_data.get('trick_completed', False),
                    'trick_winner': move_data.get('trick_winner'),
                    'next_player': move_data.get('next_player'),
                    'round_completed': move_data.get('round_completed', False),
                    'round_results': move_data.get('round_results', {}),
                    'game_completed': move_data.get('game_completed', False),
                    'game_results': move_data.get('game_results', {})
                }
            )
            
            logger.info(f"Korisnik {self.username} odigrao kartu {card_code} u igri {self.game_id}")
            
        except ValidationError as e:
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception as e:
            logger.error(f"Greška pri obradi poteza: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri obradi poteza'
            })

    async def bid_trump(self, content):
        """
        Obrada zvanja aduta.
        
        Ova metoda se poziva kada igrač zove aduta putem WebSocketa.
        Validira zvanje i obavještava sve igrače o zvanom adutu.
        """
        try:
            suit = content.get('suit')
            
            # Provjera je li igrač na redu za zvanje aduta
            if not await self.can_call_trump():
                await self.send_json({
                    'type': 'error',
                    'message': 'Nije tvoj red za zvanje aduta'
                })
                return
            
            # Validacija i zvanje aduta kroz game_service
            trump_data = await self.process_trump_call(suit)
            
            if not trump_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': trump_data.get('message', 'Nevažeće zvanje aduta')
                })
                return
            
            # Obavještavanje svih igrača o zvanju aduta
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'trump_called',
                    'user_id': self.user_id,
                    'username': self.username,
                    'suit': suit,
                    'calling_team': trump_data.get('calling_team'),
                    'round_number': trump_data.get('round_number'),
                    'next_player': trump_data.get('next_player'),
                    'player_cards': trump_data.get('player_cards', {})
                }
            )
            
            logger.info(f"Korisnik {self.username} zvao adut {suit} u igri {self.game_id}")
            
        except ValidationError as e:
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception as e:
            logger.error(f"Greška pri zvanju aduta: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri zvanju aduta'
            })

    async def declare(self, content):
        """
        Obrada zvanja (belot, niz, četvorke).
        
        Ova metoda se poziva kada igrač prijavljuje zvanje putem WebSocketa.
        Validira zvanje i obavještava sve igrače o prijavljenom zvanju.
        """
        try:
            declaration_type = content.get('type')
            cards = content.get('cards', [])
            
            # Validacija i obrada zvanja kroz game_service
            declaration_data = await self.process_declaration(declaration_type, cards)
            
            if not declaration_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': declaration_data.get('message', 'Nevažeće zvanje')
                })
                return
            
            # Obavještavanje svih igrača o zvanju
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'declaration',
                    'user_id': self.user_id,
                    'username': self.username,
                    'declaration_type': declaration_type,
                    'cards': cards,
                    'value': declaration_data.get('value')
                }
            )
            
            logger.info(f"Korisnik {self.username} prijavio zvanje {declaration_type} u igri {self.game_id}")
            
        except ValidationError as e:
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception as e:
            logger.error(f"Greška pri prijavi zvanja: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri prijavi zvanja'
            })

    async def declare_bela(self, content):
        """
        Obrada zvanja bele (kralj i dama u istoj boji u adutu).
        """
        try:
            # Validacija i obrada zvanja bele
            bela_data = await self.process_bela()
            
            if not bela_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': bela_data.get('message', 'Nevažeća bela')
                })
                return
            
            # Obavještavanje svih igrača o beli
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'bela_declared',
                    'user_id': self.user_id,
                    'username': self.username,
                    'suit': bela_data.get('suit'),
                    'value': 20
                }
            )
            
            logger.info(f"Korisnik {self.username} prijavio belu u igri {self.game_id}")
            
        except ValidationError as e:
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception as e:
            logger.error(f"Greška pri prijavi bele: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri prijavi bele'
            })

    async def chat_message(self, content):
        """
        Obrada chat poruka između igrača.
        """
        message = content.get('message', '').strip()
        
        if not message:
            return
        
        # Ograničenje duljine poruke
        if len(message) > 200:
            message = message[:197] + '...'
        
        # Slanje poruke svim igračima
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'user_id': self.user_id,
                'username': self.username,
                'message': message,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def leave_game(self):
        """
        Obrada zahtjeva za napuštanjem igre.
        """
        try:
            # Obrada napuštanja igre
            leave_data = await self.process_leave_game()
            
            # Obavještavanje svih igrača o napuštanju
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_left',
                    'user_id': self.user_id,
                    'username': self.username,
                    'game_status': leave_data.get('game_status'),
                    'winner_team': leave_data.get('winner_team')
                }
            )
            
            logger.info(f"Korisnik {self.username} napustio igru {self.game_id}")
            
            # Zatvaranje WebSocket konekcije
            await self.close(code=1000)
            
        except Exception as e:
            logger.error(f"Greška pri napuštanju igre: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri napuštanju igre'
            })

    async def start_game(self):
        """
        Obrada zahtjeva za pokretanjem igre.
        """
        try:
            # Provjera može li korisnik pokrenuti igru
            if not await self.can_start_game():
                await self.send_json({
                    'type': 'error',
                    'message': 'Ne možeš pokrenuti igru'
                })
                return
            
            # Obrada pokretanja igre
            start_data = await self.process_start_game()
            
            if not start_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': start_data.get('message', 'Nije moguće pokrenuti igru')
                })
                return
            
            # Obavještavanje svih igrača o pokretanju igre
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_started',
                    'started_by': self.username,
                    'dealer': start_data.get('dealer'),
                    'player_cards': start_data.get('player_cards', {}),
                    'next_player': start_data.get('next_player')
                }
            )
            
            logger.info(f"Korisnik {self.username} pokrenuo igru {self.game_id}")
            
        except Exception as e:
            logger.error(f"Greška pri pokretanju igre: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri pokretanju igre'
            })

    async def mark_ready(self):
        """
        Označavanje igrača kao spremnog za igru.
        """
        try:
            # Provjera može li se korisnik označiti kao spreman
            ready_data = await self.process_mark_ready()
            
            if not ready_data.get('valid', False):
                await self.send_json({
                    'type': 'error',
                    'message': ready_data.get('message', 'Nije moguće označiti spremnost')
                })
                return
            
            # Obavještavanje svih igrača o spremnosti
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_ready',
                    'user_id': self.user_id,
                    'username': self.username,
                    'all_ready': ready_data.get('all_ready', False)
                }
            )
            
            logger.info(f"Korisnik {self.username} označio spremnost u igri {self.game_id}")
            
        except Exception as e:
            logger.error(f"Greška pri označavanju spremnosti: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri označavanju spremnosti'
            })

    async def send_game_state(self):
        """
        Slanje trenutnog stanja igre klijentu.
        """
        try:
            # Dohvaćanje stanja igre
            game_state = await self.get_game_state()
            
            # Slanje stanja igre
            await self.send_json({
                'type': 'game_state',
                'game_id': self.game_id,
                'status': game_state.get('status'),
                'players': game_state.get('players', []),
                'teams': game_state.get('teams', {}),
                'scores': game_state.get('scores', {}),
                'round': game_state.get('round', {}),
                'your_turn': game_state.get('your_turn', False),
                'your_cards': game_state.get('your_cards', []),
                'current_trick': game_state.get('current_trick', []),
                'declarations': game_state.get('declarations', []),
                'history': game_state.get('history', []),
                'your_team': game_state.get('your_team')
            })
            
        except Exception as e:
            logger.error(f"Greška pri slanju stanja igre: {str(e)}", exc_info=True)
            await self.send_json({
                'type': 'error',
                'message': 'Došlo je do greške pri dohvaćanju stanja igre'
            })

    async def start_inactivity_timer(self):
        """
        Pokretanje timera za automatsko napuštanje igre zbog neaktivnosti.
        """
        # Otkazivanje postojećeg timera ako postoji
        if hasattr(self, 'inactivity_task') and self.inactivity_task:
            self.inactivity_task.cancel()
        
        # Dohvaćanje vremena neaktivnosti iz postavki
        from django.conf import settings
        inactive_timeout = settings.BELOT_GAME.get('INACTIVE_TIMEOUT', 300)  # 5 minuta zadano
        
        # Pokretanje timera
        self.inactivity_task = asyncio.create_task(
            self.handle_inactivity_timeout(inactive_timeout)
        )

    async def handle_inactivity_timeout(self, timeout):
        """
        Rukovanje istekom vremena neaktivnosti - automatsko napuštanje igre.
        """
        try:
            # Čekanje isteka timera
            await asyncio.sleep(timeout)
            
            # Provjera je li korisnik još uvijek neaktivan
            if not await self.is_user_active():
                # Automatsko napuštanje igre
                leave_data = await self.process_leave_game(reason="inactivity")
                
                # Obavještavanje svih igrača o napuštanju
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'player_left',
                        'user_id': self.user_id,
                        'username': self.username,
                        'reason': 'inactivity',
                        'game_status': leave_data.get('game_status'),
                        'winner_team': leave_data.get('winner_team')
                    }
                )
                
                logger.info(f"Korisnik {self.username} automatski napustio igru {self.game_id} zbog neaktivnosti")
                
                # Zatvaranje WebSocket konekcije
                await self.close(code=4000)
        except asyncio.CancelledError:
            # Timer je otkazan jer se korisnik vratio u igru
            pass
        except Exception as e:
            logger.error(f"Greška u timeru neaktivnosti: {str(e)}", exc_info=True)

    # Handler metode za poruke od channel layera (od drugih korisnika)
    
    async def player_status(self, event):
        """Prosljeđivanje informacije o statusu igrača."""
        await self.send_json({
            'type': 'player_status',
            'user_id': event['user_id'],
            'username': event['username'],
            'status': event['status']
        })

    async def game_move(self, event):
        """Prosljeđivanje informacije o potezu igrača."""
        await self.send_json({
            'type': 'game_move',
            'user_id': event['user_id'],
            'username': event['username'],
            'card': event['card'],
            'trick_completed': event['trick_completed'],
            'trick_winner': event['trick_winner'],
            'next_player': event['next_player'],
            'round_completed': event['round_completed'],
            'round_results': event['round_results'],
            'game_completed': event['game_completed'],
            'game_results': event['game_results']
        })

    async def trump_called(self, event):
        """Prosljeđivanje informacije o zvanju aduta."""
        # Filtriraj karte samo za trenutnog igrača
        player_cards = {}
        if self.user_id in event.get('player_cards', {}):
            player_cards = {self.user_id: event['player_cards'][self.user_id]}
        
        await self.send_json({
            'type': 'trump_called',
            'user_id': event['user_id'],
            'username': event['username'],
            'suit': event['suit'],
            'calling_team': event['calling_team'],
            'round_number': event['round_number'],
            'next_player': event['next_player'],
            'player_cards': player_cards
        })

    async def trump_passed(self, event):
        """Prosljeđivanje informacije o propuštanju zvanja aduta."""
        await self.send_json({
            'type': 'trump_passed',
            'user_id': event['user_id'],
            'username': event['username'],
            'next_player': event['next_player'],
            'must_call': event['must_call']
        })

    async def declaration(self, event):
        """Prosljeđivanje informacije o zvanju."""
        await self.send_json({
            'type': 'declaration',
            'user_id': event['user_id'],
            'username': event['username'],
            'declaration_type': event['declaration_type'],
            'cards': event['cards'],
            'value': event['value']
        })

    async def bela_declared(self, event):
        """Prosljeđivanje informacije o zvanju bele."""
        await self.send_json({
            'type': 'bela_declared',
            'user_id': event['user_id'],
            'username': event['username'],
            'suit': event['suit'],
            'value': event['value']
        })

    async def chat_message(self, event):
        """Prosljeđivanje chat poruke."""
        await self.send_json({
            'type': 'chat_message',
            'user_id': event['user_id'],
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp']
        })

    async def player_left(self, event):
        """Prosljeđivanje informacije o napuštanju igre."""
        await self.send_json({
            'type': 'player_left',
            'user_id': event['user_id'],
            'username': event['username'],
            'reason': event.get('reason', 'voluntary'),
            'game_status': event['game_status'],
            'winner_team': event['winner_team']
        })

    async def game_started(self, event):
        """Prosljeđivanje informacije o pokretanju igre."""
        # Filtriraj karte samo za trenutnog igrača
        player_cards = {}
        if self.user_id in event.get('player_cards', {}):
            player_cards = {self.user_id: event['player_cards'][self.user_id]}
        
        await self.send_json({
            'type': 'game_started',
            'started_by': event['started_by'],
            'dealer': event['dealer'],
            'player_cards': player_cards,
            'next_player': event['next_player']
        })

    async def player_ready(self, event):
        """Prosljeđivanje informacije o spremnosti igrača."""
        await self.send_json({
            'type': 'player_ready',
            'user_id': event['user_id'],
            'username': event['username'],
            'all_ready': event['all_ready']
        })

    # Database access metode (sync_to_async wrappers)
    
    @database_sync_to_async
    def is_user_in_game(self, user_id, game_id):
        """Provjera je li korisnik član igre."""
        try:
            game = Game.objects.get(id=game_id)
            return game.players.filter(id=user_id).exists()
        except Game.DoesNotExist:
            raise ObjectDoesNotExist("Igra ne postoji")

    @database_sync_to_async
    def set_user_active(self, active):
        """Označavanje korisnika kao aktivnog/neaktivnog u igri."""
        game = Game.objects.get(id=self.game_id)
        user = User.objects.get(id=self.user_id)
        
        if active:
            # Povezivanje kroz ManyToMany varijablu neće imati učinka ako korisnik već postoji
            # Koristi alternativnu metodu ako je potrebno pratiti status konekcije
            game.active_players.add(user)
        else:
            game.active_players.remove(user)
        
        return True

    @database_sync_to_async
    def is_user_active(self):
        """Provjera je li korisnik aktivan u igri."""
        game = Game.objects.get(id=self.game_id)
        return game.active_players.filter(id=self.user_id).exists()

    @database_sync_to_async
    def is_game_in_progress(self):
        """Provjera je li igra u tijeku."""
        game = Game.objects.get(id=self.game_id)
        return game.status == 'in_progress'

    @database_sync_to_async
    def is_player_turn(self):
        """Provjera je li igrač na potezu."""
        # Ovo bi trebalo pozvati odgovarajuću metodu iz GameService
        game_service = GameService(self.game_id)
        return game_service.is_player_turn(self.user_id)

    @database_sync_to_async
    def can_call_trump(self):
        """Provjera može li igrač zvati aduta."""
        game_service = GameService(self.game_id)
        return game_service.can_call_trump(self.user_id)

    @database_sync_to_async
    def can_start_game(self):
        """Provjera može li igrač pokrenuti igru."""
        game_service = GameService(self.game_id)
        return game_service.can_start_game(self.user_id)

    @database_sync_to_async
    def get_game_state(self):
        """Dohvaćanje trenutnog stanja igre."""
        game_service = GameService(self.game_id)
        return game_service.get_game_state(self.user_id)

    @database_sync_to_async
    def process_move(self, card):
        """Obrada poteza igrača."""
        game_service = GameService(self.game_id)
        return game_service.process_move(self.user_id, card)

    @database_sync_to_async
    def process_trump_call(self, suit):
        """Obrada zvanja aduta."""
        game_service = GameService(self.game_id)
        return game_service.process_trump_call(self.user_id, suit)

    @database_sync_to_async
    def process_trump_pass(self):
        """Obrada propuštanja zvanja aduta."""
        game_service = GameService(self.game_id)
        return game_service.process_trump_pass(self.user_id)

    @database_sync_to_async
    def process_declaration(self, declaration_type, cards):
        """Obrada zvanja."""
        game_service = GameService(self.game_id)
        return game_service.process_declaration(self.user_id, declaration_type, cards)

    @database_sync_to_async
    def process_bela(self):
        """Obrada zvanja bele."""
        game_service = GameService(self.game_id)
        return game_service.process_bela(self.user_id)

    @database_sync_to_async
    def process_leave_game(self, reason="voluntary"):
        """Obrada napuštanja igre."""
        game_service = GameService(self.game_id)
        return game_service.process_leave_game(self.user_id, reason)

    @database_sync_to_async
    def process_start_game(self):
        """Obrada pokretanja igre."""
        game_service = GameService(self.game_id)
        return game_service.start_game(self.user_id)

    @database_sync_to_async
    def process_mark_ready(self):
        """Obrada označavanja spremnosti."""
        game_service = GameService(self.game_id)
        return game_service.mark_player_ready(self.user_id)