"""
URL konfiguracija za web sučelje Django aplikacije "lobby".

Ovaj modul definira URL rute za funkcionalnosti predvorja Belot igre,
uključujući pregled i upravljanje sobama, slanje i primanje pozivnica,
chat funkcionalnost i drugo putem web sučelja.
"""

from django.urls import path
from django.views.generic import RedirectView

from .. import views

app_name = 'lobby'

urlpatterns = [
    # Početna stranica predvorja
    path('', views.LobbyHomeView.as_view(), name='home'),
    path('index/', RedirectView.as_view(pattern_name='lobby:home', permanent=True)),
    
    # Pregled soba
    path('rooms/', views.LobbyRoomListView.as_view(), name='room_list'),
    
    # Detalji sobe (moguć pristup putem ID-a ili koda)
    path('room/<uuid:pk>/', views.LobbyRoomDetailView.as_view(), name='room_detail'),
    path('room/code/<str:room_code>/', views.LobbyRoomDetailView.as_view(), name='room_detail_by_code'),
    
    # Stvaranje sobe
    path('room/create/', views.LobbyRoomCreateView.as_view(), name='room_create'),
    
    # Akcije za sobu
    path('room/<uuid:pk>/join/', views.JoinLobbyRoomView.as_view(), name='join_room'),
    path('room/join/code/<str:room_code>/', views.JoinLobbyRoomView.as_view(), name='join_room_by_code'),
    path('room/<uuid:pk>/leave/', views.LeaveLobbyRoomView.as_view(), name='leave_room'),
    path('room/<uuid:pk>/ready/', views.ToggleReadyStatusView.as_view(), name='toggle_ready'),
    path('room/<uuid:pk>/start/', views.StartGameFromLobbyView.as_view(), name='start_game'),
    
    # Chat poruke
    path('room/<uuid:pk>/messages/', views.LobbyMessageListView.as_view(), name='room_messages'),
    path('room/<uuid:pk>/send-message/', views.SendMessageView.as_view(), name='send_message'),
    
    # Pozivnice
    path('room/<uuid:pk>/invite/', views.SendInvitationView.as_view(), name='send_invitation'),
    path('invitation/<uuid:pk>/<str:action>/', views.RespondToInvitationView.as_view(), name='respond_to_invitation'),
    
    # Pridruživanje putem koda
    path('join-by-code/', views.LobbyRoomByCodeView.as_view(), name='join_by_code'),
    
    # AJAX ažuriranje stanja sobe
    path('room/<uuid:pk>/status/', views.update_lobby_status, name='room_status'),
    
    # Preusmjeravanje za kompatibilnost s URL-ovima iz primjera
    path('gamelobby/<str:room_code>/', RedirectView.as_view(pattern_name='lobby:room_detail_by_code'), name='tportal_gamelobby'),
]