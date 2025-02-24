import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from django.apps import apps
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from binance import AsyncClient, BinanceSocketManager
from backendapp.data_list import CRYPTO_SYMBOLS

logger = logging.getLogger(__name__)

class BinanceConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override internal queues to use a larger limit.
        self._channel_queue = asyncio.Queue(maxsize=1000)
        self._queue = asyncio.Queue(maxsize=1000)
        self._send_queue = asyncio.Queue(maxsize=1000)
        self.is_sending = False

    async def connect(self):
        try:
            await self.accept()
        except Exception as e:
            logger.exception("Error during connection accept: %s", e)
            return

        # Reinitialize custom queues after connection.
        self._channel_queue = asyncio.Queue(maxsize=1000)
        self._queue = asyncio.Queue(maxsize=1000)
        self._send_queue = asyncio.Queue(maxsize=1000)

        self.previous_data = {}
        self.latest_updates = {}  # Buffer for aggregated updates

        try:
            self.client = await AsyncClient.create()
            self.bm = BinanceSocketManager(self.client)
        except Exception as e:
            logger.exception("Error initializing Binance client/socket manager: %s", e)
            await self.close()
            return

        # Start background tasks.
        self.sender_task = asyncio.create_task(self.send_buffered_updates())
        self.tasks = []
        for symbol in CRYPTO_SYMBOLS:
            try:
                task = asyncio.create_task(self.listen_to_symbol(symbol))
                self.tasks.append(task)
            except Exception as e:
                logger.exception("Error starting task for symbol %s: %s", symbol, e)

        self.history_task = asyncio.create_task(self.fill_missing_data())

    async def disconnect(self, close_code):
        for task in self.tasks:
            task.cancel()
        self.sender_task.cancel()
        if hasattr(self, "history_task"):
            self.history_task.cancel()
        try:
            await self.client.close_connection()
        except Exception as e:
            logger.exception("Error closing Binance connection: %s", e)

    async def listen_to_symbol(self, symbol):
        trade_socket = self.bm.trade_socket(symbol.lower())
        kline_socket = self.bm.kline_socket(symbol.lower(), interval="1m")
        try:
            async with trade_socket as trade_ws, kline_socket as kline_ws:
                while True:
                    try:
                        trade_res, kline_res = await asyncio.gather(
                            trade_ws.recv(),
                            kline_ws.recv()
                        )
                        trade_data = {
                            "symbol": symbol.upper(),
                            "timestamp": trade_res.get("T"),
                        }
                        kline = kline_res.get("k", {})
                        kline_data = {
                            "open": kline.get("o"),
                            "high": kline.get("h"),
                            "low": kline.get("l"),
                            "close": kline.get("c"),
                            "volume": kline.get("v"),
                        }
                        combined_data = {**trade_data, **kline_data}

                        # Only update/send if data has changed.
                        if self.previous_data.get(symbol) != combined_data:
                            self.previous_data[symbol] = combined_data
                            self.latest_updates[symbol] = combined_data
                    except asyncio.CancelledError:
                        logger.info("Listen task for symbol %s was cancelled", symbol)
                        break
                    except Exception as e:
                        logger.exception("Error processing data for symbol %s: %s", symbol, e)
                        await asyncio.sleep(0.1)
        except Exception as e:
            logger.exception("Error in websocket context for symbol %s: %s", symbol, e)

    async def send_buffered_updates(self):
        """
        Periodically send aggregated updates to the client.
        """
        while True:
            await asyncio.sleep(1)
            if not self.latest_updates:
                continue

            try:
                self.is_sending = True
                await asyncio.wait_for(
                    self.send(text_data=json.dumps(self.latest_updates)),
                    timeout=2
                )
                logger.info("Buffered updates sent successfully.")
            except Exception as e:
                logger.error("Error in send_buffered_updates (dropping updates): %s", e)
            finally:
                self.is_sending = False
                self.latest_updates = {}

    async def fill_missing_data(self):
        """
        Every minute, check each symbol’s latest DB record.
        If the gap to the current time is at least 5 minutes,
        fetch historical 5-min data from Binance and insert missing entries.
        """
        while True:
            current_time = datetime.now(timezone.utc)
            for symbol in CRYPTO_SYMBOLS:
                try:
                    latest_data = await get_latest_binance_data(symbol)
                    if latest_data and latest_data.get("timestamp"):
                        last_timestamp = latest_data["timestamp"]
                        if last_timestamp.tzinfo is None:
                            last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)
                        
                        logger.info("Latest timestamp for %s: %s", symbol, last_timestamp)
                        
                        # Only fill if gap is at least 5 minutes.
                        if (current_time - last_timestamp).total_seconds() >= 300:
                            fetch_end_time = min(last_timestamp + timedelta(days=7), current_time)
                            start_time = last_timestamp
                            logger.info("Fetching data for %s from %s to %s", symbol, start_time, fetch_end_time)
                            await self.fetch_and_insert_klines(symbol, start_time, fetch_end_time)
                        else:
                            start_time = current_time - timedelta(days=100)
                            await self.fetch_and_insert_klines(symbol, start_time, current_time)
                    else:
                        start_time = current_time - timedelta(days=100)
                        await self.fetch_and_insert_klines(symbol, start_time, current_time)
                except Exception as e:
                    logger.exception("Error filling missing data for symbol %s: %s", symbol, e)
            await asyncio.sleep(60)

    async def fetch_and_insert_klines(self, symbol, start_time, end_time, interval="5m"):
        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)
        klines = await self.client.get_historical_klines(symbol.upper(), interval, start_ts, end_ts)
        for kline in klines:
            data = self.parse_kline(symbol, kline)
            await insert_binance_data(data)

    @staticmethod
    def parse_kline(symbol, kline):
        return {
            "symbol": symbol.upper(),
            "timestamp": datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
            "open": kline[1],
            "high": kline[2],
            "low": kline[3],
            "close": kline[4],
            "volume": kline[5],
        }

    async def send(self, *args, **kwargs):
        try:
            return await super().send(*args, **kwargs)
        except Exception as e:
            logger.error("Error in send(): %s. Dropping message.", e)
            return


# --- Helper Functions for Django ORM Access ---

@sync_to_async(thread_sensitive=True)
def get_latest_binance_data(symbol):
    Binance_Data = apps.get_model('backendapp', 'Binance_Data')  # Moved inside function
    return (
        Binance_Data.objects.filter(symbol=symbol.upper())
        .values("symbol", "timestamp")
        .order_by("-timestamp")
        .first()
    ) or None


@sync_to_async(thread_sensitive=True)
def insert_binance_data(data):
    Binance_Data = apps.get_model('backendapp', 'Binance_Data')  # Moved inside function
    Binance_Data.objects.create(
        symbol=data["symbol"],
        timestamp=data["timestamp"],
        open_price=data["open"],
        high_price=data["high"],
        low_price=data["low"],
        close_price=data["close"],
        volume=data["volume"],
    )
