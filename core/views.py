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

import logging
import time
api_logger = logging.getLogger('api')


import json

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from core.humanizer_engine import humanize_rule_based
from core.llm_engine import humanize_with_llm

from core.sanitizer import sanitize_input

from core.middleware import request_tracker


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
    request_start = time.time()

    try:
        # Parse the JSON body
        body = json.loads(request.body.decode('utf-8'))

        # Extract and sanitize fields
        # Sanitization happens BEFORE length validation so attackers
        # can't bypass limits with invisible characters.
        raw_text = body.get('text', '')
        raw_voice = body.get('voice_sample', '')
        deep_rewrite = body.get('deep_rewrite', False)

        # Sanitize input text
        if raw_text:
            text_result = sanitize_input(raw_text)
            text = text_result['text']
            if text_result['profanity_flagged']:
                security_logger = logging.getLogger('security')
                security_logger.warning(
                    f'PROFANITY | ip={request.META.get("REMOTE_ADDR")} | '
                    f'field=input | words={text_result["flagged_words"]}'
                )
                return JsonResponse(
                    {
                        'error': 'Your text contains inappropriate language. Please remove the highlighted words and try again.',
                        'flagged_words': text_result['flagged_words'],
                        'field': 'input',
                    },
                    status=400
                )
        else:
            text = ''

        # Sanitize voice sample
        if raw_voice:
            voice_result = sanitize_input(raw_voice)
            voice_sample = voice_result['text']
            if voice_result['profanity_flagged']:
                security_logger = logging.getLogger('security')
                security_logger.warning(
                    f'PROFANITY | ip={request.META.get("REMOTE_ADDR")} | '
                    f'field=voice | words={voice_result["flagged_words"]}'
                )
                return JsonResponse(
                    {
                        'error': 'Your writing sample contains inappropriate language. Please remove the highlighted words and try again.',
                        'flagged_words': voice_result['flagged_words'],
                        'field': 'voice',
                    },
                    status=400
                )
        else:
            voice_sample = ''

        # Validate: no empty text
        if not text:
            api_logger.warning(
                f'EMPTY INPUT | ip={request.META.get("REMOTE_ADDR")}'
            )
            return JsonResponse(
                {'error': 'No text provided. Please paste some text to humanize.'},
                status=400
            )

        # Validate: length limit
        # Validate: length limit
        if len(text) > 5000:
            return JsonResponse(
                {'error': 'Text is too long. Please keep it under 5,000 characters.'},
                status=400
            )

        # ── Step 1: Always run rule-based engine first ──
        rule_result = humanize_rule_based(text)

        # If toggle is OFF, return rule-based result only
        if not deep_rewrite:
            duration = round(time.time() - request_start, 2)
            api_logger.info(
                f'QUICK FIX | ip={request.META.get("REMOTE_ADDR")} | '
                f'input_words={len(text.split())} | '
                f'output_words={len(rule_result["text"].split())} | '
                f'patterns={len(rule_result["changes"])} | '
                f'duration={duration}s'
            )
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
            # Log the real error server-side for debugging
            duration = round(time.time() - request_start, 2)
            api_logger.error(
                f'LLM FAILED | ip={request.META.get("REMOTE_ADDR")} | '
                f'error={str(llm_error)} | '
                f'duration={duration}s'
            )

            # Return a safe generic message to the user
            # NEVER expose the raw error — it might contain API keys
            return JsonResponse({
                'text': rule_result['text'],
                'changes': rule_result['changes'],
                'stats': rule_result['stats'],
                'mode': 'rule-based (LLM unavailable)',
                'warning': 'Deep rewrite is temporarily unavailable. '
                           'Showing rule-based result instead.',
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

        duration = round(time.time() - request_start, 2)
        has_voice = 'yes' if voice_sample else 'no'
        api_logger.info(
            f'DEEP REWRITE | ip={request.META.get("REMOTE_ADDR")} | '
            f'input_words={len(text.split())} | '
            f'output_words={len(llm_result["text"].split())} | '
            f'voice_match={has_voice} | '
            f'model={llm_result["model"]} | '
            f'duration={duration}s'
        )

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
        api_logger.error(
            f'UNHANDLED ERROR | ip={request.META.get("REMOTE_ADDR")} | '
            f'error={str(e)}'
        )

        return JsonResponse(
            {'error': 'Something went wrong. Please try again.'},
            status=500
        )
    
def usage(request: HttpRequest) -> JsonResponse:
    """
    API endpoint: returns current usage stats for this IP.

    The frontend calls this on page load and after each request
    to show the user how many requests they've used.

    Response format:
        {
            "minute": { "used": 3, "limit": 10 },
            "hourly": { "used": 12, "limit": 25 },
            "daily":  { "used": 18, "limit": 40 }
        }
    """

    now = time.time()

    # Get client IP (same logic as middleware)
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')

    # Get timestamps for this IP
    timestamps = request_tracker.get(ip, [])

    # Count requests in each window
    minute_count = len([t for t in timestamps if now - t < 60])
    hourly_count = len([t for t in timestamps if now - t < 3600])
    daily_count = len([t for t in timestamps if now - t < 86400])

    return JsonResponse({
        'minute': {'used': minute_count, 'limit': 10},
        'hourly': {'used': hourly_count, 'limit': 25},
        'daily': {'used': daily_count, 'limit': 40},
    })