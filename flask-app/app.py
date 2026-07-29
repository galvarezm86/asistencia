from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, Response, make_response
import os
import secrets
import unicodedata
import re
import logging
import io
import qrcode
import psycopg
import uuid
from zoneinfo import ZoneInfo
from functools import wraps
from datetime import timedelta, datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from werkzeug.security import check_password_hash
from utils.db import get_db_connection
from utils.users import (
    _crear_o_actualizar_usuario,
    generar_password_temporal,
    procesar_restauracion_superadmin
)
from utils.users import ROL_ADMIN, ROL_SUPERADMIN
from utils.email_service import (
    send_password_reset_request,
    send_superadmin_reset_email
)


# =============================================================================
# APLICACIÓN
# =============================================================================
app = Flask(__name__)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

app.secret_key = os.environ["SESSION_SECRET"]
DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "DEVELOPMENT").upper()

# =============================================================================
# ERRORES
# =============================================================================

DATABASE_ERRORS = (
    psycopg.Error
)

INTEGRITY_ERRORS = (
    psycopg.IntegrityError
)

# =============================================================================
# CONSTANTES
# =============================================================================

MAX_NOMBRE_LENGTH = 100
MAX_CORREO_LENGTH = 255

# =============================================================================
# CONFIGURACIÓN DE SESIÓN
# =============================================================================

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_SECURE"] = (
    DEPLOY_ENV == "PRODUCTION"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info(
    f"Base de datos activa: {DEPLOY_ENV}"
)

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

@app.after_request
def agregar_headers_no_cache(response):

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"

    response.headers["Expires"] = "0"

    return response

def asegurar_csrf_token():

    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

def validar_csrf():

    token_form = request.form.get("csrf_token")

    token_session = session.get("csrf_token")

    if (
        not token_form or
        not token_session or
        token_form != token_session
    ):
        abort(403)

def _normalizar_nombre(nombre):

    if nombre is None:
        return ""

    nombre = nombre.strip()

    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    )

    if len(nombre) > MAX_NOMBRE_LENGTH:
        return ""

    if not re.fullmatch(
        r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]+",
        nombre
    ):
        return ""

    nombre = unicodedata.normalize(
        "NFD",
        nombre
    )

    nombre = "".join(
        c for c in nombre
        if unicodedata.category(c) != "Mn"
    )

    nombre = nombre.upper()

    return nombre


def _formatear_fecha(fecha):

    if isinstance(
        fecha,
        str
    ):
    
        fecha = datetime.strptime(
            fecha,
            "%Y-%m-%d"
        )
    
    return fecha.strftime(
        "%d/%m/%y"
    )

def _obtener_datos_asistencia(desde, hasta):
    where_clauses = []
    params = []

    if desde:

        where_clauses.append(
            "DATE(fecha_hora) >= %s"
        )

        params.append(desde)

    if hasta:

        where_clauses.append(
            "DATE(fecha_hora) <= %s"
        )

        params.append(hasta)

    where_sql = ""

    if where_clauses:

        where_sql = (
            "WHERE "
            + " AND ".join(where_clauses)
        )

    fechas_sql = f"""
    SELECT DISTINCT
        date(fecha_hora) AS fecha
    FROM asistencias
    {where_sql}
    ORDER BY fecha
    """

    asistencias_sql = f"""
    SELECT
        persona_id,
        date(fecha_hora) AS fecha
    FROM asistencias
    {where_sql}
    """

    personas_sql = f"""
    SELECT DISTINCT
        p.id,
        p.nombre
    FROM personas p
    INNER JOIN asistencias a
        ON a.persona_id = p.id
    """

    personas_params = []

    personas_where_clauses = []

    if desde:

        personas_where_clauses.append(
            "DATE(a.fecha_hora) >= %s"
        )

        personas_params.append(desde)

    if hasta:

        personas_where_clauses.append(
            "DATE(a.fecha_hora) <= %s"
        )

        personas_params.append(hasta)

    if personas_where_clauses:

        personas_sql += (
            " WHERE "
            + " AND ".join(personas_where_clauses)
        )

    personas_sql += """
     ORDER BY p.nombre
    """

    conn = None
    
    try:
        conn = get_db_connection()
        
        fechas = conn.execute(
            fechas_sql,
            params
        ).fetchall()

        personas = conn.execute(
            personas_sql,
            personas_params
        ).fetchall()

        asistencias = conn.execute(
            asistencias_sql,
            params
        ).fetchall()

        return fechas, personas, asistencias

    except DATABASE_ERRORS:
        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al obtener datos de asistencia"
        )
        abort(500)

    finally:
        if conn:
            conn.close()

