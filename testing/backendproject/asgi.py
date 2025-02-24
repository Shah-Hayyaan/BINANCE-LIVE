# backendproject/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from backendapp.consumers.binance_consumer import BinanceConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backendproject.settings')

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    path('ws/binance/', BinanceConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),  
})
