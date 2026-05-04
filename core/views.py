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

from .models import UserPreferences, Feedback, RewriteLog, EmailVerification, EmailChangeRequest, PasswordReset
 
from .email_utils import send_verification_email

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

    If the user is logged in, loads their preferences so the
    frontend can set the default mode and tone.

    Args:
        request: The incoming HTTP request

    Returns:
        The rendered index.html template
    """
    context = {}

    # Load user preferences if logged in
    if request.user.is_authenticated:
        try:
            prefs = UserPreferences.objects.get(user=request.user)
            context['user_prefs'] = {
                'default_mode': prefs.default_mode,
                'default_tone': prefs.default_tone,
            }
        except UserPreferences.DoesNotExist:
            context['user_prefs'] = None

    # Redirect unverified users to the verification page
    if request.user.is_authenticated:
        try:
            verification = EmailVerification.objects.get(user=request.user)
            if not verification.is_verified:
                return redirect('verify_email')
        except EmailVerification.DoesNotExist:
            # User created before email verification was added — let them through
            pass

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
                log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
                security_logger.warning(
                    f'PROFANITY | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
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
                log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
                security_logger.warning(
                    f'PROFANITY | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
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
            log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
            api_logger.warning(
                f'EMPTY INPUT | user={log_user} | ip={request.META.get("REMOTE_ADDR")}'
            )
            return JsonResponse(
                {'error': 'No text provided. Please paste some text to humanize.'},
                status=400
            )

        # Validate: length limit
        if len(text) > 5000:
            return JsonResponse(
                {'error': 'Text is too long. Please keep it under 5,000 characters.'},
                status=400
            )
        
        # ── Block unverified users ──
        if request.user.is_authenticated:
            try:
                verification = EmailVerification.objects.get(user=request.user)
                if not verification.is_verified:
                    return JsonResponse({
                        'error': 'Please verify your email before using Rewright.',
                    }, status=403)
            except EmailVerification.DoesNotExist:
                pass

        # ── Guest usage limit (backend safety net) ──
        # Frontend tracks usage with localStorage but that can be bypassed.
        # Backend checks session-based counter as a backup.
        if not request.user.is_authenticated:
            guest_usage = request.session.get('guest_rewrites', 0)
            if guest_usage >= 3:
                return JsonResponse({
                    'error': 'You have used your 3 free rewrites. Please create an account to continue.',
                    'guest_limit_reached': True,
                }, status=403)

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

            # Increment guest session counter
            if not request.user.is_authenticated:
                request.session['guest_rewrites'] = request.session.get('guest_rewrites', 0) + 1

            # Calculate readability before and after
            original_readability = flesch_reading_ease(text)
            final_readability = flesch_reading_ease(rule_result['text'])

            # ── Save rewrite log ──
            log_user_obj = request.user if request.user.is_authenticated else None
            RewriteLog.objects.create(
                user=log_user_obj,
                mode='quick',
                tone='default',
                language=language['name'],
                input_words=len(text.split()),
                output_words=len(rule_result['text'].split()),
                input_chars=len(text),
            )

            log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
            api_logger.info(
                f'QUICK FIX | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
                f'input_words={len(text.split())} | '
                f'output_words={len(rule_result["text"].split())} | '
                f'input_chars={len(text)} | '
                f'patterns={len(rule_result["changes"])} | '
                f'language={language["name"]} | '
                f'readability={original_readability["score"]}→{final_readability["score"]} | '
                f'duration={duration}s'
            )

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
            log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
            api_logger.error(
                f'LLM FAILED | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
                f'error={str(llm_error)} | '
                f'language={language["name"]} | '
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

        # Increment guest session counter
        if not request.user.is_authenticated:
            request.session['guest_rewrites'] = request.session.get('guest_rewrites', 0) + 1

        # Calculate readability before and after
        original_readability = flesch_reading_ease(text)
        final_readability = flesch_reading_ease(llm_result['text'])

        # ── Save rewrite log ──
        log_user_obj = request.user if request.user.is_authenticated else None
        RewriteLog.objects.create(
            user=log_user_obj,
            mode='deep',
            tone=tone,
            language=language['name'],
            input_words=len(text.split()),
            output_words=len(llm_result['text'].split()),
            input_chars=len(text),
        )

        log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
        api_logger.info(
            f'DEEP REWRITE | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
            f'input_words={len(text.split())} | '
            f'output_words={len(llm_result["text"].split())} | '
            f'input_chars={len(text)} | '
            f'tone={tone} | '
            f'voice_match={has_voice} | '
            f'language={language["name"]} | '
            f'readability={original_readability["score"]}→{final_readability["score"]} | '
            f'model={llm_result["model"]} | '
            f'duration={duration}s'
        )

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
        log_user = f'{request.user.username} (id={request.user.id})' if request.user.is_authenticated else 'Guest'
        api_logger.error(
            f'UNHANDLED ERROR | user={log_user} | ip={request.META.get("REMOTE_ADDR")} | '
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

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, LoginForm, EditProfileForm, ChangePasswordForm, PreferencesForm, FeedbackForm, OTPForm, ChangeEmailForm, ForgotPasswordForm, ResetPasswordForm
from .email_utils import send_verification_email, send_email_change_verification, send_current_email_verification, send_password_reset_email


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
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            api_logger.info(
                f'SIGNUP | user={user.username} (id={user.id}) | email={user.email} | '
                f'ip={request.META.get("REMOTE_ADDR")}'
            )

            # Create and send verification code
            verification = EmailVerification.create_for_user(user)
            send_verification_email(user, verification.code)

            return redirect('verify_email')
    else:
        # GET request — show empty form
        form = SignUpForm()

    return render(request, 'core/signup.html', {'form': form})

@login_required
def verify_email_view(request: HttpRequest) -> HttpResponse:
    """
    Email verification page — user enters the 6-digit OTP code.

    GET:  Show the OTP input form
    POST: Validate the code

    Handles:
    - Correct code → mark as verified, redirect to homepage
    - Wrong code → show error
    - Expired code → show error with resend option
    - Resend → generate new code and email it

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered verify_email.html or redirect to homepage
    """
    user = request.user

    # Check if already verified
    try:
        verification = EmailVerification.objects.get(user=user)
        if verification.is_verified:
            return redirect('index')
    except EmailVerification.DoesNotExist:
        # No verification record — create one
        verification = EmailVerification.create_for_user(user)
        send_verification_email(user, verification.code)

    form = OTPForm()
    error_message = None
    success_message = None

    if request.method == 'POST':
        action = request.POST.get('action', 'verify')

        # ── Handle resend ──
        if action == 'resend':
            verification = EmailVerification.create_for_user(user)
            sent = send_verification_email(user, verification.code)
            if sent:
                success_message = 'A new code has been sent to your email.'
            else:
                error_message = 'Could not send email. Please try again in a moment.'
            return render(request, 'core/verify_email.html', {
                'form': form,
                'email': user.email,
                'error_message': error_message,
                'success_message': success_message,
            })

        # ── Handle verify ──
        form = OTPForm(request.POST)

        if form.is_valid():
            entered_code = form.cleaned_data['code']

            # Refresh from database
            verification = EmailVerification.objects.get(user=user)

            if verification.is_expired():
                error_message = 'This code has expired. Please request a new one.'
            elif verification.code != entered_code:
                error_message = 'Incorrect code. Please check your email and try again.'
            else:
                # Code is correct and not expired
                verification.is_verified = True
                verification.save()

                api_logger.info(
                    f'EMAIL VERIFIED | user={user.username} (id={user.id}) | '
                    f'email={user.email} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

                return redirect('index')

    return render(request, 'core/verify_email.html', {
        'form': form,
        'email': user.email,
        'error_message': error_message,
        'success_message': success_message,
    })

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
    if request.user.is_authenticated:
        return redirect('index')
    
    # Check for password reset success message
    password_reset_success = request.session.pop('password_reset_success', False)

    # Pick up restriction messages from allauth redirect
    from django.contrib.messages import get_messages
    restriction_msg = None
    for msg in get_messages(request):
        if 'restricted' in str(msg).lower():
            restriction_msg = str(msg)

    if restriction_msg:
        form = LoginForm()
        return render(request, 'core/login.html', {
            'form': form,
            'restriction_error': restriction_msg,
        })

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username_or_email = form.cleaned_data['username_or_email'].strip()
            password = form.cleaned_data['password']

            # Check if they entered an email (contains @)
            if '@' in username_or_email:
                try:
                    user_obj = User.objects.filter(email=username_or_email.lower()).first()
                    if user_obj:
                        username = user_obj.username
                    else:
                        username = None
                except Exception:
                    username = None
            else:
                username = username_or_email.lower()

            # Check if user exists and is restricted BEFORE authenticating
            # We do this because ModelBackend returns None for inactive users,
            # so we'd never know if the password was right but account restricted
            if username:
                try:
                    target_user = User.objects.get(username=username)
                    if not target_user.is_active:
                        # Account is restricted — check password first
                        # so we don't reveal account existence to wrong passwords
                        if target_user.check_password(password):
                            form.add_error(
                                None,
                                'Your account has been restricted. Please contact support if you believe this is a mistake.'
                            )
                            security_logger = logging.getLogger('security')
                            security_logger.warning(
                                f'RESTRICTED LOGIN ATTEMPT | user={target_user.username} (id={target_user.id}) | '
                                f'ip={request.META.get("REMOTE_ADDR")}'
                            )
                        else:
                            form.add_error(None, 'Invalid username/email or password.')
                        # Don't proceed to authenticate — stop here
                        return render(request, 'core/login.html', {'form': form})
                except User.DoesNotExist:
                    pass

            # Try to authenticate (only reaches here if user is active or doesn't exist)
            if username:
                user = authenticate(request, username=username, password=password)
            else:
                user = None

            if user is not None:
                login(request, user)

                api_logger.info(
                        f'LOGIN | user={user.username} (id={user.id}) | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )

                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                form.add_error(None, 'Invalid username/email or password.')

                security_logger = logging.getLogger('security')
                security_logger.warning(
                    f'FAILED LOGIN | input={username_or_email} | '
                    f'ip={request.META.get("REMOTE_ADDR")} | '
                    f'attempted_user={username or "unknown"}'
                )
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {
        'form': form,
        'password_reset_success': password_reset_success,
    })

def forgot_password_view(request: HttpRequest) -> HttpResponse:
    """
    Forgot password — multi-step OTP-based password reset.

    All three steps happen on the same page:
    Step 1: Enter email → send OTP
    Step 2: Enter OTP → verify code
    Step 3: Enter new password → update and redirect to login

    Security: we never reveal whether an email has an account.
    We always say "If an account exists, we sent a code."

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered forgot_password.html at the appropriate step
    """
    # If already logged in, go to homepage
    if request.user.is_authenticated:
        return redirect('index')

    # Track which step we're on using session
    step = request.session.get('reset_step', 1)
    reset_email = request.session.get('reset_email', '')

    email_form = ForgotPasswordForm()
    otp_form = OTPForm()
    password_form = ResetPasswordForm()
    error_message = None
    info_message = None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Step 1: Submit email ──
        if action == 'send_code':
            email_form = ForgotPasswordForm(request.POST)

            if email_form.is_valid():
                email = email_form.cleaned_data['email'].lower().strip()

                # Check if user exists (but don't reveal it)
                try:
                    user = User.objects.get(email=email)
                    # User exists — create and send OTP
                    reset = PasswordReset.create_for_email(email)
                    send_password_reset_email(email, reset.code)
                except User.DoesNotExist:
                    # User doesn't exist — silently do nothing
                    # We still show the same message to prevent enumeration
                    pass

                # Always show the same message regardless
                request.session['reset_step'] = 2
                request.session['reset_email'] = email
                step = 2
                info_message = 'If an account exists with that email, we sent a verification code.'

                api_logger.info(
                    f'PASSWORD RESET REQUESTED | email={email} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

        # ── Step 2: Verify OTP ──
        elif action == 'verify_code' and step == 2:
            otp_form = OTPForm(request.POST)

            if otp_form.is_valid():
                entered_code = otp_form.cleaned_data['code']

                # Find the reset record
                try:
                    reset = PasswordReset.objects.get(
                        email=reset_email,
                        is_used=False,
                    )

                    if reset.is_expired():
                        error_message = 'Code expired. Please request a new one.'
                        # Go back to step 1
                        request.session['reset_step'] = 1
                        step = 1
                    elif reset.code != entered_code:
                        error_message = 'Incorrect code. Please try again.'
                    else:
                        # Code correct — advance to step 3
                        request.session['reset_step'] = 3
                        request.session['reset_code_verified'] = True
                        step = 3
                        otp_form = OTPForm()

                except PasswordReset.DoesNotExist:
                    error_message = 'No reset request found. Please start over.'
                    request.session['reset_step'] = 1
                    step = 1

        # ── Step 3: Set new password ──
        elif action == 'set_password' and step == 3:
            # Verify the session is valid (they went through step 2)
            if not request.session.get('reset_code_verified'):
                request.session['reset_step'] = 1
                step = 1
                error_message = 'Session expired. Please start over.'
            else:
                password_form = ResetPasswordForm(request.POST)

                if password_form.is_valid():
                    new_password = password_form.cleaned_data['new_password']

                    try:
                        user = User.objects.get(email=reset_email)
                        user.set_password(new_password)
                        user.save()

                        # Mark the reset code as used
                        PasswordReset.objects.filter(
                            email=reset_email,
                            is_used=False,
                        ).update(is_used=True)

                        # Clean up session
                        for key in ['reset_step', 'reset_email', 'reset_code_verified']:
                            request.session.pop(key, None)

                        api_logger.info(
                            f'PASSWORD RESET COMPLETE | user={user.username} (id={user.id}) | '
                            f'ip={request.META.get("REMOTE_ADDR")}'
                        )

                        # Redirect to login with a success message
                        request.session['password_reset_success'] = True
                        return redirect('login')

                    except User.DoesNotExist:
                        error_message = 'Account not found. Please start over.'
                        request.session['reset_step'] = 1
                        step = 1

        # ── Resend code ──
        elif action == 'resend_code' and step == 2:
            if reset_email:
                try:
                    user = User.objects.get(email=reset_email)
                    reset = PasswordReset.create_for_email(reset_email)
                    send_password_reset_email(reset_email, reset.code)
                except User.DoesNotExist:
                    pass
                info_message = 'If an account exists with that email, we sent a new code.'

        # ── Start over ──
        elif action == 'start_over':
            for key in ['reset_step', 'reset_email', 'reset_code_verified']:
                request.session.pop(key, None)
            step = 1
            reset_email = ''

    return render(request, 'core/forgot_password.html', {
        'step': step,
        'reset_email': reset_email,
        'email_form': email_form,
        'otp_form': otp_form,
        'password_form': password_form,
        'error_message': error_message,
        'info_message': info_message,
    })

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
            f'LOGOUT | user={request.user.username} (id={request.user.id}) | '
            f'ip={request.META.get("REMOTE_ADDR")}'
        )
        logout(request)
    return redirect('index')

@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """
    User profile page — account info, edit name, change password,
    change email (two-step OTP), delete account.

    Email change flow:
    Step 0: User enters new email → we send OTP to CURRENT email
    Step 1: User verifies current email with OTP → we send OTP to NEW email
    Step 2: User verifies new email with OTP → email gets updated
    """
    user = request.user
    has_password = user.has_usable_password()

    # Forms
    edit_form = EditProfileForm(initial={
        'first_name': user.first_name,
        'last_name': user.last_name,
    })
    password_form = ChangePasswordForm()
    email_form = ChangeEmailForm(current_email=user.email)
    otp_form = OTPForm()

    # Success/error flags
    edit_success = False
    password_success = False
    email_changed = False
    email_error = None
    email_info = None

    # Check for pending email change
    pending = EmailChangeRequest.objects.filter(user=user).first()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Edit name ──
        if action == 'edit_profile':
            edit_form = EditProfileForm(request.POST)
            if edit_form.is_valid():
                user.first_name = edit_form.cleaned_data['first_name']
                user.last_name = edit_form.cleaned_data['last_name']
                user.save()
                edit_success = True
                api_logger.info(
                    f'PROFILE EDIT | user={user.username} (id={user.id}) | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

        # ── Change password ──
        elif action == 'change_password':
            password_form = ChangePasswordForm(request.POST)
            if password_form.is_valid():
                current = password_form.cleaned_data['current_password']
                if not user.check_password(current):
                    password_form.add_error('current_password', 'Current password is incorrect.')
                else:
                    user.set_password(password_form.cleaned_data['new_password'])
                    user.save()
                    update_session_auth_hash(request, user)
                    password_success = True
                    password_form = ChangePasswordForm()
                    api_logger.info(
                        f'PASSWORD CHANGED | user={user.username} (id={user.id}) | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )

        # ── Step 0: Request email change → send OTP to CURRENT email ──
        elif action == 'change_email':
            email_form = ChangeEmailForm(request.POST, current_email=user.email)
            if email_form.is_valid():
                new_email = email_form.cleaned_data['new_email']
                pending = EmailChangeRequest.create_for_user(user, new_email)
                sent = send_current_email_verification(user, pending.code)
                if sent:
                    email_info = f'We sent a verification code to your current email ({user.email}). Enter it below.'
                    api_logger.info(
                        f'EMAIL CHANGE STEP1 | user={user.username} (id={user.id}) | '
                        f'new_email={new_email} | sent_to={user.email} | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )
                else:
                    email_error = 'Could not send verification email. Please try again.'
                    pending.delete()
                    pending = None

        # ── Step 1: Verify CURRENT email → then send OTP to NEW email ──
        elif action == 'verify_current_email':
            otp_form = OTPForm(request.POST)
            if otp_form.is_valid() and pending and pending.step == 1:
                entered_code = otp_form.cleaned_data['code']
                if pending.is_expired():
                    email_error = 'Code expired. Please start over.'
                    pending.delete()
                    pending = None
                elif pending.code != entered_code:
                    email_error = 'Incorrect code. Please check your current email and try again.'
                else:
                    # Current email verified — advance to step 2
                    pending.advance_to_step2()
                    sent = send_email_change_verification(user, pending.new_email, pending.code)
                    if sent:
                        email_info = f'Current email verified. Now check your new email ({pending.new_email}) for the next code.'
                        otp_form = OTPForm()
                        api_logger.info(
                            f'EMAIL CHANGE STEP2 | user={user.username} (id={user.id}) | '
                            f'new_email={pending.new_email} | '
                            f'ip={request.META.get("REMOTE_ADDR")}'
                        )
                    else:
                        email_error = 'Could not send verification to new email. Please try again.'
                        pending.delete()
                        pending = None
            elif pending and pending.step != 1:
                email_error = 'Invalid step. Please start over.'
            elif not pending:
                email_error = 'No pending request. Please start over.'

        # ── Step 2: Verify NEW email → update the email ──
        elif action == 'verify_new_email':
            otp_form = OTPForm(request.POST)
            if otp_form.is_valid() and pending and pending.step == 2:
                entered_code = otp_form.cleaned_data['code']
                if pending.is_expired():
                    email_error = 'Code expired. Please start over.'
                    pending.delete()
                    pending = None
                elif pending.code != entered_code:
                    email_error = 'Incorrect code. Please check your new email and try again.'
                else:
                    # Both emails verified — update the email
                    old_email = user.email
                    user.email = pending.new_email
                    user.save()

                    # Keep email verification status
                    try:
                        ev = EmailVerification.objects.get(user=user)
                        ev.is_verified = True
                        ev.save()
                    except EmailVerification.DoesNotExist:
                        pass

                    api_logger.info(
                        f'EMAIL CHANGED | user={user.username} (id={user.id}) | '
                        f'old={old_email} | new={user.email} | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )

                    pending.delete()
                    pending = None
                    email_changed = True
                    email_form = ChangeEmailForm(current_email=user.email)
                    otp_form = OTPForm()
            elif pending and pending.step != 2:
                email_error = 'Invalid step. Please start over.'
            elif not pending:
                email_error = 'No pending request. Please start over.'

        # ── Cancel email change ──
        elif action == 'cancel_email_change':
            if pending:
                pending.delete()
                pending = None

        # ── Delete account ──
        elif action == 'delete_account':
            username = user.username
            user_id = user.id
            user.delete()
            logout(request)
            api_logger.info(
                f'ACCOUNT DELETED | user={username} (id={user_id}) | '
                f'ip={request.META.get("REMOTE_ADDR")}'
            )
            return redirect('index')

    return render(request, 'core/profile.html', {
        'edit_form': edit_form,
        'password_form': password_form,
        'email_form': email_form,
        'otp_form': otp_form,
        'edit_success': edit_success,
        'password_success': password_success,
        'email_changed': email_changed,
        'email_error': email_error,
        'email_info': email_info,
        'pending': pending,
        'has_password': has_password,
    })

from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required(login_url='/login/')
def admin_users_view(request: HttpRequest) -> HttpResponse:
    """
    Custom admin page for managing users.

    Only accessible by staff users (is_staff=True).
    Non-staff users get redirected to login page.

    Features:
    - View all users in a table
    - Search by username or email
    - Filter by status (all, active, restricted)
    - Restrict/unrestrict users with confirmation

    The @staff_member_required decorator checks is_staff.
    If False, redirects to login_url.

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered admin_users.html with user list
    """

    # ── Handle restrict/unrestrict actions (POST) ──
    if request.method == 'POST':
        action = request.POST.get('action', '')
        user_id = request.POST.get('user_id', '')

        if user_id:
            try:
                target_user = User.objects.get(id=user_id)

                # Don't let admin restrict themselves
                if target_user.pk == request.user.pk:
                    pass  # Silently ignore
                elif action == 'restrict':
                    target_user.is_active = False
                    target_user.save()
                    api_logger.info(
                        f'USER RESTRICTED | admin={request.user.username} (id={request.user.id}) | '
                        f'target={target_user.username} (id={target_user.id}) | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )
                elif action == 'unrestrict':
                    target_user.is_active = True
                    target_user.save()
                    api_logger.info(
                        f'USER UNRESTRICTED | admin={request.user.username} (id={request.user.id}) | '
                        f'target={target_user.username} (id={target_user.id}) | '
                        f'ip={request.META.get("REMOTE_ADDR")}'
                    )
            except User.DoesNotExist:
                pass

        return redirect('admin_users')

    # ── GET: Build the user list ──

    # Search query
    search = request.GET.get('search', '').strip()

    # Status filter
    status = request.GET.get('status', 'all')

    # Start with all users
    users = User.objects.all().order_by('-date_joined')

    # Apply search filter
    if search:
        from django.db.models import Q
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    # Apply status filter
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'restricted':
        users = users.filter(is_active=False)

    # Stats for the top of the page
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    restricted_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()

    # Get unread feedback count for the tab badge
    unread_feedback = Feedback.objects.filter(is_read=False).count()

    return render(request, 'core/admin_users.html', {
        'users': users,
        'search': search,
        'status': status,
        'total_users': total_users,
        'active_users': active_users,
        'restricted_users': restricted_users,
        'staff_users': staff_users,
        'unread_feedback': unread_feedback,
    })

def inactive_redirect_view(request: HttpRequest) -> HttpResponse:
    """
    Catch allauth's inactive account redirect and send back to login
    with a restriction warning message.
    """
    from django.contrib import messages
    messages.error(
        request,
        'Your account has been restricted. Please contact an admin if you believe this is a mistake.'
    )
    return redirect('login')


@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    """
    User settings page — preferences and feedback.

    Two sections:
    1. Preferences — default mode and tone, saved to UserPreferences model
    2. Feedback — submit bug reports, feature requests, or general feedback

    Both forms are on the same page. A hidden 'action' field tells us
    which form was submitted.

    The @login_required decorator redirects unauthenticated users to login.

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered settings.html with preference and feedback forms
    """
    user = request.user

    # Get or create preferences for this user
    # get_or_create returns (object, created_boolean)
    # If the user has never visited settings, it creates a default record
    prefs, created = UserPreferences.objects.get_or_create(user=user)

    # Pre-fill the preferences form with current values
    prefs_form = PreferencesForm(initial={
        'default_mode': prefs.default_mode,
        'default_tone': prefs.default_tone,
    })

    feedback_form = FeedbackForm()

    # Success flags
    prefs_success = False
    feedback_success = False

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Handle preferences save ──
        if action == 'save_preferences':
            prefs_form = PreferencesForm(request.POST)

            if prefs_form.is_valid():
                prefs.default_mode = prefs_form.cleaned_data['default_mode']
                prefs.default_tone = prefs_form.cleaned_data['default_tone']
                prefs.save()
                prefs_success = True

                api_logger.info(
                    f'PREFERENCES SAVED | user={user.username} (id={user.id}) | '
                    f'mode={prefs.default_mode} | tone={prefs.default_tone} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

        # ── Handle feedback submission ──
        elif action == 'submit_feedback':
            feedback_form = FeedbackForm(request.POST)

            if feedback_form.is_valid():
                category_saved = feedback_form.cleaned_data['category']

                # Create the feedback record
                Feedback.objects.create(
                    user=user,
                    category=category_saved,
                    message=feedback_form.cleaned_data['message'],
                )

                api_logger.info(
                    f'FEEDBACK SUBMITTED | user={user.username} (id={user.id}) | '
                    f'category={category_saved} | '
                    f'ip={request.META.get("REMOTE_ADDR")}'
                )

                feedback_success = True
                feedback_form = FeedbackForm()  # Clear the form after success

    # Get user's past feedback to show below the form
    user_feedback = Feedback.objects.filter(user=user).order_by('-created_at')[:5]

    return render(request, 'core/settings.html', {
        'prefs_form': prefs_form,
        'feedback_form': feedback_form,
        'prefs_success': prefs_success,
        'feedback_success': feedback_success,
        'user_feedback': user_feedback,
        'current_prefs': prefs,
    })

@login_required
def analytics_view(request: HttpRequest) -> HttpResponse:
    """
    User analytics page — personal usage stats.

    Shows:
    - Row 1: Total rewrites, words processed, words generated, chars processed
    - Row 2: Most used mode, tone, language, average input length
    - Row 3: Rewrites today, this week, this month, last rewrite time

    Only accessible by logged-in users.

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered analytics.html with stats
    """
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    import datetime

    user = request.user
    user_logs = RewriteLog.objects.filter(user=user)

    # ── Row 1: Big numbers ──
    total_rewrites = user_logs.count()
    words_processed = user_logs.aggregate(total=Sum('input_words'))['total'] or 0
    words_generated = user_logs.aggregate(total=Sum('output_words'))['total'] or 0
    chars_processed = user_logs.aggregate(total=Sum('input_chars'))['total'] or 0

    # ── Row 2: Usage breakdown ──

    # Most used mode
    mode_counts = user_logs.values('mode').annotate(count=Count('id')).order_by('-count')
    if mode_counts:
        top_mode = mode_counts[0]
        most_used_mode = 'Deep Rewrite' if top_mode['mode'] == 'deep' else 'Quick Fix'
        mode_pct = round((top_mode['count'] / total_rewrites) * 100) if total_rewrites > 0 else 0
    else:
        most_used_mode = '—'
        mode_pct = 0

    # Most used tone
    tone_counts = user_logs.values('tone').annotate(count=Count('id')).order_by('-count')
    if tone_counts:
        top_tone = tone_counts[0]
        most_used_tone = top_tone['tone'].capitalize()
        tone_pct = round((top_tone['count'] / total_rewrites) * 100) if total_rewrites > 0 else 0
    else:
        most_used_tone = '—'
        tone_pct = 0

    # Most used language
    lang_counts = user_logs.values('language').annotate(count=Count('id')).order_by('-count')
    if lang_counts:
        top_lang = lang_counts[0]
        most_used_lang = top_lang['language']
        lang_pct = round((top_lang['count'] / total_rewrites) * 100) if total_rewrites > 0 else 0
    else:
        most_used_lang = '—'
        lang_pct = 0

    # Average input length
    avg_input = user_logs.aggregate(avg=Avg('input_words'))['avg']
    avg_input_words = round(avg_input) if avg_input else 0

    # ── Row 3: Activity ──
    # Use the user's timezone from the browser for accurate "today/this week" counts
    import zoneinfo
    user_tz_name = request.GET.get('tz', 'UTC')
    try:
        user_tz = zoneinfo.ZoneInfo(user_tz_name)
    except (KeyError, Exception):
        user_tz = zoneinfo.ZoneInfo('UTC')

    now_utc = timezone.now()
    now_local = now_utc.astimezone(user_tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=now_local.weekday())
    month_start = today_start.replace(day=1)

    rewrites_today = user_logs.filter(created_at__gte=today_start).count()
    rewrites_week = user_logs.filter(created_at__gte=week_start).count()
    rewrites_month = user_logs.filter(created_at__gte=month_start).count()

    last_rewrite = user_logs.first()
    last_rewrite_time = last_rewrite.created_at.astimezone(user_tz) if last_rewrite else None

    stats = {
        'total_rewrites': total_rewrites,
        'words_processed': words_processed,
        'words_generated': words_generated,
        'chars_processed': chars_processed,
        'most_used_mode': most_used_mode,
        'mode_pct': mode_pct,
        'most_used_tone': most_used_tone,
        'tone_pct': tone_pct,
        'most_used_lang': most_used_lang,
        'lang_pct': lang_pct,
        'avg_input_words': avg_input_words,
        'rewrites_today': rewrites_today,
        'rewrites_week': rewrites_week,
        'rewrites_month': rewrites_month,
        'last_rewrite_time': last_rewrite_time,
    }

    return render(request, 'core/analytics.html', {'stats': stats})

@staff_member_required(login_url='/login/')
def admin_feedback_view(request: HttpRequest) -> HttpResponse:
    """
    Admin page for viewing and managing user feedback.

    Features:
    - View all feedback submissions
    - Filter by category (bug, feature, general)
    - Mark individual feedback as read/unread
    - Expand to see full message

    Only accessible by staff users.

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered admin_feedback.html with feedback list
    """

    # ── Handle mark as read/unread actions (POST) ──
    if request.method == 'POST':
        action = request.POST.get('action', '')
        feedback_id = request.POST.get('feedback_id', '')

        if feedback_id:
            try:
                fb = Feedback.objects.get(id=feedback_id)

                if action == 'mark_read':
                    fb.is_read = True
                    fb.save()
                elif action == 'mark_unread':
                    fb.is_read = False
                    fb.save()
                elif action == 'delete_feedback':
                    fb.delete()

            except Feedback.DoesNotExist:
                pass

        # Preserve current filters in redirect
        category = request.POST.get('current_category', '')
        status = request.POST.get('current_status', '')
        params = []
        if category:
            params.append(f'category={category}')
        if status:
            params.append(f'status={status}')
        redirect_url = '/manage/feedback/'
        if params:
            redirect_url += '?' + '&'.join(params)
        return redirect(redirect_url)

    # ── GET: Build the feedback list ──

    # Category filter
    category = request.GET.get('category', 'all')

    # Read status filter
    status = request.GET.get('status', 'all')

    # Start with all feedback
    feedback_list = Feedback.objects.all().order_by('-created_at')

    # Apply category filter
    if category in ['bug', 'feature', 'general']:
        feedback_list = feedback_list.filter(category=category)

    # Apply read status filter
    if status == 'unread':
        feedback_list = feedback_list.filter(is_read=False)
    elif status == 'read':
        feedback_list = feedback_list.filter(is_read=True)

    # Stats
    total_feedback = Feedback.objects.count()
    unread_count = Feedback.objects.filter(is_read=False).count()
    bug_count = Feedback.objects.filter(category='bug').count()
    feature_count = Feedback.objects.filter(category='feature').count()
    general_count = Feedback.objects.filter(category='general').count()

    return render(request, 'core/admin_feedback.html', {
        'feedback_list': feedback_list,
        'category': category,
        'status': status,
        'total_feedback': total_feedback,
        'unread_count': unread_count,
        'bug_count': bug_count,
        'feature_count': feature_count,
        'general_count': general_count,
    })

@staff_member_required(login_url='/login/')
def admin_analytics_view(request: HttpRequest) -> HttpResponse:
    """
    Admin analytics dashboard — platform-wide stats.

    Shows overall usage, today's activity, usage breakdown,
    and growth comparisons (this week vs last, this month vs last).

    Only accessible by staff users.

    Args:
        request: The incoming HTTP request

    Returns:
        Rendered admin_analytics.html with platform stats
    """
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    import datetime
    import zoneinfo

    # Use admin's timezone from browser
    user_tz_name = request.GET.get('tz', 'UTC')
    try:
        user_tz = zoneinfo.ZoneInfo(user_tz_name)
    except (KeyError, Exception):
        user_tz = zoneinfo.ZoneInfo('UTC')

    now_utc = timezone.now()
    now_local = now_utc.astimezone(user_tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Week boundaries
    week_start = today_start - datetime.timedelta(days=now_local.weekday())
    last_week_start = week_start - datetime.timedelta(weeks=1)
    last_week_end = week_start

    # Month boundaries
    month_start = today_start.replace(day=1)
    last_month_end = month_start
    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)

    all_logs = RewriteLog.objects.all()
    all_users = User.objects.all()

    # ── Row 1: Platform overview ──
    total_rewrites = all_logs.count()
    total_users = all_users.count()
    total_words = all_logs.aggregate(total=Sum('input_words'))['total'] or 0
    total_feedback = Feedback.objects.count()

    # ── Row 2: Today's activity ──
    today_logs = all_logs.filter(created_at__gte=today_start)
    rewrites_today = today_logs.count()
    new_users_today = all_users.filter(date_joined__gte=today_start).count()
    active_users_today = today_logs.values('user').distinct().count()
    words_today = today_logs.aggregate(total=Sum('input_words'))['total'] or 0

    # ── Row 3: Usage breakdown ──

    # Quick Fix vs Deep Rewrite
    quick_count = all_logs.filter(mode='quick').count()
    deep_count = all_logs.filter(mode='deep').count()
    quick_pct = round((quick_count / total_rewrites) * 100) if total_rewrites > 0 else 0
    deep_pct = round((deep_count / total_rewrites) * 100) if total_rewrites > 0 else 0

    # Top 3 tones
    top_tones = (
        all_logs.values('tone')
        .annotate(count=Count('id'))
        .order_by('-count')[:3]
    )
    top_tones_list = []
    for t in top_tones:
        pct = round((t['count'] / total_rewrites) * 100) if total_rewrites > 0 else 0
        top_tones_list.append({
            'name': t['tone'].capitalize(),
            'count': t['count'],
            'pct': pct,
        })

    # Top 3 languages
    top_langs = (
        all_logs.values('language')
        .annotate(count=Count('id'))
        .order_by('-count')[:3]
    )
    top_langs_list = []
    for l in top_langs:
        pct = round((l['count'] / total_rewrites) * 100) if total_rewrites > 0 else 0
        top_langs_list.append({
            'name': l['language'],
            'count': l['count'],
            'pct': pct,
        })

    # Average input length
    avg_input = all_logs.aggregate(avg=Avg('input_words'))['avg']
    avg_input_words = round(avg_input) if avg_input else 0

    # ── Row 4: Growth ──

    # This week vs last week
    rewrites_this_week = all_logs.filter(created_at__gte=week_start).count()
    rewrites_last_week = all_logs.filter(
        created_at__gte=last_week_start,
        created_at__lt=last_week_end
    ).count()

    users_this_week = all_users.filter(date_joined__gte=week_start).count()
    users_last_week = all_users.filter(
        date_joined__gte=last_week_start,
        date_joined__lt=last_week_end
    ).count()

    # This month vs last month
    rewrites_this_month = all_logs.filter(created_at__gte=month_start).count()
    rewrites_last_month = all_logs.filter(
        created_at__gte=last_month_start,
        created_at__lt=last_month_end
    ).count()

    users_this_month = all_users.filter(date_joined__gte=month_start).count()
    users_last_month = all_users.filter(
        date_joined__gte=last_month_start,
        date_joined__lt=last_month_end
    ).count()

    # Calculate change percentages
    def calc_change(current, previous):
        """Calculate percentage change between two values."""
        if previous == 0:
            return '+100' if current > 0 else '0'
        change = round(((current - previous) / previous) * 100)
        return f'+{change}' if change >= 0 else str(change)

    # Unread feedback count for tab badge
    unread_feedback = Feedback.objects.filter(is_read=False).count()

    stats = {
        # Row 1
        'total_rewrites': total_rewrites,
        'total_users': total_users,
        'total_words': total_words,
        'total_feedback': total_feedback,
        # Row 2
        'rewrites_today': rewrites_today,
        'new_users_today': new_users_today,
        'active_users_today': active_users_today,
        'words_today': words_today,
        # Row 3
        'quick_count': quick_count,
        'deep_count': deep_count,
        'quick_pct': quick_pct,
        'deep_pct': deep_pct,
        'top_tones': top_tones_list,
        'top_langs': top_langs_list,
        'avg_input_words': avg_input_words,
        # Row 4
        'rewrites_this_week': rewrites_this_week,
        'rewrites_last_week': rewrites_last_week,
        'rewrites_week_change': calc_change(rewrites_this_week, rewrites_last_week),
        'users_this_week': users_this_week,
        'users_last_week': users_last_week,
        'users_week_change': calc_change(users_this_week, users_last_week),
        'rewrites_this_month': rewrites_this_month,
        'rewrites_last_month': rewrites_last_month,
        'rewrites_month_change': calc_change(rewrites_this_month, rewrites_last_month),
        'users_this_month': users_this_month,
        'users_last_month': users_last_month,
        'users_month_change': calc_change(users_this_month, users_last_month),
    }

    return render(request, 'core/admin_analytics.html', {
        'stats': stats,
        'unread_feedback': unread_feedback,
    })

@require_POST
def feedback_api(request: HttpRequest) -> JsonResponse:
    """
    API endpoint for submitting feedback via the floating button.

    Accepts POST with JSON:
        { "category": "bug|feature|general", "message": "..." }

    Only authenticated users can submit.
    Returns JSON success/error response.

    Args:
        request: The incoming HTTP POST request

    Returns:
        JsonResponse with success or error message
    """
    # Only logged-in users can submit feedback
    if not request.user.is_authenticated:
        return JsonResponse(
            {'error': 'Please log in to submit feedback.'},
            status=401
        )

    try:
        body = json.loads(request.body.decode('utf-8'))
        category = body.get('category', '').strip()
        message = body.get('message', '').strip()

        # Validate category
        valid_categories = ['bug', 'feature', 'general']
        if category not in valid_categories:
            return JsonResponse(
                {'error': 'Invalid category. Choose bug, feature, or general.'},
                status=400
            )

        # Validate message
        if not message:
            return JsonResponse(
                {'error': 'Please enter a message.'},
                status=400
            )

        if len(message) > 2000:
            return JsonResponse(
                {'error': 'Message is too long. Please keep it under 2,000 characters.'},
                status=400
            )

        # Create the feedback record
        Feedback.objects.create(
            user=request.user,
            category=category,
            message=message,
        )

        api_logger.info(
            f'FEEDBACK SUBMITTED | user={request.user.username} (id={request.user.id}) | '
            f'category={category} | '
            f'ip={request.META.get("REMOTE_ADDR")}'
        )

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid request.'},
            status=400
        )
    except Exception as e:
        api_logger.error(
            f'FEEDBACK ERROR | user={request.user.username} (id={request.user.id}) | '
            f'error={str(e)}'
        )
        return JsonResponse(
            {'error': 'Something went wrong. Please try again.'},
            status=500
        )