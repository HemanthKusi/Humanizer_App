"""
core/email_utils.py
-------------------
Helper functions for sending emails.

Keeps email logic separate from views so it's easy to
test, modify, and reuse.
"""

from django.core.mail import send_mail
from django.conf import settings
import logging

api_logger = logging.getLogger('api')


def send_verification_email(user, code):
    """
    Send a verification OTP code to the user's email.

    Args:
        user: The User object
        code: The 6-digit OTP code string

    Returns:
        True if sent successfully, False if failed
    """
    subject = f'Rewright — Your verification code is {code}'

    message = (
        f'Hi {user.username},\n\n'
        f'Your verification code is: {code}\n\n'
        f'Enter this code on the verification page to confirm your email.\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not create an account on Rewright, please ignore this email.\n\n'
        f'— Rewright'
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        api_logger.info(
            f'VERIFICATION EMAIL SENT | user={user.username} (id={user.id}) | '
            f'email={user.email}'
        )
        return True
    except Exception as e:
        api_logger.error(
            f'VERIFICATION EMAIL FAILED | user={user.username} (id={user.id}) | '
            f'email={user.email} | error={str(e)}'
        )
        return False