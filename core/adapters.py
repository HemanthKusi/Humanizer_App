"""
core/adapters.py
----------------
Custom adapter for django-allauth.

Overrides allauth's default behavior to use our custom
login and signup pages instead of allauth's built-in ones.
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import resolve_url
from django.conf import settings


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter that redirects allauth to our pages.
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
        Override allauth's login to handle restricted users.
        
        If the user is inactive (restricted), we DON'T log them in
        and instead store a flag in the session so our login view
        can show the warning message.
        """
        if not user.is_active:
            from django.contrib import messages
            messages.error(
                request,
                'Your account has been restricted. Please contact an admin if you believe this is a mistake.'
            )
            return
        super().login(request, user)