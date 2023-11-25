import copy

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, APIError
from trades import INITIAL_ASSETS
import copy
import pandas as pd
import sqlite3
import datetime
from dotenv import load_dotenv
import os


load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL, api_version='v2')
alpaca = REST(API_KEY, API_SECRET)


conn = sqlite3.connect('db_crypto.db')

# Create a cursor object
cursor = conn.cursor()

assets = list(INITIAL_ASSETS.keys())

# Create the 'crypto_bars' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS crypto_bars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME,
        symbol TEXT,
        close REAL,
        high REAL,
        low REAL,
        trade_count INTEGER,
        open REAL,
        volume REAL,
        vwap REAL,
        added_on DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()

start_month_dates = pd.date_range(start=f'{2022}-01-01', end=datetime.date.today() + datetime.timedelta(days=1), freq='MS')
end_month_dates = start_month_dates + pd.offsets.MonthEnd(1)
start_month_dates = list(start_month_dates)
end_month_dates = [e if e <= datetime.date.today() else datetime.date.today() for e in list(end_month_dates)]

for start_date, end_date in zip(start_month_dates, end_month_dates):
    bars = api.get_crypto_bars(assets, '1H', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d')).df
    if len(bars.index) == 0:
        print(f'No data from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}.')
        continue
    bars.index = bars.index.tz_convert(None)
    bars.reset_index(inplace=True)
    bars['timestamp'] = bars['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    bars.to_sql('crypto_bars', conn, if_exists='append', index=False)
    print(f'Added data ({len(bars.index)}) from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} to the database.')

# Delete repeated values
cursor.execute('''
    CREATE TEMPORARY TABLE latest_entries AS
    SELECT MAX(id) AS max_id
    FROM crypto_bars
    GROUP BY timestamp, symbol
''')

cursor.execute('''
    DELETE FROM crypto_bars
    WHERE id NOT IN (SELECT max_id FROM latest_entries)
''')

conn.commit()
conn.close()