#!/usr/bin/env python
"""
Skripta za punjenje testnih podataka u Belot aplikaciju.

Ova skripta stvara početne testne podatke za razvoj i testiranje,
uključujući korisnike, sobe, igre, i druge entitete potrebne za
normalnu funkcionalnost aplikacije.

Korištenje:
    python scripts/seed_data.py [opcije]

Opcije:
    --env {dev,test,prod}  Okolina za koju se pune podaci (zadano: dev)
    --flush                Briše postojeće podatke prije punjenja novih
    --count N              Broj entiteta svake vrste koji se stvaraju (zadano: 10)
    --only MODULE          Puni podatke samo za određeni modul (npr. users, game, lobby)
"""

import os
import sys
import random
import argparse
import django
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

# Dodaj projektni direktorij u Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Postavi Django postavke
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "belot.settings.development")
django.setup()

# Sada možemo uvesti Django modele
from game.models import Game, Round, Declaration, Move
from lobby.models import LobbyRoom, LobbyMembership, LobbyInvitation, LobbyMessage
from users.models import UserProfile, Friendship, Achievement, UserAchievement

User = get_user_model()


class DataSeeder:
    """
    Klasa za punjenje testnih podataka u bazu.
    
    Sadrži metode za stvaranje različitih vrsta testnih podataka
    i njihovo međusobno povezivanje.
    """
    
    def __init__(self, count=10, flush=False):
        """
        Inicijalizira seeder s konfiguracijom.
        
        Args:
            count: Broj entiteta svake vrste koji se stvaraju
            flush: Treba li izbrisati postojeće podatke prije punjenja novih
        """
        self.count = count
        self.flush = flush
        self.users = []
        self.profiles = []
        self.rooms = []
        self.games = []
        
        # Postavke testnih podataka
        self.usernames = [
            "ivica", "marica", "petar", "ana", "marko", "lucija",
            "ivan", "marina", "davor", "kristina", "tomislav", "sanja",
            "stjepan", "valentina", "mario", "jelena", "nikola", "maja",
            "ante", "katarina", "matija", "petra", "josip", "iva"
        ]
        
        self.room_names = [
            "Vesela ekipa", "Poker face", "Aduti kraljevi", "Belot majstori",
            "Kartaška elita", "Štihovi i zvanja", "As u rukavu", "Zvanje u zadnji čas",
            "Dalmatinska bela", "Zagorska belica", "Kraljevski stol", "Adut je srce",
            "Štih po štih", "Dama i kralj", "Decko i devetka", "Slavonski špil",
            "Licitarsko srce", "Istarska trešeta", "Primorski briškula", "Štiglici"
        ]
        
        self.achievement_names = [
            "Prvi koraci", "Majstor aduta", "Belot virtuoz", "Kralj asa",
            "Nepobjedivi", "Kraljolovac", "Zvonar", "Štiholovac",
            "Marljivac", "Društvenjak", "Štrajkaš", "Vječiti zvonar"
        ]
        
        # Inicijaliziraj generator slučajnih brojeva s fiksnim seed-om
        # za reproducibilnost testnih podataka
        random.seed(42)
    
    def clear_data(self):
        """Briše sve postojeće podatke iz baze."""
        print("Brisanje postojećih podataka...")
        
        # Brisanje u odgovarajućem redoslijedu zbog ograničenja referencijalnog integriteta
        UserAchievement.objects.all().delete()
        Achievement.objects.all().delete()
        
        Move.objects.all().delete()
        Declaration.objects.all().delete()
        Round.objects.all().delete()
        
        LobbyMessage.objects.all().delete()
        LobbyInvitation.objects.all().delete()
        LobbyMembership.objects.all().delete()
        
        # Resetiranje veza M2M
        for game in Game.objects.all():
            game.players.clear()
            game.active_players.clear()
        for room in LobbyRoom.objects.all():
            room.players.clear()
        
        Game.objects.all().delete()
        LobbyRoom.objects.all().delete()
        
        Friendship.objects.all().delete()
        UserProfile.objects.all().delete()
        
        # Izbriši sve korisnike osim superuser-a
        User.objects.filter(is_superuser=False).delete()
        
        print("Svi postojeći podaci su obrisani.")
    
    def create_users(self):
        """Stvara testne korisnike s profilima."""
        print(f"Stvaranje {self.count} testnih korisnika...")
        
        for i in range(self.count):
            # Dohvati korisničko ime ili generiraj ako nema dovoljno
            if i < len(self.usernames):
                username = self.usernames[i]
            else:
                username = f"user{i+1}"
            
            email = f"{username}@example.com"
            
            # Stvaranje korisnika
            user = User.objects.create_user(
                username=username,
                email=email,
                password="password123",
                first_name=username.capitalize(),
                last_name="Testić",
                is_active=True
            )
            
            # Profil će se automatski stvoriti kroz signal, dohvati ga
            profile = UserProfile.objects.get(user=user)
            
            # Dodaj dodatne informacije u profil
            profile.bio = f"Testni profil korisnika {username}"
            profile.experience_points = random.randint(100, 10000)
            profile.games_played = random.randint(10, 200)
            profile.games_won = random.randint(0, profile.games_played)
            profile.save()
            
            self.users.append(user)
            self.profiles.append(profile)
        
        print(f"Stvoreno {len(self.users)} korisnika.")
    
    def create_friendships(self):
        """Stvara prijateljstva između testnih korisnika."""
        print("Stvaranje prijateljstava...")
        
        # Svakom korisniku dodaj nekoliko prijatelja
        for user in self.users:
            # Odaberi nasumično 3-6 drugih korisnika za prijateljstvo
            potential_friends = [u for u in self.users if u != user]
            num_friends = min(len(potential_friends), random.randint(3, 6))
            friends = random.sample(potential_friends, num_friends)
            
            for friend in friends:
                # Provjeri postoji li već prijateljstvo u bilo kojem smjeru
                if not Friendship.objects.filter(
                    (models.Q(sender=user) & models.Q(receiver=friend)) |
                    (models.Q(sender=friend) & models.Q(receiver=user))
                ).exists():
                    # Stvaranje prijateljstva s različitim statusima
                    status_choices = ['pending', 'accepted', 'accepted', 'accepted']
                    status = random.choice(status_choices)
                    
                    Friendship.objects.create(
                        sender=user,
                        receiver=friend,
                        status=status,
                        created_at=timezone.now()
                    )
        
        # Dohvati ukupan broj stvorenih prijateljstava
        friendship_count = Friendship.objects.count()
        print(f"Stvoreno {friendship_count} prijateljstava.")
    
    def create_achievements(self):
        """Stvara dostignuća i dodjeljuje ih korisnicima."""
        print("Stvaranje dostignuća...")
        
        # Stvori dostignuća
        achievements = []
        for i, name in enumerate(self.achievement_names):
            achievement = Achievement.objects.create(
                name=name,
                description=f"Opis za dostignuće {name}",
                icon=f"achievement_{i+1}.png",
                points=random.choice([10, 25, 50, 100]),
                difficulty=random.choice(['easy', 'medium', 'hard']),
                hidden=(random.random() > 0.8)  # 20% su skrivena
            )
            achievements.append(achievement)
        
        print(f"Stvoreno {len(achievements)} dostignuća.")
        
        # Dodijeli dostignuća korisnicima
        print("Dodjeljivanje dostignuća korisnicima...")
        for user in self.users:
            # Odaberi nasumično 0-5 dostignuća za korisnika
            num_achievements = random.randint(0, min(5, len(achievements)))
            user_achievements = random.sample(achievements, num_achievements)
            
            for achievement in user_achievements:
                # Postavi datum osvajanja između 1 i 100 dana u prošlosti
                days_ago = random.randint(1, 100)
                achieved_at = timezone.now() - timezone.timedelta(days=days_ago)
                
                UserAchievement.objects.create(
                    user=user,
                    achievement=achievement,
                    achieved_at=achieved_at
                )
        
        # Dohvati ukupan broj dodijeljenih dostignuća
        user_achievement_count = UserAchievement.objects.count()
        print(f"Dodijeljeno {user_achievement_count} dostignuća korisnicima.")
    
    def create_lobby_rooms(self):
        """Stvara sobe u predvorju."""
        print(f"Stvaranje {self.count} soba u predvorju...")
        
        for i in range(self.count):
            # Dohvati ime sobe ili generiraj ako nema dovoljno
            if i < len(self.room_names):
                name = self.room_names[i]
            else:
                name = f"Soba {i+1}"
            
            # Odaberi nasumičnog kreatora
            creator = random.choice(self.users)
            
            # Odredi je li soba privatna
            is_private = random.random() < 0.3  # 30% soba su privatne
            
            # Odredi status sobe
            status_choices = ['open', 'open', 'open', 'full', 'starting', 'closed']
            status = random.choice(status_choices)
            
            # Odredi koristi li brži format
            use_quick_format = random.random() < 0.4  # 40% soba koriste brži format
            points_to_win = 701 if use_quick_format else 1001
            
            # Stvori sobu
            room = LobbyRoom.objects.create(
                name=name,
                creator=creator,
                status=status,
                is_private=is_private,
                max_players=4,
                points_to_win=points_to_win,
                use_quick_format=use_quick_format
            )
            
            # Ako soba nije zatvorena, dodaj članove
            if status != 'closed':
                # Dodaj kreatora kao prvog člana
                LobbyMembership.objects.create(
                    room=room,
                    user=creator,
                    is_ready=(status == 'starting')
                )
                
                # Dodaj još 1-3 člana (ukupno 2-4)
                potential_members = [u for u in self.users if u != creator]
                num_members = random.randint(1, 3)
                if status == 'full':
                    num_members = 3  # Ukupno 4 s kreatorom
                
                members = random.sample(potential_members, min(num_members, len(potential_members)))
                
                for member in members:
                    LobbyMembership.objects.create(
                        room=room,
                        user=member,
                        is_ready=(status == 'starting')
                    )
                
                # Ako je status 'starting' ili 'closed', stvori igru
                if status in ['starting', 'closed']:
                    game = Game.objects.create(
                        creator=creator,
                        points_to_win=points_to_win,
                        is_private=is_private,
                        status='waiting' if status == 'starting' else 'in_progress'
                    )
                    
                    # Dodaj igrače u igru
                    game.players.add(creator)
                    for member in members:
                        game.players.add(member)
                    
                    # Ako je igra 'in_progress', dodaj ih u aktivne igrače
                    if game.status == 'in_progress':
                        game.active_players.add(creator)
                        for member in members:
                            game.active_players.add(member)
                    
                    # Poveži igru sa sobom
                    room.game = game
                    room.save()
                    
                    self.games.append(game)
            
            self.rooms.append(room)
        
        print(f"Stvoreno {len(self.rooms)} soba u predvorju.")
    
    def create_lobby_messages(self):
        """Stvara poruke u sobama predvorja."""
        print("Stvaranje poruka u sobama predvorja...")
        
        # Samo za otvorene ili pune sobe
        active_rooms = [room for room in self.rooms if room.status in ['open', 'full', 'starting']]
        
        for room in active_rooms:
            # Dohvati članove sobe
            memberships = LobbyMembership.objects.filter(room=room)
            members = [membership.user for membership in memberships]
            
            if not members:
                continue
            
            # Dodaj 5-15 poruka
            num_messages = random.randint(5, 15)
            
            for _ in range(num_messages):
                # Odaberi nasumičnog pošiljatelja među članovima
                sender = random.choice(members)
                
                # 10% poruka su sistemske
                is_system = random.random() < 0.1
                
                if is_system:
                    content = random.choice([
                        f"{sender.username} je ušao/la u sobu.",
                        f"{sender.username} je izašao/la iz sobe.",
                        f"{sender.username} je spreman/na za igru.",
                        f"{sender.username} više nije spreman/na za igru.",
                        "Igra uskoro počinje.",
                        "Čekanje na još igrača..."
                    ])
                else:
                    content = random.choice([
                        "Pozdrav svima!",
                        "Tko će zvati adut?",
                        "Spremni za igru?",
                        "Idemo igrati!",
                        "Čekamo još jednog igrača.",
                        "Koja su pravila?",
                        "Dobra karta!",
                        "Sretan belot!",
                        "Već sam igrao/la s vama prije.",
                        "Tko je za još jednu rundu nakon ove?",
                        "Brz sam/a kao munja!",
                        "Oprezno s adutima...",
                        "Danas mi je dobar dan za kartanje.",
                        "Još jedna pobjeda za moj tim!",
                        "Nemojte blefirati, to nije poker!"
                    ])
                
                # Stvori poruku s nasumičnim vremenom unutar posljednja 2 dana
                minutes_ago = random.randint(1, 60 * 24 * 2)  # Do 2 dana unazad
                created_at = timezone.now() - timezone.timedelta(minutes=minutes_ago)
                
                LobbyMessage.objects.create(
                    room=room,
                    sender=sender,
                    content=content,
                    created_at=created_at,
                    is_system_message=is_system
                )
        
        # Dohvati ukupan broj stvorenih poruka
        message_count = LobbyMessage.objects.count()
        print(f"Stvoreno {message_count} poruka u sobama predvorja.")
    
    def create_lobby_invitations(self):
        """Stvara pozivnice za sobe u predvorju."""
        print("Stvaranje pozivnica za sobe u predvorju...")
        
        # Samo za privatne sobe koje nisu zatvorene
        private_rooms = [room for room in self.rooms if room.is_private and room.status != 'closed']
        
        for room in private_rooms:
            # Dohvati kreatora i članove sobe
            creator = room.creator
            memberships = LobbyMembership.objects.filter(room=room)
            members = [membership.user for membership in memberships]
            
            # Dohvati korisnike koji nisu članovi
            non_members = [user for user in self.users if user not in members]
            
            if not non_members:
                continue
            
            # Odaberi 1-3 korisnika za pozivnice
            num_invitations = random.randint(1, min(3, len(non_members)))
            recipients = random.sample(non_members, num_invitations)
            
            for recipient in recipients:
                # Odaberi pošiljatelja (kreator ili nasumični član)
                if random.random() < 0.7:  # 70% pozivnica šalje kreator
                    sender = creator
                else:
                    sender = random.choice(members)
                
                # Odredi status pozivnice
                status_choices = ['pending', 'pending', 'pending', 'accepted', 'declined', 'expired']
                status = random.choice(status_choices)
                
                # Nasumično vrijeme stvaranja unutar posljednja 3 dana
                hours_ago = random.randint(1, 72)  # Do 3 dana unazad
                created_at = timezone.now() - timezone.timedelta(hours=hours_ago)
                
                # Vrijeme isteka 24 sata nakon stvaranja
                expires_at = created_at + timezone.timedelta(hours=24)
                
                # Ako je status 'accepted' i soba još ima mjesta, dodaj korisnika u sobu
                if status == 'accepted' and LobbyMembership.objects.filter(room=room).count() < 4:
                    try:
                        # Stvaranje pozivnice
                        invitation = LobbyInvitation.objects.create(
                            room=room,
                            sender=sender,
                            recipient=recipient,
                            status=status,
                            created_at=created_at,
                            expires_at=expires_at,
                            message=f"Hej {recipient.username}, pridruži nam se u igri!"
                        )
                        
                        # Dodaj člana u sobu (ali samo ako ima mjesta)
                        LobbyMembership.objects.create(
                            room=room,
                            user=recipient,
                            is_ready=False,
                            joined_at=created_at + timezone.timedelta(minutes=random.randint(5, 60))
                        )
                    except Exception as e:
                        print(f"Greška pri stvaranju prihvaćene pozivnice: {e}")
                else:
                    # Stvaranje pozivnice bez dodavanja u sobu
                    LobbyInvitation.objects.create(
                        room=room,
                        sender=sender,
                        recipient=recipient,
                        status=status,
                        created_at=created_at,
                        expires_at=expires_at,
                        message=f"Hej {recipient.username}, pridruži nam se u igri!"
                    )
        
        # Dohvati ukupan broj stvorenih pozivnica
        invitation_count = LobbyInvitation.objects.count()
        print(f"Stvoreno {invitation_count} pozivnica za sobe u predvorju.")
    
    def create_games(self):
        """Stvara dodatne igre koje nisu vezane za sobe u predvorju."""
        print(f"Stvaranje dodatnih {self.count} igara...")
        
        games_to_create = self.count - len(self.games)
        
        if games_to_create <= 0:
            print("Već je stvoreno dovoljno igara kroz sobe u predvorju.")
            return
        
        for i in range(games_to_create):
            # Odaberi nasumičnog kreatora
            creator = random.choice(self.users)
            
            # Odredi je li igra privatna
            is_private = random.random() < 0.3  # 30% igara su privatne
            
            # Odredi bodove za pobjedu
            use_quick_format = random.random() < 0.4  # 40% igara koriste brži format
            points_to_win = 701 if use_quick_format else 1001
            
            # Odredi status igre
            status_choices = ['waiting', 'in_progress', 'completed', 'aborted']
            status_weights = [0.2, 0.4, 0.3, 0.1]  # Vjerojatnosti za svaki status
            status = random.choices(status_choices, weights=status_weights, k=1)[0]
            
            # Stvori igru
            game = Game.objects.create(
                creator=creator,
                points_to_win=points_to_win,
                is_private=is_private,
                status=status
            )
            
            # Dodaj igrače u igru
            potential_players = [u for u in self.users if u != creator]
            num_players = 3  # Ukupno 4 s kreatorom
            
            if len(potential_players) < num_players:
                # Ako nema dovoljno igrača, nastavi na sljedeću igru
                game.delete()
                continue
            
            players = random.sample(potential_players, num_players)
            
            # Dodaj igrače u igru
            game.players.add(creator)
            for player in players:
                game.players.add(player)
            
            # Ako igra nije 'waiting', dodaj ih u aktivne igrače
            if status != 'waiting':
                game.active_players.add(creator)
                for player in players:
                    game.active_players.add(player)
            
            # Dodaj rezultate ako je igra završena
            if status == 'completed':
                # Odredi pobjednički tim
                all_players = [creator] + players
                team_a = [all_players[0], all_players[2]]
                team_b = [all_players[1], all_players[3]]
                
                winning_team = random.choice(['a', 'b'])
                
                if winning_team == 'a':
                    winners = team_a
                    losers = team_b
                else:
                    winners = team_b
                    losers = team_a
                
                # Postavi rezultate
                game.team_a_score = 1001 if winning_team == 'a' else random.randint(700, 950)
                game.team_b_score = 1001 if winning_team == 'b' else random.randint(700, 950)
                game.winning_team = winning_team
                game.save()
                
                # Ažuriraj statistike igrača
                for winner in winners:
                    profile = UserProfile.objects.get(user=winner)
                    profile.games_played += 1
                    profile.games_won += 1
                    profile.experience_points += random.randint(20, 50)
                    profile.save()
                
                for loser in losers:
                    profile = UserProfile.objects.get(user=loser)
                    profile.games_played += 1
                    profile.experience_points += random.randint(5, 15)
                    profile.save()
            
            self.games.append(game)
        
        print(f"Stvoreno {games_to_create} dodatnih igara.")
    
    @transaction.atomic
    def seed(self):
        """Glavni metoda za punjenje svih testnih podataka."""
        if self.flush:
            self.clear_data()
        
        self.create_users()
        self.create_friendships()
        self.create_achievements()
        self.create_lobby_rooms()
        self.create_lobby_messages()
        self.create_lobby_invitations()
        self.create_games()
        
        print("\nPunjenje testnih podataka završeno!")
        print(f"Stvoreno {len(self.users)} korisnika")
        print(f"Stvoreno {Friendship.objects.count()} prijateljstava")
        print(f"Stvoreno {Achievement.objects.count()} dostignuća")
        print(f"Stvoreno {UserAchievement.objects.count()} dodjela dostignuća")
        print(f"Stvoreno {len(self.rooms)} soba u predvorju")
        print(f"Stvoreno {LobbyMessage.objects.count()} poruka")
        print(f"Stvoreno {LobbyInvitation.objects.count()} pozivnica")
        print(f"Stvoreno {len(self.games)} igara")


