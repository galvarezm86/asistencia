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