"""
core/context_processors.py
--------------------------
Custom template context processors.

Context processors run on every request and inject variables
into every template automatically. This avoids passing the
same data manually in every view function.

Currently provides:
    - GOOGLE_ANALYTICS_ID: for the tracking script in templates
"""

import os


def global_context(request):
    """
    Add global variables available in all templates.

    Returns:
        Dictionary of variables injected into every template context.
    """
    return {
        'GOOGLE_ANALYTICS_ID': os.environ.get('GOOGLE_ANALYTICS_ID', ''),
    }