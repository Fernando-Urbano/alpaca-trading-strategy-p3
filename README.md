# Trading Strategy Alpaca - P3

# 0. Contributing Guidelines
# 0.1. Set API Key and Secret
Using your Alpaca Account, you can set your API key and secret.

Afterwards, use the ".env" file already in this project and paste your key and secret in the file. There is no need to add quotation marks to make it be a string.

```
API_KEY=EXAMPLE987OFKEY112
API_SECRET=eXAMPle1083072ofSeCRET10910245
```

# 0.2. Possible Increments
- Change the format in which data is updated to make the trader faster.
- Try to use APIs that have lower trading cost.

# 1. Introduction
This project aims to create a trading strategy and trade paper money with it using the Alpaca API. If wanted, the strategy can also be used to trade dollars.

The trading strategy market chosen was the crypto market and the benchmark of the strategy is the Bitcoin. It's goal is to overperform Bitcoin.

The strategy uses three crypto currencies:
- Ethereum (ETH/USD)
- Uniswap (UNI/USD)
- Bitcoin (BTC/USD)

The strategy aims to trade every hour and uses hourly data from the three crypto currencies to generate predictions about the returns of the three crypto assets.

The model chosen to generate predictions about the three crypto assets is the VAR (Vector Autoregressive) model. In the model, we predict:

- returns of the three crypto currencies
- average price for a given amount of hours divided by the rolling average price for another given amount of hours:

$\frac{AVG(P_{(t-n, t)})}{AVG(P_{(t-d, t)}))} - 1$

Where $n$ and $d$ are:
- 10 with 20
- 10 with 50
- 50 with 200
- 100 with 400
- 150 with 600

The VAR model predicts values for all those, using all the variables to predict each one. Afterwards, only the prediction of the hourly returns (not the average) are used.

The expected return according to the model for BTC, ETH and UNI are than used with the covariance matrix of returns to the "portfolio management" part of the strategy, which defines optimal weights for each of the assets for the next hour. The weights of each asset are defined using mean-variance (Efficient Frontier) optimization with RIDGE. RIDGE makes the weights less disperse. If any weight is negative, it becomes zero. Afterwards, the weights are scaled to add up to 100% of the total equity available.

Finally, the "portfolio managament" send the target weights to the "operation" side of the strategy with calculates how much of each of the three assets should be sold/bought.

# 2. Market Data Retrieval
The market data retrieval is divided in two parts.
1. Retrieve data to first create model when there is not data already stored.
2. Update data to make trades.

## 2.1. Retrieve data to create model
The first part of the data retrieval is when there is no data available yet. For that, we use `data_creation.py`.

This script is designed to interact with the Alpaca Trade API to fetch cryptocurrency data and store it in a SQLite database. Below is a detailed explanation of each part of the script:

### 2.1.1. Import Statements
```python
import copy
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, APIError
from trades import INITIAL_ASSETS
import pandas as pd
import sqlite3
import datetime
from dotenv import load_dotenv
import os
```
- `copy`: Used for creating deep copies of objects.
- `alpaca_trade_api`: A library to interact with the Alpaca Trade API.
- `REST, APIError`: Classes from `alpaca_trade_api` for RESTful API interaction and error handling.
- `INITIAL_ASSETS`: A module that presumably contains initial asset configurations.
- `pandas` (as `pd`): A data manipulation library, here likely used for handling date ranges.
- `sqlite3`: A library for interacting with SQLite databases.
- `datetime`: For handling date and time objects.
- `dotenv`: To load environment variables from a `.env` file.
- `os`: To interact with the operating system, including environment variables.

### 2.1.2. Environment Setup
```python
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL, api_version='v2')
alpaca = REST(API_KEY, API_SECRET)
```
- `load_dotenv()`: Loads the environment variables from a `.env` file.
- `API_KEY`, `API_SECRET`, `BASE_URL`: Environment variables for API access.
- `api`: An instance of the `REST` class for interacting with the Alpaca API.
- `alpaca`: Another instance of the `REST` class, seemingly redundant.

### 2.1.3. Database Connection
```python
conn = sqlite3.connect('db_crypto.db')
cursor = conn.cursor()
```
- `conn`: Establishes a connection to the SQLite database `db_crypto.db`.
- `cursor`: A cursor object to execute SQL commands.