def _construir_tabla_asistencia(fechas, personas, asistencias):
    asistencias_set = {
        (
            asistencia["persona_id"],
            asistencia["fecha"]
        )
        for asistencia in asistencias
    }

    tabla = []

    for persona in personas:

        fila = {
            "nombre": persona["nombre"],
            "total": 0,
            "asistencias": []
        }

        for fecha in fechas:

            presente = (
                persona["id"],
                fecha["fecha"]
            ) in asistencias_set

            fila["asistencias"].append(presente)

            if presente:
                fila["total"] += 1


        tabla.append(fila)

    return tabla

def _obtener_ip_cliente():

    forwarded_for = request.headers.get("X-Forwarded-For")
    
    if forwarded_for:
    
        return forwarded_for.split(",")[0].strip()
    
    return request.remote_addr

def _obtener_user_agent():

    return request.headers.get(
        "User-Agent",
        ""
    )

# =============================================================================
# DECORADORES
# =============================================================================
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
    
        if not session.get("admin"):
            return redirect(url_for("login"))
    
        return f(*args, **kwargs)
    
    return decorated_function

    

def change_password_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if (
            session.get("must_change_password", False)
            and request.endpoint != "cambiar_clave"
        ):

            return redirect(
                url_for("cambiar_clave")
            )

        return view(*args, **kwargs)

    return wrapped

def superadmin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
    
        if session.get("rol") != ROL_SUPERADMIN:
            abort(403)
    
        return view(*args, **kwargs)
    
    return wrapped

# =============================================================================
# ERRORS HANDLERS
# =============================================================================

@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403

@app.errorhandler(404)
def page_not_found(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(405)
def method_not_allowed(error):

    return render_template(
        "errors/405.html"
    ), 405

@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "errors/500.html"
    ), 500



# =============================================================================
# RUTAS PÚBLICAS
# =============================================================================

@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.get("/health")
def health():
    return Response("OK", status=200, mimetype="text/plain")

