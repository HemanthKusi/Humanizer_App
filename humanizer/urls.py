"""
humanizer/urls.py
-----------------
The root URL configuration for the entire project.

When a request comes in, Django looks here first to decide
which app should handle it.

Think of this like a traffic controller:
- Request comes in for "/"      → send to core app
- Request comes in for "/admin" → send to Django admin
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django's built-in admin panel at /admin/
    path('admin/', admin.site.urls),

    # Everything else goes to our core app's urls.py
    # include() means "go look in core/urls.py for more routes"
    path('', include('core.urls')),
]