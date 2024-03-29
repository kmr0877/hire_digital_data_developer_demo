from pathlib import Path

import numpy as np
import pandas as pd

from matplotlib import pyplot as plt
from shiny import App, render, ui
from sklearn.metrics import (mean_absolute_error,
                             mean_absolute_percentage_error,
                             mean_squared_error)
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.holtwinters import (ExponentialSmoothing,
                                         SimpleExpSmoothing)
from statsmodels.tsa.seasonal import seasonal_decompose


app_ui = ui.page_fluid(
    ui.input_file("input_file", "Choose a file to upload:", multiple=False),
    ui.h3("Mean Absolute Error:"),
    ui.output_text_verbatim("mae"),
    ui.h3("Mean Absolute Percentage Error:"),
    ui.output_text_verbatim("mape"),
    ui.h3("Root Mean Square Error:"),
    ui.output_text_verbatim("rmse"),
    ui.output_plot("plot"),
    ui.output_plot("seasonal_decompose_plot"),
    ui.output_plot("holt_winters_seasonal_plot"),
    ui.output_plot("forecast_plot"),

)

def server(input, output, session):
    MAX_SIZE = 2000000

    @output
    @render.plot()
    def plot():
        # Variables
        m = 12
        alpha = 1/(2*m)

        # Assuming train test split of 80 and 20
        # TODO: Add sliding window cross validation
        train_test_split_ratio = 0.8

        # Read file inputs
        file_inputs = input.input_file()

        if file_inputs:
            # Assuming we allow only one file to upload
            infile = file_inputs[0]['datapath']
        else:
            # If no file is uploaded, we default to local file on server
            infile = Path(__file__).parent/"Data.xlsx"

        product_sales_info = pd.read_excel(
            infile, index_col='PO Date', parse_dates=True
        )
        product_sales_info.sort_index(inplace=True)

        # Removing NaNs
        product_sales_info_without_nulls = \
            product_sales_info[product_sales_info['Sales Amt'].notna()]


        df_product_sales_info = pd.DataFrame(
            product_sales_info_without_nulls[['Year', 'Month', 'Sales Amt']])
        df_product_sales_info[['Year', 'Month', 'Sales Amt']] = \
            df_product_sales_info[['Year', 'Month', 'Sales Amt']].astype(int)

        df_product_sales_info['PO Date'] = df_product_sales_info['Year'] \
            .astype(str) + '-' + df_product_sales_info['Month'].astype(str)

        df_product_sales_info.index = pd.to_datetime(
            df_product_sales_info['PO Date']
        )
        resampled_df = df_product_sales_info.resample('M').sum()

        holt_winters_df = resampled_df[['Sales Amt']]

        # Plot sales data by month
        sales_data_plot = holt_winters_df.plot(title='Sales by Month')

        @output
        @render.plot()
        def seasonal_decompose_plot():
            # Seasonal decomposition
            seasonal_decompose_result = seasonal_decompose(
                holt_winters_df['Sales Amt'], model='multiplicative', period=12)
            seasonal_decompose_plot = seasonal_decompose_result.plot()
            return seasonal_decompose_plot

        # Set index frequency to month
        holt_winters_df.index.freq = 'M'

        @output
        @render.plot()
        def holt_winters_seasonal_plot():
            holt_winters_df['HWES_ADD_SEASONAL'] = \
                ExponentialSmoothing(
                    holt_winters_df['Sales Amt'],
                    trend='add',seasonal='add',
                    seasonal_periods=12
                ).fit().fittedvalues
            holt_winters_df['HWES_MUL_SEASONAL'] = \
                ExponentialSmoothing(
                    holt_winters_df['Sales Amt'],
                    trend='mul',
                    seasonal='mul',
                    seasonal_periods=12
                ).fit().fittedvalues
            holt_winters_seasonal_plot = \
                holt_winters_df[
                    ['Sales Amt','HWES_ADD_SEASONAL','HWES_MUL_SEASONAL']
                ].plot(
                    title='Holt Winters Exponential Smoothing: Additive and Multiplicative Seasonality'
                )

            return holt_winters_seasonal_plot

        # Get training data size based on available dataset and take recent
        # 20% data for testing and remainder for training
        train_size = round(len(resampled_df) * train_test_split_ratio)

        resampled_df = resampled_df[['Sales Amt']]
        df_train = resampled_df[:train_size]
        df_test = resampled_df[train_size:]

        # Fit model
        fitted_model = ExponentialSmoothing(
            resampled_df['Sales Amt'],
            trend='mul',
            seasonal='mul',
            seasonal_periods=12
        ).fit()

        # Forecast for next 24 months
        forecast = fitted_model.forecast(24)

        # Run model against test data set to compare actual values
        # against predicted values and see how the model performs
        predictions_on_test_data = fitted_model.predict(
            start=df_test.index[0], end=df_test.index[-1]
        )

        @output
        @render.plot()
        def forecast_plot():
            forecast_plot = forecast.plot(legend=True,label='forecast')
            return forecast_plot

        @output
        @render.text
        def mae():
            return f'{mean_absolute_error(df_test,predictions_on_test_data)}'

        @output
        @render.text
        def rmse():
            rmse = lambda act, pred: np.sqrt(mean_squared_error(act, pred))
            return f'{rmse(df_test, predictions_on_test_data)}'

        @output
        @render.text
        def mape():
            return f'{mean_absolute_percentage_error(df_test, predictions_on_test_data)}'


        return sales_data_plot


app = App(app_ui, server, debug=True)