@app.route("/formulario/<token>", methods=["GET", "POST"])
def formulario(token):

    asegurar_csrf_token()

    conn = None

    try:

        conn = get_db_connection()

        config = conn.execute(
            """
            SELECT token_actual
            FROM configuracion
            WHERE id = 1
            """
        ).fetchone()

        if config is None:
            abort(500)

        token_valido = config["token_actual"]

        if token != token_valido:
            abort(404)

        device_id = request.cookies.get("device_id")
        nueva_cookie = False

        if not device_id:
            device_id = str(uuid.uuid4())
            nueva_cookie = True
        
        if request.method == "POST":

            validar_csrf()

            persona_id = request.form.get(
                "persona_id",
                ""
            ).strip()

            if not persona_id.isdigit():

                flash(
                    "Persona inválida",
                    "error"
                )

                return redirect(
                    url_for(
                        "formulario",
                        token=token
                    )
                )

            persona_id = int(persona_id)

            if persona_id <= 0:

                flash(
                    "Debe seleccionar una persona",
                    "warning"
                )

                return redirect(
                    url_for(
                        "formulario",
                        token=token
                    )
                )

            persona = conn.execute(
                """
                SELECT id, nombre
                FROM personas
                WHERE id = %s
                AND activo = 1
                """,
                (persona_id,)
            ).fetchone()

            if persona is None:
                abort(404)

            existe_persona_sql = """
                SELECT 1
                FROM asistencias
                WHERE persona_id = %s
                AND DATE(fecha_hora) = CURRENT_DATE
            """

            existe_persona = conn.execute(
                existe_persona_sql,
                (persona_id,)
            ).fetchone()

            if existe_persona:

                flash(
                    "Asistencia ya registrada hoy",
                    "warning"
                )

                return redirect(
                    url_for(
                        "formulario",
                        token=token
                    )
                )

            # Los administradores pueden registrar múltiples asistencias desde sus dispositivos
            if session.get("rol") not in (ROL_ADMIN, ROL_SUPERADMIN):
                existe_device_sql = """
                    SELECT 1
                    FROM asistencias
                    WHERE device_id = %s
                    AND DATE(fecha_hora) = CURRENT_DATE
                """
    
                existe_device = conn.execute(
                    existe_device_sql,
                    (device_id,)
                ).fetchone()
    
                if existe_device:
    
                    flash(
                        "Este dispositivo ya registró una asistencia hoy",
                        "warning"
                    )
    
                    return redirect(
                        url_for(
                            "formulario",
                            token=token
                        )
                    )
    
            ip = _obtener_ip_cliente()
            user_agent = _obtener_user_agent()
            
            conn.execute(
                """
                INSERT INTO asistencias (
                    persona_id,
                    device_id,
                    ip,
                    user_agent
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    persona_id,
                    device_id,
                    ip,
                    user_agent
                )
            )

            conn.commit()

            session["ultimo_nombre"] = persona["nombre"]

            session["ultimo_token"] = token

            return redirect(
                url_for("confirmacion")
            )

        personas = conn.execute(
            """
            SELECT id, nombre
            FROM personas
            WHERE activo = 1
            ORDER BY nombre
            """
        ).fetchall()

        response = make_response(
            render_template(
                "formulario.html",
                personas=personas
            )
        )

        if nueva_cookie:
            response.set_cookie(
                key="device_id",
                value=device_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                secure=request.is_secure,
                samesite="Lax"
            )
        return response

    except INTEGRITY_ERRORS:

        if conn:
            conn.rollback()

        flash(
            "Asistencia ya registrada hoy",
            "warning"
        )

        return redirect(
            url_for(
                "formulario",
                token=token
            )
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al registrar asistencia"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )

        return redirect(url_for("inicio"))

    finally:

        if conn:
            conn.close()

@app.route("/confirmacion")
def confirmacion():

    nombre = session.pop("ultimo_nombre", None)
    token = session.get("ultimo_token")

    if not token:

        flash(
            "Sesión inválida",
            "error"
        )

        return redirect(url_for("inicio"))

    if not nombre:

        return redirect(
            url_for("formulario", token=token)
        )

    return render_template(
        "confirmacion.html",
        nombre=nombre,
        token=token
    )

# =============================================================================
# RUTAS AUTENTICACIÓN
# =============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    asegurar_csrf_token()
    
    if session.get("admin"):
        return redirect(url_for("admin"))
        
    if request.method == "POST":

        validar_csrf()
        
        username = request.form.get(
            "username",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            flash(
                "Debe ingresar usuario y contraseña",
                "error"
            )

            return redirect(url_for("login"))

        conn = None
        
        try:
            conn = get_db_connection()
            usuario = conn.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    rol,
                    must_change_password
                FROM usuarios
                WHERE username = %s
                """,
                (username,)
            ).fetchone()
            
            if (usuario and check_password_hash(
                    usuario["password_hash"],
                    password
                )
            ):
    
                session.clear()
                session.permanent = True
                session["admin"] = True
                session["user_id"] = usuario["id"]
                session["username"] = usuario["username"]
                session["rol"] = usuario["rol"]
                session["must_change_password"] = usuario["must_change_password"]
                session["csrf_token"] = secrets.token_hex(32)

                if usuario["must_change_password"]:

                    return redirect(url_for("cambiar_clave"))

                flash(
                    "Sesión iniciada correctamente",
                    "success"
                )

                if usuario["rol"] == ROL_SUPERADMIN:
                    return redirect(url_for("superadmin"))
                    
                return redirect(url_for("admin"))
    
            flash(
                "Credenciales incorrectas",
                "error"
            )
    
            return redirect(url_for("login"))

        except DATABASE_ERRORS:
            if conn:
                conn.rollback()
            app.logger.exception(
                "Error en la base de datos al iniciar sesión"
            )
            flash(
                "Ocurrió un error interno", "error")
            return redirect(url_for("login"))

        finally:
            if conn:
                conn.close()
                
    return render_template("login.html")

@app.route("/cambiar-clave", methods=["GET", "POST"])
@login_required
def cambiar_clave():

    asegurar_csrf_token()
    
    if request.method == "POST":
        validar_csrf()
        clave_actual = request.form.get("clave_actual")
        clave_nueva = request.form.get("clave_nueva")
        clave_nueva_confirmacion = request.form.get("clave_nueva_confirmacion")
        
        if not clave_actual or not clave_nueva or not clave_nueva_confirmacion:
            flash("Todos los campos son obligatorios", "error")
            return redirect(url_for("cambiar_clave"))
        
        if clave_nueva != clave_nueva_confirmacion:
            flash("Las nuevas claves no coinciden", "error")
            return redirect(url_for("cambiar_clave"))
        
        usuario_actual = session["user_id"]
        conn = None
        try:
            conn = get_db_connection()
            usuario = conn.execute(
                """
                SELECT password_hash
                FROM usuarios
                WHERE id = %s
                """,
                (usuario_actual,)
            ).fetchone()

            if not usuario:
                flash(
                    "Ocurrió un error interno.",
                    "error"
                )
                return redirect(url_for("logout"))
            
            if not check_password_hash(
                usuario["password_hash"],
                clave_actual
            ):
                flash(
                    "La clave actual no es correcta",
                    "error"
                )
                return redirect(url_for("cambiar_clave"))

            if clave_nueva == clave_actual:
                flash("La nueva clave debe ser distinta a la actual", "error")
                return redirect(url_for("cambiar_clave"))

            if len(clave_nueva) < 8:
                flash("La nueva clave debe tener al menos 8 caracteres", "error")
                return redirect(url_for("cambiar_clave"))

            _crear_o_actualizar_usuario(conn, session["username"], clave_nueva, session["rol"], False, False)
            conn.commit()
            session["must_change_password"] = False
            flash("Clave cambiada correctamente", "success")
            return redirect(url_for("admin"))

        except DATABASE_ERRORS:
            if conn:
                conn.rollback()
            app.logger.exception("Error en la base de datos al cambiar clave")
            flash("Ocurrió un error interno", "error")
            return redirect(url_for("cambiar_clave"))

        finally:
            if conn:
                conn.close()

    return render_template("admin/cambiar_clave.html")

