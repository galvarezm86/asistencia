import os
import psycopg
from psycopg.rows import dict_row

DEPLOY_ENV = os.environ.get(
    "DEPLOY_ENV",
    "DEVELOPMENT"
).upper()

if DEPLOY_ENV not in ("DEVELOPMENT", "PRODUCTION"):
    raise ValueError("DEPLOY_ENV inválido")

if DEPLOY_ENV == "DEVELOPMENT":
    DATABASE_URL = os.environ.get("DATABASE_URL_DEVELOP")

else:
    DATABASE_URL = os.environ.get("DATABASE_URL_PRODUCTION")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL no configurada")

def get_db_connection():
    return psycopg.connect(
        DATABASE_URL,  # type: ignore[arg-type]
        row_factory=dict_row  # type: ignore[arg-type]
    )