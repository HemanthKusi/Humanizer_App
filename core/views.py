"""
core/views.py
-------------
Views are Python functions that handle web requests and return responses.

The flow is:
    1. User visits a URL
    2. Django matches it to a URL pattern in urls.py
    3. Django calls the view function mapped to that URL
    4. The view function does some logic (optional)
    5. The view function returns an HTTP response (usually renders an HTML template)

This is the heart of our application logic.
"""

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse


def index(request: HttpRequest) -> HttpResponse:
    """
    Renders the homepage of the humanizer app.

    What it does:
        Receives a GET request for the root URL '/'
        Returns the rendered index.html template

    Args:
        request (HttpRequest): The incoming HTTP request object.
                               Contains info about the user, method, data, etc.

    Returns:
        HttpResponse: The rendered HTML page sent back to the browser.
    """

    # context is a dictionary we pass to the template
    # The template can display any values we put here
    # For now it's empty, but we will add data here later
    context = {}

    # render() does three things:
    # 1. Finds the template file (core/templates/core/index.html)
    # 2. Fills in the template with our context data
    # 3. Returns it as an HTTP response
    return render(request, 'core/index.html', context)