from django.urls import re_path
from backendapp.consumers.fyers_consumer import FyersConsumer
from backendapp.consumers.binance_consumer import BinanceConsumer
from backendapp.consumers.ibapi_consumer import IbApiConsumer

websocket_urlpatterns = [
    re_path(r'ws/fyers/$', FyersConsumer.as_asgi()),  # WebSocket route for Fyers
    re_path(r'ws/binance/$', BinanceConsumer.as_asgi()),  # WebSocket route for Binance
    re_path(r'ws/ibapi/$', IbApiConsumer.as_asgi()),  # WebSocket route for Other API
]