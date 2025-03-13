"""
Inicijalizacijski modul za testove Belot igre.

Ovaj modul omogućuje grupiranje svih testova za Belot igru i definira
zajedničke funkcije i konstante koje se koriste kroz različite test module.
"""

# Konstante za testiranje
TEST_CARDS = {
    'SPADES': ['7S', '8S', '9S', '10S', 'JS', 'QS', 'KS', 'AS'],
    'HEARTS': ['7H', '8H', '9H', '10H', 'JH', 'QH', 'KH', 'AH'],
    'DIAMONDS': ['7D', '8D', '9D', '10D', 'JD', 'QD', 'KD', 'AD'],
    'CLUBS': ['7C', '8C', '9C', '10C', 'JC', 'QC', 'KC', 'AC']
}

TEST_PLAYERS = [
    {'username': 'player1', 'email': 'player1@example.com'},
    {'username': 'player2', 'email': 'player2@example.com'},
    {'username': 'player3', 'email': 'player3@example.com'},
    {'username': 'player4', 'email': 'player4@example.com'}
]

# Konstante za bodovanje u testovima
POINTS_TO_WIN = 1001
CARD_POINTS = {
    'NON_TRUMP': {
        'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0
    },
    'TRUMP': {
        'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0
    }
}

# Konstante za zvanja u testovima
DECLARATIONS = {
    'BELOT': 1001,            # Osam karata u istoj boji u nizu
    'FOUR_JACKS': 200,        # Četiri dečka
    'FOUR_NINES': 150,        # Četiri devetke
    'FOUR_ACES': 100,         # Četiri asa
    'FOUR_KINGS': 100,        # Četiri kralja
    'FOUR_QUEENS': 100,       # Četiri dame
    'SEQUENCE_5_PLUS': 100,   # Pet, šest ili sedam karata u nizu iste boje
    'SEQUENCE_4': 50,         # Četiri karte u nizu iste boje
    'SEQUENCE_3': 20,         # Tri karte u nizu iste boje
    'BELA': 20                # Kralj i dama iste boje u adutu
}

# Pomoćne funkcije za testiranje
def get_test_deck():
    """Vraća kompletan špil karata za testiranje."""
    deck = []
    for suit in TEST_CARDS:
        deck.extend(TEST_CARDS[suit])
    return deck

def get_test_hand(cards_list):
    """Stvara test ruku od liste kodova karata."""
    from game.game_logic.card import Card
    return [Card.from_code(card) for card in cards_list]

def create_test_game(num_players=4):
    """Stvara test igru s navedenim brojem igrača."""
    from django.contrib.auth import get_user_model
    from game.models import Game
    
    User = get_user_model()
    
    # Stvaranje test korisnika ako ne postoje
    users = []
    for i in range(num_players):
        user_data = TEST_PLAYERS[i]
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={'email': user_data['email']}
        )
        users.append(user)
    
    # Stvaranje igre
    game = Game.objects.create(
        creator=users[0],
        is_private=False,
        points_to_win=POINTS_TO_WIN,
        status='waiting'
    )
    
    # Dodavanje igrača u igru
    for user in users:
        game.players.add(user)
        game.active_players.add(user)
    
    return game, users

def create_test_round(game, dealer=None):
    """Stvara test rundu za navedenu igru."""
    from game.models import Round
    
    if dealer is None:
        dealer = game.players.first()
    
    return Round.objects.create(
        game=game,
        number=1,
        dealer=dealer
    )

def create_test_moves(round_obj, cards_per_player=8):
    """Stvara test poteze za navedenu rundu."""
    from game.models import Move
    from game.game_logic.deck import Deck
    
    deck = Deck()
    deck.shuffle()
    
    players = list(round_obj.game.players.all())
    player_hands = {player.id: [] for player in players}
    
    # Dijeljenje karata igračima
    for _ in range(cards_per_player):
        for player in players:
            card = deck.draw()
            player_hands[player.id].append(card)
    
    # Stvaranje poteza (igra prva četiri poteza)
    moves = []
    for i in range(4):
        player = players[i]
        card = player_hands[player.id][0]  # Uzmi prvu kartu
        move = Move.objects.create(
            round=round_obj,
            player=player,
            card=card.code,
            order=i
        )
        moves.append(move)
    
    return moves, player_hands