### 2.1.4. SQL Table Creation
```python
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
```
- Creates a table `crypto_bars` in the database if it does not already exist, with various fields for storing cryptocurrency data.

### 2.1.5. Add new Data to SQL Table
- The script then generates a range of start and end dates for each month from January 1, 2022, to the current date.
- It iterates over these dates, fetching cryptocurrency data from the Alpaca API for each month.
- The data is then converted to a suitable format and inserted into the `crypto_bars` table in the database.
- It prints messages to the console about the data being added or if no data is found for a specific range.

### 2.1.6. Cleanup and Close Connection
```python
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
```
- Creates a temporary table to identify the latest entries for each timestamp and symbol.
- Deletes any repeated values in the `crypto_bars` table.
- Commits the changes to the database and closes the connection.

This script effectively sets up a process to regularly fetch and store cryptocurrency data in a structured format, making it useful for analysis or tracking purposes.

## 2.2.Update data
The second part of the data retrieval is when there is already data available. For that, we use `data_update.py`.

This script defines a class `Updater` for interacting with the Alpaca Trade API and updating a SQLite database with cryptocurrency data. Here's a breakdown of its components:

### 2.2.1. Import Statements
```python
import copy
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, APIError
from trades import INITIAL_ASSETS
import pandas as pd
import sqlite3
import datetime
```
- The import statements are similar to the previous script, providing necessary libraries for database interaction, data manipulation, and API communication.

### 2.2.2. Class Definition: `Updater`
- The `Updater` class is designed to encapsulate the functionality for updating cryptocurrency data.

### 2.2.3. Method: `__init__`
```python
def __init__(self):
    self.api = None
    self.alpaca = None
    self.assets = list(INITIAL_ASSETS.keys())
```
- Initializes the `Updater` instance with `api`, `alpaca`, and `assets` attributes. `assets` is initialized with the keys from `INITIAL_ASSETS`, which are the tickers of the three assets used.

### 2.2.4. Method: `initialize_api`
```python
def initialize_api(self, api_key, api_secret, base_url='https://paper-api.alpaca.markets'):
    self.api = tradeapi.REST(api_key, api_secret, base_url=base_url, api_version='v2')
    self.alpaca = REST(api_key, api_secret)
```
- Initializes the Alpaca API connection using provided credentials

### 2.2.5. Method: `get_max_datetime`
```python
def get_max_datetime(self):
    # ... Database interaction to get the maximum timestamp
```
- Connects to the SQLite database to retrieve the maximum timestamp from the `crypto_bars` table.

### 2.2.6 Method: `update_data`
```python
def update_data(self, prior_days=1):
    # ... Updates the crypto_bars table with new data
```
- Connects to the database and fetches cryptocurrency data for a specified date range.
- Processes and inserts the data into the `crypto_bars` table.
- Creates a temporary table `latest_entries` and removes duplicate entries in `crypto_bars`.
- Returns the maximum timestamp of the newly added data.

This script modularizes the process of updating cryptocurrency data, encapsulating API interaction and database management within a class structure for better code organization and reusability.

# 3. Data Storage Strategy
The chosen database storage is the SQLite.

SQLite allows a quick and efficient way to store data. Furthermore, as mentioned in the last part, it allows us to easily convert pandas dataframes to SQL.

The datetime from the crypto are all in UTC time. Because of that, we remove the timezone information from it in the SQL table and make sure to define every other datetime using UTC timezone as well.

The data storage and update where detailed explained in part 2, where we go over `data_creation.py` and `data_update.py`.

# 4. Trading Strategy Development
The trading strategy was developed to overperform Bitcoin, due to that, it has a similar risk than Bitcoin.

If the investor has no particular directional view about Bitcoin performance, he/she should go long in BITI (ETF short 1x in Bitcoin - BTC/USD), while holding this strategy.

The strategy development can be divided into:

