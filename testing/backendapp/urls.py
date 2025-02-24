from django.urls import path
from django.http import JsonResponse
from backendapp.views import start_fyers_ws_and_fetch_history, start_binance_ws_api

def api_root(request):
    return JsonResponse({
        'status': 'API is running',
        'available_endpoints': {
            'fyers_websocket': '/api/start-fyers-and-fetch-history/',
            'binance_websocket': '/api/start-binance/',
        },
        'documentation': 'Each endpoint starts a WebSocket connection in a separate thread'
    })

urlpatterns = [
    path('', api_root, name='api_root'),  # Add this root endpoint
    path('start-fyers-and-fetch-history/', start_fyers_ws_and_fetch_history, name='start_fyers_and_fetch_history'),
    path('start-binance/', start_binance_ws_api, name='start_binance_ws_api'),
]
