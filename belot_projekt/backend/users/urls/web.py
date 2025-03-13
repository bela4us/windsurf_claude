"""
URL konfiguracija za web sučelje Django aplikacije "users".

Ovaj modul definira URL rute za funkcionalnosti korisničkih računa,
uključujući registraciju, prijavu, upravljanje profilom, prijateljstva i drugo.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

from .. import views

app_name = 'users'

urlpatterns = [
    # Prikaz korisničkog profila
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/<uuid:pk>/', views.ProfileDetailView.as_view(), name='profile_detail'),
    
    # Autentikacija
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Upravljanje računom
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Potvrda email adrese
    path('verify-email/<str:token>/', views.EmailVerificationView.as_view(), name='verify_email'),
    
    # Resetiranje lozinke
    path('reset-password/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html'), 
        name='password_reset'),
    path('reset-password/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'), 
        name='password_reset_done'),
    path('reset-password/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html'), 
        name='password_reset_confirm'),
    path('reset-password/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'), 
        name='password_reset_complete'),
    
    # Prijateljstva
    path('friends/', views.FriendListView.as_view(), name='friends'),
    path('friends/requests/', views.FriendRequestsView.as_view(), name='friend_requests'),
    path('friends/add/<uuid:pk>/', views.AddFriendView.as_view(), name='add_friend'),
    path('friends/accept/<uuid:pk>/', views.AcceptFriendRequestView.as_view(), name='accept_friend'),
    path('friends/decline/<uuid:pk>/', views.DeclineFriendRequestView.as_view(), name='decline_friend'),
    path('friends/remove/<uuid:pk>/', views.RemoveFriendView.as_view(), name='remove_friend'),
    
    # Obavijesti
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/mark-read/<uuid:pk>/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_notifications_read'),
    
    # Postignuća
    path('achievements/', views.AchievementListView.as_view(), name='achievements'),
    
    # Pretraga korisnika
    path('search/', views.UserSearchView.as_view(), name='search'),
]