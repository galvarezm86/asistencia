import os
import sys
import glob
from utils.db import get_db_connection
from utils.users import _crear_o_actualizar_usuario
from utils.users import ROL_ADMIN, ROL_SUPERADMIN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
MIGRATION_DIR = os.path.join(DB_DIR, "migrations")

DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "DEVELOPMENT").upper()

print(
    f"Base de datos activa: {DEPLOY_ENV}"
)

def run_sql(conn, file_path):

    with open(file_path, encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)

if __name__ == "__main__":

    print("Ejecutando migraciones...")

    if len(sys.argv) != 2:
        print(
            "Uso: python migrations.py <numero_migracion>"
        )
        sys.exit(1)

    migration_number = sys.argv[1]

    migration_files = glob.glob(
        os.path.join(
            MIGRATION_DIR,
            f"{migration_number}_*.sql"
        )
    )

    if len(migration_files) == 0:

        print(
            f"No se encontró migración {migration_number}"
        )

        sys.exit(1)

    if len(migration_files) > 1:

        print(
            f"Existe más de una migración con número {migration_number}"
        )

        sys.exit(1)

    migration_file = migration_files[0]
    
    conn = get_db_connection()

    try:
        run_sql(conn, migration_file)
        if migration_number == "002":
            # Usuario inicial creado con contraseña temporal.
            # Debe cambiarse en el primer inicio de sesión.
            _crear_o_actualizar_usuario(
                conn,
                "admin",
                "ClaveTemporal12345",
                ROL_ADMIN,
                True
            )
    
            _crear_o_actualizar_usuario(
                conn,
                "superadmin",
                "ClaveTemporal12345",
                ROL_SUPERADMIN,
                True
            )
        conn.commit()
        print("Migración ejecutada correctamente")

    except Exception as e:
        conn.rollback()
        print(
            f"Error ejecutando migración: {e}"
        )

    finally:

        conn.close()