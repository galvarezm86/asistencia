from werkzeug.security import generate_password_hash
import secrets
import string

ROL_ADMIN = "admin"
ROL_SUPERADMIN = "superadmin"

def _crear_o_actualizar_usuario(
    conn,
    username,
    password,
    rol,
    must_change_password,
    restauracion_pendiente
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

    
    usuario_existente = conn.execute(
        """
        SELECT id
        FROM usuarios
        WHERE username = %s
        """,
        (username,)
    ).fetchone()

    usuario_creado = False
    if usuario_existente:
        conn.execute(
            """
            UPDATE usuarios
            SET
                password_hash = %s,
                rol = %s,
                must_change_password = %s,
                restauracion_pendiente = %s
            WHERE username = %s
            """,
            (
                hashed_password,
                rol,
                must_change_password,
                restauracion_pendiente,
                username
            )
        )

    else:
        conn.execute(
            """
            INSERT INTO usuarios (
                username,
                password_hash,
                rol,
                must_change_password,
                restauracion_pendiente
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                username,
                hashed_password,
                rol,
                must_change_password,
                restauracion_pendiente
            )
        )
        usuario_creado = True

    return usuario_creado

def generar_password_temporal(longitud=12):

    if longitud < 8:
        raise ValueError(
            "La contraseña temporal debe tener al menos 8 caracteres"
        )
    
    mayuscula = secrets.choice(string.ascii_uppercase)
    minuscula = secrets.choice(string.ascii_lowercase)
    numero = secrets.choice(string.digits)
    simbolo = secrets.choice("!@#$%&*")
    
    resto = longitud - 4
    
    caracteres = (
        string.ascii_letters +
        string.digits +
        "!@#$%&*"
    )
    
    password = [
        mayuscula,
        minuscula,
        numero,
        simbolo
    ]
    
    password.extend(
        secrets.choice(caracteres)
        for _ in range(resto)
    )
    
    secrets.SystemRandom().shuffle(password)
    
    return "".join(password)


def procesar_restauracion_superadmin(
    conn,
    usuario
):
    """
    Genera y actualiza una contraseña temporal
    para un superadmin.

    Retorna:
        str: contraseña temporal generada
    """

    password_temp = generar_password_temporal()

    _crear_o_actualizar_usuario(
        conn,
        usuario["username"],
        password_temp,
        usuario["rol"],
        True,
        False
    )

    return password_temp