1. Filter asset: filter crypto currencies with enough liquidity to avoid price impact in the market.
2. Feature selection: create features to help explain the returns and generate expected returns predictions. The features that could be easily found and had reasonable level of importance when predicting returns were the moving averages. The selected moving average (better explanation in 1. Introduction) were defined based on out-of-sample performance tests.
3. Model development: create model that could predict all assets returns together. To avoid different biases of models from each asset, we define a model that is able to predict the returns from all the assets together: VAR (Vector Auto Regressive Model). With VAR we predict the hourly returns and the features hourly data as well, but only the hourly returns are used. All the features need to be predicted because the features are used to predict the hourly returns as well. In this way, we transform the `statsmodel` VAR into a VARX (Vector Auto Regressive Model with features).
4. Compare models: test the model and compare to other models. OLS Regression is also tested and compared with the VAR.
5. Manage risk: to avoid putting all the money into the asset that has the highest expected return, RIDGE for efficient frontier is used to build weights that efficiently allocate resources considering expected return and covariance matrix of the assets' returns.

The following parts give a detailed explanation about feature engineering and model.

## 4.1. Explanation of the Script: `model.py`

This script defines a class `Model` that is used for financial modeling with cryptocurrency data. The class includes methods for data retrieval, transformation, model fitting, and prediction. Here's a detailed breakdown of its components:

### 4.1.1. Import Statements
```python
import sqlite3
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.api import VAR
import datetime
```
- Imports necessary libraries for database interaction (`sqlite3`), data manipulation (`pandas`), statistical modeling (`statsmodels`), and handling dates (`datetime`).

### 4.1.2. Class Definition: `Model`
- The `Model` class encapsulates functionality for retrieving and processing cryptocurrency data, fitting a model, and making predictions.

### 4.1.3. Method: `__init__`
```python
def __init__(self):
    self.prices = None
    self.features = None
    self.symbols = []
    self.model = None
```
- Initializes the `Model` instance with attributes for storing prices, features, symbols, and the model itself.

### 4.1.4. Method: `get_data`
```python
def get_data(self, prices=None, max_datetime=None):
    # ... Retrieves and processes cryptocurrency data
```
- Retrieves data from a SQLite database or accepts pre-loaded `prices` data.
- Transforms the data into a pivot table format for analysis.
- Filters data based on `max_datetime` if provided.
- Handles missing data with forward filling.

### 4.1.5. Method: `transform_data`
```python
def transform_data(self):
    # ... Transforms the data for modeling
```
- Creates new features based on moving averages and percentage changes for each cryptocurrency symbol.

### 4.1.6. Method: `fit`
```python
def fit(self):
    # ... Fits a VAR model to the transformed data
```
- Resets the index of the feature DataFrame and fits a Vector Autoregression (VAR) model to the data.

### 4.1.7. Property: `prediction_datetime`
```python
@property
def prediction_datetime(self):
    return self.prices.index[-1] + datetime.timedelta(hours=1)
```
- Calculates the datetime for the next prediction based on the last known data point.

### 4.1.8. Method: `predict`
```python
def predict(self):
    # ... Makes predictions using the fitted model
```
- Uses the fitted model to forecast the next data point and returns predictions for each symbol.

### 4.1.9. Method: `calc_cov_matrix`
```python
def calc_cov_matrix(self):
    return self.features[self.symbols].cov()
```
- Calculates the covariance matrix of the features for the symbols.

### 4.1.10. Main Execution
- If the script is run as the main program, it creates an instance of `Model`, retrieves data, transforms it, fits the model, and then prints predictions and the covariance matrix.

This script is a comprehensive tool for financial analysis of cryptocurrency data, leveraging statistical modeling techniques to make predictions and assess risk.


## 4.2. Explanation of the Script: `portfolio_management.py`

This script defines a class `PortfolioManager` for managing a financial portfolio based on predictions from a financial model. The class includes methods for setting predictions, calculating tangency portfolio weights, and allocating assets. Here's a detailed breakdown of its components:

## 4.2.1. Import Statements
```python
from trades import INITIAL_ASSETS
import copy
import numpy as np
from model import Model
import random
```
- Imports necessary libraries and modules for data manipulation (`numpy`, `copy`), and includes the `Model` class from the `model` module for financial modeling. `INITIAL_ASSETS` is imported from `trades`, likely providing initial asset configurations.

