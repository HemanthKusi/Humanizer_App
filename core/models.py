"""
core/models.py
--------------
Database models for the Rewright app.

Models define the structure of our database tables.
Each model class = one table. Each field = one column.

Django automatically:
- Creates the table when you run migrations
- Adds an auto-incrementing 'id' primary key
- Handles all SQL queries through the ORM

Models:
1. UserPreferences — stores each user's default settings
2. Feedback — stores user-submitted feedback and suggestions
"""

from django.db import models
from django.contrib.auth.models import User


class UserPreferences(models.Model):
    """
    Stores a user's default settings.

    One-to-one relationship with User — each user has exactly
    one preferences record. Created automatically when they
    first visit settings.

    Fields:
        user: Link to the User who owns these preferences
        default_mode: 'quick' or 'deep' — which mode loads by default
        default_tone: Which tone is pre-selected in Deep Rewrite mode

    The defaults match what a new user sees on first visit:
    Quick Fix mode with Default tone.
    """

    MODE_CHOICES = [
        ('quick', 'Quick Fix'),
        ('deep', 'Deep Rewrite'),
    ]

    TONE_CHOICES = [
        ('default', 'Default'),
        ('casual', 'Casual'),
        ('formal', 'Formal'),
        ('academic', 'Academic'),
        ('simple', 'Simple'),
        ('summarize', 'Summarize'),
        ('expand', 'Expand'),
    ]

    # OneToOneField means each user has exactly one preferences record
    # on_delete=CASCADE means if the user is deleted, their preferences are too
    # related_name='preferences' lets us access it as user.preferences
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences',
    )

    default_mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default='quick',
        help_text='Which mode loads by default on the homepage',
    )

    default_tone = models.CharField(
        max_length=20,
        choices=TONE_CHOICES,
        default='default',
        help_text='Which tone is pre-selected in Deep Rewrite mode',
    )

    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    timezone = models.CharField(
        max_length=63,
        default='UTC',
        help_text='User browser timezone (e.g., America/Denver)',
    )

    class Meta:
        verbose_name_plural = 'User preferences'

    def __str__(self):
        return f'{self.user.username} preferences'


