"""
core/forms.py
-------------
Django forms for user authentication.

Forms handle two things:
1. Rendering HTML form fields (what the user sees)
2. Validating input data (checking it's correct before saving)

We create custom forms instead of using Django's defaults because:
- We want to control the HTML output for our custom styling
- We want to add extra validation (like email required on signup)
- We want better error messages

Django forms work like this:
    1. User submits a form
    2. Django creates a form instance with the submitted data
    3. form.is_valid() checks all validation rules
    4. If valid, we use the cleaned data to create/authenticate the user
    5. If invalid, form.errors contains what went wrong
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class SignUpForm(forms.Form):
    """
    Registration form for new users.

    Fields:
        - username: unique identifier, 3-30 chars, letters/numbers/underscores only
        - email: required, must be unique (no two users with same email)
        - password: must pass Django's built-in validators
        - confirm_password: must match password

    Why not use Django's UserCreationForm?
    It works fine but gives us less control over validation messages
    and HTML rendering. Building our own is more educational and
    lets us match our UI exactly.
    """

    username = forms.CharField(
        min_length=3,
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': 'Choose a username',
            'autocomplete': 'username',
            'autofocus': True,
        }),
        help_text='3-30 characters. Letters, numbers, and underscores only.',
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
        }),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create a password',
            'autocomplete': 'new-password',
        }),
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
        }),
    )

    def clean_username(self):
        """
        Validate the username field.

        Checks:
        1. Only contains letters, numbers, and underscores
        2. Not already taken by another user

        This method is called automatically by form.is_valid().
        Django calls clean_<fieldname>() for each field.

        @return: The cleaned username (lowercase, stripped)
        """
        username = self.cleaned_data['username'].strip().lower()

        # Check for invalid characters
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )

        # Check if username is already taken
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')

        return username

    def clean_email(self):
        """
        Validate the email field.

        Checks that no other user has this email.
        We enforce unique emails to prevent confusion and
        to support password reset by email later.

        @return: The cleaned email (lowercase, stripped)
        """
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists.')

        return email

    def clean_password(self):
        """
        Validate the password using Django's built-in validators.

        Django checks:
        - Minimum 8 characters
        - Not too similar to username or email
        - Not a commonly used password (like "password123")
        - Not entirely numeric

        @return: The password string
        """
        password = self.cleaned_data.get('password', '')

        # Run Django's built-in password validators
        # This raises ValidationError if password is too weak
        validate_password(password, user=None)

        return password

    def clean(self):
        """
        Cross-field validation — runs after all individual field validators.

        Checks that password and confirm_password match.
        This is the only place we can compare two fields against each other.

        @return: The full cleaned_data dictionary
        """
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')

        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'Passwords do not match.')

        return cleaned_data


class LoginForm(forms.Form):
    """
    Login form for existing users.

    Accepts either username or email for flexibility.
    The view handles looking up the user and checking the password.

    Fields:
        - username_or_email: the user types their username OR email
        - password: their password
    """

    username_or_email = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Username or email',
            'autocomplete': 'username',
            'autofocus': True,
        }),
        label='Username or email',
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        }),
    )