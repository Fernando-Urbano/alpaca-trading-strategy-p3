import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, APIError
import os
import time
import copy
import re
from trades import INITIAL_ASSETS
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

class Operator:
    def __init__(self):
        self.current_usd_positions = copy.deepcopy(INITIAL_ASSETS)
        self.current_prices = {}
        self.current_quantities = copy.deepcopy(INITIAL_ASSETS)
        self.current_weights = copy.deepcopy(INITIAL_ASSETS)
        self.target_weights = {}
        self.orders = {}
        self.bad_requests = []
        self.api = None
        self.alpaca = None
        self.cash = 0
        self.equity = 0
        self.margin = .01
        self.order_history = []

    def initialize_api(self, api_key, api_secret, base_url='https://paper-api.alpaca.markets'):
        self.api = tradeapi.REST(api_key, api_secret, base_url=base_url, api_version='v2')
        self.alpaca = REST(api_key, api_secret)

    def update_bad_requests(self):
        new_bad_request = time.time()
        self.bad_requests = [b for b in self.bad_requests if b > new_bad_request - (60 * 30)]
        self.bad_requests.append(new_bad_request)
        if len(self.bad_requests) > 10:
            self.close_positions()
            raise Exception("Bad requested exceeded 10 in 30 minutes.")

    def close_positions(self):
        open_positions = self.api.list_positions()
        for position in open_positions:
            self.api.submit_order(
                symbol=position.symbol,
                qty=position.qty,
                side='sell',
                type='market',
                time_in_force='gtc'
            )

    def cancel_open_orders(self):
        open_orders = self.api.list_orders()
        for order in open_orders:
            self.api.cancel_order(order.id)

    def get_last_order_datetime(self):
        last_order = self.api.list_orders(status='all', limit=1)
        if last_order:
            last_order_datetime = last_order[0].created_at.tz_convert(None)
            return last_order_datetime.to_pydatetime()
        else:
            return None

    def update_equity(self):
        account = self.api.get_account()
        self.equity = float(account.equity)
        self.cash = float(account.cash)

    def update_current_positions(self, update_equity=True):
        positions = self.api.list_positions()
        for position in positions:
            symbol = position.symbol[:-3] + "/" + position.symbol[-3:] if position.symbol.endswith('USD') else position.symbol
            current_usd_position = float(position.current_price) * float(position.qty)
            self.current_usd_positions[symbol] = current_usd_position
            self.current_quantities[symbol] = float(position.qty)
            self.current_prices[symbol] = float(position.current_price)
        if update_equity:
            self.update_equity()
        self.current_weights = {s: p / self.equity for s, p in self.current_usd_positions.items()}

    def update_target_positions(self, weights):
        self.target_weights = weights

    def __repr__(self):
        # self.update_current_positions(update_equity=True)
        repr = []
        repr.append(f'Total equity: USD {self.equity:.2f}; Total cash: USD {self.cash:.2f}')
        for ticker, position in self.current_usd_positions.items():
            equity_in_ticker = self.current_prices[ticker] * self.current_quantities[ticker]
            repr.append(f"{ticker}: USD {equity_in_ticker:.2f} ({(equity_in_ticker / self.equity):.2%})")
        return '\n'.join(repr)

    def update_prices(self):
        tickers = list(self.current_weights.keys())
        for ticker in tickers:
            last_trade = self.api.get_latest_crypto_trades([ticker])
            if last_trade:
                self.current_prices[ticker] = float(last_trade[ticker].p)
            else:
                self.update_bad_requests()

    def define_orders(self):
        diff_target_current_weights = {s: self.target_weights[s] - self.current_weights[s] for s in self.target_weights}
        diff_target_current_positions = {s: diff_target_current_weights[s] * self.equity for s in diff_target_current_weights}
        diff_target_current_positions = {s: d if d < 0 else d * (1 - self.margin) for s, d in diff_target_current_positions.items()}
        self.orders = {s: diff_target_current_positions[s] / self.current_prices[s] for s in diff_target_current_positions}

    def place_orders(self):
        orders = dict(sorted(self.orders.items(), key=lambda item: item[1]))
        for order_symbol, quantity in orders.items():
            if quantity > 0:
                order_quantity = round(abs(quantity), 4)
                while True:
                    try:
                        order = self.api.submit_order(
                            symbol=order_symbol,
                            qty=order_quantity,
                            side='buy',
                            type='market',
                            time_in_force='gtc',
                        )
                        self.order_history.append(order)
                        break
                    except APIError as e:
                        match = re.search('insufficient balance for USD [(]requested: ([0-9]+[.][0-9]+), available: ([0-9]+[.][0-9]+)[)]', str(e))
                        if bool(match):
                            requested = float(match.group(1))
                            available = float(match.group(2))
                            order_quantity *= (available / requested)
                        elif str(e) == 'cost basis must be >= minimal amount of order 1':
                            return
            elif quantity < 0:
                order_quantity = round(abs(quantity), 4)
                order_quantity = min(order_quantity, self.current_quantities[order_symbol])
                order = self.api.submit_order(
                    symbol=order_symbol,
                    qty=order_quantity,
                    side='sell',
                    type='market',
                    time_in_force='gtc',
                )
                self.order_history.append(order)
        self.orders = {}


if __name__ == '__main__':
    operator = Operator()
    operator.initialize_api(API_KEY, API_SECRET)
    operator.get_last_order_datetime()