### 4.2.2. Class Definition: `PortfolioManager`
- The `PortfolioManager` class encapsulates functionality for managing a portfolio based on model predictions.

### 4.2.3. Method: `__init__`
```python
def __init__(self):
    self.predictions = None
    self.cov_matrix = None
    self.weights = copy.deepcopy(INITIAL_ASSETS)
    self.lambda_reg = 3
```
- Initializes the `PortfolioManager` instance with attributes for storing predictions, covariance matrix, asset weights, and a regularization parameter `lambda_reg`.

### 4.2.4. Method: `get_predictions`
```python
def get_predictions(self, predictions, cov_matrix):
    self.predictions = predictions
    self.cov_matrix = cov_matrix
```
- Sets the predictions and covariance matrix based on input from an external model.

### 4.2.5. Method: `calc_tangency_weights`
```python
def calc_tangency_weights(self, allow_short=False):
    # ... Calculates tangency portfolio weights
```
- Calculates the weights for a tangency portfolio based on predictions and covariance matrix.
- Allows control over short selling through the `allow_short` parameter.

### 4.2.6. Method: `allocate`
```python
def allocate(self):
    return self.calc_tangency_weights()
```
- Allocates assets based on the calculated tangency portfolio weights.

### 4.2.7. Main Execution
- If the script is run as the main program, it creates instances of `PortfolioManager` and `Model`, retrieves data, transforms it, fits the model, and then uses the model's predictions and covariance matrix to allocate the portfolio.

This script is a practical tool for portfolio management in financial markets, using model-based predictions and portfolio optimization techniques.

# 5. Testing and Optimization
The testing of the strategy was majorly done in the definition of model and features and the definition of the best model was done based on the out-of-sample performance.

The models tested were:
- SVM (Support Vector Machine)
- OLS Regression
- VARX (Vector Auto Regressive with exogenous features)

The definition of features was done based on which rolling average returns provided the best results.

The measure to determine out-of-sample performance was the MAE. For each of the assets $a$, the MAE was calculated:

$MAE_{a} = \sum_{t=1}^{n}(\hat{r}_{a, t}-r_{a, t})$

Afterwards, the MAE of the assets were summed to determine the composed MAE.

# 6. Automation and Scheduling
The automation and scheduling is done by the `Operator` class, which is in `operate.py` file. The `Operator` is later used inside of the `main.py`, which is able to manage all the resources.

## 6.1. Explanation of the Script: `operator.py`
This script defines a class `Operator` intended for use with the Alpaca Trade API. It is designed to automate the management of a trading portfolio, including the retrieval of market data, execution of trades based on predefined strategies, and handling of various operational scenarios. The class incorporates several methods to facilitate these tasks, ensuring robustness and efficiency in trading operations.

- `Operator` is a comprehensive class that encapsulates various functionalities required for automated trading. It maintains the state of the portfolio, interacts with the trading API, and executes trading strategies.

### 6.1.2. Key Methods and Their Roles
1. **Initialization (`__init__`)**: Sets up the initial state of the portfolio, including current positions, prices, and quantities. It also initializes API connections and financial metrics like cash, equity, and margin.

2. **API Initialization (`initialize_api`)**: Establishes the connection with the Alpaca Trade API using provided API credentials. This method is crucial for enabling subsequent trading operations.

3. **Bad Request Management (`update_bad_requests`)**: Maintains a log of timestamps when bad API requests occur. It implements a fail-safe mechanism to close all positions and halt operations if excessive bad requests are detected within a short timeframe, enhancing operational safety.

4. **Position Management (`close_positions`, `cancel_open_orders`)**: These methods are essential for risk management, allowing the script to exit positions rapidly and cancel pending orders in response to specific conditions or errors.

5. **Order History Tracking (`get_last_order_datetime`)**: Retrieves the timestamp of the last executed order, which is instrumental in scheduling subsequent trading operations and ensuring that the trading strategy aligns with the latest market conditions.

6. **Equity and Position Updates (`update_equity`, `update_current_positions`)**: Regularly updates the portfolio's equity and the current market positions. These methods are fundamental to maintaining an accurate view of the portfolio's state and making informed trading decisions.

