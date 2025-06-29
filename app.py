
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
from flask import Flask, render_template, request
from threading import Thread
import mysql.connector
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')


load_dotenv()

app = Flask(__name__)

# Database Configuration
DB_HOST = os.getenv("MYSQL_HOST")
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = os.getenv("MYSQL_DB")

# FRED API Key
FRED_API_KEY = "32d1fa37c639637c4fbf10df162df251"

# Indicators to Fetch
INDICATORS = {
    "GDP": "GDP",
    "Unemployment Rate": "UNRATE",
    "PCE (Inflation)": "PCE",
    "Federal Funds Rate": "FEDFUNDS",
    "S&P 500 Index": "SP500",
    "Trade Balance": "BOPGSTB",
    "2-Year Treasury Yield": "DGS2",
    "10-Year Treasury Yield": "DGS10",
    "20-Year Treasury Yield": "DGS20",
    "M2 Money Supply": "M2SL",
    "Corporate Profits": "CP",
    "Consumer Sentiment": "UMCSENT",
    "Initial Jobless Claims": "IC4WSA",
    "Retail Sales": "RSXFS",
    "Industrial Production": "INDPRO",
    "Housing Starts": "HOUST",
    "ISM Manufacturing PMI": "NAPM",
    "Producer Price Index": "PPIACO"
}


def get_db_connection():
  conn = mysql.connector.connect(
      host=DB_HOST,
      user=DB_USER,
      password=DB_PASSWORD
  )
  return conn


