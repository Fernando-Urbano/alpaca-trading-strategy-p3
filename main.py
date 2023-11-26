import copy
import os
from operate import Operator
from dotenv import load_dotenv
import datetime
from data_update import Updater
from time import sleep
from model import Model
from portfolio_management import PortfolioManager

load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

if __name__ == '__main__':
    # Create objects
    updater = Updater()
    model = Model()
    portfolio_manager = PortfolioManager()
    operator = Operator()
    # Initialize API
    updater.initialize_api(API_KEY, API_SECRET)
    operator.initialize_api(API_KEY, API_SECRET)
    # Cancel open orders
    operator.cancel_open_orders()
    operator.api.list_orders(status='all', limit=1)
    update_position = operator.get_last_order_datetime() < datetime.datetime.utcnow() - datetime.timedelta(hours=2) if operator.get_last_order_datetime() else True
    while True:
        operator.update_current_positions()
        print("\n" * 2)
        print(operator)
        max_datetime = updater.get_max_datetime()
        update_max_datetime = copy.deepcopy(max_datetime)
        while True:
            update_max_datetime = updater.update_data()
            if update_max_datetime > max_datetime or update_position:
                update_position = False
                break
            sleep(60)
        model.get_data()
        if model.prediction_datetime > datetime.datetime.utcnow():
            model.transform_data()
            model.fit()
            model.predict()
            predictions = model.predict()
            cov_matrix = model.calc_cov_matrix()
            portfolio_manager.get_predictions(predictions, cov_matrix)
            target_weights = portfolio_manager.allocate()
            operator.update_prices()
            operator.cancel_open_orders()
            operator.update_current_positions()
            print(operator)
            print("\n" * 2)
            operator.update_target_positions(target_weights)
            operator.define_orders()
            operator.place_orders()
            operator.update_current_positions()
        else:
            operator.update_current_positions()
            print(operator)
            print("\n" * 2)
            print('Waiting for data to make prediction...')
            sleep(60)


