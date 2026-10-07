import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

database_url = os.environ["DATABASE_URL"]

with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user;")
        database_name, user_name = cursor.fetchone()

print(f"Connected to database: {database_name}")
print(f"Connected as user: {user_name}")