@app.route("/solicitar-restauracion", methods=["GET", "POST"])
def solicitar_restauracion():

    asegurar_csrf_token()

    if request.method == "POST":

        validar_csrf()

        username = request.form.get("username", "").strip()

        if not username:
            flash("Debes ingresar tu nombre de usuario.", "error")
            return redirect(url_for("solicitar_restauracion"))

        conn = None

        try:
            conn = get_db_connection()

            usuario = conn.execute(
                """
                SELECT id, username, rol, restauracion_pendiente
                FROM usuarios
                WHERE username = %s
                """,
                (username,)
            ).fetchone()

            # Respuesta genérica para no revelar usuarios existentes
            if usuario:

                if not usuario["restauracion_pendiente"]:

                    if usuario["rol"] == ROL_SUPERADMIN:

                        password_temp = procesar_restauracion_superadmin(
                            conn,
                            usuario
                        )
                        conn.commit()
                        # Se confirma el cambio antes del envío del correo.
                        # Si el envío falla, el usuario podrá solicitar nuevamente
                        # una restauración.
                        try:
                            admin_email = os.environ.get("ADMIN_EMAIL")
                            if not admin_email:
                                raise ValueError("ADMIN_EMAIL no está configurado")

                            send_superadmin_reset_email(
                                usuario["username"],
                                password_temp,
                                admin_email
                            )

                        except Exception:

                            app.logger.exception(
                                "Error enviando correo de restauración de superadmin"
                            )
                            
                            flash(
                                "No fue posible completar el proceso. "
                                "Por favor, envía nuevamente la solicitud de restablecimiento.",
                                "error"
                            )
                            return redirect(url_for("solicitar_restauracion"))

                    else:
                        
        
                        conn.execute(
                            """
                            UPDATE usuarios
                            SET restauracion_pendiente = TRUE
                            WHERE id = %s
                            """,
                            (usuario["id"],)
                        )
        
                        conn.commit()
        
                        try:
                            panel_url = url_for("admin", _external=True)
        
                            send_password_reset_request(
                                usuario["username"],
                                panel_url
                            )
        
                        except Exception:
        
                            app.logger.exception(
                                "Error enviando solicitud de restauración"
                            )
                            app.logger.warning(
                                "Solicitud de restauración creada pero correo no enviado para %s",
                                usuario["username"]
                            )
        
            flash(
                "Si el usuario existe, se activará el procedimiento adecuado para restablecer la contraseña.",
                "success"
            )

            return redirect(url_for("login"))

        except DATABASE_ERRORS:

            if conn:
                conn.rollback()
            app.logger.exception(
                "Error al solicitar restauración de contraseña"
            )

            flash(
                "Ocurrió un error al procesar la solicitud.",
                "error"
            )
            return redirect(url_for("solicitar_restauracion"))

        finally:
            if conn:
                conn.close()

    return render_template("solicitar_restauracion.html")
    
        
@app.route("/logout", methods=["POST"])
@login_required
def logout():

    validar_csrf()
    
    session.clear()

    flash(
        "Sesión cerrada correctamente",
        "success"
    )

    return redirect(url_for("login"))

# =============================================================================
# RUTAS ADMIN
# =============================================================================

@app.route("/admin")
@login_required
@change_password_required
def admin():
    return render_template(
        "admin/admin.html"
    )

@app.route("/superadmin")
@login_required
@change_password_required
@superadmin_required
def superadmin():

    conn = None

    try:
        conn = get_db_connection()

        solicitudes = conn.execute(
            """
            SELECT id, username
            FROM usuarios
            WHERE restauracion_pendiente = TRUE
            ORDER BY username
            """
        ).fetchall()

    except DATABASE_ERRORS:

        app.logger.exception(
            "Error cargando panel superadmin"
        )

        solicitudes = []

    finally:

        if conn:
            conn.close()

    return render_template(
        "superadmin/superadmin.html",
        solicitudes=solicitudes
    )
    