7. **Target Position Setting (`update_target_positions`)**: Allows for the dynamic adjustment of target portfolio weights based on the chosen trading strategy or market analysis.

8. **Price Updates (`update_prices`)**: Regularly fetches the latest market prices for assets in the portfolio, ensuring that trading decisions are based on up-to-date information.

9. **Order Definition and Execution (`define_orders`, `place_orders`)**: These methods calculate the necessary trades to align the portfolio with the target weights and execute these trades through the API. They are core to the script's trading functionality.

### 6.1.4. Script Execution Flow
- When run as the main program, the script initializes the `Operator`, establishes API connections, and performs a series of steps to manage the trading portfolio. This includes updating positions, fetching current market prices, defining and executing trades, and handling any operational exceptions.

### 6.1.5. Automation and Scheduling Requirements
1. **Automated Data Retrieval**: The script automates the retrieval of market data and portfolio states through its various methods, ensuring that all trading decisions are based on the latest available information.

2. **Scheduled Task Execution**: The script can be integrated with scheduling tools like cron jobs to execute trading operations at predetermined intervals or based on specific market events.

3. **Error Handling and Exception Management**: Robust error handling is implemented to manage API errors, bad requests, and operational anomalies. This includes mechanisms to close positions and cancel orders in case of critical failures, ensuring the safety and integrity of the trading operations.

4. **Logging and Monitoring**: While not explicitly detailed in the script, incorporating logging mechanisms is crucial for tracking the script's operations, decisions, and performance. This would provide valuable insights into the trading strategy's effectiveness and identify areas for improvement.

5. **Version Control and Script Maintenance**: Utilizing version control tools like Git is essential for maintaining the script, tracking changes, and facilitating collaborative development and debugging.

### 6.1.6 Conclusion
This script represents a comprehensive solution for automated trading, with robust functionalities for market data retrieval, trade execution, risk management, and operational control. It is adaptable to various trading strategies and market conditions, making it a valuable tool for traders and portfolio managers.

## 6.2. Explanation of the Script: `operator.py`

### 6.2.1. Overview
This main script serves as the central orchestrator for an automated trading system, integrating functionalities from the `Updater`, `Model`, `PortfolioManager`, and `Operator` modules. It continuously updates market data, generates predictions, manages a portfolio, and executes trades.

### 6.2.2. Import Statements
```python
import copy
import os
from operate import Operator
from dotenv import load_dotenv
import datetime
from data_update import Updater
from time import sleep
from model import Model
from portfolio_management import PortfolioManager
```
- Imports necessary modules and classes. `copy` and `os` for basic Python operations, `dotenv` for environment variable management, `datetime` and `time` for date and time handling, and custom classes for different aspects of the trading system.

### 6.2.3. Environment Setup
```python
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
```
- Loads environment variables, including API credentials, essential for connecting to the Alpaca Trade API.

### 6.2.4. Main Execution Flow (`if __name__ == '__main__':`)
1. **Object Creation**:
    ```python
    updater = Updater()
    model = Model()
    portfolio_manager = PortfolioManager()
    operator = Operator()
    ```
    - Instantiates the `Updater` for data updates, `Model` for prediction, `PortfolioManager` for portfolio management, and `Operator` for trading operations.

2. **API Initialization**:
    ```python
    updater.initialize_api(API_KEY, API_SECRET)
    operator.initialize_api(API_KEY, API_SECRET)
    ```
    - Initializes API connections for both data updating and trading operations.

3. **Order Management**:
    ```python
    operator.cancel_open_orders()
    operator.api.list_orders(status='all', limit=1)
    ```
    - Cancels any open orders to ensure a fresh start. Then checks for the list of all orders, possibly for logging or verification.

