import os
import resend

resend.api_key = os.environ["RESEND_API_KEY"]


def send_email_with_attachment(
    to_email,
    subject,
    html_content,
    file_bytes=None,
    filename=None,
    mime_type=None
):

    attachments = []

    if file_bytes and filename:

        import base64

        attachments.append({
            "filename": filename,
            "content": base64.b64encode(file_bytes).decode("utf-8")
        })

    params = {
        "from": os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    if attachments:
        params["attachments"] = attachments

    try:
        response = resend.Emails.send(params)
        return response

    except Exception as e:
        print("Error enviando email:", e)
        return None

def send_password_reset_request(username, panel_url):

    html_content = f"""
    <h2>Solicitud de restablecimiento de contraseña</h2>
    
    <p>
        Se ha solicitado restablecer la contraseña del siguiente usuario:
    </p>
    
    <p>
        <strong>{username}</strong>
    </p>
    
    <p>
        Ingresa al <a href="{panel_url}"> Panel de administración </a> para revisar la solicitud.
    </p>
    
    """
    
    return send_email_with_attachment(
        to_email=os.environ["ADMIN_EMAIL"],
        subject="Solicitud de restablecimiento de contraseña",
        html_content=html_content
    )

def send_superadmin_reset_email(
    username,
    password_temp,
    to_email
):
    """
    Envía una contraseña temporal generada
    para recuperación del superadmin.
    """

    html_content = f"""
    <h2>Restablecimiento de contraseña</h2>

    <p>
        Se solicitó un restablecimiento de contraseña
        para el usuario <strong>{username}</strong>.
    </p>

    <p>
        Se ha generado una contraseña temporal:
    </p>

    <p>
        <strong>{password_temp}</strong>
    </p>

    <p>
        Ingresa al sistema utilizando esta contraseña.
        Al iniciar sesión se solicitará cambiarla.
    </p>

    <p>
        Si no realizaste esta solicitud, revisa la seguridad
        del sistema.
    </p>
    """

    params = {
        "from": os.environ.get(
            "RESEND_FROM_EMAIL",
            "onboarding@resend.dev"
        ),
        "to": [to_email],
        "subject": "Restablecimiento de contraseña de superadmin",
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        return response

    except Exception as e:
        print("Error enviando correo de superadmin:", e)
        return None