import os
import sys

import psycopg2

DATABASE_URL = os.environ['DATABASE_URL']

if "darwin" in sys.implementation._multiarch:
    conn = psycopg2.connect(DATABASE_URL, host="localhost")
else:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')

autocommit = psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
conn.set_isolation_level(autocommit)

cursor = conn.cursor()


def setup_db():
    cursor.execute("""CREATE TABLE IF NOT EXISTS STATUS_DATA(STATUS_ID BIGINT PRIMARY KEY CHECK (STATUS_ID > 0),
    JSON_DATA JSONB);""")
    cursor.execute("""CREATE TABLE if NOT EXISTS USER_DATA(USER_ID BIGINT PRIMARY KEY CHECK (USER_ID > 0), 
    JSON_DATA JSONB);""")


def get_cache(cache_type: str, item_id: int):
    cursor.execute("""SELECT JSON_DATA FROM {0}_DATA WHERE {0}_ID = {1};""".format(cache_type, item_id))
    values = cursor.fetchall()
    if len(values) != 1:
        return None
    else:
        return values[0][0]


def write_cache(cache_type: str, item_id: int, data: str):
    cursor.execute("""INSERT INTO {0}_DATA VALUES ({1}, '{2}');""".format(cache_type.upper(), item_id, data.replace(
        "'", "''")))


setup_db()
