import time
from django.http import JsonResponse
from django.core.cache import cache

class RateLimitAndSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Enforce IP-based Rate Limiting (100 requests per minute)
        ip = self.get_client_ip(request)
        cache_key = f"rate_limit_{ip}"
        requests_info = cache.get(cache_key, [])
        
        current_time = time.time()
        # Filter requests in the last 60 seconds
        requests_info = [t for t in requests_info if current_time - t < 60]
        
        if len(requests_info) >= 100:
            return JsonResponse({
                "error": "Too many requests. Rate limit exceeded. Please try again in a minute."
            }, status=429)
            
        requests_info.append(current_time)
        cache.set(cache_key, requests_info, 60)

        # 2. Process Request
        response = self.get_response(request)

        # 3. Add Security Headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Content-Security-Policy'] = "default-src 'self' https:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.plot.ly https://cdnjs.cloudflare.com https://cdn.datatables.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.datatables.net; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https://img.icons8.com https://img.shields.line.pm https://img.shields.io; connect-src 'self' ws://localhost:* ws://127.0.0.1:*;"
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
