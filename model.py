import sqlite3
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.api import VAR
import datetime


class Model:
    def __init__(self):
        self.prices = None
        self.features = None
        self.symbols = []
        self.model = None

    def get_data(self, prices=None, max_datetime=None):
        if prices is not None:
            self.prices = prices
            self.symbols = prices.columns.tolist()
            return
        conn = sqlite3.connect('db_crypto.db')
        query = 'SELECT * FROM crypto_bars'
        crypto_bars = pd.read_sql_query(query, conn)
        conn.close()
        prices = crypto_bars[['timestamp', 'symbol', 'close']].copy()
        prices = prices.pivot(index='timestamp', columns='symbol', values='close')
        prices.index.name = 'date'
        prices.columns.name = None
        prices = prices.loc[lambda df: ~df.index.isna(), :]
        prices.index = prices.index.map(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
        self.symbols = prices.columns.tolist()
        if max_datetime is not None:
            prices = prices.loc[lambda df: df.index <= max_datetime, :]
        self.prices = prices.fillna(method='ffill')

    def transform_data(self):
        features = self.prices.copy()
        for symbol in self.symbols:
            for n, d in [[10, 20], [10, 50], [50, 200], [100, 400], [150, 600]]:
                features[f'{symbol} MA{n}/{d}'] = self.prices[symbol].rolling(n).mean() / self.prices[symbol].rolling(d).mean() - 1
        features = features.assign(**{symbol: self.prices[symbol].pct_change() for symbol in self.symbols})
        self.features = features.dropna()

    def fit(self):
        features = self.features.reset_index(drop=True).copy()
        var_model = VAR(features)
        self.model = var_model.fit(maxlags=15, ic='aic')

    @property
    def prediction_datetime(self):
        return self.prices.index[-1] + datetime.timedelta(hours=1)

    def predict(self):
        predictions = self.model.forecast(self.features.values[-self.model.k_ar:], steps=1)
        predictions = predictions[0][:len(self.symbols)]
        return dict(zip(self.symbols, predictions))

    def calc_cov_matrix(self):
        return self.features[self.symbols].cov()


if __name__ == '__main__':
    model = Model()
    model.get_data()
    model.transform_data()
    model.fit()
    print(model.predict())
    print(model.calc_cov_matrix())