class Feedback(models.Model):
    """
    Stores user-submitted feedback, bug reports, and feature requests.

    Each submission creates one record. Admins can view all feedback
    from the admin panel.

    Fields:
        user: Who submitted it (nullable for anonymous feedback in future)
        category: bug, feature, or general
        message: The actual feedback text
        created_at: When it was submitted
        is_read: Whether an admin has seen it
    """

    CATEGORY_CHOICES = [
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('general', 'General Feedback'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback',
        help_text='The user who submitted this feedback',
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general',
    )

    message = models.TextField(
        max_length=2000,
        help_text='The feedback message (max 2000 characters)',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this feedback was submitted',
    )

    is_read = models.BooleanField(
        default=False,
        help_text='Whether an admin has reviewed this feedback',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Feedback'

    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f'{self.category} from {username} ({self.created_at.strftime("%Y-%m-%d")})'
    
class RewriteLog(models.Model):
    """
    Tracks every rewrite request for per-user analytics.

    One record per successful rewrite. Used to build the stats
    dashboard on the user's profile page.

    Unlike the text log files (api.log), this data is:
    - Queryable (filter by user, mode, date range)
    - Permanent (doesn't get rotated or deleted)
    - Fast (database indexes for common queries)

    Fields:
        user: Who made the request (null for anonymous/non-logged-in users)
        mode: 'quick' or 'deep'
        tone: Which tone was used (only relevant for deep mode)
        language: Detected input language
        input_words: Word count of the original text
        output_words: Word count of the rewritten text
        input_chars: Character count of the original text
        created_at: When the rewrite happened
    """

    MODE_CHOICES = [
        ('quick', 'Quick Fix'),
        ('deep', 'Deep Rewrite'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rewrite_logs',
        help_text='The user who made this request',
    )

    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        help_text='Quick Fix or Deep Rewrite',
    )

    tone = models.CharField(
        max_length=20,
        default='default',
        help_text='Which tone was selected',
    )

    language = models.CharField(
        max_length=50,
        default='English',
        help_text='Detected input language',
    )

    input_words = models.IntegerField(
        default=0,
        help_text='Word count of the original text',
    )

    output_words = models.IntegerField(
        default=0,
        help_text='Word count of the rewritten text',
    )

    input_chars = models.IntegerField(
        default=0,
        help_text='Character count of the original text',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this rewrite happened',
    )

    class Meta:
        ordering = ['-created_at']
        # Indexes speed up common queries like "all rewrites by this user"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f'{self.mode} by {username} ({self.created_at.strftime("%Y-%m-%d %H:%M")})'
    
import random
import string
from django.utils import timezone
from datetime import timedelta


class EmailVerification(models.Model):
    """
    Stores OTP codes for email verification.

    How it works:
    1. User signs up → we create a record with a 6-digit code
    2. We email the code to the user
    3. User enters the code on the verify page
    4. If code matches and hasn't expired → mark as verified
    5. Codes expire after 10 minutes

    Fields:
        user        — the user this code belongs to
        code        — the 6-digit OTP code
        created_at  — when the code was generated
        expires_at  — when the code expires (10 min after creation)
        is_verified — whether the user has successfully verified
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='email_verification'
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} — {"verified" if self.is_verified else "pending"}'

    def is_expired(self):
        """Check if the OTP code has expired."""
        return timezone.now() > self.expires_at

    @staticmethod
    def generate_code():
        """Generate a random 6-digit numeric code."""
        return ''.join(random.choices(string.digits, k=6))

    @classmethod
    def create_for_user(cls, user):
        """
        Create or refresh a verification code for a user.

        If a record already exists, update it with a new code.
        If not, create a new record.

        Args:
            user: The User object to create verification for

        Returns:
            The EmailVerification object with the new code
        """
        code = cls.generate_code()
        expires = timezone.now() + timedelta(minutes=10)

        verification, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'code': code,
                'expires_at': expires,
                'is_verified': False,
            }
        )
        return verification
    
class EmailChangeRequest(models.Model):
    """
    Stores pending email change requests with two-step OTP verification.

    Flow:
    Step 1: Send OTP to current email → user proves they own it
    Step 2: Send OTP to new email → user proves they own it
    Then update user.email

    Fields:
        user            — the user requesting the change
        new_email       — the new email address they want
        code            — current 6-digit OTP code
        step            — which verification step we're on (1 or 2)
        created_at      — when the request was made
        expires_at      — when the current code expires
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_change_requests'
    )
    new_email = models.EmailField()
    code = models.CharField(max_length=6)
    step = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f'{self.user.username} → {self.new_email} (step {self.step})'

    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def create_for_user(cls, user, new_email):
        """
        Create a new email change request at step 1.
        Deletes any previous pending requests for this user.
        """
        cls.objects.filter(user=user).delete()

        code = EmailVerification.generate_code()
        expires = timezone.now() + timedelta(minutes=10)

        return cls.objects.create(
            user=user,
            new_email=new_email,
            code=code,
            step=1,
            expires_at=expires,
        )

    def advance_to_step2(self):
        """
        Generate a new code for step 2 (verify new email).
        """
        self.code = EmailVerification.generate_code()
        self.step = 2
        self.expires_at = timezone.now() + timedelta(minutes=10)
        self.save()
        return self
    
class PasswordReset(models.Model):
    """
    Stores OTP codes for password reset.

    Flow:
    1. User enters email on forgot password page
    2. We create a record with a 6-digit code
    3. We email the code
    4. User enters the code
    5. If correct and not expired → they set a new password

    Fields:
        email       — the email address (not a FK to User — we don't
                      reveal whether the account exists)
        code        — 6-digit OTP
        created_at  — when generated
        expires_at  — when code expires (10 min)
        is_used     — whether the code has been used successfully
    """
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.email} — {"used" if self.is_used else "pending"}'

    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def create_for_email(cls, email):
        """
        Create a new password reset code for an email.
        Deletes any previous unused codes for this email.
        """
        cls.objects.filter(email=email, is_used=False).delete()

        code = EmailVerification.generate_code()
        expires = timezone.now() + timedelta(minutes=10)

        return cls.objects.create(
            email=email,
            code=code,
            expires_at=expires,
        )