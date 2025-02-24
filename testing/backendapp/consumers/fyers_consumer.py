import json
import os
from dotenv import load_dotenv
from channels.generic.websocket import AsyncWebsocketConsumer
from fyers_apiv3.FyersWebsocket import data_ws
from backendapp.data_list import FYERS_SYMBOLS
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from backendapp.models import HistoryData
from fyers_apiv3 import fyersModel
from datetime import timedelta, datetime




load_dotenv()

# access_token = os.getenv("ACCESS_TOKEN")

access_token='eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhcGkuZnllcnMuaW4iLCJpYXQiOjE3MzkzNDk0OTMsImV4cCI6MTczOTQwNjYxMywibmJmIjoxNzM5MzQ5NDkzLCJhdWQiOlsieDowIiwieDoxIiwieDoyIiwiZDoxIiwiZDoyIiwieDoxIiwieDowIiwieDoxIiwieDowIiwieDoxIiwieDowIl0sInN1YiI6ImFjY2Vzc190b2tlbiIsImF0X2hhc2giOiJnQUFBQUFCbnJGMzFlOHY3WnQ1RDEtaURENU80cEpiY01vbEpmc3VkTmhGM3hpQWlIb2tHLVRRNXhKSHFRVlpkQ0lZSWVEMnY2OE1RVVh4RW1YZEJsVTR4VXdvNUc3bXpKak5sVENZU0xnV1VLcEhoZFFyY3BzUT0iLCJkaXNwbGF5X25hbWUiOiJNVUtFU0ggUkFNTEFMIFZJU0hXQUtBUk1BIiwib21zIjoiSzEiLCJoc21fa2V5IjoiNWM1Y2Q3MDUxODdmODRhN2RjMTM1ZDRiMjUzZWMyODVlYzNkNTdmNjJhNjU3MzRmN2VmY2U3MmUiLCJpc0RkcGlFbmFibGVkIjoiTiIsImlzTXRmRW5hYmxlZCI6Ik4iLCJmeV9pZCI6IllNMjg0MTIiLCJhcHBUeXBlIjoxMDAsInBvYV9mbGFnIjoiTiJ9.IyRo0-AzOSaMFTl2yTuQdR2hFkuLg3ser6sGYDAK-PE'
# client_id = os.getenv("FYERS_CLIENT_ID")
client_id = "3TQOJHLJIT-100"

class FyersConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latest_updates = {}
        self.fyers_socket = None

    async def connect(self):
        await self.accept()
        await self.channel_layer.group_add("fyers_updates", self.channel_name)
        try:
            self.fyers_socket = data_ws.FyersDataSocket(
                access_token=access_token,
                log_path="",
                litemode=False,
                reconnect=True,
                on_connect=self.on_fyers_open,
                on_error=self.on_fyers_error,
                on_message=self.on_fyers_message
            )
            self.fyers_socket.connect()
        except Exception as e:
            print(f"Error during connection: {str(e)}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("fyers_updates", self.channel_name)
        try:
            if self.fyers_socket:
                if hasattr(self.fyers_socket, 'stop'):
                    self.fyers_socket.stop()
                elif hasattr(self.fyers_socket, 'close'):
                    self.fyers_socket.close()
            print("🔴 Fyers WebSocket Disconnected")
        except Exception as e:
            print(f"Error during disconnection: {str(e)}")

    def on_fyers_open(self):
        """Handle WebSocket connection opening for Fyers."""
        try:
            if FYERS_SYMBOLS:
                # print(f"Subscribing to symbols: {FYERS_SYMBOLS}")
                self.fyers_socket.subscribe(symbols=FYERS_SYMBOLS, data_type="SymbolUpdate")
            print("🟢 Fyers WebSocket Connected")
            self.fyers_socket.keep_running()
        except Exception as e:
            print(f"Error subscribing: {str(e)}")

    def on_fyers_error(self, error):
        """Handle WebSocket errors for Fyers."""
        print(f"🔴 Fyers WebSocket Error: {error}")
        if isinstance(error, dict) and 'code' in error and error['code'] == -300:
            print(f"Invalid input error details: {error}")
            
    def on_fyers_message(self, message):
        """Handle incoming messages from Fyers WebSocket."""
        # Ignore messages that are empty or missing a valid symbol.
        if not message or message.get("symbol") is None:
            return

        filtered_message = {
            "symbol": message.get("symbol"),
            # Use "last_traded_time" as the timestamp.
            "timestamp": message.get("last_traded_time"),
            "open_price": message.get("open_price"),
            "high_price": message.get("high_price"),
            "low_price": message.get("low_price"),
            # Use "ltp" as the close_price.
            "close_price": message.get("ltp"),
            # Use "vol_traded_today" as the volume.
            "volume": message.get("vol_traded_today")
        }

        # Save real-time data and fill in any missing 5-minute intervals.
        save_symbol_data(filtered_message)

        # Send the filtered message via the channel layer to the frontend.
        async_to_sync(get_channel_layer().group_send)(
            "fyers_updates",
            {
                "type": "send.fyers",
                "message": filtered_message
            }
        )

    async def send_fyers_update(self):
        """Send updates using Django Channels' layer to prevent event loop issues."""
        channel_layer = get_channel_layer()
        await channel_layer.send(self.channel_name, {
            "type": "send.fyers",
            "message": self.latest_updates
        })

    async def send_fyers(self, event):
        # This method is called in the consumer’s event loop.
        await self.send(text_data=json.dumps(event["message"]))


def save_symbol_data(filtered_message):
    """Save real-time data and fill in any missing 5-minute intervals."""
    
    symbol_raw = filtered_message["symbol"]
    # Convert the incoming timestamp (in seconds) to a timezone-aware datetime.
    current_ts = datetime.fromtimestamp(filtered_message["timestamp"])
    current_ts = timezone.make_aware(current_ts)

    # Normalize the symbol, e.g. "NSE:ICICIBANK-EQ" becomes "ICICIBANK"
    symbol = symbol_raw.split(":")[1].split("-")[0]
    # print("symbol", symbol)

    try:
        # Get the latest saved record for this symbol as a dict.
        last_record = (
            HistoryData.objects.filter(symbol=symbol)
            .values("symbol", "timestamp")
            .order_by("-timestamp")
            .first()
        )
        # print("last_record", last_record)
    except HistoryData.DoesNotExist:
        last_record = None

    records = []  # List to accumulate new HistoryData instances

    if last_record:
        gap = current_ts - last_record["timestamp"]
        if gap < timedelta(minutes=5):
            # Less than 5 minutes have passed; do not save a new record.
            return
        else:
            # Calculate how many 5-minute intervals are missing.
            num_intervals = int(gap.total_seconds() // (5 * 60))
            # Create a placeholder record for each missing interval.
            for i in range(1, num_intervals):
                missing_timestamp = last_record["timestamp"] + timedelta(minutes=5 * i)
                record = HistoryData(
                    symbol=symbol,
                    timestamp=missing_timestamp,
                    open_price=filtered_message["open_price"],
                    high_price=filtered_message["high_price"],
                    low_price=filtered_message["low_price"],
                    close_price=filtered_message["close_price"],
                    volume=filtered_message["volume"],
                )
                records.append(record)
            # Append the current realtime record.
            records.append(
                HistoryData(
                    symbol=symbol,
                    timestamp=current_ts,
                    open_price=filtered_message["open_price"],
                    high_price=filtered_message["high_price"],
                    low_price=filtered_message["low_price"],
                    close_price=filtered_message["close_price"],
                    volume=filtered_message["volume"],
                )
            )
            # Save all new records using bulk_create with ignore_conflicts.
            HistoryData.objects.bulk_create(records, ignore_conflicts=True)
            print(f"Saved Gap record for {symbol} at {current_ts}")
    else:
        # No previous record exists for this symbol.
        # Define a historical range: from 100 days ago until now.
        range_to = current_ts
        range_from = current_ts - timedelta(days=100)
        data = {
            "symbol": symbol,
            "resolution": "5",  # 5-minute resolution
            "date_format": "0",
            "range_from": int(range_from.timestamp()),  # UNIX timestamp (seconds)
            "range_to": int(range_to.timestamp()),
            "cont_flag": "1",
        }
        try:
            fyers = fyersModel.FyersModel(
                client_id=client_id, is_async=False, token=access_token, log_path=""
            )
            # Call the Fyers history API to fetch historical candle data.
            response = fyers.history(data=data)
            if "candles" in response:
                candles = response["candles"]
                records_to_save = []
                for candle in candles:
                    # Assume candle[0] is a UNIX timestamp (in seconds)
                    ts = datetime.fromtimestamp(candle[0])
                    ts = timezone.make_aware(ts)
                    record = HistoryData(
                        symbol=symbol,
                        timestamp=ts,
                        open_price=candle[1],
                        high_price=candle[2],
                        low_price=candle[3],
                        close_price=candle[4],
                        volume=candle[5],
                    )
                    records_to_save.append(record)
                if records_to_save:
                    HistoryData.objects.bulk_create(records_to_save, ignore_conflicts=True)
                    print(f"Saved 5minute Interval record for {symbol} at {current_ts}")
        except Exception as e:
            print("Error fetching historical data:", e)

        # Finally, save the current realtime record.
        # record = HistoryData(
        #     symbol=symbol,
        #     timestamp=current_ts,
        #     open_price=filtered_message["open_price"],
        #     high_price=filtered_message["high_price"],
        #     low_price=filtered_message["low_price"],
        #     close_price=filtered_message["close_price"],
        #     volume=filtered_message["volume"],
        # )
        # HistoryData.objects.bulk_create([record], ignore_conflicts=True)
        # print(f"Saved realtime record for {symbol} at {current_ts}")
