"""
core/views.py
-------------
Views handle web requests and return responses.

We now have TWO views:
1. index()     — Serves the homepage HTML (GET request)
2. humanize()  — API endpoint that processes text (POST request)

The humanize view receives text from the frontend via JavaScript fetch(),
runs it through the rule-based engine, and returns JSON.

Why JSON?
    Because the frontend uses JavaScript to call this endpoint
    without reloading the page. This is called AJAX.
    The frontend sends text → the backend returns JSON → JavaScript
    updates the page with the result.
"""

import json

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from core.humanizer_engine import humanize_rule_based


def index(request: HttpRequest) -> HttpResponse:
    """
    Renders the homepage of the humanizer app.

    What it does:
        Serves the main HTML page with the two-panel UI.
        All the interactive behavior is handled by JavaScript
        in main.js, which calls the /api/humanize/ endpoint.

    Args:
        request: The incoming HTTP request

    Returns:
        The rendered index.html template
    """
    context = {}
    return render(request, 'core/index.html', context)


@csrf_exempt      # We'll handle CSRF properly later; for now this lets us test
@require_POST     # Only accept POST requests, reject GET/PUT/DELETE
def humanize(request: HttpRequest) -> JsonResponse:
    """
    API endpoint: receives text, runs rule-based humanization, returns JSON.

    This is the backend half of the Humanize button.

    Flow:
        1. Frontend sends POST request with JSON body: {"text": "..."}
        2. This view extracts the text
        3. Passes it to humanize_rule_based() from our engine
        4. Returns the result as JSON

    Request format:
        POST /api/humanize/
        Content-Type: application/json
        Body: {"text": "Your AI-generated text here..."}

    Response format:
        {
            "text": "The humanized text...",
            "changes": [...list of changes...],
            "stats": {...summary stats...},
            "mode": "rule-based"
        }

    Args:
        request: The incoming HTTP POST request

    Returns:
        JsonResponse with humanized text, changes, and stats
    """
    try:
        # Parse the JSON body from the request
        # request.body is raw bytes, so we decode it to a string first
        body = json.loads(request.body.decode('utf-8'))

        # Extract the text field
        text = body.get('text', '').strip()

        # Validate: don't process empty text
        if not text:
            return JsonResponse(
                {'error': 'No text provided. Please paste some text to humanize.'},
                status=400  # 400 = Bad Request
            )

        # Validate: don't process extremely long text (prevent abuse)
        if len(text) > 50000:
            return JsonResponse(
                {'error': 'Text is too long. Please keep it under 50,000 characters.'},
                status=400
            )

        # Run the rule-based humanizer engine
        result = humanize_rule_based(text)

        # Return the result as JSON
        # "mode" tells the frontend which engine produced this result
        return JsonResponse({
            'text': result['text'],
            'changes': result['changes'],
            'stats': result['stats'],
            'mode': 'rule-based',
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON in request body.'},
            status=400
        )
    except Exception as e:
        # Catch any unexpected errors so the frontend gets a clean error
        return JsonResponse(
            {'error': f'Something went wrong: {str(e)}'},
            status=500  # 500 = Internal Server Error
        )