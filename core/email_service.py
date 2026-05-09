"""
core/email_service.py
---------------------
Email service router.

Supports multiple email providers. The active provider is
determined by the EMAIL_PROVIDER environment variable:

    EMAIL_PROVIDER=gmail    → Gmail SMTP (default, for local dev)
    EMAIL_PROVIDER=resend   → Resend HTTP API (for production)
    EMAIL_PROVIDER=zoho     → Zoho SMTP (future option)

All providers use the same function signatures, so the rest
of the app doesn't need to know which provider is active.
"""

import os
import logging

api_logger = logging.getLogger('api')

# Which provider to use — read from environment
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'gmail')


def send_email(to_email, subject, html_body, text_body):
    """
    Send an email using the configured provider.

    Routes to the correct provider based on EMAIL_PROVIDER env var.
    All providers return True on success, False on failure.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_body: HTML version of the email
        text_body: Plain text fallback

    Returns:
        True if sent successfully, False if failed
    """
    if EMAIL_PROVIDER == 'resend':
        return _send_via_resend(to_email, subject, html_body, text_body)
    elif EMAIL_PROVIDER == 'zoho':
        return _send_via_zoho(to_email, subject, html_body, text_body)
    else:
        # Default: Gmail SMTP via Django's email backend
        return _send_via_django_smtp(to_email, subject, html_body, text_body)


def _send_via_resend(to_email, subject, html_body, text_body):
    """
    Send email using Resend's HTTP API.

    Uses HTTPS (port 443) — works on all hosting platforms
    including Railway where SMTP ports are blocked.

    Requires RESEND_API_KEY in environment variables.
    Sends from: no-reply@rewright.app
    """
    try:
        import resend

        resend.api_key = os.environ.get('RESEND_API_KEY', '')

        if not resend.api_key:
            api_logger.error('RESEND_API_KEY not set in environment')
            return False

        from_email = os.environ.get('RESEND_FROM_EMAIL', 'Rewright <no-reply@rewright.app>')

        params = {
            'from': from_email,
            'to': [to_email],
            'subject': subject,
            'html': html_body,
            'text': text_body,
        }

        resend.Emails.send(params)
        return True
    except Exception as e:
        api_logger.error(f'RESEND EMAIL FAILED | to={to_email} | error={str(e)}')
        return False


def _send_via_django_smtp(to_email, subject, html_body, text_body):
    """
    Send email using Django's SMTP backend.

    Uses whatever SMTP settings are configured in settings.py
    (Gmail by default, or console backend if no credentials).

    Works locally but may fail on hosting platforms that block
    SMTP ports (587, 465).
    """
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        api_logger.error(f'SMTP EMAIL FAILED | to={to_email} | error={str(e)}')
        return False


def _send_via_zoho(to_email, subject, html_body, text_body):
    """
    Send email using Zoho SMTP.

    Placeholder for future implementation.
    Uses SMTP on port 465 with SSL.

    Requires ZOHO_EMAIL and ZOHO_PASSWORD in environment variables.
    """
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        zoho_email = os.environ.get('ZOHO_EMAIL', '')
        zoho_password = os.environ.get('ZOHO_PASSWORD', '')

        if not zoho_email or not zoho_password:
            api_logger.error('ZOHO_EMAIL or ZOHO_PASSWORD not set in environment')
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'Rewright <{zoho_email}>'
        msg['To'] = to_email

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            server.login(zoho_email, zoho_password)
            server.send_message(msg)

        return True
    except Exception as e:
        api_logger.error(f'ZOHO EMAIL FAILED | to={to_email} | error={str(e)}')
        return False