@app.route(
    "/superadmin/restablecer-clave/<int:usuario_id>",
    methods=["GET", "POST"]
)
@login_required
@change_password_required
@superadmin_required
def restablecer_clave(usuario_id):

    asegurar_csrf_token()

    conn = None
    
    try:
        conn = get_db_connection()
        usuario = conn.execute(
            """
            SELECT id, username
            FROM usuarios
            WHERE id = %s
            AND restauracion_pendiente = TRUE
            """,
            (usuario_id,)
        ).fetchone()

        if not usuario:
            abort(404)

    except DATABASE_ERRORS:
        if conn:
            conn.rollback()
        app.logger.exception(
            "Error cargando restablecimiento de clave"
        )
        flash("Ocurrió un error interno", "error")
        return redirect(url_for("superadmin"))

    finally:
        if conn:
            conn.close()
    
    if request.method == "POST":

        validar_csrf()

        password_temp = request.form.get(
            "password_temp",
            ""
        ).strip()

        if len(password_temp) < 8:
            flash(
                "La contraseña debe tener al menos 8 caracteres",
                "error"
            )
            return redirect(
                url_for(
                    "restablecer_clave",
                    usuario_id=usuario_id
                )
            )

        session["usuario_restauracion_id"] = usuario_id
        session["password_temp"] = password_temp

        return redirect(
            url_for("confirmar_restablecimiento")
        )


    return render_template(
        "superadmin/restablecer_clave.html",
        usuario=usuario
    )

@app.route("/superadmin/confirmar-restablecimiento", methods=["GET", "POST"])
@login_required
@change_password_required
@superadmin_required
def confirmar_restablecimiento():

    asegurar_csrf_token()
    password_temp = session.get("password_temp")

    if not password_temp:
        flash(
            "No existe una solicitud de restauración activa.",
            "error"
        )
        return redirect(url_for("superadmin"))

    if request.method == "POST":
        validar_csrf()
        password_temp = session.get("password_temp")
        usuario_id = session.get("usuario_restauracion_id")
        if password_temp is None or usuario_id is None:
            flash(
                "No se encontró información de restauración.",
                "error"
            )
            return redirect(url_for("superadmin"))

        if len(password_temp) < 8:
            flash(
                "La contraseña debe tener al menos 8 caracteres",
                "error"
            )
            return redirect(url_for("superadmin"))

        conn = None
        try:
            conn = get_db_connection()
            usuario = conn.execute(
                """
                SELECT username, rol
                FROM usuarios
                WHERE id = %s
                """,
                (usuario_id,)
            ).fetchone()
            
            if not usuario:
                flash(
                    "El usuario no existe.",
                    "error"
                )
                return redirect(url_for("superadmin"))
                
            _crear_o_actualizar_usuario(
                conn,
                usuario["username"],
                password_temp,
                usuario["rol"],
                True,
                False
            )
            
            conn.commit()
            

        except DATABASE_ERRORS:
            if conn:
                conn.rollback()
            flash("Ocurrió un error interno", "error")
            return redirect(url_for("superadmin"))

        finally:
            if conn:
                conn.close()

        session.pop(
            "password_temp",
            None
        )
        session.pop(
            "usuario_restauracion_id",
            None
        )
        
        flash(
            f"La contraseña del usuario {usuario['username']} fue restablecida correctamente.",
            "success"
        )
    
        return redirect(
            url_for("superadmin")
        )

    return render_template(
        "superadmin/confirmar_restablecimiento.html",
        password_temp=password_temp
    )

@app.route(
    "/superadmin/cancelar-restablecimiento",
    methods=["POST"]
)
@login_required
@change_password_required
@superadmin_required
def cancelar_restablecimiento():

    validar_csrf()
    session.pop(
        "password_temp",
        None
    )
    session.pop(
        "usuario_restauracion_id",
        None
    )

    flash(
        "Restablecimiento cancelado",
        "success"
    )

    return redirect(
        url_for("superadmin")
    )
    
    

# =============================================================================
# GESTIÓN QR
# =============================================================================

