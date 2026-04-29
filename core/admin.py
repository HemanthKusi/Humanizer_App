"""
core/admin.py
-------------
Customizes the Django admin panel for user management.

Django comes with a built-in admin panel at /admin/ that lets
staff users manage data. By default, the User model has a basic
admin view. We customize it to show more useful information
and add a "Restrict" action.

What this gives you:
- Table view of all users with username, email, join date, last login
- Search by username or email
- Filter by active status, staff status, date joined
- "Restrict" and "Unrestrict" bulk actions
- Click any user to view/edit their details
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin view for the User model.

    Extends Django's built-in UserAdmin with:
    - More columns in the list view
    - Search and filter options
    - Restrict/Unrestrict actions

    The list_display controls which columns appear in the table.
    The list_filter adds filter dropdowns in the sidebar.
    The search_fields controls what the search box searches through.
    """

    # ── Columns shown in the user list table ──
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_active',       # True/False — shows as green/red icon
        'is_staff',        # True/False — admin access
        'date_joined',
        'last_login',
    )

    # ── Filters in the right sidebar ──
    list_filter = (
        'is_active',       # Filter by restricted/unrestricted
        'is_staff',        # Filter by admin/non-admin
        'date_joined',     # Filter by join date ranges
    )

    # ── Search box searches these fields ──
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
    )

    # ── Default sort order (newest first) ──
    ordering = ('-date_joined',)

    # ── How many users per page ──
    list_per_page = 25

    # ── Bulk actions ──
    actions = ['restrict_users', 'unrestrict_users']

    @admin.action(description='Restrict selected users (prevent login)')
    def restrict_users(self, request, queryset):
        """
        Bulk action: restrict selected users.

        Sets is_active=False which prevents them from logging in.
        Their account and data are preserved — they just can't access it.
        Django's auth system automatically blocks login for inactive users.

        @param request: The admin request
        @param queryset: The selected users
        """
        # Don't let admin restrict themselves
        queryset = queryset.exclude(pk=request.user.pk)
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{count} user(s) have been restricted.',
        )

    @admin.action(description='Unrestrict selected users (allow login)')
    def unrestrict_users(self, request, queryset):
        """
        Bulk action: unrestrict selected users.

        Sets is_active=True so they can log in again.

        @param request: The admin request
        @param queryset: The selected users
        """
        count = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{count} user(s) have been unrestricted.',
        )


# Unregister the default User admin and register our custom one
# Django auto-registers User with a basic admin — we replace it
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Customize the admin panel header text
admin.site.site_header = 'Rewright Admin'
admin.site.site_title = 'Rewright Admin'
admin.site.index_title = 'Dashboard'