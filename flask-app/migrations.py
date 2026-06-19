import os
import sqlite3
import psycopg

from psycopg.rows import dict_row

CURRENT_DATABASE = os.environ.get(
    "CURRENT_DATABASE",
    "POSTGRESQL"
).upper()

if CURRENT_DATABASE == "SQLITE":

    DATABASE_URL = os.environ[
        "DATABASE_URL_SQLITE"
    ]

elif CURRENT_DATABASE == "POSTGRESQL":

    DATABASE_URL = os.environ[
        "DATABASE_URL_POSTGRESQL"
    ]

else:

    raise ValueError(
        "Motor de base de datos no soportado"
    )

print(
    f"Base de datos activa: {CURRENT_DATABASE}"
)

DATABASE_IS_SQLITE = DATABASE_URL.startswith(
    "sqlite:///"
)

DATABASE_IS_POSTGRESQL = DATABASE_URL.startswith(
    "postgresql://"
)

if not DATABASE_IS_SQLITE and not DATABASE_IS_POSTGRESQL:

    raise ValueError(
        "Motor de base de datos no soportado"
    )

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_DIR = os.path.join(
    BASE_DIR,
    "db"
)

MIGRATION_DIR = os.path.join(
    DB_DIR,
    "migrations"
)

def get_db_connection():

    if DATABASE_IS_SQLITE:
        return get_sqlite_connection()

    if DATABASE_IS_POSTGRESQL:
        return get_postgresql_connection()

    raise ValueError(
        "Motor no soportado"
    )


def get_sqlite_connection():

    db_name = DATABASE_URL.replace(
        "sqlite:///",
        ""
    )

    DATABASE_PATH = os.path.join(
        BASE_DIR,
        db_name
    )

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def get_postgresql_connection():

    conn = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row  # type: ignore[arg-type]
    )

    return conn
    
def run_sql(conn, file_name):

    path = os.path.join(
        MIGRATION_DIR,
        file_name
    )
    
    with open(
        path,
        encoding="utf-8"
    ) as f:
    
        sql = f.read()
    
    if DATABASE_IS_SQLITE:
    
        conn.executescript(sql)
    
    elif DATABASE_IS_POSTGRESQL:
    
        conn.execute(sql)
    
    else:
    
        raise ValueError(
            "Motor no soportado"
        )

if DATABASE_IS_SQLITE:

    MIGRATION_FILE = (
        "001_configuracion_automatizaciones.sql"
    )

elif DATABASE_IS_POSTGRESQL:

    MIGRATION_FILE = (
        "001_configuracion_automatizaciones_postgresql.sql"
    )

else:

    raise ValueError(
        "Motor no soportado"
    )


if __name__ == "__main__":

    conn = get_db_connection()
    
    try:
    
        run_sql(
            conn,
            MIGRATION_FILE
        )
    
        conn.commit()
    
    finally:
    
        conn.close()
    
    print(
        f"Migración ejecutada ({CURRENT_DATABASE})"
    )