def create_database_and_tables():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
  cursor.execute(f"USE {DB_NAME}")
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS economic_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            indicator_name VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            value FLOAT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE(indicator_name, date)
        )
    """)
  conn.commit()
  cursor.close()
  conn.close()


def get_start_date(time_range):
  today = datetime.today()
  if time_range == '3m':
    return (today - timedelta(days=90)).strftime('%Y-%m-%d')
  elif time_range == '1y':
    return (today - timedelta(days=365)).strftime('%Y-%m-%d')
  elif time_range == '3y':
    return (today - timedelta(days=3 * 365)).strftime('%Y-%m-%d')
  elif time_range == '5y':
    return (today - timedelta(days=5 * 365)).strftime('%Y-%m-%d')
  elif time_range == '10y':
    return (today - timedelta(days=10 * 365)).strftime('%Y-%m-%d')
  elif time_range == '20y':
    return (today - timedelta(days=20 * 365)).strftime('%Y-%m-%d')
  else:
    return (today - timedelta(days=5 * 365)).strftime('%Y-%m-%d')


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


def refresh_data_in_background():
  def refresh():
    conn = mysql.connector.connect(
      host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor()

    start_date = (datetime.today() - timedelta(days=20 * 365)
                  ).strftime('%Y-%m-%d')

    for name, series_id in INDICATORS.items():
      if name == "S&P 500 Index":
        df = fetch_sp500_data(start_date)
      else:
        df = fetch_fred_data(series_id, start_date)

      if df is not None:
        for date, row in df.iterrows():
          cursor.execute("""
                        INSERT INTO economic_data (indicator_name, date, value)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE value = %s
                    """, (name, date.date(), row['value'], row['value']))

    conn.commit()
    cursor.close()
    conn.close()

  thread = Thread(target=refresh)
  thread.start()


def get_data_from_db(time_range):
  conn = mysql.connector.connect(
      host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
  cursor = conn.cursor()

  start_date = get_start_date(time_range)

  data_frames = {}
  for name in INDICATORS.keys():
    cursor.execute(
        "SELECT date, value FROM economic_data WHERE indicator_name = %s AND date >= %s", (name, start_date))
    data = cursor.fetchall()
    if data:
      df = pd.DataFrame(data, columns=['date', 'value'])
      df['date'] = pd.to_datetime(df['date'])
      df = df.set_index('date')
      if time_range in ['3y', '5y'] and (name == "S&P 500 Index" or "Treasury Yield" in name):
        df = df.resample('W').last()
      if time_range in ['10y', '20y'] and (name == "S&P 500 Index" or "Treasury Yield" in name):
        df = df.resample('M').last()
      data_frames[name] = df

  cursor.close()
  conn.close()
  return data_frames


def needs_refresh():
  conn = mysql.connector.connect(
    host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
    "SELECT last_updated FROM economic_data ORDER BY last_updated DESC LIMIT 1")
  last_updated = cursor.fetchone()
  cursor.close()
  conn.close()

  if not last_updated or (datetime.now() - last_updated[0]) > timedelta(weeks=1):
    return True
  return False


@app.route('/')
def index():
  create_database_and_tables()

  if needs_refresh():
    refresh_data_in_background()

  time_range = request.args.get('time_range', '5y')
  data_frames = get_data_from_db(time_range)

  if not data_frames:
    refresh_data_in_background()
    data_frames = get_data_from_db(time_range)

  if "PCE (Inflation)" in data_frames and data_frames["PCE (Inflation)"] is not None:
    df_pce = data_frames["PCE (Inflation)"].copy()
    df_pce["value"] = df_pce["value"].pct_change(periods=12) * 100
    data_frames["Inflation Rate"] = df_pce[["value"]]

  if "GDP" in data_frames and data_frames["GDP"] is not None:
    df_gdp = data_frames["GDP"].copy()
    df_gdp["value"] = df_gdp["value"].pct_change(periods=1) * 400
    data_frames["GDP Change"] = df_gdp[["value"]]

  # Combine Treasury Yields
    treasury_yields = {}
    if "2-Year Treasury Yield" in data_frames and data_frames["2-Year Treasury Yield"] is not None:
      treasury_yields["2-Year"] = data_frames["2-Year Treasury Yield"]["value"]
      del data_frames["2-Year Treasury Yield"]
    if "10-Year Treasury Yield" in data_frames and data_frames["10-Year Treasury Yield"] is not None:
      treasury_yields["10-Year"] = data_frames["10-Year Treasury Yield"]["value"]
      del data_frames["10-Year Treasury Yield"]
    if "20-Year Treasury Yield" in data_frames and data_frames["20-Year Treasury Yield"] is not None:
      treasury_yields["20-Year"] = data_frames["20-Year Treasury Yield"]["value"]
      del data_frames["20-Year Treasury Yield"]

    if treasury_yields:
      df_treasury = pd.DataFrame(treasury_yields)
      data_frames["Treasury Yields"] = df_treasury

    # Define the desired plot order
    PLOT_ORDER = [
        "GDP",
        "GDP Change",
        "PCE (Inflation)",
        "Inflation Rate",
        "S&P 500 Index",
        "Treasury Yields",
        "Unemployment Rate",
        "Initial Jobless Claims",
        "Corporate Profits",
        "Industrial Production",
        "Consumer Sentiment",
        "Retail Sales",
        "Federal Funds Rate",
        "M2 Money Supply",
        "ISM Manufacturing PMI",
        "Producer Price Index"
        "Housing Starts",
        "Trade Balance",
    ]

    # Filter and order data_frames based on PLOT_ORDER
    ordered_data_frames = []
    for indicator_name in PLOT_ORDER:
      if indicator_name in data_frames and data_frames[indicator_name] is not None:
        ordered_data_frames.append(
          (indicator_name, data_frames[indicator_name]))

    # Determine number of rows for subplots
    num_plots = len(ordered_data_frames)
    nrows = (num_plots + 1) // 2  # Calculate rows needed for 2 columns

    fig, axes = plt.subplots(nrows=nrows, ncols=2, figsize=(16, nrows * 4))
    fig.suptitle(f"Key US Economic Indicators (Last {time_range})")

    for ax, (name, df) in zip(axes.flatten(), ordered_data_frames):
      if df is not None:
        if name == "Treasury Yields":
          for col in df.columns:
            ax.plot(df.index, df[col], label=col +
                    " Treasury Yield", linewidth=1)
        else:
          ax.plot(df.index, df["value"], label=name, linewidth=1)
        ax.set_title(name)
        ax.set_ylabel("Value")
        ax.legend()
        ax.grid(True)

    # Hide any unused subplots
    for i in range(num_plots, nrows * 2):
      fig.delaxes(axes.flatten()[i])

  plt.tight_layout(rect=[0, 0, 1, 0.96])

  buf = BytesIO()
  plt.savefig(buf, format="png")
  data = base64.b64encode(buf.getbuffer()).decode("ascii")
  return render_template('index.html', plot_url=data, selected_time_range=time_range)


if __name__ == '__main__':
  app.run(debug=True)
