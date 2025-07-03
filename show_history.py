

import mysql.connector
import os
import argparse
from dotenv import load_dotenv

# Set up argument parser
parser = argparse.ArgumentParser(description="Show all table entries for a specific indicator.")
parser.add_argument("indicator", help="The name of the indicator to display.")
parser.add_argument("--first", type=int, help="Show only the first X entries.")
args = parser.parse_args()

# Load environment variables
load_dotenv()

DB_HOST = os.environ.get('MYSQL_HOST')
DB_USER = os.environ.get('MYSQL_USER')
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD')
DB_NAME = os.environ.get('MYSQL_DB')

try:
    # Establish database connection
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor()

    # Get the indicator_id, units, and last_updated from the indicators table
    cursor.execute("SELECT id, units, last_updated FROM indicators WHERE name = %s", (args.indicator,))
    indicator_info = cursor.fetchone()

    if not indicator_info:
        print(f"No indicator found with name: '{args.indicator}'")
        cursor.close()
        conn.close()
        exit()

    indicator_id = indicator_info[0]
    indicator_units = indicator_info[1]
    indicator_last_updated = indicator_info[2]

    # Execute the query to fetch data for the specific indicator from historical_data
    query = "SELECT date, value FROM historical_data WHERE indicator_id = %s ORDER BY date DESC"
    if args.first:
        query += f" LIMIT {args.first}"
    cursor.execute(query, (indicator_id,))
    results = cursor.fetchall()

    if results:
        print(f"Historical data for '{args.indicator}' (Units: {indicator_units if indicator_units else 'N/A'}, Last Updated: {indicator_last_updated if indicator_last_updated else 'N/A'}):")
        print(f"{'Date':<15} {'Value':<15}")
        print('-'*30)
        for row in results:
            # Format the date for consistent output
            date_str = row[0].strftime('%Y-%m-%d')
            print(f"{date_str:<15} {row[1]:<15}")
    else:
        print(f"No historical data found for indicator: '{args.indicator}'")

    # Clean up
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Database Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}")

