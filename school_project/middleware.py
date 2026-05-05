"""
Custom middleware for error handling
"""
import logging
from django.http import JsonResponse
from django.db import OperationalError
from django.shortcuts import render

logger = logging.getLogger(__name__)


class DatabaseErrorMiddleware:
    """
    Middleware to catch database locked errors and return a proper response
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Handle database exceptions"""
        if isinstance(exception, OperationalError):
            error_message = str(exception)
            
            if 'database is locked' in error_message:
                logger.warning(f"Database locked error for {request.path}")
                
                # Return appropriate response based on request type
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Database is temporarily locked. Please try again in a moment.',
                        'retry': True
                    }, status=503)
                
                # For regular requests, render an error page
                try:
                    return render(request, 'error.html', {
                        'error_title': 'Database Temporarily Locked',
                        'error_message': 'The database is currently busy. Please wait a moment and try again.',
                        'retry': True
                    }, status=503)
                except Exception:
                    # If template rendering fails, return a simple response
                    from django.http import HttpResponse
                    return HttpResponse(
                        '<h1>Database Temporarily Locked</h1><p>Please wait a moment and try again.</p>',
                        status=503
                    )
        
        return None  # Let other middleware handle other exceptions


class RemoveUnsupportedSecurityHeadersMiddleware:
    """
    Remove security headers that browsers reject on non-HTTPS (HTTP) origins.
    Cross-Origin-Opener-Policy is only meaningful over HTTPS; sending it over
    plain HTTP causes a browser console warning and is silently ignored anyway.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Only strip on plain HTTP — keep headers intact when served over HTTPS
        if not request.is_secure():
            response.headers.pop('Cross-Origin-Opener-Policy', None)
            response.headers.pop('Cross-Origin-Embedder-Policy', None)
        return response
