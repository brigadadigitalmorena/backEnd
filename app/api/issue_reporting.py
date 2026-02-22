"""
Issue reporting email service endpoints.

Security:
  - Requires authentication (AnyUser).
  - Rate-limited to 3 requests/minute per IP.
  - HTML-escapes all user-supplied text before embedding in the email body.
  - Recipient is server-side only (not user-controlled).
"""
import html
import logging

import resend
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.limiter import limiter
from app.api.dependencies import AnyUser

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY

ISSUE_REPORT_RECIPIENT = "brigadadigitalmorena@gmail.com"

router = APIRouter(prefix="/api/email", tags=["email"])


class IssueReportRequest(BaseModel):
    subject: str
    body: str


@router.post("/send-issue-report")
@limiter.limit("3/minute")
async def send_issue_report(
    request: Request,
    payload: IssueReportRequest,
    current_user: AnyUser,
):
    """
    Send an issue report email via Resend.

    - **Authentication required** (Bearer token).
    - Sender identity is taken from the authenticated user — cannot be spoofed.
    - The recipient address is fixed on the server side.
    """
    safe_subject = html.escape(payload.subject)
    safe_body = html.escape(payload.body)
    sender_email = html.escape(current_user.email)

    try:
        email_html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #d32f2f;">Reporte de Problema</h2>
            <p><strong>Asunto:</strong> {safe_subject}</p>
            <p><strong>Reportado por:</strong> {sender_email}</p>
            <hr style="border: 1px solid #eee; margin: 20px 0;" />
            <h3>Descripción:</h3>
            <p style="white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 4px;">{safe_body}</p>
          </body>
        </html>
        """

        response = resend.Emails.send(
            {
                "from": settings.FROM_EMAIL,
                "to": ISSUE_REPORT_RECIPIENT,
                "subject": f"[Brigada] {safe_subject}",
                "html": email_html,
                "reply_to": current_user.email,
            }
        )

        return {
            "message": "Email enviado exitosamente",
            "id": response.get("id"),
        }

    except Exception:
        logger.exception("Failed to send issue-report email for user %s", current_user.id)
        raise HTTPException(
            status_code=500,
            detail="Error enviando el reporte. Intenta de nuevo más tarde.",
        )
