"""
Issue reporting email service endpoints
"""
import resend
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY

router = APIRouter(prefix="/api/email", tags=["email"])


class IssueReportRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    user_email: EmailStr


@router.post("/send-issue-report")
async def send_issue_report(request: IssueReportRequest):
    """Send an issue report email via Resend."""
    try:
        email_html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #d32f2f;">Reporte de Problema</h2>
            <p><strong>Asunto:</strong> {request.subject}</p>
            <p><strong>Reportado por:</strong> {request.user_email}</p>
            <hr style="border: 1px solid #eee; margin: 20px 0;" />
            <h3>Descripción:</h3>
            <p style="white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 4px;">{request.body}</p>
          </body>
        </html>
        """

        response = resend.Emails.send(
            {
                "from": settings.FROM_EMAIL,
                "to": request.to_email,
                "subject": request.subject,
                "html": email_html,
                "reply_to": request.user_email,
            }
        )

        return {
            "message": "Email enviado exitosamente",
            "id": response.get("id"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enviando email: {str(e)}")
