import asyncio
from datetime import datetime, timezone, timedelta
import logging
from binance import AsyncClient, BinanceSocketManager, exceptions
from backendapp.data_list import CRYPTO_SYMBOLS
from backendapp.models import Binance_Data
from django.db.utils import IntegrityError
from asgiref.sync import sync_to_async  

logger = logging.getLogger(__name__)

# ✅ Convert Django ORM calls into async-safe functions
@sync_to_async
def save_bulk_binance_data(data_list):
    """Bulk insert Binance data asynchronously while ignoring duplicates."""
    try:
        Binance_Data.objects.bulk_create(data_list, ignore_conflicts=True)
        print(f"✅ Inserted {len(data_list)} historical records (if not duplicates)")
    except IntegrityError as e:
        logger.warning(f"⚠️ IntegrityError: {e}")
    except Exception as e:
        logger.exception(f"❌ Error saving historical Binance data: {e}")

@sync_to_async
def get_latest_binance_data(symbol):
    """Fetch the latest Binance data entry for a given symbol."""
    return Binance_Data.objects.filter(symbol=symbol).values(
        'symbol', 'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
    ).order_by('-timestamp').first()

async def fetch_historical_data(client, symbol):
    """Fetch 10 years of historical Binance data in 5-minute intervals and store it."""
    
    latest_data = await get_latest_binance_data(symbol)  # ✅ Now async-safe!

    if latest_data:
        start_time = latest_data['timestamp']
    else:
        start_time = datetime.now(timezone.utc) - timedelta(days=365 * 10)

    end_time = datetime.now(timezone.utc)
    print(f"⏳ Fetching historical data for {symbol} from {start_time} to {end_time}")

    historical_data = []
    
    while start_time < end_time:
        try:
            klines = await client.get_historical_klines(
                symbol=symbol,
                interval=AsyncClient.KLINE_INTERVAL_5MINUTE,
                start_str=str(int(start_time.timestamp() * 1000)),  
                end_str=str(int(end_time.timestamp() * 1000)),      
                limit=1000
            )
        except exceptions.BinanceAPIException as e:
            if e.code == -1121:
                logger.warning(f"⚠️ Skipping invalid symbol: {symbol} (Error: {e.message})")
            else:
                logger.exception(f"❌ Error fetching historical data for {symbol}: {e}")
            return  # Skip this symbol and continue with the next one
        except Exception as e:
            logger.exception(f"❌ Unexpected error fetching data for {symbol}: {e}")
            return  # Skip this symbol

        if not klines:
            print(f"⚠️ No historical data found for {symbol}, skipping.")
            return  

        for kline in klines:
            timestamp = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)  
            historical_data.append(
                Binance_Data(
                    symbol=symbol,
                    timestamp=timestamp,
                    open_price=float(kline[1]),
                    high_price=float(kline[2]),
                    low_price=float(kline[3]),
                    close_price=float(kline[4]),
                    volume=float(kline[5]),
                )
            )

        start_time = datetime.fromtimestamp(klines[-1][0] / 1000, tz=timezone.utc)

        if len(historical_data) >= 1000:
            await save_bulk_binance_data(historical_data)
            historical_data.clear()

    if historical_data:
        await save_bulk_binance_data(historical_data)

    print(f"✅ Completed fetching & storing data for {symbol}")

async def listen_to_symbol(client, symbol):
    """Listen to Binance WebSocket for live price updates."""
    bm = BinanceSocketManager(client)
    ts = bm.kline_socket(symbol=symbol, interval=AsyncClient.KLINE_INTERVAL_5MINUTE)

    async with ts as stream:
        while True:
            try:
                msg = await stream.recv()
                kline = msg['k']
                if kline['x']:  # Check if candle is closed
                    binance_data = Binance_Data(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(kline['t'] / 1000, tz=timezone.utc),
                        open_price=float(kline['o']),
                        high_price=float(kline['h']),
                        low_price=float(kline['l']),
                        close_price=float(kline['c']),
                        volume=float(kline['v']),
                    )
                    print(binance_data)
                    await save_bulk_binance_data([binance_data])
                    print(f"📊 Live update for {symbol}: {binance_data.close_price}")
            except exceptions.BinanceAPIException as e:
                if e.code == -1121:
                    logger.warning(f"⚠️ Invalid symbol in WebSocket: {symbol}. Skipping.")
                    return  # Exit WebSocket for this symbol
                else:
                    logger.exception(f"❌ WebSocket error for {symbol}: {e}")
            except Exception as e:
                logger.exception(f"❌ Unexpected WebSocket error for {symbol}: {e}")
                return  # Exit WebSocket for this symbol

async def start_binance_ws():
    """Fetch historical data, then start Binance WebSocket streaming."""
    try:
        client = await AsyncClient.create()

        # ✅ Step 1: Fetch and store historical data before starting WebSocket
        await asyncio.gather(*(fetch_historical_data(client, symbol) for symbol in CRYPTO_SYMBOLS))

        # ✅ Step 2: Start real-time WebSocket data streaming
        tasks = [listen_to_symbol(client, symbol) for symbol in CRYPTO_SYMBOLS]
        await asyncio.gather(*tasks)

    except Exception as e:
        logger.exception(f"❌ Error starting Binance WebSocket: {e}")






