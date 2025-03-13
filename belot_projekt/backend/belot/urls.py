"""
Glavna URL konfiguracija za Belot aplikaciju.

Ovaj modul definira sve URL putanje u aplikaciji, uključujući API i web sučelje.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import JsonResponse

# Health check view
def health_check(request):
    """
    Jednostavni health check endpoint koji vraća status API-ja.
    """
    return JsonResponse({
        'status': 'ok',
        'version': '1.0.0',
        'api': 'Belot API',
        'environment': getattr(settings, 'ACTIVE_ENVIRONMENT', 'unknown')
    })

# Definiranje glavnih URL ruta
urlpatterns = [
    # Admin sučelje
    path('admin/', admin.site.urls, name='admin:index'),
    
    # API health check
    path('api/health/', health_check, name='health_check'),
    
    # Uključivanje URL ruta pojedinih aplikacija
    # API rute
    path('api/game/', include('game.urls.api')),
    path('api/lobby/', include('lobby.urls.api')),
    path('api/users/', include('users.urls.api')),
    path('api/stats/', include('stats.urls.api')),
    
    # Web rute
    path('game/', include('game.urls.web')),
    path('lobby/', include('lobby.urls.web')),
    path('users/', include('users.urls.web')),
    path('stats/', include('stats.urls.web')),
    
    # REST framework autentikacija
    path('api-auth/', include('rest_framework.urls')),
    
    # Početna stranica
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
]

# Dodajemo static i media URL-ove u razvoju
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)