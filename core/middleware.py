"""
core/middleware.py
-----------------
Custom middleware for security.

Contains:
    - SimpleRateLimiter: limits requests per IP to prevent abuse
    - Tracks request counts in memory (good for single-server deployment)
"""

import time
from django.http import JsonResponse

import logging

security_logger = logging.getLogger('security')

# Module-level request tracker — shared between middleware and views.
# This allows the /api/usage/ endpoint to read current usage.
request_tracker = {}


class SimpleRateLimiter:
    """
    Rate limiting middleware that tracks requests per IP address.

    How it works:
        - Stores {ip: [timestamp, timestamp, ...]} in memory
        - On each request, removes timestamps older than the window
        - If remaining timestamps exceed the limit, blocks the request
        - Only applies to POST requests to /api/ endpoints

    Configuration:
        MAX_REQUESTS: maximum requests allowed per window
        WINDOW_SECONDS: time window in seconds
        BURST_LIMIT: max requests in a short burst (5 seconds)

    Why in-memory?
        For a single-server app this is fine and fast.
        For multi-server deployment, you'd use Redis instead.
    """

    # Allow 3 requests in 5 seconds (prevents rapid-fire)
    BURST_LIMIT = 3
    BURST_WINDOW = 5

    # Allow 10 requests per minute
    MINUTE_LIMIT = 10
    MINUTE_WINDOW = 60

    # Allow 25 requests per hour
    HOURLY_LIMIT = 25
    HOURLY_WINDOW = 3600

    # Allow 40 requests per day
    DAILY_LIMIT = 40
    DAILY_WINDOW = 86400

    def __init__(self, get_response):
        self.get_response = get_response
        # Use the module-level tracker so views can access it
        self.requests = request_tracker
        # Cleanup counter — purge stale IPs every 100 requests
        self.request_count = 0

    def __call__(self, request):

        # Only rate-limit API POST endpoints
        if request.method == 'POST' and request.path.startswith('/api/'):
            ip = self._get_client_ip(request)
            now = time.time()

            # Initialize IP if first request
            if ip not in self.requests:
                self.requests[ip] = []

            # Remove timestamps older than the daily window
            self.requests[ip] = [
                t for t in self.requests[ip]
                if now - t < self.DAILY_WINDOW
            ]

            # Skip rate limiting in development but track usage
            import os
            if os.getenv('DEBUG', 'False').lower() == 'true':
                return self.get_response(request)

            # Check burst limit (3 in 5 seconds)
            recent = [t for t in self.requests[ip] if now - t < self.BURST_WINDOW]
            if len(recent) >= self.BURST_LIMIT:
                security_logger.warning(
                    f'RATE LIMIT BURST | ip={ip} | '
                    f'{len(recent)} requests in {self.BURST_WINDOW}s'
                )
                return JsonResponse(
                    {'error': 'Too many requests. Please wait a few seconds.'},
                    status=429
                )

            # Check minute limit (10 per minute)
            last_minute = [t for t in self.requests[ip] if now - t < self.MINUTE_WINDOW]
            if len(last_minute) >= self.MINUTE_LIMIT:
                security_logger.warning(
                    f'RATE LIMIT MINUTE | ip={ip} | '
                    f'{len(last_minute)} requests in 60s'
                )
                wait = int(self.MINUTE_WINDOW - (now - min(last_minute)))
                return JsonResponse(
                    {'error': f'Rate limit reached. Try again in {wait} seconds.'},
                    status=429
                )

            # Check hourly limit (25 per hour)
            if len(self.requests[ip]) >= self.HOURLY_LIMIT:
                security_logger.warning(
                    f'RATE LIMIT HOURLY | ip={ip} | '
                    f'{len(self.requests[ip])} requests in 1h'
                )
                wait = max(1, int((self.HOURLY_WINDOW - (now - min(self.requests[ip]))) / 60))
                return JsonResponse(
                    {'error': f'Hourly limit reached ({self.HOURLY_LIMIT} requests). Try again in ~{wait} minutes.'},
                    status=429
                )

            # Check daily limit (40 per day)
            if len(self.requests[ip]) >= self.DAILY_LIMIT:
                security_logger.warning(
                    f'RATE LIMIT DAILY | ip={ip} | '
                    f'{len(self.requests[ip])} requests in 24h'
                )
                wait = max(1, int((self.DAILY_WINDOW - (now - min(self.requests[ip]))) / 3600))
                return JsonResponse(
                    {'error': f'Daily limit reached ({self.DAILY_LIMIT} requests). Try again in ~{wait} hours.'},
                    status=429
                )

            # Periodic cleanup of stale IPs
            self.request_count += 1
            if self.request_count % 100 == 0:
                self._cleanup(now)

        return self.get_response(request)

    def _get_client_ip(self, request):
        """
        Extract the real client IP address.

        Checks X-Forwarded-For header first (set by proxies/load balancers),
        falls back to REMOTE_ADDR.
        """
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            # X-Forwarded-For can contain multiple IPs; first is the client
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _cleanup(self, now):
        """Remove IPs that haven't made requests recently."""
        stale_ips = [
            ip for ip, timestamps in self.requests.items()
            if not timestamps or now - max(timestamps) > self.WINDOW_SECONDS * 2
        ]
        for ip in stale_ips:
            del self.requests[ip]