import os
from utils.db import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
MIGRATION_DIR = os.path.join(DB_DIR, "migrations")
MIGRATION_FILE = ""

DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "DEVELOPMENT").upper()

print(
    f"Base de datos activa: {DEPLOY_ENV}"
)

def run_sql(conn, file_name):

    path = os.path.join(MIGRATION_DIR, file_name)

    with open(path, encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)

if __name__ == "__main__":

    print("Ejecutando migraciones...")

    conn = get_db_connection()

    try:
        run_sql(conn, MIGRATION_FILE)
        conn.commit()

    finally:
        conn.close()

    print("Migración ejecutada correctamente")