import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
from flask import Flask, render_template, request, Response
from threading import Thread, Event
import mysql.connector
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import base64
from io import BytesIO
import matplotlib
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

matplotlib.use('Agg')

load_dotenv()

app = Flask(__name__)

# Database Configuration
DB_HOST = os.environ.get("MYSQL_HOST")
DB_USER = os.environ.get("MYSQL_USER")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD")
DB_NAME = os.environ.get("MYSQL_DB")

# FRED API Key
FRED_API_KEY = os.environ.get("FRED_API_KEY")

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
    "Producer Price Index": "PPIACO",
    "Money Market Funds": "MMMFFAQ027S"
}

update_event = Event()


def get_db_connection():
  conn = mysql.connector.connect(
      host=DB_HOST,
      user=DB_USER,
      password=DB_PASSWORD,
      database=DB_NAME
  )
  return conn


def create_database_and_tables():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
  cursor.execute(f"USE {DB_NAME}")
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            units VARCHAR(50),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            indicator_id INT NOT NULL,
            date DATE NOT NULL,
            value FLOAT NOT NULL,
            UNIQUE(indicator_id, date),
            FOREIGN KEY (indicator_id) REFERENCES indicators(id)
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
  try:
    today = datetime.today().strftime('%Y-%m-%d')
    sp500 = yf.Ticker("^GSPC")
    df = sp500.history(start=start_date, end=today)
    if df.empty:
      print(f"No S&P 500 data found for start_date: {start_date}")
      return None
    df = df[["Close"]].rename(columns={"Close": "value"})
    df.index = pd.to_datetime(df.index)
    return df
  except Exception as e:
    print(f"Error fetching S&P 500 data: {e}")
    return None


def fetch_fred_data(series_id, start_date):
  # Fetch observations
  obs_url = f"https://api.stlouisfed.org/fred/series/observations"
  obs_params = {
      "series_id": series_id,
      "api_key": FRED_API_KEY,
      "file_type": "json",
      "observation_start": start_date
  }
  try:
    obs_response = requests.get(obs_url, params=obs_params)
    obs_response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
    obs_data = obs_response.json()
  except requests.exceptions.RequestException as e:
    print(f"Error fetching FRED observations for {series_id}: {e}")
    return None, None

  # Fetch series info for units
  series_url = f"https://api.stlouisfed.org/fred/series"
  series_params = {
      "series_id": series_id,
      "api_key": FRED_API_KEY,
      "file_type": "json"
  }
  units = None
  try:
    series_response = requests.get(series_url, params=series_params)
    series_response.raise_for_status()
    series_info = series_response.json()
    if "seriess" in series_info and len(series_info["seriess"]) > 0:
      units = series_info["seriess"][0].get("units")
  except requests.exceptions.RequestException as e:
    print(f"Error fetching FRED series info for {series_id}: {e}")
    # Continue even if units cannot be fetched

  if "observations" in obs_data:
    df = pd.DataFrame(obs_data["observations"])
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["value"] != "."]
    df["value"] = df["value"].astype(float)
    return df.set_index("date"), units
  else:
    print(f"No observations found for FRED series {series_id}")
    return None, units


def refresh_data(indicator_names=None):
  global update_event
  conn = None
  cursor = None
  logging.info("Starting refresh_data function.")
  try:
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor(dictionary=True)

    start_date = (datetime.today() - timedelta(days=20 * 365)
                  ).strftime('%Y-%m-%d')

    indicators_to_fetch = INDICATORS
    if indicator_names:
      indicators_to_fetch = {name: INDICATORS[name]
                             for name in indicator_names if name in INDICATORS}

    updated = False
    for name, series_id in indicators_to_fetch.items():
      logging.info(f"Fetching data for indicator: {name} (Series ID: {series_id})")
      df = None
      units = None
      if name == "S&P 500 Index":
        df = fetch_sp500_data(start_date)
        units = "Points"  # S&P 500 is in points
        if df is None:
          # If S&P 500 data from yfinance fails, try FRED as a fallback
          df, units = fetch_fred_data(series_id, start_date)
      else:
        df, units = fetch_fred_data(series_id, start_date)

      if df is not None:
        logging.info(f"Fetched {len(df)} entries for {name}.")
        try:
          # Insert or update indicator in the indicators table
          cursor.execute(
              "INSERT INTO indicators (name, units) VALUES (%s, %s) ON DUPLICATE KEY UPDATE units = %s, last_updated = CURRENT_TIMESTAMP",
              (name, units, units))
          conn.commit()
          logging.info(f"Indicator {name} (units: {units}) updated in 'indicators' table.")

          # Get the indicator_id
          cursor.execute("SELECT id FROM indicators WHERE name = %s", (name,))
          indicator_id = cursor.fetchone()['id']

          inserted_count = 0
          updated_count = 0
          for date, row in df.iterrows():
            try:
                cursor.execute("INSERT INTO historical_data (indicator_id, date, value) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE value = %s",
                               (indicator_id, date.date(), row['value'], row['value']))
                if cursor.rowcount == 1: # 1 for insert, 2 for update
                    inserted_count += 1
                elif cursor.rowcount == 2:
                    updated_count += 1
                updated = True
            except mysql.connector.Error as err:
                logging.error(f"Database error inserting/updating data for {name} on {date.date()}: {err}")
                conn.rollback()
                break # Stop processing this indicator if an error occurs
          conn.commit()
          logging.info(f"For {name}: Inserted {inserted_count} new entries, Updated {updated_count} existing entries in 'historical_data'.")
        except mysql.connector.Error as err:
          logging.error(f"Database error for {name}: {err}")
          conn.rollback()
        except Exception as e:
          logging.error(f"An unexpected error occurred for {name}: {e}")
          conn.rollback()
      else:
        logging.warning(f"Skipping {name} due to no data fetched.")

    if updated:
      update_event.set()
      logging.info("update_event signaled due to data changes.")

  except mysql.connector.Error as err:
    logging.error(f"Connection error: {err}")
  except Exception as e:
    logging.error(f"An unexpected error occurred during refresh_data: {e}")
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()
    logging.info("Finished refresh_data function.")


