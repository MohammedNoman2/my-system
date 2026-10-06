import logging
from email.message import EmailMessage
import aiosmtplib
from app.core.config import settings

logger = logging.getLogger("arp.email")


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    subject = "ARP Platform - إعادة تعيين كلمة المرور"
    body = f"""مرحباً،

لقد تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك في منصة ARP.
يمكنك إعادة تعيين كلمة المرور بالنقر على الرابط التالي (صالح لمدة ساعة واحدة):

{reset_url}

إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذه الرسالة.

مع تحيات إدارة النظام.
"""

    # Check if SMTP is configured
    if not settings.SMTP_HOST:
        logger.warning(
            f"⚠️ [SMTP NOT CONFIGURED] Password reset requested for {to_email}. "
            f"Reset Link: {reset_url}"
        )
        print(f"\n=======================================================")
        print(f"📧 [EMAIL FALLBACK - SMTP NOT CONFIGURED]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Password Reset URL: {reset_url}")
        print(f"=======================================================\n")
        return True

    try:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_TLS,
        )
        logger.info(f"Password reset email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send email to {to_email} via SMTP: {e}. "
            f"Fallback Reset Link: {reset_url}"
        )
        print(f"\n=======================================================")
        print(f"📧 [EMAIL FALLBACK - SMTP FAILED]")
        print(f"To: {to_email}")
        print(f"Reset Link: {reset_url}")
        print(f"=======================================================\n")
        return True
