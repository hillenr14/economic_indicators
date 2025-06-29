import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get('MYSQL_HOST')
DB_USER = os.environ.get('MYSQL_USER')
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD')
DB_NAME = os.environ.get('MYSQL_DB')

try:
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor()
    cursor.execute('SELECT indicator_name, COUNT(*), MAX(last_updated) FROM economic_data GROUP BY indicator_name')
    results = cursor.fetchall()

    print(f"{'Indicator':<30} {'Entries':<10} {'Last Update Date':<20}")
    print('-'*60)
    for row in results:
        print(f"{row[0]:<30} {row[1]:<10} {str(row[2]):<20}")

    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}")
