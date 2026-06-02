import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def run_sql(conn, file_name):
    MIGRATION_DIR = os.path.join(DB_DIR, "migrations")
    path = os.path.join(MIGRATION_DIR, file_name)
    with open(path) as f:
        conn.executescript(f.read())
        
if __name__ == "__main__":

    conn = get_db_connection()

    run_sql(conn, "migracion_inicial.sql")

    conn.commit()
    conn.close()

    print("Base de datos actualizada en:", DATABASE_PATH)