import jwt
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings
from utilities.db_connection import get_db
from bson import ObjectId

db = get_db()

def get_token_from_request(request):
    """Extract token from Authorization header or session."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    
    # Fallback to session
    return request.session.get('access_token')

def get_current_user(request):
    """Retrieve current user from decoded token data."""
    token = get_token_from_request(request)
    if not token:
        return None
        
    try:
        # Decode JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if not user_id:
            return None
            
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            # Strip password hash for safety
            user.pop('password_hash', None)
            user['_id'] = str(user['_id'])
            user['id'] = user['_id']
            return user
    except Exception:
        pass
    return None

def login_required_api(view_func):
    """API Decorator ensuring user is authenticated via JWT or Session."""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Authentication required. Invalid or missing token."}, status=401)
        request.user_data = user
        return view_func(request, *args, **kwargs)
    return wrapped_view

def login_required_ui(view_func):
    """UI Decorator redirecting non-authenticated users to login page."""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            return redirect('auth_login_page')
        request.user_data = user
        return view_func(request, *args, **kwargs)
    return wrapped_view

def roles_allowed(allowed_roles):
    """Decorator to enforce role-based access control (RBAC)."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                return JsonResponse({"error": "Authentication required."}, status=401)
                
            user_role = user.get('role', 'viewer')
            if user_role not in allowed_roles:
                return JsonResponse({
                    "error": "Forbidden. You do not have the required permissions to perform this action."
                }, status=403)
                
            request.user_data = user
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
