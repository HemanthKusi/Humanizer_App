"""
core/email_utils.py
-------------------
Helper functions for sending emails.

Uses Django's HTML email support to send professional-looking
emails with the Rewright branding.
"""

from .email_service import send_email
import logging

api_logger = logging.getLogger('api')


def _build_otp_email_html(username, code, purpose='verify'):
    """
    Build a professional HTML email template with the OTP code.

    The template is inline-styled because most email clients
    strip <style> tags. Gmail, Outlook, Apple Mail all require
    inline CSS for reliable rendering.

    Args:
        username: The user's username
        code: The 6-digit OTP code
        purpose: 'verify' for email verification, 'password' for password reset

    Returns:
        HTML string for the email body
    """
    if purpose == 'verify':
        heading = 'Verify your email'
        instruction = 'Enter this code on the verification page to confirm your email address.'
    elif purpose == 'password':
        heading = 'Reset your password'
        instruction = 'Enter this code on the password reset page to set a new password.'
    elif purpose == 'email_change':
        heading = 'Confirm your new email'
        instruction = 'Enter this code to confirm this email address for your Rewright account.'
    elif purpose == 'identity':
        heading = 'Confirm your identity'
        instruction = 'You requested to change your email. Enter this code to verify your current email first.'
    else:
        heading = 'Your verification code'
        instruction = 'Enter this code to continue.'

    return f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0; padding:0; background-color:#f4f1ec; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f1ec; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.06);">

                        <!-- Logo bar -->
                        <tr>
                            <td style="background-color:#1a1a2e; padding: 20px 30px; text-align:center;">
                                <img src="https://rewright.app/static/core/logo-email.png" alt="Rewright" width="28" height="28" style="display:inline-block; vertical-align:middle; margin-right:8px; border:0;" />
                                <span style="font-size:22px; font-weight:700; color:#e8a24e; letter-spacing:0.5px; vertical-align:middle;">
                                    Rewright
                                </span>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td style="padding: 36px 30px 20px;">
                                <h1 style="margin:0 0 8px; font-size:22px; font-weight:700; color:#1a1a1a; text-align:center;">
                                    {heading}
                                </h1>
                                <p style="margin:0 0 28px; font-size:14px; color:#6b7280; text-align:center; line-height:1.6;">
                                    Hi {username}, here is your verification code.
                                </p>

                                <!-- OTP Code box -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center">
                                            <div style="background-color:#fdf8f3; border:2px dashed #e8a24e; border-radius:12px; padding:20px 40px; display:inline-block;">
                                                <span style="font-size:36px; font-weight:800; letter-spacing:12px; color:#1a1a1a; font-family: 'Courier New', monospace;">
                                                    {code}
                                                </span>
                                            </div>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin:24px 0 0; font-size:13px; color:#6b7280; text-align:center; line-height:1.6;">
                                    {instruction}<br>
                                    This code expires in <strong>10 minutes</strong>.
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="padding: 20px 30px 28px; border-top:1px solid #f0ebe4;">
                                <p style="margin:0; font-size:12px; color:#9ca3af; text-align:center; line-height:1.5;">
                                    If you did not request this code, you can safely ignore this email.<br>
                                    &copy; Rewright — Make AI writing actually good.
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''


def send_verification_email(user, code):
    """
    Send a verification OTP code to the user's email.

    Sends both HTML and plain text versions. Email clients
    that support HTML show the styled version; others fall
    back to plain text.

    Args:
        user: The User object
        code: The 6-digit OTP code string

    Returns:
        True if sent successfully, False if failed
    """
    subject = 'Rewright — Verify your email'

    # Plain text fallback for email clients that don't render HTML
    text_body = (
        f'Hi {user.username},\n\n'
        f'Your verification code is: {code}\n\n'
        f'Enter this code on the verification page to confirm your email.\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not create an account on Rewright, please ignore this email.\n\n'
        f'— Rewright'
    )

    html_body = _build_otp_email_html(user.username, code, purpose='verify')

    result = send_email(user.email, subject, html_body, text_body)

    if result:
        api_logger.info(
            f'VERIFICATION EMAIL SENT | user={user.username} (id={user.id}) | '
            f'email={user.email}'
        )
    else:
        api_logger.error(
            f'VERIFICATION EMAIL FAILED | user={user.username} (id={user.id}) | '
            f'email={user.email}'
        )

    return result


def send_email_change_verification(user, new_email, code):
    """
    Send a verification OTP code to the NEW email address
    when a user wants to change their email.

    Args:
        user: The User object
        new_email: The new email address to verify
        code: The 6-digit OTP code string

    Returns:
        True if sent successfully, False if failed
    """
    subject = 'Rewright — Confirm your new email'

    text_body = (
        f'Hi {user.username},\n\n'
        f'Your verification code is: {code}\n\n'
        f'Enter this code on Rewright to confirm this as your new email address.\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not request this change, please ignore this email.\n\n'
        f'— Rewright'
    )

    html_body = _build_otp_email_html(user.username, code, purpose='email_change')

    result = send_email(new_email, subject, html_body, text_body)

    if result:
        api_logger.info(
            f'EMAIL CHANGE VERIFICATION SENT | user={user.username} (id={user.id}) | '
            f'new_email={new_email}'
        )
    else:
        api_logger.error(
            f'EMAIL CHANGE VERIFICATION FAILED | user={user.username} (id={user.id}) | '
            f'new_email={new_email}'
        )

    return result
    
def send_current_email_verification(user, code):
    """
    Send OTP to the user's CURRENT email to prove ownership
    before allowing an email change.

    Args:
        user: The User object
        code: The 6-digit OTP code

    Returns:
        True if sent, False if failed
    """
    subject = 'Rewright — Verify your identity'

    text_body = (
        f'Hi {user.username},\n\n'
        f'You requested to change your email address.\n'
        f'Your verification code is: {code}\n\n'
        f'Enter this code to confirm your identity before changing your email.\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not request this, please ignore this email.\n\n'
        f'— Rewright'
    )

    html_body = _build_otp_email_html(user.username, code, purpose='identity')

    result = send_email(user.email, subject, html_body, text_body)

    if result:
        api_logger.info(
            f'IDENTITY VERIFICATION SENT | user={user.username} (id={user.id}) | '
            f'email={user.email}'
        )
    else:
        api_logger.error(
            f'IDENTITY VERIFICATION FAILED | user={user.username} (id={user.id}) | '
            f'email={user.email}'
        )

    return result
    
def send_password_reset_email(email, code):
    """
    Send a password reset OTP code.

    Note: we send to the email address provided, not to a user object.
    This is intentional — we don't confirm whether an account exists.

    Args:
        email: The email address to send to
        code: The 6-digit OTP code

    Returns:
        True if sent, False if failed
    """
    subject = 'Rewright — Reset your password'

    # Extract username-like part from email for the greeting
    name = email.split('@')[0]

    text_body = (
        f'Hi {name},\n\n'
        f'Your password reset code is: {code}\n\n'
        f'Enter this code on the password reset page to set a new password.\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not request a password reset, please ignore this email.\n\n'
        f'— Rewright'
    )

    html_body = _build_otp_email_html(name, code, purpose='password')

    result = send_email(email, subject, html_body, text_body)

    if result:
        api_logger.info(f'PASSWORD RESET EMAIL SENT | email={email}')
    else:
        api_logger.error(f'PASSWORD RESET EMAIL FAILED | email={email}')

    return result