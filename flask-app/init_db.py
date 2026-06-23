import os
from utils.db import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(
    BASE_DIR,
    "db"
)

DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "DEVELOPMENT").upper()

print(
    f"Base de datos activa: {DEPLOY_ENV}"
)

def run_sql(conn, file_name):
    
    path = os.path.join(DB_DIR, file_name)
    
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    
    with conn.cursor() as cur:
        cur.execute(sql, prepare=True)

SCHEMA_FILE = "schema_postgresql.sql"
SEED_FILE = "seed_postgresql.sql"
MIGRATION_FILE = "migracion_inicial_postgresql.sql"

if __name__ == "__main__":

    conn = get_db_connection()

    try:

        run_sql(conn, SCHEMA_FILE)
        run_sql(conn, SEED_FILE)
        run_sql(conn, MIGRATION_FILE)

        conn.commit()

    finally:

        conn.close()

    