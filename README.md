# Economic Indicators Dashboard

This project is a Flask web application that displays key US economic indicators. It fetches data from the FRED API and Yahoo Finance, and then plots the data using Matplotlib.

## Features

*   Visualizes the following economic indicators:
    *   GDP
    *   Unemployment Rate
    *   CPI (Inflation)
    *   PCE (Inflation)
    *   Federal Funds Rate
    *   S&P 500 Index
    *   Trade Balance
    *   10-Year Treasury Yield
    *   M2 Money Supply
    *   Corporate Profits
    *   Consumer Sentiment
*   Allows users to select different time ranges for the data (3 months, 1 year, 3 years, 5 years, 10 years, and 20 years).
*   The data is displayed as a series of plots on a single dashboard.

## Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/hillenr14/economic_indicators.git
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python app.py
    ```
4.  Open your browser and navigate to `http://127.0.0.1:5000/`.

