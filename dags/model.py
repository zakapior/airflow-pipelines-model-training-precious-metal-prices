"""
A reference machine learning model provided by the Data Scientists with some
helper functions.

The real model will be different, but the API will remain stable, so the file
should be used by the workflow as a reference.
"""
from pathlib import Path
from typing import Tuple, List, Dict
import numpy as np
import pandas as pd
from sktime.forecasting.arima import ARIMA

rng = np.random.default_rng()

AR_LOWER = 0.1
AR_UPPER = 0.6
MEAN_LOWER = 1000
MEAN_UPPER = 2000
STD = 1


def generate_integrated_autocorrelated_series(
    p: float, mean: float, std: float, length: int
) -> np.ndarray:
    """
    Generates an integrated autocorrelated time series using a specified
    autoregression parameter, mean and standard deviation of the normal
    distribution, and the desired length of the series.
    """
    x = 0
    ar1_series = np.asarray([x := p * x + rng.normal(0, 1)
                             for _ in range(length)])
    return np.cumsum(ar1_series * std) + mean


def generate_sample_data(
    cols: List[str], x_size: int, y_size: int
) -> Tuple[pd.DataFrame, pd.DataFrame, Tuple[np.ndarray, np.ndarray]]:
    """
    Generates sample training and test data for specified columns. The data
    consists of autocorrelated series, each created with randomly generated
    autoregression coefficients and means. The method also returns the
    generated autocorrelation coefficients and means for reference. 'x_size'
    determines the length of the training set, and 'y_size' determines the
    length of the test set. 'cols' determines the names of the columns.
    """
    ar_coefficients = rng.uniform(AR_LOWER, AR_UPPER, len(cols))
    means = rng.uniform(MEAN_LOWER, MEAN_UPPER, len(cols))
    full_dataset = pd.DataFrame.from_dict(
        {
            col_name: generate_integrated_autocorrelated_series(
                ar_coefficient, mean, STD, x_size + y_size
            )
            for ar_coefficient, mean, col_name in zip(ar_coefficients,
                                                      means,
                                                      cols)
        }
    )
    return (
        full_dataset.head(x_size),
        full_dataset.tail(y_size),
        (ar_coefficients, means),
    )


class Model:
    def __init__(self, tickers: List[str], x_size: int = None, y_size: int = None) -> None:
        self.tickers = tickers
        self.x_size = x_size
        self.y_size = y_size
        self.models: dict[str, ARIMA] = {}

    def train(self, /, use_generated_data: bool = False, data: Dict[str, List[float]] = None) -> None:
        if use_generated_data:
            data, _, _ = generate_sample_data(
                self.tickers, self.x_size, self.y_size
            )
        else:
            if data is None:
                raise ValueError("Data not provided")
        for ticker in self.tickers:
            dataset = data[ticker].values
            model = ARIMA(order=(1, 1, 0),
                          with_intercept=True,
                          suppress_warnings=True)
            model.fit(dataset)
            self.models[ticker] = model

    def save(self, path_to_dir: str) -> None:
        path_to_dir = Path(path_to_dir)
        path_to_dir.mkdir(parents=True, exist_ok=True)
        for ticker in self.tickers:
            full_path = path_to_dir / ticker
            self.models[ticker].save(full_path)
