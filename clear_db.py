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
        # Delete entries for a specific indicator
        query = "DELETE FROM economic_data WHERE indicator_name = %s"
        cursor.execute(query, (args.indicator,))
        conn.commit()
        print(f"All entries for indicator '{args.indicator}' have been deleted.")
    else:
        # Truncate the entire table
        cursor.execute("TRUNCATE TABLE economic_data")
        conn.commit()
        print("Table 'economic_data' has been successfully emptied.")

    # Clean up
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Database Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}")
