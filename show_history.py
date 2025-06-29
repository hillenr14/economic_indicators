

import mysql.connector
import os
import argparse
from dotenv import load_dotenv

# Set up argument parser
parser = argparse.ArgumentParser(description="Show all table entries for a specific indicator.")
parser.add_argument("indicator", help="The name of the indicator to display.")
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

    # Execute the query to fetch data for the specified indicator
    query = "SELECT date, value, last_updated FROM economic_data WHERE indicator_name = %s ORDER BY date DESC"
    cursor.execute(query, (args.indicator,))
    results = cursor.fetchall()

    if results:
        print(f"Historical data for '{args.indicator}':")
        print(f"{'Date':<15} {'Value':<15} {'Last Updated':<20}")
        print('-'*50)
        for row in results:
            # Format the date for consistent output
            date_str = row[0].strftime('%Y-%m-%d')
            print(f"{date_str:<15} {row[1]:<15} {str(row[2]):<20}")
    else:
        print(f"No data found for indicator: '{args.indicator}'")

    # Clean up
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Database Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}")

