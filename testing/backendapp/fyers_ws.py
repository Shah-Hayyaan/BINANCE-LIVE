import asyncio
import threading
from datetime import datetime, timezone, timedelta
from backendapp.models import HistoryData
from fyers_apiv3 import fyersModel
import os
from dotenv import load_dotenv
from backendapp.data_list import FYERS_SYMBOLS
from asgiref.sync import sync_to_async  
from django.http import JsonResponse

load_dotenv()

access_token = os.getenv("ACCESS_TOKEN")
client_id = os.getenv("FYERS_CLIENT_ID")

# Use sync_to_async to run Django ORM operations in a separate thread
@sync_to_async(thread_sensitive=True)
def get_latest_fyers_data(symbol):
    """Fetch the latest available data entry for a given symbol."""
    return HistoryData.objects.filter(symbol=symbol).values(
        'symbol', 'timestamp'
    ).order_by('-timestamp').first()

async def fetch_and_save_historical_data():
    """Fetch last 10 years of historical data from Fyers API in 100-day chunks and save to DB"""
    
    fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")

    for symbol in FYERS_SYMBOLS:
        latest_data = await get_latest_fyers_data(symbol)

        if latest_data:
            latest_timestamp = latest_data["timestamp"]
        else:
            latest_timestamp = datetime.now(timezone.utc) - timedelta(days=100)  # Start from 10 years ago
        
        current_time = datetime.now(timezone.utc)

        while latest_timestamp < current_time:
            range_from = int(latest_timestamp.timestamp())  
            range_to = int((latest_timestamp + timedelta(days=100)).timestamp())

            if range_to > int(current_time.timestamp()):
                range_to = int(current_time.timestamp())

            print(f'Fetching data for {symbol} from {datetime.utcfromtimestamp(range_from)} to {datetime.utcfromtimestamp(range_to)}')

            data = {
                "symbol": symbol,  
                "resolution": "5",  # Daily resolution
                "date_format": "0",  
                "range_from": range_from,  
                "range_to": range_to,  
                "cont_flag": "1"  
            }

            try:
                response = fyers.history(data=data)
                if "candles" in response:
                    candles = response["candles"]

                    records_to_save = []
                    for candle in candles:
                        timestamp = datetime.fromtimestamp(candle[0], tz=timezone.utc)
                        record = HistoryData(
                            symbol=symbol.split(":")[1].split("-")[0],
                            timestamp=timestamp,
                            open_price=candle[1],
                            high_price=candle[2],
                            low_price=candle[3],
                            close_price=candle[4],
                            volume=candle[5],
                        )
                        records_to_save.append(record)

                    if records_to_save:
                        await sync_to_async(HistoryData.objects.bulk_create, thread_sensitive=True)(records_to_save, ignore_conflicts=True)
                        print(f"✅ Saved {len(records_to_save)} records for {symbol} from {datetime.utcfromtimestamp(range_from)} to {datetime.utcfromtimestamp(range_to)}")
                else:
                    print(f"⚠️ No data for {symbol} in this range")

            except Exception as e:
                print(f"❌ Error fetching historical data for {symbol}: {str(e)}")
            
            # Move forward by 100 days
            latest_timestamp += timedelta(days=100)
            await asyncio.sleep(2)  # Small delay to prevent hitting API limits


