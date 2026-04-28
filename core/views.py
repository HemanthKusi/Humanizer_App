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

from .readability import flesch_reading_ease

from .language import detect_language

def track_usage(request):
    """
    Record a successful request in the rate limiter's tracker.
    Only call this AFTER a successful response is ready.
    """
    import time

    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')

    now = time.time()

    if ip not in request_tracker:
        request_tracker[ip] = []

    request_tracker[ip].append(now)

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
        tone = body.get('tone', 'default')

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

        # ── Detect input language ──
        language = detect_language(text)

        # ── Check voice sample language matches input language ──
        # If user provides a voice sample in a different language than
        # their input text, the LLM gets confused trying to match
        # an English style while writing in French. Block this early.
        if voice_sample:
            voice_lang = detect_language(voice_sample)
            if not language['is_english'] or not voice_lang['is_english']:
                if language['code'] != voice_lang['code']:
                    return JsonResponse({
                        'error': f"Your text is in {language['name']} but your writing sample is in {voice_lang['name']}. Please provide a writing sample in {language['name']} so the style matching works correctly.",
                        'field': 'voice',
                    }, status=400)

        # ── Step 1: Always run rule-based engine first ──
        rule_result = humanize_rule_based(text)

        # If toggle is OFF, return rule-based result only
        if not deep_rewrite:

            # Block non-English text in Quick Fix mode
            # Rule-based patterns are English-only, so results would be useless
            if not language['is_english']:
                return JsonResponse({
                    'error': f"Quick Fix only supports English. Your text appears to be in {language['name']}. Please enable Deep Rewrite to rewrite text in other languages.",
                    'language': language,
                    'language_unsupported': True,
                }, status=400)

            duration = round(time.time() - request_start, 2)
            track_usage(request)
            api_logger.info(
                f'QUICK FIX | ip={request.META.get("REMOTE_ADDR")} | '
                f'input_words={len(text.split())} | '
                f'output_words={len(rule_result["text"].split())} | '
                f'patterns={len(rule_result["changes"])} | '
                f'duration={duration}s'
            )

            # Calculate readability before and after
            original_readability = flesch_reading_ease(text)
            final_readability = flesch_reading_ease(rule_result['text'])

            return JsonResponse({
                'text': rule_result['text'],
                'changes': rule_result['changes'],
                'stats': rule_result['stats'],
                'readability': {
                    'original': original_readability,
                    'final': final_readability,
                },
                'language': language,
                'mode': 'rule-based',
            })

        # ── Step 2: Toggle is ON — send text to LLM ──
        try:
            llm_result = humanize_with_llm(text, voice_sample=voice_sample, tone=tone, language=language['name'])
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
        track_usage(request)
        api_logger.info(
            f'DEEP REWRITE | ip={request.META.get("REMOTE_ADDR")} | '
            f'input_words={len(text.split())} | '
            f'output_words={len(llm_result["text"].split())} | '
            f'voice_match={has_voice} | '
            f'model={llm_result["model"]} | '
            f'duration={duration}s'
        )

        # Calculate readability before and after
        original_readability = flesch_reading_ease(text)
        final_readability = flesch_reading_ease(llm_result['text'])

        return JsonResponse({
            'text': llm_result['text'],
            'changes': rule_result['changes'],
            'stats': stats,
            'readability': {
                'original': original_readability,
                'final': final_readability,
            },
            'language': language,
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

def download(request: HttpRequest) -> HttpResponse:
    """
    API endpoint: generates a downloadable file from the rewritten text.

    Accepts POST with:
        { "text": "...", "format": "txt" | "docx" | "pdf" }

    Returns the file as a download response.
    """
    import json

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body.decode('utf-8'))
        text = body.get('text', '').strip()
        file_format = body.get('format', 'txt').lower()

        if not text:
            return JsonResponse({'error': 'No text to download'}, status=400)

        if file_format == 'txt':
            response = HttpResponse(text, content_type='text/plain; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="rewright-output.txt"'
            return response

        elif file_format == 'docx':
            from docx import Document
            from docx.shared import Pt, Inches
            from io import BytesIO

            doc = Document()

            # Set default font
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Calibri'
            font.size = Pt(11)

            # Add paragraphs (split by double newlines)
            paragraphs = text.split('\n\n')
            for i, para_text in enumerate(paragraphs):
                para_text = para_text.strip()
                if para_text:
                    # Replace single newlines with spaces within paragraphs
                    para_text = para_text.replace('\n', ' ')
                    doc.add_paragraph(para_text)

            # Save to bytes
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = 'attachment; filename="rewright-output.docx"'
            return response

        elif file_format == 'pdf':
            from fpdf import FPDF
            from io import BytesIO

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=25)
            pdf.set_font('Helvetica', size=11)

            # Add text line by line
            paragraphs = text.split('\n\n')
            for i, para_text in enumerate(paragraphs):
                para_text = para_text.strip()
                if para_text:
                    para_text = para_text.replace('\n', ' ')
                    pdf.multi_cell(0, 6, para_text)
                    pdf.ln(4)  # Space between paragraphs

            buffer = BytesIO()
            pdf.output(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = 'attachment; filename="rewright-output.pdf"'
            return response

        else:
            return JsonResponse({'error': 'Invalid format. Use txt, docx, or pdf.'}, status=400)

    except Exception as e:
        import logging
        logging.getLogger('api').error(f'Download failed: {str(e)}')
        return JsonResponse({'error': 'Download failed. Please try again.'}, status=500)
    
# ═══════════════════════════════════════════════════════════════════
# AUTHENTICATION VIEWS
# ═══════════════════════════════════════════════════════════════════

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect
from .forms import SignUpForm, LoginForm


def signup_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user registration.

    GET:  Show the signup form
    POST: Validate the form, create the user, log them in, redirect to homepage

    How it works:
    1. User fills out username, email, password, confirm password
    2. Django validates all fields (our custom rules + built-in password validators)
    3. If valid: create the User object, hash the password, log them in automatically
    4. If invalid: re-render the form with error messages next to the bad fields

    Args:
        request: The incoming HTTP request

    Returns:
        GET:  Rendered signup.html with empty form
        POST (valid): Redirect to homepage (user is now logged in)
        POST (invalid): Rendered signup.html with form errors
    """
    # If user is already logged in, send them to homepage
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = SignUpForm(request.POST)

        if form.is_valid():
            # Create the user
            # create_user() handles password hashing automatically
            # NEVER store raw passwords — Django hashes with PBKDF2
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
            )

            # Log the user in immediately after signup
            # No need to make them go to a separate login page
            login(request, user)

            api_logger.info(
                f'SIGNUP | user={user.username} | email={user.email} | '
                f'ip={request.META.get("REMOTE_ADDR")}'
            )

            return redirect('index')
    else:
        # GET request — show empty form
        form = SignUpForm()

    return render(request, 'core/signup.html', {'form': form})


def login_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user login.

    GET:  Show the login form
    POST: Validate credentials, log the user in, redirect to homepage

    Supports login with either username OR email:
    1. Check if input looks like an email (contains @)
    2. If email: look up the username for that email, then authenticate
    3. If username: authenticate directly
    4. If valid: create a session and redirect
    5. If invalid: show error message

    Args:
        request: The incoming HTTP request

    Returns:
        GET:  Rendered login.html with empty form
        POST (valid): Redirect to homepage (user is now logged in)
        POST (invalid): Rendered login.html with error message
    """
    # If user is already logged in, send them to homepage
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username_or_email = form.cleaned_data['username_or_email'].strip()
            password = form.cleaned_data['password']

            # Check if they entered an email (contains @)
            if '@' in username_or_email:
                # Look up the username for this email
                try:
                    user_obj = User.objects.get(email=username_or_email.lower())
                    username = user_obj.username
                except User.DoesNotExist:
                    username = None
            else:
                username = username_or_email.lower()

            # Try to authenticate
            # authenticate() checks the password hash — returns User or None
            if username:
                user = authenticate(request, username=username, password=password)
            else:
                user = None

            if user is not None:
                # Success — create session and redirect
                login(request, user)

                api_logger.info(
                    f'LOGIN | user={user.username} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

                # Redirect to 'next' parameter if it exists
                # (e.g., if they were trying to access a protected page)
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                # Failed — add a non-field error
                form.add_error(None, 'Invalid username/email or password.')

                security_logger = logging.getLogger('security')
                security_logger.warning(
                    f'FAILED LOGIN | input={username_or_email} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Log the user out and redirect to homepage.

    Uses POST method to prevent CSRF attacks — a malicious site
    can't log your users out by tricking them into clicking a link.
    GET requests are redirected to homepage without logging out.

    Args:
        request: The incoming HTTP request

    Returns:
        Redirect to homepage
    """
    if request.method == 'POST':
        api_logger.info(
            f'LOGOUT | user={request.user.username} | '
            f'ip={request.META.get("REMOTE_ADDR")}'
        )
        logout(request)
    return redirect('index')