def main():
    """Glavna funkcija za pokretanje punjenja podataka."""
    parser = argparse.ArgumentParser(description="Skripta za punjenje testnih podataka u Belot aplikaciju.")
    parser.add_argument("--env", choices=["dev", "test", "prod"], default="dev",
                        help="Okolina za koju se pune podaci (zadano: dev)")
    parser.add_argument("--flush", action="store_true",
                        help="Briše postojeće podatke prije punjenja novih")
    parser.add_argument("--count", type=int, default=10,
                        help="Broj entiteta svake vrste koji se stvaraju (zadano: 10)")
    parser.add_argument("--only", type=str,
                        help="Puni podatke samo za određeni modul (npr. users, game, lobby)")
    
    args = parser.parse_args()
    
    # Postavi Django postavke prema okolini
    if args.env == "test":
        os.environ["DJANGO_SETTINGS_MODULE"] = "belot.settings.testing"
    elif args.env == "prod":
        os.environ["DJANGO_SETTINGS_MODULE"] = "belot.settings.production"
    else:
        os.environ["DJANGO_SETTINGS_MODULE"] = "belot.settings.development"
    
    try:
        # Stvori seeder i pokreni punjenje podataka
        seeder = DataSeeder(count=args.count, flush=args.flush)
        
        if args.only:
            # Pokreni samo određenu metodu
            method_name = f"create_{args.only}"
            if hasattr(seeder, method_name):
                print(f"Punjenje podataka samo za modul: {args.only}")
                method = getattr(seeder, method_name)
                method()
            else:
                print(f"Greška: Nepoznati modul '{args.only}'")
                print("Dostupni moduli: users, friendships, achievements, lobby_rooms, lobby_messages, lobby_invitations, games")
                return 1
        else:
            # Pokreni sve metode
            seeder.seed()
        
        return 0
    
    except Exception as e:
        print(f"Greška prilikom punjenja podataka: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())