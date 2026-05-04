"""
core/urls.py
------------
URL routes specific to our core app.

This file lists which URL paths map to which view functions.
Django reads this after being pointed here from humanizer/urls.py.

Pattern:
    path('url-pattern/', view_function, name='name-for-this-route')

Routes:
    /              → Homepage
    /signup/       → Registration page
    /login/        → Login page
    /logout/       → Logout action (POST only)
    /api/humanize/ → Humanize text API
    /api/usage/    → Usage stats API
    /api/download/ → File download API
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Pages ──

    # The empty string '' means the root URL: yoursite.com/
    # views.index is the function we will write in views.py
    # name='index' lets us refer to this URL by name in templates
    path('', views.index, name='index'),
    # Registration page
    # The user sees this when they click "Sign Up" on the homepage.
    path('signup/', views.signup_view, name='signup'),
    # Login page
    # The user sees this when they click "Log In" on the homepage.
    path('login/', views.login_view, name='login'),
    # Logout action (POST only for security)
    # The user sees this when they click "Log Out" on their profile.
    path('logout/', views.logout_view, name='logout'),
    # Profile page
    # The user sees this when they click "Profile" on the homepage.
    path('profile/', views.profile_view, name='profile'),
    # Admin user management page
    # This is a custom admin page we create at /manage/users/ for staff users to manage user accounts.
    path('manage/users/', views.admin_users_view, name='admin_users'),
    # User settings page
    # The user sees this when they click "Settings" on their profile.
    path('settings/', views.settings_view, name='settings'),
    # Analytics page
    # The user sees this when they click "Analytics" on their profile.
    path('analytics/', views.analytics_view, name='analytics'),
    # Admin feedback management page
    # This is a custom admin page we create at /manage/feedback/ for staff users to manage user feedback.
    path('manage/feedback/', views.admin_feedback_view, name='admin_feedback'),
    # Admin analytics page
    # This is a custom admin page we create at /manage/analytics/ for staff users to view overall usage analytics.
    path('manage/analytics/', views.admin_analytics_view, name='admin_analytics'),
    # Email verification page
    # Users can enter their email OTP code here
    path('verify/', views.verify_email_view, name='verify_email'),
    # Users can request a password reset here
    # This is the view where users can enter their email to receive a password reset link
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),

    # ── API endpoints ──

    # API endpoint — receives text, returns humanized JSON
    # The frontend calls this with fetch() when the user clicks Humanize
    path('api/humanize/', views.humanize, name='humanize'),
    # API endpoint — returns usage stats for the current user
    # This is used by the frontend to show usage info on the homepage
    path('api/usage/', views.usage, name='usage'),
    # API endpoint — generates a downloadable file from the rewritten text
    # This is called when the user clicks "Download" after rewriting.
    path('api/download/', views.download, name='download'),
    # API endpoint — submits user feedback
    # This is called when the user clicks the feedback button.
    path('api/feedback/', views.feedback_api, name='feedback_api'),
]