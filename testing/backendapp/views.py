from django.http import JsonResponse
import threading
import asyncio
from backendapp.fyers_ws import fetch_and_save_historical_data
from backendapp.binance_ws import start_binance_ws

# New view for both tasks
def start_fyers_ws_and_fetch_history(request):
    """Start WebSocket and fetch historical data in one function"""

    # Start historical data fetching asynchronously
    def run_ws():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch_and_save_historical_data())

    threading.Thread(target=run_ws, daemon=True).start()
    
    return JsonResponse({"message": "Fyers WebSocket started and historical data is being fetched!"})


def start_binance_ws_api(request):
    """API to start Binance WebSocket in a separate thread."""
    
    # Function to start event loop in a new thread
    def run_ws():
        asyncio.run(start_binance_ws())  # ✅ Properly await the async function

    # Start WebSocket in a new thread
    threading.Thread(target=run_ws, daemon=True).start()
    
    return JsonResponse({"message": "Binance WebSocket started!"})

# def start_ibapi_ws_api(request):
#     """API to start Other WebSocket"""
#     threading.Thread(target=start_ibkr_ws, daemon=True).start()
#     return JsonResponse({"message": "IbApi WebSocket started!"})

