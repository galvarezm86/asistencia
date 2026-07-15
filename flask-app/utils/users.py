from werkzeug.security import generate_password_hash

ROL_ADMIN = "admin"
ROL_SUPERADMIN = "superadmin"

def _crear_o_actualizar_usuario(
    conn,
    username,
    password,
    rol,
    must_change_password
):
    """
    Crea un usuario o actualiza su contraseña, rol y estado.

    Retorna:
        True si el usuario fue creado.
        False si el usuario ya existía y fue actualizado.
    """
    
    if username is None:
        raise ValueError("El nombre de usuario es requerido")

    username = username.strip().lower()

    if not username:
        raise ValueError("El nombre de usuario es requerido")

    if not password:
        raise ValueError("La contraseña es requerida")

    if rol not in (ROL_ADMIN, ROL_SUPERADMIN):
        raise ValueError(f"El rol debe ser '{ROL_ADMIN}' o '{ROL_SUPERADMIN}'")

    if not isinstance(
        must_change_password,
        bool
    ):
        raise ValueError(
            "must_change_password debe ser booleano"
        )

    
    hashed_password = generate_password_hash(password)

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT id
            FROM usuarios
            WHERE username = %s
            """,
            (username,)
        )
    
        usuario_existente = cur.fetchone()

        usuario_creado = False
        if usuario_existente:
            cur.execute(
                """
                UPDATE usuarios
                SET
                    password_hash = %s,
                    rol = %s,
                    must_change_password = %s
                WHERE username = %s
                """,
                (
                    hashed_password,
                    rol,
                    must_change_password,
                    username
                )
            )

        else:
            cur.execute(
                """
                INSERT INTO usuarios (
                    username,
                    password_hash,
                    rol,
                    must_change_password
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    username,
                    hashed_password,
                    rol,
                    must_change_password
                )
            )
            usuario_creado = True

    return usuario_creado