@app.route("/admin/qr")
@login_required
@change_password_required
def admin_qr():

    conn = None

    try:

        conn = get_db_connection()

        config = conn.execute(
            """
            SELECT
                token_actual,
                qr_updated_at
            FROM configuracion
            WHERE id = 1
            """
        ).fetchone()

        if config is None:

            abort(500)

        fecha_qr = config["qr_updated_at"]

        qr_vencido = False
        fecha_qr_formateada = None

        if fecha_qr:

            if isinstance(fecha_qr, str):
                fecha_qr = datetime.fromisoformat(fecha_qr)

            fecha_qr = fecha_qr.replace(
                tzinfo=ZoneInfo("UTC")
            ).astimezone(
                ZoneInfo("America/Santiago")
            )

            fecha_qr_formateada = fecha_qr.strftime(
                "%d/%m/%Y a las %H:%M horas"
            )

            qr_vencido = (
                fecha_qr.isocalendar().week
                != datetime.now().isocalendar().week
            )
        
        return render_template(
            "admin/qr.html",
            token=config["token_actual"],
            qr_updated_at=fecha_qr_formateada,
            qr_vencido=qr_vencido
        )

    except DATABASE_ERRORS:
        if conn:
            conn.rollback()
        app.logger.exception(
            "Error en la base de datos al cargar gestión QR"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )

        return redirect(url_for("admin"))

    finally:

        if conn:
            conn.close()

@app.route("/admin/qr/imagen")
@login_required
@change_password_required
def qr_imagen():

    conn = None

    try:

        conn = get_db_connection()

        config = conn.execute(
            """
            SELECT token_actual
            FROM configuracion
            WHERE id = 1
            """
        ).fetchone()

        if config is None:
            abort(500)

        url_formulario = url_for(
            "formulario",
            token=config["token_actual"],
            _external=True
        )

        qr = qrcode.make(url_formulario)

        buffer = io.BytesIO()

        qr.save(buffer, format="PNG")

        buffer.seek(0)

        return send_file(
            buffer,
            mimetype="image/png"
        )

    except DATABASE_ERRORS:
        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al generar QR"
        )

        abort(500)

    finally:

        if conn:
            conn.close()

@app.route("/admin/qr/pdf", methods=["POST"])
@login_required
@change_password_required
def qr_pdf():

    validar_csrf()

    # 1. Obtener token actual
    conn = None
    try:
        conn = get_db_connection()
        config = conn.execute(
            """
            SELECT token_actual
            FROM configuracion
            WHERE id = 1
            """
        ).fetchone()
        token = config["token_actual"]
    except DATABASE_ERRORS:
        if conn:
            conn.rollback()
        app.logger.exception(
            "Error en la base de datos al generar PDF"
        )
        abort(500)
    finally:
        if conn:
            conn.close()



    # 2. URL del formulario
    url_formulario = url_for("formulario", token=token, _external=True)

    # 3. Generar QR
    qr_img = qrcode.make(url_formulario)

    # 4. Crear buffer para PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 5. Título
    MESES = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre"
    }

    hoy = datetime.now()

    dias_hasta_sabado = (5 - hoy.weekday()) % 7

    proximo_sabado = hoy + timedelta(days=dias_hasta_sabado)

    fecha_str = (
        f"{proximo_sabado.day} de "
        f"{MESES[proximo_sabado.month]} de "
        f"{proximo_sabado.year}"
    )

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height - 80, "Asistencia Sábado")
    c.drawCentredString(width/2, height - 120, fecha_str)

    # 6. Insertar QR
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Ajustar tamaño QR para ocupar ancho de la página (dejando márgenes)
    qr_width = width - 100  # 50pt margen a cada lado
    qr_height = qr_width
    qr_buffer.seek(0)

    qr_img_reader = ImageReader(qr_buffer)

    qr_size = width - 50  # deja márgenes laterales

    x = (width - qr_size) / 2
    y = height - qr_size - 200  # 👈 baja el QR claramente

    c.drawImage(
        qr_img_reader,
        x,
        y,
        width=qr_size,
        height=qr_size
    )

    # 7. Finalizar PDF
    c.showPage()
    c.save()
    buffer.seek(0)

    nombre_archivo = (
        f"qr_asistencia_{proximo_sabado.day}{MESES[proximo_sabado.month]}{proximo_sabado.year}.pdf"
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nombre_archivo
    )

