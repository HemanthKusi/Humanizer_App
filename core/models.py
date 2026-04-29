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