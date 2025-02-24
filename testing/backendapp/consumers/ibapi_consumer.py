import json
import asyncio
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import ChannelFull
from binance import AsyncClient, BinanceSocketManager
from backendapp.data_list import CRYPTO_SYMBOLS

logger = logging.getLogger(__name__)

class IbApiConsumer(AsyncWebsocketConsumer):
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

        # Reassign our custom queues after connection acceptance.
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

        # Start a background task to send buffered updates.
        self.sender_task = asyncio.create_task(self.send_buffered_updates())

        # Start a listening task for each symbol.
        self.tasks = []
        for symbol in CRYPTO_SYMBOLS:
            try:
                task = asyncio.create_task(self.listen_to_symbol(symbol))
                self.tasks.append(task)
            except Exception as e:
                logger.exception("Error starting task for symbol %s: %s", symbol, e)

    async def disconnect(self, close_code):
        for task in self.tasks:
            task.cancel()
        self.sender_task.cancel()
        try:
            await self.client.close_connection()
        except Exception as e:
            logger.exception("Error closing Binance connection: %s", e)

    async def send_buffered_updates(self):
        """
        Periodically send aggregated updates to the client.
        We increase the interval to 1 second to throttle sending.
        """
        while True:
            # Wait 1 second between sends.
            await asyncio.sleep(1)
            if not self.latest_updates:
                continue

            try:
                self.is_sending = True
                # Attempt to send the aggregated update with a timeout.
                await asyncio.wait_for(
                    self.send(text_data=json.dumps(self.latest_updates)),
                    timeout=2
                )
                logger.info("Buffered updates sent successfully.")
            except Exception as e:
                # Catch any exception (including ChannelFull and the internal queue error)
                logger.error("Error in send_buffered_updates (dropping updates): %s", e)
            finally:
                self.is_sending = False
                # Clear the buffer regardless of send success.
                self.latest_updates = {}

    async def send(self, *args, **kwargs):
        """
        Override send() to catch all exceptions that might be thrown by the
        underlying send mechanism (including the 'Message queue size 100 exceeded' error)
        and drop the message if it fails.
        """
        try:
            return await super().send(*args, **kwargs)
        except Exception as e:
            logger.error("Error in send(): %s. Dropping message.", e)
            # We drop the message (return None) if sending fails.
            return
