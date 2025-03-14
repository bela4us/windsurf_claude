"""
Serializeri za statistiku igrača u Belot aplikaciji.

Ovaj modul sadrži serializere koji se koriste za transformaciju
modela PlayerStats u JSON format i obrnuto za potrebe API-ja.
"""

from rest_framework import serializers
from ..models import PlayerStats

class PlayerStatsSerializer(serializers.ModelSerializer):
    """
    Serializer za puni prikaz statistike igrača.
    """
    class Meta:
        model = PlayerStats
        fields = '__all__'

class PlayerStatsMinimalSerializer(serializers.ModelSerializer):
    """
    Serializer za sažeti prikaz statistike igrača.
    """
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PlayerStats
        fields = ['id', 'user', 'user_username', 'games_played', 'games_won', 'win_percentage']

class TopPlayersByStatSerializer(serializers.Serializer):
    """
    Serializer za prikaz najboljih igrača po određenoj statistici.
    """
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    value = serializers.FloatField()
    rank = serializers.IntegerField()

class PlayerComparisonSerializer(serializers.Serializer):
    """
    Serializer za usporedbu statistike dva igrača.
    """
    player1 = PlayerStatsSerializer()
    player2 = PlayerStatsSerializer()
    games_played_diff = serializers.IntegerField()
    win_percentage_diff = serializers.FloatField()
    avg_points_diff = serializers.FloatField()
    common_games = serializers.IntegerField()
    player1_wins_against_player2 = serializers.IntegerField()
    player2_wins_against_player1 = serializers.IntegerField() 