@app.route("/admin/qr/regenerar", methods=["POST"])
@login_required
@change_password_required
def regenerar_token():

    validar_csrf()

    nuevo_token = secrets.token_urlsafe(16)

    conn = None

    try:

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE configuracion
            SET token_actual = %s,
                qr_updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (nuevo_token,)
        )

        conn.commit()

        flash(
            "QR regenerado correctamente",
            "success"
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al regenerar token"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )
        return redirect(url_for("admin_qr"))

    finally:

        if conn:
            conn.close()

    return redirect(url_for("admin_qr"))


# =============================================================================
# VISUALIZACIÓN ASISTENCIAS
# =============================================================================

@app.route("/admin/asistencia")
@login_required
@change_password_required
def asistencia_admin():


    desde = request.args.get("desde")
    hasta = request.args.get("hasta")

    if desde and hasta and desde > hasta:
        flash(
            "La fecha 'Desde' no puede ser mayor que 'Hasta'",
            "error"
        )
        return redirect(url_for("asistencia_admin"))
        
    fechas, personas, asistencias = _obtener_datos_asistencia(desde, hasta)
    
    # Convertir asistencias a un set para búsquedas rápidas

    if not fechas:
        flash("No existen asistencias para el período seleccionado", "info")
        fechas = []
        datos = []

        return render_template("admin/asistencia.html", fechas=fechas, datos=datos)

    tabla = _construir_tabla_asistencia(fechas, personas, asistencias)
    
    desde_mostrar = None
    hasta_mostrar = None

    if desde:
        desde_mostrar = _formatear_fecha(desde)

    if hasta:
        hasta_mostrar = _formatear_fecha(hasta)

    fechas_mostrar = []

    for fecha in fechas:

        fechas_mostrar.append(
            _formatear_fecha(
                fecha["fecha"]
            )
        )
            
    return render_template(
        "admin/asistencia.html",
        fechas=fechas,
        fechas_mostrar=fechas_mostrar,
        tabla=tabla,
        desde=desde,
        hasta=hasta,
        desde_mostrar=desde_mostrar,
        hasta_mostrar=hasta_mostrar
    )

@app.route("/admin/asistencia/excel")
@login_required
@change_password_required
def exportar_asistencia_excel():
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")

    if desde and hasta and desde > hasta:
        flash(
            "La fecha 'Desde' no puede ser mayor que 'Hasta'",
            "error"
        )
        return redirect(url_for("asistencia_admin"))

    fechas, personas, asistencias = _obtener_datos_asistencia(desde, hasta)
    
   
    # Convertir asistencias a un set para búsquedas rápidas

    if not fechas:

        flash(
            "No existen asistencias para el período seleccionado",
            "info"
        )

        return redirect(
            url_for("asistencia_admin")
        )

    tabla = _construir_tabla_asistencia(fechas, personas, asistencias)
    
    wb = Workbook()
    ws = wb.active

    ws.title = "Asistencia"

    encabezados = ["Persona"]

    for fecha in fechas:

        encabezados.append(
            _formatear_fecha(
                fecha["fecha"]
            )
        )

    encabezados.append("Total")

    ws.append(encabezados)

    for fila in tabla:

        fila_excel = [fila["nombre"]]

        for presente in fila["asistencias"]:

            fila_excel.append(
                "Sí" if presente else "No"
            )

        fila_excel.append(
            fila["total"]
        )

        ws.append(fila_excel)

    

    for column in ws.columns:

        max_length = 0

        column_letter = get_column_letter(
            column[0].column
        )

        for cell in column:

            try:

                cell_length = len(
                    str(cell.value)
                )

                if cell_length > max_length:
                    max_length = cell_length

            except Exception:
                pass

        adjusted_width = max_length + 5

        ws.column_dimensions[
            column_letter
        ].width = adjusted_width

    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in ws.iter_rows():

        for cell in row:

            if cell.column != 1 and cell.value is not None:

                cell.alignment = Alignment(
                    horizontal="center"
                )
            
    ws.freeze_panes = "B2"
        
    output = io.BytesIO()

    
    wb.save(output)

    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name="asistencia.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )
    
# =============================================================================
# GESTIÓN PERSONAS
# =============================================================================

@app.route("/admin/personas")
@login_required
@change_password_required
def personas():

    conn = get_db_connection()

    personas = conn.execute(
        """
        SELECT id, nombre
        FROM personas
        WHERE activo = 1
        ORDER BY nombre
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/personas.html",
        personas=personas
    )

@app.route("/admin/personas/inactivas")
@login_required
@change_password_required
def personas_inactivas():

    conn = get_db_connection()

    personas = conn.execute(
        """
        SELECT id, nombre
        FROM personas
        WHERE activo = 0
        ORDER BY nombre
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/personas_inactivas.html",
        personas=personas
    )

@app.route("/admin/personas/agregar", methods=["POST"])
@login_required
@change_password_required
def agregar_persona():

    validar_csrf()
    
    nombre = request.form.get("nombre", "")

    nombre = _normalizar_nombre(nombre)

    if not nombre:
        flash("Nombre inválido", "error")
        return redirect(url_for("personas"))

    conn = None

    try:

        conn = get_db_connection()

        existe = conn.execute(
            """
            SELECT 1
            FROM personas
            WHERE nombre = %s
            """,
            (nombre,)
        ).fetchone()

        if existe:

            flash(
                "Ya existe una persona con ese nombre",
                "error"
            )

            return redirect(url_for("personas"))

        conn.execute(
            """
            INSERT INTO personas (nombre)
            VALUES (%s)
            """,
            (nombre,)
        )

        conn.commit()

        flash(
            "Persona agregada correctamente",
            "success"
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al agregar persona"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )
        return redirect(url_for("personas"))

    finally:

        if conn:
            conn.close()

    return redirect(url_for("personas"))

@app.route("/admin/personas/desactivar/<int:id>", methods=["POST"])
@login_required
@change_password_required
def desactivar_persona(id):

    validar_csrf()
    
    conn = None

    try:

        conn = get_db_connection()

        persona = conn.execute(
            """
            SELECT id, activo
            FROM personas
            WHERE id = %s
            """,
            (id,)
        ).fetchone()

        if not persona:
            abort(404)

        if persona["activo"] == 0:

            flash(
                "La persona ya está inactiva",
                "warning"
            )

            return redirect(url_for("personas"))

        conn.execute(
            """
            UPDATE personas
            SET activo = 0
            WHERE id = %s
            """,
            (id,)
        )

        conn.commit()

        flash(
            "Persona desactivada correctamente",
            "success"
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al desactivar persona"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )
        return redirect(url_for("personas"))

    finally:

        if conn:
            conn.close()

    return redirect(url_for("personas"))

@app.route("/admin/personas/reactivar/<int:id>", methods=["POST"])
@login_required
@change_password_required
def reactivar_persona(id):

    validar_csrf()
    
    conn = None

    try:

        conn = get_db_connection()

        persona = conn.execute(
            """
            SELECT id, activo
            FROM personas
            WHERE id = %s
            """,
            (id,)
        ).fetchone()

        if not persona:
            abort(404)

        if persona["activo"] == 1:

            flash(
                "La persona ya está activa",
                "warning"
            )

            return redirect(url_for("personas_inactivas"))

        conn.execute(
            """
            UPDATE personas
            SET activo = 1
            WHERE id = %s
            """,
            (id,)
        )

        conn.commit()

        flash(
            "Persona reactivada correctamente",
            "success"
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception(
            "Error en la base de datos al reactivar persona"
        )

        flash(
            "Ocurrió un error interno",
            "error"
        )
        return redirect(url_for("personas_inactivas"))

    finally:

        if conn:
            conn.close()

    return redirect(url_for("personas"))

@app.route("/admin/persona/<int:id>/editar", methods=["GET", "POST"])
@login_required
@change_password_required
def editar_persona(id):

    asegurar_csrf_token()
    conn = None

    try:

        conn = get_db_connection()

        persona = conn.execute(
            """
            SELECT id, nombre, activo
            FROM personas
            WHERE id = %s
            """,
            (id,)
        ).fetchone()

        if not persona:
            abort(404)

        # Obtener URL de origen (next) del query param, fallback según activo
        volver_url = request.args.get("next")
        if not volver_url:
            volver_url = url_for("personas") if persona["activo"] == 1 else url_for("personas_inactivas")

        if request.method == "POST":

            validar_csrf()

            nombre = request.form.get("nombre", "")
            nombre = _normalizar_nombre(nombre)

            if not nombre:
                flash("Nombre inválido", "error")
                return redirect(url_for("editar_persona", id=id, next=volver_url))

            if nombre == persona["nombre"]:
                flash("No se realizaron cambios", "warning")
                return redirect(url_for("editar_persona", id=id, next=volver_url))

            existe = conn.execute(
                """
                SELECT 1
                FROM personas
                WHERE nombre = %s
                AND id != %s
                """,
                (nombre, id)
            ).fetchone()

            if existe:
                flash("Ya existe una persona con ese nombre", "error")
                return redirect(url_for("editar_persona", id=id, next=volver_url))

            conn.execute(
                """
                UPDATE personas
                SET nombre = %s
                WHERE id = %s
                """,
                (nombre, id)
            )

            conn.commit()
            flash("Nombre actualizado correctamente", "success")

            # Redirigir al origen o fallback
            return redirect(volver_url)

        return render_template(
            "admin/editar_persona.html",
            persona=persona,
            volver_url=volver_url  # enviar al template para el botón "Volver"
        )

    except DATABASE_ERRORS:

        if conn:
            conn.rollback()

        app.logger.exception("Error en la base de datos al editar persona")
        flash("Ocurrió un error interno", "error")
        return redirect(url_for("personas"))

    finally:
        if conn:
            conn.close()


# =============================================================================
# EJECUCIÓN
# =============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)