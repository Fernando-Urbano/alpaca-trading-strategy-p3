from trades import INITIAL_ASSETS
import copy
import numpy as np
from model import Model
import random
from model import Model



class PortfolioManager:
    def __init__(self):
        self.predictions = None
        self.cov_matrix = None
        self.weights = copy.deepcopy(INITIAL_ASSETS)
        self.lambda_reg = 3

    def get_predictions(self, predictions, cov_matrix):
        self.predictions = predictions
        self.cov_matrix = cov_matrix

    def calc_tangency_weights(self, allow_short=False):
        cov_matrix_diag = np.diag(np.diag(self.cov_matrix))
        cov_matrix_reg = cov_matrix_diag + self.lambda_reg * cov_matrix_diag
        cov_matrix_inv = np.linalg.inv(cov_matrix_reg)

        ones = np.ones(self.cov_matrix.columns.shape)
        mu = list(self.predictions.values())
        scaling = 1 / (np.transpose(ones) @ cov_matrix_inv @ mu)
        tangency_weights = scaling * (cov_matrix_inv @ mu)
        if not allow_short:
            tangency_weights = np.maximum(tangency_weights, 0)
            tangency_weights /= tangency_weights.sum()
        return dict(zip(self.predictions.keys(), tangency_weights))

    def allocate(self):
        return self.calc_tangency_weights()


if __name__ == '__main__':
    portfolio_manager = PortfolioManager()
    model = Model()
    model.get_data()
    model.transform_data()
    model.fit()
    predictions = model.predict()
    cov_matrix = model.calc_cov_matrix()
    portfolio_manager.get_predictions(predictions, cov_matrix)
    weights = portfolio_manager.allocate()