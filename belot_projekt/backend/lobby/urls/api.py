"""
URL konfiguracija za API endpointe Django aplikacije "lobby".

Ovaj modul definira URL rute za REST API funkcionalnosti predvorja Belot igre,
uključujući pregled i upravljanje sobama, slanje i primanje pozivnica,
chat funkcionalnost i drugo putem JSON API-ja.
"""

from django.urls import path

from .. import api_views

app_name = 'lobby_api'

urlpatterns = [
    # Dohvat liste soba
    path('rooms/', api_views.room_list, name='room_list'),
    
    # Detalji sobe
    path('rooms/<uuid:pk>/', api_views.room_detail, name='room_detail'),
    
    # Stvaranje nove sobe
    path('rooms/create/', api_views.create_room, name='create_room'),
    
    # Pridruživanje i napuštanje sobe
    path('rooms/<uuid:pk>/join/', api_views.join_room, name='join_room'),
    path('rooms/<uuid:pk>/leave/', api_views.leave_room, name='leave_room'),
    
    # Promjena statusa spremnosti
    path('rooms/<uuid:pk>/toggle-ready/', api_views.toggle_ready, name='toggle_ready'),
    
    # Pokretanje igre
    path('rooms/<uuid:pk>/start-game/', api_views.start_game, name='start_game'),
    
    # Chat poruke
    path('rooms/<uuid:pk>/messages/', api_views.room_messages, name='room_messages'),
    path('rooms/<uuid:pk>/send-message/', api_views.send_message, name='send_message'),
    
    # Dohvat statusa sobe
    path('rooms/<uuid:pk>/status/', api_views.room_status, name='room_status'),
]