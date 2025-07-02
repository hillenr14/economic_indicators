import mysql.connector
import os
import argparse
from dotenv import load_dotenv

# Set up argument parser
parser = argparse.ArgumentParser(description="Clear entries from the economic_data table.")
parser.add_argument("--indicator", help="The name of the indicator to delete.")
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

    if args.indicator:
        # Get the indicator_id
        cursor.execute("SELECT id FROM indicators WHERE name = %s", (args.indicator,))
        indicator_id = cursor.fetchone()

        if indicator_id:
            indicator_id = indicator_id[0]
            # Delete entries for a specific indicator from historical_data
            cursor.execute("DELETE FROM historical_data WHERE indicator_id = %s", (indicator_id,))
            # Delete the indicator from the indicators table
            cursor.execute("DELETE FROM indicators WHERE id = %s", (indicator_id,))
            conn.commit()
            print(f"All entries for indicator '{args.indicator}' have been deleted.")
        else:
            print(f"Indicator '{args.indicator}' not found.")
    else:
        # Truncate both tables (order matters due to foreign key constraint)
        cursor.execute("TRUNCATE TABLE historical_data")
        cursor.execute("TRUNCATE TABLE indicators")
        conn.commit()
        print("Tables 'historical_data' and 'indicators' have been successfully emptied.")

    # Clean up
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Database Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}")
