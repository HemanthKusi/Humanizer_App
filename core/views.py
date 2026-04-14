"""
core/views.py
-------------
Views handle web requests and return responses.

Two views:
1. index()     — Serves the homepage (GET)
2. humanize()  — API endpoint that processes text (POST)

The humanize view now supports two modes:
    - deep_rewrite: false → Rule-based only (instant, free)
    - deep_rewrite: true  → LLM rewrite (2-5 sec, costs ~$0.002)

The toggle switch on the frontend controls which mode is used.
"""

import json

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from core.humanizer_engine import humanize_rule_based
from core.llm_engine import humanize_with_llm


def index(request: HttpRequest) -> HttpResponse:
    """
    Renders the homepage of the humanizer app.

    Args:
        request: The incoming HTTP request

    Returns:
        The rendered index.html template
    """
    context = {}
    return render(request, 'core/index.html', context)


@csrf_exempt
@require_POST
def humanize(request: HttpRequest) -> JsonResponse:
    """
    API endpoint: humanize text using rule-based and/or LLM engine.

    The frontend sends:
        {
            "text": "...",
            "deep_rewrite": true/false
        }

    Flow when deep_rewrite is FALSE:
        1. Run rule-based engine only
        2. Return cleaned text + changes report

    Flow when deep_rewrite is TRUE:
        1. Send text to LLM for deep rewriting
        2. Return LLM-rewritten text

    Args:
        request: The incoming HTTP POST request

    Returns:
        JsonResponse with humanized text, changes, and stats
    """
    try:
        # Parse the JSON body
        body = json.loads(request.body.decode('utf-8'))

        # Extract fields
        # Extract fields
        text = body.get('text', '').strip()
        deep_rewrite = body.get('deep_rewrite', False)
        voice_sample = body.get('voice_sample', '').strip()

        # Validate: no empty text
        if not text:
            return JsonResponse(
                {'error': 'No text provided. Please paste some text to humanize.'},
                status=400
            )

        # Validate: length limit
        if len(text) > 50000:
            return JsonResponse(
                {'error': 'Text is too long. Please keep it under 50,000 characters.'},
                status=400
            )

        # ── Step 1: Always run rule-based engine first ──
        rule_result = humanize_rule_based(text)

        # If toggle is OFF, return rule-based result only
        if not deep_rewrite:
            return JsonResponse({
                'text': rule_result['text'],
                'changes': rule_result['changes'],
                'stats': rule_result['stats'],
                'mode': 'rule-based',
            })

        # ── Step 2: Toggle is ON — send text to LLM ──
        try:
            llm_result = humanize_with_llm(text, voice_sample=voice_sample)
        except Exception as llm_error:
            # If the LLM fails, return the rule-based result as fallback
            # with a warning so the user knows the LLM part failed
            return JsonResponse({
                'text': rule_result['text'],
                'changes': rule_result['changes'],
                'stats': rule_result['stats'],
                'mode': 'rule-based (LLM failed)',
                'warning': f'Deep rewrite failed: {str(llm_error)}. '
                           f'Showing rule-based result instead.',
            })

        # Compute final stats comparing original to LLM output
        original_word_count = len(text.split())
        final_word_count = len(llm_result['text'].split())

        stats = {
            'original_words': original_word_count,
            'final_words': final_word_count,
            'words_removed': original_word_count - final_word_count,
            'patterns_found': len(rule_result['changes']),
        }

        return JsonResponse({
            'text': llm_result['text'],
            'changes': rule_result['changes'],
            'stats': stats,
            'mode': f"AI editor ({llm_result['model']})",
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON in request body.'},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {'error': f'Something went wrong: {str(e)}'},
            status=500
        )