def get_data_from_db(time_range):
  conn = mysql.connector.connect(
      host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
  cursor = conn.cursor()

  start_date = get_start_date(time_range)

  data_frames = {}
  indicator_units = {}
  for name, series_id in INDICATORS.items():
    cursor.execute(
        "SELECT h.date, h.value, i.units FROM historical_data h JOIN indicators i ON h.indicator_id = i.id WHERE i.name = %s AND h.date >= %s", (name, start_date))
    data = cursor.fetchall()
    if data:
      df = pd.DataFrame(data, columns=['date', 'value', 'units'])
      units = df['units'].iloc[0]  # Get the unit from the first row
      df = df.drop(columns=['units'])
      df['date'] = pd.to_datetime(df['date'])
      df = df.set_index('date')
      if time_range in ['3y', '5y'] and (name == "S&P 500 Index" or "Treasury Yield" in name):
        df = df.resample('W').last()
      if time_range in ['10y', '20y'] and (name == "S&P 500 Index" or "Treasury Yield" in name):
        df = df.resample('ME').last()
      data_frames[name] = df
      indicator_units[name] = units

  cursor.close()
  conn.close()
  return data_frames, indicator_units


@app.route('/')
def index():
  time_range = request.args.get('time_range', '5y')
  data_frames, indicator_units = get_data_from_db(time_range)

  # Handle calculated indicators and their units
  if "PCE (Inflation)" in data_frames and data_frames["PCE (Inflation)"] is not None:
    df_pce = data_frames["PCE (Inflation)"].copy()
    df_pce["value"] = df_pce["value"].pct_change(periods=12) * 100
    data_frames["Inflation Rate"] = df_pce[["value"]]
    indicator_units["Inflation Rate"] = "Percent"

  if "GDP" in data_frames and data_frames["GDP"] is not None:
    df_gdp = data_frames["GDP"].copy()
    df_gdp["value"] = df_gdp["value"].pct_change(periods=1) * 400
    data_frames["GDP Change"] = df_gdp[["value"]]
    indicator_units["GDP Change"] = "Percent"

  # Combine Treasury Yields and assign a common unit
  treasury_yields = {}
  if "2-Year Treasury Yield" in data_frames and data_frames["2-Year Treasury Yield"] is not None:
    treasury_yields["2-Year"] = data_frames["2-Year Treasury Yield"]["value"]
    del data_frames["2-Year Treasury Yield"]
    del indicator_units["2-Year Treasury Yield"]
  if "10-Year Treasury Yield" in data_frames and data_frames["10-Year Treasury Yield"] is not None:
    treasury_yields["10-Year"] = data_frames["10-Year Treasury Yield"]["value"]
    del data_frames["10-Year Treasury Yield"]
    del indicator_units["10-Year Treasury Yield"]
  if "20-Year Treasury Yield" in data_frames and data_frames["20-Year Treasury Yield"] is not None:
    treasury_yields["20-Year"] = data_frames["20-Year Treasury Yield"]["value"]
    del data_frames["20-Year Treasury Yield"]
    del indicator_units["20-Year Treasury Yield"]

  if treasury_yields:
    df_treasury = pd.DataFrame(treasury_yields)
    data_frames["Treasury Yields"] = df_treasury
    indicator_units["Treasury Yields"] = "Percent"

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
      "Producer Price Index",
      "Housing Starts",
      "Trade Balance",
      "Money Market Funds",
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
        ax.set_ylabel("Percent")
      else:
        ax.plot(df.index, df["value"], label=name, linewidth=1)
        ax.set_ylabel(indicator_units.get(name, "Value")) # Use stored unit or default to "Value"
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


@app.route('/subscribe')
def subscribe():
  def event_stream():
    global update_event
    while True:
      update_event.wait()
      yield "data: refresh\n\n"
      update_event.clear()
  return Response(event_stream(), mimetype='text/event-stream')


def initial_db_load():
  create_database_and_tables()
  print("Performing initial data load...")
  try:
    refresh_data()
    print("Initial data load complete.")
  except Exception as e:
    print(f"Error during initial data load: {e}")


if __name__ == '__main__':
  initial_db_load()
  scheduler = BackgroundScheduler(timezone=pytz.timezone('US/Eastern'))
  scheduler.add_job(refresh_data, 'cron', hour=16)
  scheduler.start()
  app.run(debug=True, host='0.0.0.0', port=5001)