4. **Continuous Operation Loop**:
    ```python
    while True:
    ```
    - Enters an infinite loop, signifying continuous operation of the trading system.

    a. **Update Current Positions**:
        ```python
        operator.update_current_positions()
        print("
" * 2)
        print(operator)
        ```
        - Updates and prints the current positions in the portfolio.

    b. **Data Update Check**:
        ```python
        max_datetime = updater.get_max_datetime()
        update_max_datetime = copy.deepcopy(max_datetime)
        while True:
            update_max_datetime = updater.update_data()
            ...
        ```
        - Checks if new data is available. Continuously updates data until the most recent data is obtained or an update is necessary.

    c. **Prediction and Portfolio Management**:
        - Conditionally checks if it's time to make a prediction based on the latest data.
        - Utilizes the `Model` to process data, generate predictions, and calculate the covariance matrix.
        - Employs the `PortfolioManager` to determine target weights based on predictions.
        - Updates asset prices and current positions, then defines and executes new trade orders based on target weights.
        - The loop then repeats, continually managing the portfolio based on updated data and market conditions.

5. **Wait State**:
    - In case new data is not yet available for prediction, the script enters a wait state, periodically checking for data availability.

### 6.2.5. Conclusion
This script meticulously orchestrates the entire trading operation, leveraging the capabilities of the individual modules. It automates data retrieval, prediction generation, portfolio management, and trade execution, making it an effective tool for algorithmic trading.

# 7. Testing and Optimization
The testing and graphics of the model can be viewed in the `model_development.py`. There we show the construction of the strategy, map graphics of cummulative returns of the strategy and the assets and develop a backtest of the strategy.

Overall, we see that:
- the strategy, without trading cost, underperforms BTC/USD if considering the whole backtest sample (2023) and overperforms the UNI/USD and ETH/USD.
- the strategy has better Sharpe and returns in the second part o the year (since the beginning of June).

For more graphics and better understand of the code, check `model_development.py`.

## 7.1. Performance of the Long-Short Portfolio between June and November 2023
| Metric    | Portfolio - BTC/USD | Portfolio - ETH/USD | Portfolio - UNI/USD |
|-----------|---------------------|---------------------|---------------------|
| Mean      | 0.00004%            | 0.000071%           | 0.000035%           |
| Std       | 0.2688%             | 0.2439%             | 0.4529%             |
| Mean/Vol  | 0.1375%             | 2.9317%             | 0.7790%             |
| Min       | -1.8446%            | -2.7509%            | -5.1100%            |
| Max       | 4.5366%             | 4.1731%             | 9.0381%             |
| Skew      | 2.434037            | 1.801426            | 1.518455            |
| Kurtosis  | 37.473948           | 42.678689           | 50.706519           |

## 7.2. Performance of the Long-Short Portfolio between January and November 2023
| Metric    | Portfolio - BTC/USD | Portfolio - ETH/USD | Portfolio - UNI/USD |
|-----------|---------------------|---------------------|---------------------|
| Mean      | -0.00007%           | 0.0039%             | 0.0077%             |
| Std       | 0.2757%             | 0.2483%             | 0.4939%             |
| Mean/Vol  | -0.2437%            | 1.5583%             | 1.5631%             |
| Min       | -5.5720%            | -4.6636%            | -16.6254%           |
| Max       | 4.5366%             | 4.1731%             | 14.1928%            |
| Skew      | 0.036425            | -0.626036           | -1.957791           |
| Kurtosis  | 56.702591           | 62.151323           | 291.956289          |

## 7.3. Long Only Portfolio between June and November 2023
| Metric    | Portfolio Return | BTC/USD   | ETH/USD   | UNI/USD   |
|-----------|------------------|-----------|-----------|-----------|
| Mean      | 0.0104%          | 0.0100%   | 0.0032%   | 0.0069%   |
| Std       | 0.4735%          | 0.4043%   | 0.4340%   | 0.7542%   |
| Mean/Vol  | 2.1919%          | 2.4760%   | 0.7442%   | 0.9084%   |
| Min       | -5.8525%         | -4.2443%  | -5.7937%  | -12.7802% |
| Max       | 5.4737%          | 5.6273%   | 4.9589%   | 5.5185%   |
| Skew      | 0.018719         | 0.875961  | -0.098094 | -1.336817 |
| Kurtosis  | 20.835120        | 30.221639 | 28.955977 | 28.732899 |


# 8. Compliance and Legal Considerations 
## 8.1. Transparency and Reporting
In my approach, I've emphasized the importance of transparency and reporting, which is a key compliance requirement. Through scripts like the Operator, I maintain detailed logs of all trading activities. This logging is not only a best practice for algorithmic trading but also aligns with regulatory expectations for transparency.

