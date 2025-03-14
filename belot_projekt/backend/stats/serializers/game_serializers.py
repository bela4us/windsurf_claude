"""
Serializeri za statistiku igara u Belot aplikaciji.

Ovaj modul sadrži serializere koji se koriste za transformaciju
modela GameStats u JSON format i obrnuto za potrebe API-ja.
"""

from rest_framework import serializers
from ..models import GameStats

class GameStatsSerializer(serializers.ModelSerializer):
    """
    Serializer za prikaz statistike pojedinačne igre.
    """
    class Meta:
        model = GameStats
        fields = '__all__'

class GameHistoryStatsSerializer(serializers.Serializer):
    """
    Serializer za prikaz povijesti igara igrača.
    
    Koristi se za agregirane podatke o igrama u određenom vremenskom periodu.
    """
    date = serializers.DateTimeField()
    games_played = serializers.IntegerField()
    games_won = serializers.IntegerField()
    win_rate = serializers.FloatField()
    total_score = serializers.IntegerField()
    avg_score = serializers.FloatField() 