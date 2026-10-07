import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from flask import current_app
from app.utils import create_notification, get_setting

logger = logging.getLogger(__name__)


def send_in_app_notification(
    title: str,
    message: str,
    type: str = 'info',
    student_id: Optional[int] = None,
    user_id: Optional[int] = None
):
    """Dispatches in-app notification to student or user."""
    create_notification(title=title, message=message, type=type, student_id=student_id, user_id=user_id)


def send_email_notification(
    recipient_email: str,
    subject: str,
    html_body: str
) -> bool:
    """
    Sends email via configured SMTP settings if SMTP is enabled in config or settings.
    Never crashes application if SMTP fails.
    """
    try:
        smtp_enabled = current_app.config.get('SMTP_ENABLED', False)
        if not smtp_enabled:
            logger.info(f"SMTP disabled. Skipping email to {recipient_email}: {subject}")
            return False

        host = current_app.config.get('SMTP_HOST')
        port = current_app.config.get('SMTP_PORT', 587)
        user = current_app.config.get('SMTP_USERNAME')
        password = current_app.config.get('SMTP_PASSWORD')
        sender = current_app.config.get('SMTP_FROM', 'no-reply@smartattendance.edu')

        if not host or not user or not password:
            logger.warning("SMTP configuration incomplete. Skipping email dispatch.")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient_email

        part = MIMEText(html_body, 'html')
        msg.attach(part)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [recipient_email], msg.as_string())

        logger.info(f"Email successfully sent to {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False
