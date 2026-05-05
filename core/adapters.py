"""
core/adapters.py
----------------
Custom adapters for django-allauth.

Two adapters:
1. CustomAccountAdapter — handles regular account behavior
   (redirects, restricted users, terms acceptance on login)
2. CustomSocialAccountAdapter — handles Google Sign-In behavior
   (auto-link to existing accounts, terms acceptance on signup)
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import resolve_url
from django.conf import settings
from django.utils import timezone


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter that redirects allauth to our pages
    and records terms acceptance for users who haven't accepted yet.
    """

    def get_login_redirect_url(self, request):
        """After login, go to homepage."""
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def get_logout_redirect_url(self, request):
        """After logout, go to homepage."""
        return resolve_url(settings.LOGOUT_REDIRECT_URL)

    def is_open_for_signup(self, request):
        """Allow signups."""
        return True

    def login(self, request, user):
        """
        Override allauth's login to handle restricted users
        and record terms acceptance for existing users.

        If the user is inactive (restricted), we DON'T log them in.
        If the user has never accepted terms, we record acceptance
        now — because by logging in they implicitly agree (terms
        note is shown on the login page under the Google button).
        """
        if not user.is_active:
            from django.contrib import messages
            messages.error(
                request,
                'Your account has been restricted. Please contact an admin if you believe this is a mistake.'
            )
            return

        # Record terms acceptance if not already recorded
        from core.models import UserPreferences
        prefs, created = UserPreferences.objects.get_or_create(user=user)
        if not prefs.terms_accepted_at:
            prefs.terms_accepted_at = timezone.now()
            prefs.save(update_fields=['terms_accepted_at'])

        super().login(request, user)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for social (Google) authentication.

    Handles two key scenarios:
    1. New Google user → create account, record terms acceptance
    2. Existing user with same email → auto-link the Google account
       to the existing account instead of showing an error page
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called after Google authenticates but BEFORE the user is
        logged in or an account is created.

        This is where we auto-link Google accounts to existing
        email accounts. Without this, allauth shows an error page
        when a user with an existing manual account tries Google Sign-In.

        How it works:
        1. Get the email from the Google account
        2. Check if a Django user with that email already exists
        3. If yes, connect the Google account to that existing user
        4. If no, let allauth create a new user as normal
        """
        # If the social account is already connected to a user, nothing to do
        if sociallogin.is_existing:
            return

        # Get email from the Google account
        email = None
        if sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get('email', '').lower().strip()

        if not email:
            # Try from email addresses provided by allauth
            for addr in sociallogin.email_addresses:
                if addr.email:
                    email = addr.email.lower().strip()
                    break

        if not email:
            return

        # Check if a user with this email already exists
        from django.contrib.auth.models import User
        try:
            existing_user = User.objects.get(email=email)
        except User.DoesNotExist:
            # No existing user — allauth will create a new one
            return
        except User.MultipleObjectsReturned:
            # Multiple users with same email (shouldn't happen but be safe)
            return

        # Connect the Google account to the existing user
        sociallogin.connect(request, existing_user)

        # Record terms acceptance if not yet recorded
        from core.models import UserPreferences, EmailVerification
        prefs, created = UserPreferences.objects.get_or_create(user=existing_user)
        if not prefs.terms_accepted_at:
            prefs.terms_accepted_at = timezone.now()
            prefs.save(update_fields=['terms_accepted_at'])

        # Mark email as verified since Google verified it
        from datetime import timedelta
        try:
            ev = EmailVerification.objects.get(user=existing_user)
            if not ev.is_verified:
                ev.is_verified = True
                ev.save(update_fields=['is_verified'])
        except EmailVerification.DoesNotExist:
            EmailVerification.objects.create(
                user=existing_user,
                code='000000',
                expires_at=timezone.now() + timedelta(minutes=1),
                is_verified=True,
            )

    def save_user(self, request, sociallogin, form=None):
        """
        Called when a NEW user is being created via Google Sign-In.

        We let allauth create the user normally, then:
        1. Record terms acceptance
        2. Mark email as verified (Google already verified it)
        """
        user = super().save_user(request, sociallogin, form)

        # Record terms acceptance for new Google users
        from core.models import UserPreferences, EmailVerification
        prefs, created = UserPreferences.objects.get_or_create(user=user)
        if not prefs.terms_accepted_at:
            prefs.terms_accepted_at = timezone.now()
            prefs.save(update_fields=['terms_accepted_at'])

        # Mark email as verified — Google already verified it
        from datetime import timedelta
        EmailVerification.objects.update_or_create(
            user=user,
            defaults={
                'code': '000000',
                'expires_at': timezone.now() + timedelta(minutes=1),
                'is_verified': True,
            }
        )

        return user