"""
humanizer/urls.py
-----------------
The root URL configuration for the entire project.

When a request comes in, Django looks here first to decide
which app should handle it.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib import messages


def inactive_redirect(request):
    """Catch allauth's inactive redirect and send to our login page."""
    messages.error(
        request,
        'Your account has been restricted. Please contact an admin if you believe this is a mistake.'
    )
    return redirect('/login/')


urlpatterns = [
    # Catch allauth's inactive redirect BEFORE allauth handles it
    path('accounts/inactive/', inactive_redirect, name='account_inactive'),

    # Django's built-in admin panel at /admin/
    path('admin/', admin.site.urls),

    # Allauth social auth URLs (handles Google OAuth callback)
    path('accounts/', include('allauth.urls')),

    # Everything else goes to our core app's urls.py
    path('', include('core.urls')),
]