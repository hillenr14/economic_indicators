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
  cursor.execute('SELECT i.name, i.units, COUNT(h.id), i.last_updated FROM indicators i LEFT JOIN historical_data h ON i.id = h.indicator_id GROUP BY i.id, i.name, i.units, i.last_updated')
  results = cursor.fetchall()

  print(f"{'Indicator':<30} {'Units':<30} {'Entries':<10} {'Last Update Date':<20}")
  print('-' * 90)
  for row in results:
    print(f"{row[0]:<30} {row[1] if row[1] is not None else '':<30} {row[2]:<10} {str(row[3]) if row[3] is not None else 'N/A':<20}")

  cursor.close()
  conn.close()

except mysql.connector.Error as err:
  print(f"Error: {err}")
except Exception as e:
  print(f"An error occurred: {e}")
