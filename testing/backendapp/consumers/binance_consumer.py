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
        # Initialize tasks as empty list upon creation
        self.tasks = []
        self.client = None
        self.bm = None
        self.sender_task = None
        self.history_task = None
        self.previous_data = {}
        self.latest_updates = {}

    async def connect(self):
        try:
            await self.accept()
            logger.info("WebSocket connection accepted")
            
            # Ping/pong heartbeat task to keep connection alive
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
            self.tasks.append(self.heartbeat_task)
            
            # Initialize Binance client with additional timeout
            self.client = await AsyncClient.create(request_timeout=30)
            self.bm = BinanceSocketManager(self.client)
            
            # Start background tasks
            self.sender_task = asyncio.create_task(self.send_buffered_updates())
            self.tasks.append(self.sender_task)
            
            # Create tasks for each symbol
            for symbol in CRYPTO_SYMBOLS:
                try:
                    task = asyncio.create_task(self.listen_to_symbol(symbol))
                    self.tasks.append(task)
                    logger.info(f"Started listening to symbol: {symbol}")
                except Exception as e:
                    logger.exception("Error starting task for symbol %s: %s", symbol, e)
            
            self.history_task = asyncio.create_task(self.fill_missing_data())
            self.tasks.append(self.history_task)
            
            logger.info(f"Connection setup complete with {len(self.tasks)} active tasks")
            
        except Exception as e:
            logger.exception("Error during connection setup: %s", e)
            await self.close(code=3000)  # 1011 = Internal Error

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting with code: {close_code}")
        try:
            # Cancel all tasks
            for task in self.tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Clean up Binance client connection
            if self.client:
                await self.client.close_connection()
                
            logger.info("Disconnection cleanup completed successfully")
        except Exception as e:
            logger.exception("Error during disconnect cleanup: %s", e)

    async def send_heartbeat(self):
        """Send regular pings to keep the connection alive"""
        try:
            while True:
                await asyncio.sleep(25)  # Send heartbeat every 25 seconds
                if self.is_sending:
                    continue  # Skip if already sending data
                
                try:
                    await self.send(text_data=json.dumps({"ping": True}))
                    logger.debug("Heartbeat ping sent")
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")
                    break
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.exception(f"Heartbeat task error: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages from the client"""
        if text_data:
            data = json.loads(text_data)
            if data.get("pong") is True:
                logger.debug("Received pong from client")
            elif data.get("type") == "subscribe":
                # Handle any client subscription requests
                logger.info(f"Client subscription request: {data}")

    async def listen_to_symbol(self, symbol):
        """Listen to a specific symbol and process its data"""
        retry_count = 0
        max_retries = 5
        retry_delay = 1
        
        while retry_count < max_retries:
            try:
                trade_socket = self.bm.trade_socket(symbol.lower())
                kline_socket = self.bm.kline_socket(symbol.lower(), interval="1m")
                
                async with trade_socket as trade_ws, kline_socket as kline_ws:
                    logger.info(f"Socket connections established for {symbol}")
                    while True:
                        try:
                            trade_res, kline_res = await asyncio.gather(
                                trade_ws.recv(),
                                kline_ws.recv(),
                                return_exceptions=True
                            )
                            
                            # Handle exception cases
                            if isinstance(trade_res, Exception):
                                logger.error(f"Trade socket error for {symbol}: {trade_res}")
                                raise trade_res
                            if isinstance(kline_res, Exception):
                                logger.error(f"Kline socket error for {symbol}: {kline_res}")
                                raise kline_res
                                
                            # Process trade data
                            trade_data = {
                                "symbol": symbol.upper(),
                                "timestamp": trade_res.get("T"),
                            }
                            
                            # Process kline data
                            kline = kline_res.get("k", {})
                            kline_data = {
                                "open": kline.get("o"),
                                "high": kline.get("h"),
                                "low": kline.get("l"),
                                "close": kline.get("c"),
                                "volume": kline.get("v"),
                            }
                            
                            # Combine the data
                            combined_data = {**trade_data, **kline_data}

                            # Only update if data has changed
                            if self.previous_data.get(symbol) != combined_data:
                                self.previous_data[symbol] = combined_data
                                self.latest_updates[symbol] = combined_data
                                
                        except asyncio.CancelledError:
                            logger.info(f"Listen task for symbol {symbol} was cancelled")
                            return
                        except Exception as e:
                            logger.exception(f"Error processing data for {symbol}: {e}")
                            await asyncio.sleep(0.5)
                            
            except asyncio.CancelledError:
                logger.info(f"Listen task for symbol {symbol} was cancelled during setup")
                return
            except Exception as e:
                retry_count += 1
                logger.error(f"Socket error for {symbol}, retry {retry_count}/{max_retries}: {e}")
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for {symbol}, giving up")
                    return
                    
                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** (retry_count - 1)))

    async def send_buffered_updates(self):
        """Periodically send aggregated updates to the client"""
        try:
            while True:
                await asyncio.sleep(1)  # Send updates every second
                
                if not self.latest_updates:
                    continue
                
                updates_to_send = self.latest_updates.copy()
                self.latest_updates = {}  # Clear the buffer before sending
                
                try:
                    self.is_sending = True
                    await asyncio.wait_for(
                        self.send(text_data=json.dumps(updates_to_send)),
                        timeout=3
                    )
                    logger.debug(f"Sent updates for {len(updates_to_send)} symbols")
                except asyncio.TimeoutError:
                    logger.error("Send operation timed out")
                except Exception as e:
                    logger.error(f"Error sending updates: {e}")
                finally:
                    self.is_sending = False
                    
        except asyncio.CancelledError:
            logger.info("Send buffered updates task cancelled")
        except Exception as e:
            logger.exception(f"Fatal error in send_buffered_updates: {e}")

    async def fill_missing_data(self):
        """Fill in missing historical data"""
        try:
            while True:
                current_time = datetime.now(timezone.utc)
                logger.info("Starting missing data check")
                
                for symbol in CRYPTO_SYMBOLS:
                    try:
                        latest_data = await get_latest_binance_data(symbol)
                        
                        if latest_data and latest_data.get("timestamp"):
                            last_timestamp = latest_data["timestamp"]
                            if last_timestamp.tzinfo is None:
                                last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)
                            
                            time_gap = (current_time - last_timestamp).total_seconds()
                            logger.info(f"Gap for {symbol}: {time_gap/60:.1f} minutes")
                            
                            if time_gap >= 300:  # 5 minutes gap
                                fetch_end_time = min(last_timestamp + timedelta(hours=1), current_time)
                                start_time = last_timestamp
                                logger.info(f"Fetching data for {symbol} from {start_time} to {fetch_end_time}")
                                await self.fetch_and_insert_klines(symbol, start_time, fetch_end_time)
                        else:
                            # No data exists, fetch the last day
                            start_time = current_time - timedelta(days=1)
                            logger.info(f"No data for {symbol}, fetching last 24h")
                            await self.fetch_and_insert_klines(symbol, start_time, current_time)
                    except Exception as e:
                        logger.exception(f"Error filling data for {symbol}: {e}")
                
                # Run this check every 5 minutes
                await asyncio.sleep(300)
                
        except asyncio.CancelledError:
            logger.info("Fill missing data task cancelled")
        except Exception as e:
            logger.exception(f"Fatal error in fill_missing_data: {e}")

    async def fetch_and_insert_klines(self, symbol, start_time, end_time, interval="5m"):
        """Fetch and store historical kline data"""
        try:
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)
            
            klines = await self.client.get_historical_klines(
                symbol.upper(), 
                interval, 
                start_ts, 
                end_ts,
                limit=500
            )
            
            logger.info(f"Fetched {len(klines)} klines for {symbol}")
            
            for kline in klines:
                data = self.parse_kline(symbol, kline)
                await insert_binance_data(data)
                
            logger.info(f"Inserted historical data for {symbol}")
            
        except Exception as e:
            logger.exception(f"Error fetching/inserting klines for {symbol}: {e}")

    @staticmethod
    def parse_kline(symbol, kline):
        """Parse a kline into a structured data format"""
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
        """Override send to add error handling"""
        try:
            return await super().send(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in send(): {e}. Dropping message.")
            return


# --- Helper Functions for Django ORM Access ---

@sync_to_async(thread_sensitive=True)
def get_latest_binance_data(symbol):
    """Get the latest stored data for a symbol"""
    try:
        Binance_Data = apps.get_model('backendapp', 'Binance_Data')  # Moved inside function
        return (
            Binance_Data.objects.filter(symbol=symbol.upper())
            .values("symbol", "timestamp")
            .order_by("-timestamp")
            .first()
        ) or None
    except Exception as e:
        logger.exception(f"Database error getting latest data for {symbol}: {e}")
        return None


@sync_to_async(thread_sensitive=True)
def insert_binance_data(data):
    """Insert new data record into the database"""
    try:
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
    except Exception as e:
        logger.exception(f"Database error inserting data: {e}")
