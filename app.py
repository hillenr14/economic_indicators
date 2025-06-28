
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
from datetime import datetime, timedelta

from flask import Flask, render_template, request
import requests
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

app = Flask(__name__)

# FRED API Key
FRED_API_KEY = "32d1fa37c639637c4fbf10df162df251"

# Indicators to Fetch
INDICATORS = {
    "GDP": "GDP",
    "Unemployment Rate": "UNRATE",
    "CPI (Inflation)": "CPIAUCSL",
    "PCE (Inflation)": "PCE",
    "Federal Funds Rate": "FEDFUNDS",
    "S&P 500 Index": "SP500",
    "Trade Balance": "BOPGSTB",
    "10-Year Treasury Yield": "DGS10",
    "M2 Money Supply": "M2SL",
    "Corporate Profits": "CP",
    "Consumer Sentiment": "UMCSENT"
}

def get_start_date(time_range):
    today = datetime.today()
    if time_range == '3m':
        return (today - timedelta(days=90)).strftime('%Y-%m-%d')
    elif time_range == '1y':
        return (today - timedelta(days=365)).strftime('%Y-%m-%d')
    elif time_range == '3y':
        return (today - timedelta(days=3*365)).strftime('%Y-%m-%d')
    elif time_range == '5y':
        return (today - timedelta(days=5*365)).strftime('%Y-%m-%d')
    elif time_range == '10y':
        return (today - timedelta(days=10*365)).strftime('%Y-%m-%d')
    elif time_range == '20y':
        return (today - timedelta(days=20*365)).strftime('%Y-%m-%d')
    else:
        return (today - timedelta(days=5*365)).strftime('%Y-%m-%d')

def fetch_sp500_data(start_date):
    sp500 = yf.Ticker("^GSPC")
    df = sp500.history(start=start_date)
    df = df[["Close"]].rename(columns={"Close": "value"})
    df.index = pd.to_datetime(df.index)
    return df

def fetch_fred_data(series_id, start_date):
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date
    }
    response = requests.get(url, params=params)
    data = response.json()
    
    if "observations" in data:
        df = pd.DataFrame(data["observations"])
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["value"] != "."]
        df["value"] = df["value"].astype(float)
        return df.set_index("date")
    else:
        return None

@app.route('/')
def index():
    time_range = request.args.get('time_range', '5y')
    start_date = get_start_date(time_range)

    data_frames = {name: fetch_fred_data(series_id, start_date) for name, series_id in INDICATORS.items()}
    data_frames["S&P 500 Index"] = fetch_sp500_data(start_date)

    if data_frames["CPI (Inflation)"] is not None:
        df_cpi = data_frames["CPI (Inflation)"].copy()
        df_cpi["value"] = df_cpi["value"].pct_change(periods=12) * 100
        data_frames["Inflation Rate"] = df_cpi[["value"]]

    fig, axes = plt.subplots(nrows=6, ncols=2, figsize=(16, 20))
    fig.suptitle(f"Key US Economic Indicators (Last {time_range})")

    for ax, (name, df) in zip(axes.flatten(), data_frames.items()):
        if df is not None:
            ax.plot(df.index, df["value"], label=name, linewidth=2)
            ax.set_title(name)
            ax.set_ylabel("Value")
            ax.legend()
            ax.grid(True)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    buf = BytesIO()
    plt.savefig(buf, format="png")
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    return render_template('index.html', plot_url=data, selected_time_range=time_range)

if __name__ == '__main__':
    app.run(debug=True)
