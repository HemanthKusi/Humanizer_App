"""
core/urls.py
------------
URL routes specific to our core app.

This file lists which URL paths map to which view functions.
Django reads this after being pointed here from humanizer/urls.py.

Pattern:
    path('url-pattern/', view_function, name='name-for-this-route')

We now have two routes:
    /              → index view (homepage)
    /api/humanize/ → humanize view (API endpoint)
"""

from django.urls import path
from . import views  # Import views from this same app (the dot means "current folder")

urlpatterns = [
    # The empty string '' means the root URL: yoursite.com/
    # views.index is the function we will write in views.py
    # name='index' lets us refer to this URL by name in templates
    path('', views.index, name='index'),
    # API endpoint — receives text, returns humanized JSON
    # The frontend calls this with fetch() when the user clicks Humanize
    path('api/humanize/', views.humanize, name='humanize'),
    # API endpoint — returns usage stats for the current user
    # This is used by the frontend to show usage info on the homepage
    path('api/usage/', views.usage, name='usage'),
    # API endpoint — generates a downloadable file from the rewritten text
    # This is called when the user clicks "Download" after rewriting.
    path('api/download/', views.download, name='download'),
]