## 8.2.
Adherence to Market Conduct Rules
My strategy is designed to respect market conduct rules. By programming my algorithms to generate genuine orders intended for execution, and not for manipulative practices like quote stuffing or spoofing, I adhere to these crucial standards. The logic in my scripts ensures that every trade decision and order is legitimate and in line with fair market practices.

## 8.3. Risk Management
Risk management is a cornerstone of my strategy. Through the integration of the Model, PortfolioManager, and Operator, I've established a robust framework to manage and mitigate risks. This includes mechanisms for cancelling open orders and managing positions dynamically, which are essential in fast-paced trading environments. Such controls are not only prudent for risk management but also necessary to meet regulatory standards in algorithmic trading.

## 8.4. Algorithm Auditability
Given the automated nature of my trading system, it's important to have mechanisms for auditing and reviewing algorithmic decisions. This aligns with regulatory expectations for algorithmic traders to be able to explain their trading decisions if required. My scripts are structured to allow for such auditability and review.

## 8.5. Data Protection and Privacy
In handling financial data, I ensure strict adherence to data protection laws, such as GDPR for European clients. My system safeguards client data, maintaining the confidentiality and integrity of all transactions. This is not only a legal obligation but also a commitment to my clients' privacy and trust. An example of that is not writing the API Key and Secret in the scripts.

# 9. Results and Lessons Learned
Reflecting on the results of my project, which involved creating a comprehensive automated trading system, I've gained valuable insights and encountered several challenges along the way. Here's an overview of my experience, the lessons I've learned, and thoughts on potential improvements for future iterations:

## 9.1. Results and Performance
The integration of various components like Updater, Model, PortfolioManager, and Operator resulted in a multifaceted trading system. This system has shown promising results in automating trade decision processes and managing a portfolio efficiently. The ability to update market data, analyze trends, make predictions, and execute trades in a cohesive manner is a significant achievement.

## 9.2. Challenges Encountered
### 9.2.1. Complexity in Integration
One of the main challenges was ensuring seamless integration between different components. Each module, while effective on its own, needed to be precisely synchronized with others, which required extensive testing and debugging.

### 9.2.2. Data Accuracy and Timeliness
Ensuring the accuracy and timeliness of data in the Updater module was crucial for the effectiveness of the entire system. Any discrepancies in data could lead to misguided predictions and poor trading decisions.

### 9.2.3. Algorithm Efficiency
Developing and fine-tuning the algorithms in the Model component to make accurate predictions was challenging. Balancing between overfitting and underfitting the model required careful consideration and iterative testing.

## 9.3. Lessons Learned
### 9.3.1. Importance of Robust Testing:
Rigorous testing is vital. Simulating various market conditions and testing how different components react and interact was instrumental in refining the system.

### 9.3.2. Adaptability is Key
The importance of adaptability became clear, especially in a domain as dynamic as financial markets. The ability to quickly adjust strategies and algorithms in response to market changes is crucial.

### 9.3.3. Risk Management
I learned the importance of having robust risk management protocols. The development of the PortfolioManager and Operator modules highlighted the need for measures to mitigate risks associated with automated trading.

## 9.4. Potential Improvements
### 9.4.1. Enhanced Data Analysis
Improving the data analysis capabilities of the Updater and Model components could enhance prediction accuracy. Incorporating more diverse data sources and advanced analytical techniques might yield better insights.

### 9.4.2. Algorithm Optimization
There's room for further optimization of the trading algorithms in the Model. Exploring different algorithmic approaches and machine learning techniques could improve the system's performance.

### 9.4.3. User Interface Development
Developing a user-friendly interface would make the system more accessible, allowing for easier monitoring and adjustments of the trading strategies.

### 9.4.4. Scalability and Flexibility
Ensuring the system is scalable to handle larger datasets and flexible enough to adapt to different trading instruments would be beneficial for future iterations.

### 9.5. Conclusion
Overall, this project has been a profound learning experience, offering valuable insights into the complexities of algorithmic trading. The challenges encountered have paved the way for significant improvements, and the lessons learned will be instrumental in enhancing future versions of my trading systems.


