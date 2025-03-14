"""
Serializeri za globalne statistike u Belot aplikaciji.

Ovaj modul sadrži serializere koji se koriste za transformaciju
modela GlobalStats, DailyStats, StatisticsSnapshot i Leaderboard
u JSON format i obrnuto za potrebe API-ja.
"""

from rest_framework import serializers
from ..models import GlobalStats, DailyStats, StatisticsSnapshot, Leaderboard

class GlobalStatsSerializer(serializers.ModelSerializer):
    """
    Serializer za prikaz globalnih statistika.
    """
    class Meta:
        model = GlobalStats
        fields = '__all__'

class DailyStatsSerializer(serializers.ModelSerializer):
    """
    Serializer za prikaz dnevnih statistika.
    """
    class Meta:
        model = DailyStats
        fields = '__all__'

class StatisticsSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer za prikaz snapshot-a statistike.
    """
    class Meta:
        model = StatisticsSnapshot
        fields = '__all__'

class LeaderboardSerializer(serializers.ModelSerializer):
    """
    Serializer za detaljni prikaz ljestvice.
    """
    class Meta:
        model = Leaderboard
        fields = '__all__'

class LeaderboardMinimalSerializer(serializers.ModelSerializer):
    """
    Serializer za sažeti prikaz ljestvice.
    """
    class Meta:
        model = Leaderboard
        fields = ['id', 'category', 'period', 'updated_at'] 