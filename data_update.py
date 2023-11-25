import copy

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, APIError
from trades import INITIAL_ASSETS
import copy
import pandas as pd
import sqlite3
import datetime


class Updater:
    def __init__(self):
        self.api = None
        self.alpaca = None
        self.assets = list(INITIAL_ASSETS.keys())

    def initialize_api(self, api_key, api_secret, base_url='https://paper-api.alpaca.markets'):
        self.api = tradeapi.REST(api_key, api_secret, base_url=base_url, api_version='v2')
        self.alpaca = REST(api_key, api_secret)

    def get_max_datetime(self):
        conn = sqlite3.connect('db_crypto.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(timestamp) FROM crypto_bars
        ''')
        max_datetime = cursor.fetchone()[0]
        conn.close()
        return datetime.datetime.strptime(max_datetime, '%Y-%m-%d %H:%M:%S')
    def update_data(self, prior_days=1):
        conn = sqlite3.connect('db_crypto.db')
        cursor = conn.cursor()
        start_date = datetime.date.today() - datetime.timedelta(days=prior_days)
        end_date = datetime.date.today() + datetime.timedelta(days=1)
        bars = self.api.get_crypto_bars(
            self.assets, '1H', start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d')
        ).df
        bars.index = bars.index.tz_convert(None)
        bars.reset_index(inplace=True)
        bars['timestamp'] = bars['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        bars.to_sql('crypto_bars', conn, if_exists='append', index=False)
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
        return datetime.datetime.strptime(bars['timestamp'].max(), '%Y-%m-%d %H:%M:%S')
