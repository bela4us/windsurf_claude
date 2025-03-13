"""
WebSocket potrošači (consumers) za Django aplikaciju "lobby".

Ovaj modul implementira WebSocket potrošače koji omogućuju stvarno-vremensku
komunikaciju između servera i klijenata u predvorju Belot igre, uključujući
chat, obavijesti o promjenama statusa sobe i ažuriranja korisničkih akcija.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from utils.decorators import require_websocket
from .models import LobbyRoom, LobbyMembership, LobbyMessage, LobbyEvent, LobbyInvitation

User = get_user_model()
logger = logging.getLogger('lobby.consumers')


class LobbyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket potrošač za predvorje Belot igre.
    
    Upravlja općim obavijestima za predvorje, kao što su stvaranje
    novih soba, ažuriranje statusa igrača i pozivnice za igru.
    """
    
    async def connect(self):
        """Uspostavi WebSocket vezu s klijentom."""
        self.user = self.scope["user"]
        
        # Provjeri je li korisnik prijavljen
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Pridruži se općem kanalu za predvorje
        self.lobby_group_name = 'lobby_general'
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        
        # Pridruži se osobnom kanalu korisnika za obavijesti
        self.user_group_name = f'user_{self.user.id}'
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Obavijesti korisnika o uspješnom povezivanju
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': _('Povezan na predvorje Belot igre.')
        }))
        
        # Pošalji korisnikov popis pozivnica koje čekaju odgovor
        await self.send_pending_invitations()
    
    async def disconnect(self, close_code):
        """Prekini WebSocket vezu s klijentom."""
        # Napusti grupe
        if hasattr(self, 'lobby_group_name'):
            await self.channel_layer.group_discard(
                self.lobby_group_name,
                self.channel_name
            )
        
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Primi poruku od klijenta."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            # Obradi različite tipove poruka
            if message_type == 'lobby_status_request':
                await self.send_lobby_status()
            elif message_type == 'invitation_response':
                await self.handle_invitation_response(data)
            elif message_type == 'check_invitations':
                await self.send_pending_invitations()
        except json.JSONDecodeError:
            logger.error(f"Primljen nevažeći JSON: {text_data[:100]}...")
        except Exception as e:
            logger.error(f"Greška pri primanju poruke: {str(e)}")
    
    async def lobby_update(self, event):
        """Proslijedi ažuriranje predvorja klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'lobby_update',
            'update_type': event.get('update_type', ''),
            'message': event.get('message', ''),
            'data': event.get('data', {})
        }))
    
    async def room_update(self, event):
        """Proslijedi ažuriranje sobe klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'room_update',
            'room_id': event.get('room_id', ''),
            'update_type': event.get('update_type', ''),
            'message': event.get('message', ''),
            'data': event.get('data', {})
        }))
    
    async def user_notification(self, event):
        """Proslijedi osobnu obavijest klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'user_notification',
            'notification_type': event.get('notification_type', ''),
            'message': event.get('message', ''),
            'data': event.get('data', {})
        }))
    
    async def invitation_notification(self, event):
        """Proslijedi obavijest o pozivnici klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'invitation_notification',
            'invitation_id': event.get('invitation_id', ''),
            'sender': event.get('sender', ''),
            'room_name': event.get('room_name', ''),
            'message': event.get('message', '')
        }))
    
    @database_sync_to_async
    def get_pending_invitations(self):
        """Dohvati pozivnice korisnika koje čekaju odgovor."""
        invitations = LobbyInvitation.objects.filter(
            recipient=self.user,
            status='pending'
        ).select_related('room', 'sender')
        
        return [
            {
                'id': str(inv.id),
                'sender': inv.sender.username,
                'room_name': inv.room.name,
                'room_id': str(inv.room.id),
                'created_at': inv.created_at.isoformat(),
                'message': inv.message
            }
            for inv in invitations
        ]
    
    @database_sync_to_async
    def get_lobby_status(self):
        """Dohvati trenutni status predvorja."""
        # Dohvati otvorene javne sobe
        public_rooms = LobbyRoom.objects.filter(
            is_private=False,
            status='open'
        ).select_related('creator')[:10]
        
        # Dohvati sobe korisnika
        user_rooms = LobbyRoom.objects.filter(
            players=self.user
        ).exclude(
            status='closed'
        ).select_related('creator')
        
        # Formatiraj podatke za odgovor
        public_room_data = []
        for room in public_rooms:
            player_count = room.lobbymembership_set.count()
            public_room_data.append({
                'id': str(room.id),
                'name': room.name,
                'creator': room.creator.username,
                'player_count': player_count,
                'status': room.status,
                'created_at': room.created_at.isoformat()
            })
        
        user_room_data = []
        for room in user_rooms:
            player_count = room.lobbymembership_set.count()
            user_room_data.append({
                'id': str(room.id),
                'name': room.name,
                'creator': room.creator.username,
                'player_count': player_count,
                'status': room.status,
                'created_at': room.created_at.isoformat()
            })
        
        return {
            'public_rooms': public_room_data,
            'user_rooms': user_room_data
        }
    
    @database_sync_to_async
    def process_invitation_response(self, invitation_id, action):
        """Obradi odgovor na pozivnicu."""
        try:
            invitation = LobbyInvitation.objects.get(
                id=invitation_id,
                recipient=self.user,
                status='pending'
            )
            
            if action == 'accept':
                return invitation.accept()
            elif action == 'decline':
                return invitation.decline()
            else:
                return False
                
        except LobbyInvitation.DoesNotExist:
            return False
    
    async def send_pending_invitations(self):
        """Pošalji popis pozivnica koje čekaju odgovor."""
        invitations = await self.get_pending_invitations()
        
        await self.send(text_data=json.dumps({
            'type': 'pending_invitations',
            'invitations': invitations
        }))
    
    async def send_lobby_status(self):
        """Pošalji trenutni status predvorja."""
        status = await self.get_lobby_status()
        
        await self.send(text_data=json.dumps({
            'type': 'lobby_status',
            'status': status
        }))
    
    async def handle_invitation_response(self, data):
        """Obradi odgovor na pozivnicu."""
        invitation_id = data.get('invitation_id')
        action = data.get('action')
        
        if not invitation_id or action not in ['accept', 'decline']:
            return
        
        success = await self.process_invitation_response(invitation_id, action)
        
        if success and action == 'accept':
            # Obavijesti korisnika o uspješnom pridruživanju
            await self.send(text_data=json.dumps({
                'type': 'invitation_processed',
                'success': True,
                'action': action,
                'message': _('Uspješno ste se pridružili sobi.')
            }))
        else:
            # Obavijesti korisnika o ishodu
            await self.send(text_data=json.dumps({
                'type': 'invitation_processed',
                'success': success,
                'action': action,
                'message': _('Pozivnica je obrađena.') if success else _('Nije moguće obraditi pozivnicu.')
            }))


class RoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket potrošač za sobu u predvorju.
    
    Upravlja stvarno-vremenskom komunikacijom unutar sobe, uključujući
    chat poruke, obavijesti o promjenama statusa igrača i pokretanje igre.
    """
    
    async def connect(self):
        """Uspostavi WebSocket vezu s klijentom."""
        self.user = self.scope["user"]
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        
        # Provjeri je li korisnik prijavljen
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Provjeri ima li korisnik pristup sobi
        if not await self.can_access_room():
            await self.close()
            return
        
        # Pridruži se grupi sobe
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Obavijesti sobu o povezivanju korisnika
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'username': self.user.username,
                'user_id': self.user.id
            }
        )
        
        # Pošalji trenutni status sobe
        await self.send_room_status()
    
    async def disconnect(self, close_code):
        """Prekini WebSocket vezu s klijentom."""
        # Ažuriraj status korisnika u sobi ako je odspojio
        # await self.mark_user_inactive()
        
        # Obavijesti sobu o odspajanju korisnika
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'username': self.user.username,
                    'user_id': self.user.id
                }
            )
            
            # Napusti grupu sobe
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Primi poruku od klijenta."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            # Obradi različite tipove poruka
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'toggle_ready':
                await self.handle_toggle_ready()
            elif message_type == 'start_game':
                await self.handle_start_game()
            elif message_type == 'status_request':
                await self.send_room_status()
        except json.JSONDecodeError:
            logger.error(f"Primljen nevažeći JSON: {text_data[:100]}...")
        except Exception as e:
            logger.error(f"Greška pri primanju poruke: {str(e)}")
    
    async def chat_message(self, event):
        """Proslijedi chat poruku klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event.get('message_id', ''),
            'sender': event.get('sender', ''),
            'sender_id': event.get('sender_id', ''),
            'content': event.get('content', ''),
            'timestamp': event.get('timestamp', ''),
            'is_system_message': event.get('is_system_message', False)
        }))
    
    async def user_joined(self, event):
        """Proslijedi obavijest o pridruživanju korisnika klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'username': event.get('username', ''),
            'user_id': event.get('user_id', '')
        }))
    
    async def user_left(self, event):
        """Proslijedi obavijest o napuštanju korisnika klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'username': event.get('username', ''),
            'user_id': event.get('user_id', '')
        }))
    
    async def user_ready(self, event):
        """Proslijedi obavijest o promjeni statusa spremnosti klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'user_ready',
            'username': event.get('username', ''),
            'user_id': event.get('user_id', ''),
            'is_ready': event.get('is_ready', False)
        }))
    
    async def room_status(self, event):
        """Proslijedi ažuriranje statusa sobe klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'room_status',
            'status': event.get('status', {}),
            'members': event.get('members', []),
            'all_ready': event.get('all_ready', False),
            'can_start': event.get('can_start', False)
        }))
    
    async def game_started(self, event):
        """Proslijedi obavijest o pokretanju igre klijentu."""
        # Proslijedi poruku kao JSON
        await self.send(text_data=json.dumps({
            'type': 'game_started',
            'game_id': event.get('game_id', ''),
            'message': event.get('message', '')
        }))
    
    @database_sync_to_async
    def can_access_room(self):
        """Provjeri ima li korisnik pristup sobi."""
        try:
            room = LobbyRoom.objects.get(id=self.room_id)
            
            # Svaki korisnik može pristupiti javnoj sobi
            if not room.is_private:
                return True
            
            # Provjeri je li korisnik već član privatne sobe
            return LobbyMembership.objects.filter(
                room=room,
                user=self.user
            ).exists()
            
        except LobbyRoom.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_room_status(self):
        """Dohvati trenutni status sobe."""
        try:
            room = LobbyRoom.objects.select_related('creator', 'game').get(id=self.room_id)
            
            # Provjeri je li igra pokrenuta
            if room.game:
                return {
                    'status': 'game_started',
                    'game_id': str(room.game.id),
                    'room_status': room.status
                }
            
            # Dohvati članstva
            memberships = LobbyMembership.objects.filter(
                room=room
            ).select_related('user')
            
            # Formatiraj podatke o članovima
            members = []
            for m in memberships:
                members.append({
                    'id': m.user.id,
                    'username': m.user.username,
                    'is_ready': m.is_ready,
                    'is_creator': (m.user == room.creator),
                    'joined_at': m.joined_at.isoformat()
                })
            
            # Dohvati nedavne poruke
            messages = LobbyMessage.objects.filter(
                room=room
            ).order_by('-created_at')[:20].values(
                'id', 'sender__username', 'sender__id', 'content', 
                'created_at', 'is_system_message'
            )
            
            # Formatiraj poruke
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    'id': str(msg['id']),
                    'sender': msg['sender__username'],
                    'sender_id': msg['sender__id'],
                    'content': msg['content'],
                    'timestamp': msg['created_at'].isoformat(),
                    'is_system_message': msg['is_system_message']
                })
            
            # Jesu li svi igrači spremni
            all_ready = all(m.is_ready for m in memberships)
            
            # Može li se igra pokrenuti
            can_start = all_ready and len(memberships) >= 4
            
            return {
                'id': str(room.id),
                'name': room.name,
                'status': room.status,
                'creator': {
                    'id': room.creator.id,
                    'username': room.creator.username
                },
                'is_private': room.is_private,
                'max_players': room.max_players,
                'points_to_win': room.points_to_win,
                'created_at': room.created_at.isoformat(),
                'members': members,
                'messages': formatted_messages,
                'all_ready': all_ready,
                'can_start': can_start,
                'player_count': len(members)
            }
            
        except LobbyRoom.DoesNotExist:
            return {'status': 'error', 'message': 'Soba ne postoji.'}
    
    @database_sync_to_async
    def save_chat_message(self, content):
        """Spremi novu chat poruku u bazu."""
        try:
            room = LobbyRoom.objects.get(id=self.room_id)
            
            # Provjeri je li korisnik član sobe
            if not LobbyMembership.objects.filter(room=room, user=self.user).exists():
                return None
            
            # Stvaranje nove poruke
            message = LobbyMessage.objects.create(
                room=room,
                sender=self.user,
                content=content
            )
            
            return {
                'id': str(message.id),
                'sender': self.user.username,
                'sender_id': self.user.id,
                'content': message.content,
                'timestamp': message.created_at.isoformat(),
                'is_system_message': message.is_system_message
            }
            
        except LobbyRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def toggle_ready_status(self):
        """Promijeni status spremnosti korisnika."""
        try:
            room = LobbyRoom.objects.get(id=self.room_id)
            
            # Dohvati članstvo
            membership = LobbyMembership.objects.get(room=room, user=self.user)
            
            # Promijeni status
            is_ready = not membership.is_ready
            room.mark_player_ready(self.user, is_ready)
            
            return is_ready
            
        except (LobbyRoom.DoesNotExist, LobbyMembership.DoesNotExist):
            return None
    
    @database_sync_to_async
    def start_game(self):
        """Pokreni igru iz sobe."""
        try:
            room = LobbyRoom.objects.get(id=self.room_id)
            
            # Provjeri je li korisnik kreator sobe
            if room.creator != self.user:
                return None
            
            # Pokreni igru
            game = room.start_game()
            
            if game:
                return str(game.id)
            else:
                return None
                
        except (LobbyRoom.DoesNotExist, ValueError):
            return None
    
    async def send_room_status(self):
        """Pošalji trenutni status sobe."""
        status = await self.get_room_status()
        
        if status.get('status') == 'game_started':
            # Ako je igra već pokrenuta, obavijesti klijenta
            await self.send(text_data=json.dumps({
                'type': 'game_started',
                'game_id': status.get('game_id', ''),
                'message': _('Igra je pokrenuta.')
            }))
            return
        
        # Proslijedi status svim klijentima u sobi
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'room_status',
                'status': status,
                'members': status.get('members', []),
                'all_ready': status.get('all_ready', False),
                'can_start': status.get('can_start', False)
            }
        )
    
    async def handle_chat_message(self, data):
        """Obradi novu chat poruku."""
        content = data.get('content', '').strip()
        
        if not content:
            return
        
        # Spremi poruku u bazu
        message_data = await self.save_chat_message(content)
        
        if not message_data:
            return
        
        # Proslijedi poruku svim klijentima u sobi
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message_data.get('id', ''),
                'sender': message_data.get('sender', ''),
                'sender_id': message_data.get('sender_id', ''),
                'content': message_data.get('content', ''),
                'timestamp': message_data.get('timestamp', ''),
                'is_system_message': message_data.get('is_system_message', False)
            }
        )
    
    async def handle_toggle_ready(self):
        """Obradi zahtjev za promjenu statusa spremnosti."""
        is_ready = await self.toggle_ready_status()
        
        if is_ready is None:
            return
        
        # Obavijesti sve klijente u sobi o promjeni
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_ready',
                'username': self.user.username,
                'user_id': self.user.id,
                'is_ready': is_ready
            }
        )
        
        # Ažuriraj status sobe
        await self.send_room_status()
    
    async def handle_start_game(self):
        """Obradi zahtjev za pokretanje igre."""
        game_id = await self.start_game()
        
        if not game_id:
            # Obavijesti korisnika o grešci
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': _('Nije moguće pokrenuti igru. Provjerite jesu li svi igrači spremni.')
            }))
            return
        
        # Obavijesti sve klijente u sobi o pokretanju igre
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_started',
                'game_id': game_id,
                'message': _('Igra je pokrenuta!')
            }
        )