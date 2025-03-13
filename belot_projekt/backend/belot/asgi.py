"""
ASGI config for Belot project.

This module configures the ASGI application which handles both HTTP and WebSocket
protocols essential for real-time card game interactions.

It exposes the ASGI callable as a module-level variable named application.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'belot.settings.development')

# Import Django ASGI application first
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# Import channels components
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

# Import WebSocket URL patterns
from lobby.routing import websocket_urlpatterns as lobby_ws_urlpatterns
from game.routing import websocket_urlpatterns as game_ws_urlpatterns

# Combine WebSocket patterns from all apps
all_websocket_urlpatterns = lobby_ws_urlpatterns + game_ws_urlpatterns

# Configure the ASGI application
application = ProtocolTypeRouter({
    # Django's ASGI application handles traditional HTTP requests
    "http": django_asgi_app,

    # WebSocket handler with authentication and origin validation
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                all_websocket_urlpatterns
            )
        )
    ),
})