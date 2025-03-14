"""
Web URL konfiguracija za Django aplikaciju "users".

Ovaj modul definira URL uzorke za web sučelje vezano uz korisnike,
uključujući stranice za prijavu, registraciju, profile, itd.
"""

from django.urls import path

# URL uzorci za web stranice
urlpatterns = [
    # Autentikacija i registracija
    # path('login/', LoginView.as_view(), name='login'),
    # path('logout/', LogoutView.as_view(), name='logout'),
    # path('register/', RegisterView.as_view(), name='register'),
    
    # Korisnički profil
    # path('profile/', ProfileView.as_view(), name='profile'),
    # path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    
    # Ostale stranice
    # path('dashboard/', DashboardView.as_view(), name='dashboard'),
    # path('settings/', SettingsView.as_view(), name='settings'),
] 