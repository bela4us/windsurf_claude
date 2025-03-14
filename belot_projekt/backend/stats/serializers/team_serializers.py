"""
Serializeri za statistiku timova u Belot aplikaciji.

Ovaj modul sadrži serializere koji se koriste za transformaciju
modela TeamStats u JSON format i obrnuto za potrebe API-ja.
"""

from rest_framework import serializers
from ..models import TeamStats

class TeamStatsSerializer(serializers.ModelSerializer):
    """
    Serializer za prikaz statistike timova.
    
    Uključuje dodatna polja za korisničko ime prvog i drugog igrača
    kako bi se olakšao prikaz podataka na frontend-u.
    """
    player1_username = serializers.CharField(source='player1.username', read_only=True)
    player2_username = serializers.CharField(source='player2.username', read_only=True)
    
    class Meta:
        model = TeamStats
        fields = '__all__' 