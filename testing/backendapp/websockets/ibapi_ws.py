# ib_api_module.py
import asyncio
from datetime import datetime, timezone, timedelta
from ib_insync import IB, Stock
from asgiref.sync import sync_to_async

# Replace the following import with your actual Django model
from backendapp.models import HistoryData

# Define the list of symbols you wish to fetch historical data for.
# For example, you might have:
IB_SYMBOLS = ["AAPL", "MSFT", "GOOG"]  # Update with your desired symbols

class IBConnection:
    _next_client_id = 1

    def __init__(self, client_id=None):
        self.ib = IB()
        if client_id is not None:
            self.client_id = client_id
        else:
            self.client_id = IBConnection._next_client_id
            IBConnection._next_client_id += 1

    async def connect(self, host='127.0.0.1', port=7496, timeout=30):
        """Connect to TWS/IB Gateway."""
        await self.ib.connectAsync(host, port, clientId=self.client_id, timeout=timeout)
        return self.ib

    async def disconnect(self):
        """Disconnect from TWS/IB Gateway."""
        if self.ib.isConnected():
            self.ib.disconnect()

    @staticmethod
    def get_stock_contract(symbol, exchange='SMART', currency='USD'):
        """
        Return a contract for a stock.
        Adjust the exchange or currency based on your market requirements.
        """
        return Stock(symbol, exchange, currency)

    @sync_to_async(thread_sensitive=True)
    def save_history_records(self, records):
        """Save a list of HistoryData records using Django ORM."""
        if records:
            HistoryData.objects.bulk_create(records, ignore_conflicts=True)

    async def fetch_and_save_historical_data_for_symbol(
        self, symbol, duration='1 Y', bar_size='1 day', total_years=10
    ):
        """
        Fetch historical data for a given symbol in chunks and save to DB.
        This method will fetch data in 1-year chunks until a total of `total_years` is reached.
        """
        contract = self.get_stock_contract(symbol)
        await self.ib.qualifyContractsAsync(contract)
        
        # Set the initial end date to now (UTC)
        current_end = datetime.now(timezone.utc)
        # Calculate the earliest date to fetch (total_years back)
        earliest_date = current_end - timedelta(days=total_years * 365)

        while current_end > earliest_date:
            # IB requires the end date as a formatted string.
            endDateTime = current_end.strftime('%Y%m%d %H:%M:%S')
            try:
                bars = await self.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime=endDateTime,
                    durationStr=duration,
                    barSizeSetting=bar_size,
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )
            except Exception as e:
                print(f"❌ Error fetching historical data for {symbol} at {endDateTime}: {e}")
                break

            if not bars:
                print(f"⚠️ No data returned for {symbol} for chunk ending {endDateTime}")
                break

            records = []
            for bar in bars:
                try:
                    dt = datetime.strptime(bar.date, '%Y%m%d')
                    dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                record = HistoryData(
                    symbol=symbol,
                    timestamp=dt,
                    open_price=bar.open,
                    high_price=bar.high,
                    low_price=bar.low,
                    close_price=bar.close,
                    volume=bar.volume,
                )
                records.append(record)
            await self.save_history_records(records)
            print(f"✅ Saved {len(records)} bars for {symbol} up to {endDateTime}")

            try:
                new_end = datetime.strptime(bars[0].date, '%Y%m%d').replace(tzinfo=timezone.utc)
            except Exception:
                break

            # If no progress is made, exit the loop.
            if new_end >= current_end:
                break

            current_end = new_end
            await asyncio.sleep(1)  # Small pause to avoid rate limits

    async def fetch_and_save_all_historical_data(self):
        """
        Fetch historical data concurrently for all symbols defined in IB_SYMBOLS.
        """
        tasks = [
            asyncio.shield(self.fetch_and_save_historical_data_for_symbol(symbol))
            for symbol in IB_SYMBOLS
        ]
        await asyncio.gather(*tasks)


async def main():
    ib_conn = IBConnection()
    await ib_conn.connect()
    await ib_conn.fetch_and_save_all_historical_data()
    await ib_conn.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
