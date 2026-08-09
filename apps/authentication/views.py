import datetime
import uuid
import jwt
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api, roles_allowed, get_current_user
from utilities.custom_logger import get_logger

logger = get_logger('authentication')
db = get_db()

def log_user_activity(user_id, action, details, request=None):
    """Log user activity to audit_logs collection."""
    if db is None:
        return
    ip_addr = '127.0.0.1'
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(',')[0]
        else:
            ip_addr = request.META.get('REMOTE_ADDR', '127.0.0.1')
            
    log_doc = {
        "user_id": ObjectId(user_id) if user_id else None,
        "action": action,
        "details": details,
        "ip_address": ip_addr,
        "timestamp": datetime.datetime.utcnow()
    }
    db.audit_logs.insert_one(log_doc)
    logger.info(f"Audit Log: User {user_id} - {action} - {details}")

def landing_page(request):
    """Render the public landing page for the AI Enterprise Decision Intelligence platform."""
    return render(request, 'landing.html')

def solutions_page(request):
    """Render the public Solutions index with enterprise AI solution cards."""
    return render(request, 'solutions.html')

def call_center_page(request):
    """Render the dedicated AI Base Call Center product page."""
    return render(request, 'ai_base_call_center.html')

def architecture_page(request):
    """Render the platform architecture page."""
    return render(request, 'architecture.html')

def login_page(request):
    """Render Landing/Login Template."""
    return render(request, 'landing.html')

def register_page(request):
    """Render Register Template."""
    return render(request, 'auth/register.html')

# API Endpoints
@csrf_exempt
def api_register(request):
    """API for User Registration."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    import json
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        role = data.get('role', 'viewer').strip().lower()
        
        # Validations
        if not email or not password or not first_name or not last_name:
            return JsonResponse({"error": "All fields are required."}, status=400)
            
        if role not in ['admin', 'manager', 'analyst', 'viewer']:
            role = 'viewer'  # Default fallback
            
        if db is None:
            return JsonResponse({"error": "Database connection failure."}, status=500)
            
        # Check if email exists
        if db.users.find_one({"email": email}):
            return JsonResponse({"error": "Email is already registered."}, status=400)
            
        # Get or create default Organization
        org = db.organizations.find_one({"name": "Default Organization"})
        if not org:
            org_doc = {"name": "Default Organization", "created_at": datetime.datetime.utcnow()}
            org_result = db.organizations.insert_one(org_doc)
            org_id = org_result.inserted_id
        else:
            org_id = org['_id']

        # Create temporary User ID to associate with workspace
        temp_user_id = ObjectId()

        # Get or create default Workspace
        workspace = db.workspaces.find_one({"organization_id": org_id, "name": "Staging Sandbox"})
        if not workspace:
            ws_doc = {
                "organization_id": org_id,
                "name": "Staging Sandbox",
                "owner_id": temp_user_id,
                "created_at": datetime.datetime.utcnow()
            }
            ws_result = db.workspaces.insert_one(ws_doc)
            workspace_id = ws_result.inserted_id
        else:
            workspace_id = workspace['_id']

        # Create User document
        verification_token = str(uuid.uuid4())
        user_doc = {
            "_id": temp_user_id,
            "email": email,
            "password_hash": make_password(password),
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "organization_id": org_id,
            "workspace_id": workspace_id,
            "is_verified": False,
            "verification_token": verification_token,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        # Log Audit activity
        log_user_activity(user_id, "REGISTER", f"User registered as {role} in organization {org_id}.", request)
        
        # In a real environment, send verification email.
        # We will simulate this by returning the token in response for testing.
        return JsonResponse({
            "message": "User registered successfully. Please verify your email.",
            "verification_token": verification_token,
            "user_id": user_id
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JsonResponse({"error": "Internal server error."}, status=500)

@csrf_exempt
def api_login(request):
    """API for User Login."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    import json
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return JsonResponse({"error": "Email and password are required."}, status=400)
            
        if db is None:
            return JsonResponse({"error": "Database connection failure."}, status=500)
            
        user = db.users.find_one({"email": email})
        if not user or not check_password(password, user['password_hash']):
            return JsonResponse({"error": "Invalid email or password."}, status=401)
            
        # Note: we allow login even if is_verified is False for demonstration,
        # but in production, check user.get('is_verified', False)
        
        # Generate JWT Token
        payload = {
            "user_id": str(user['_id']),
            "email": user['email'],
            "role": user.get('role', 'viewer'),
            "organization_id": str(user.get('organization_id', '')),
            "workspace_id": str(user.get('workspace_id', '')),
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Set token in session for UI views
        request.session['access_token'] = token
        
        # Log Audit
        log_user_activity(str(user['_id']), "LOGIN", "User logged in successfully.", request)
        
        return JsonResponse({
            "message": "Login successful.",
            "token": token,
            "user": {
                "id": str(user['_id']),
                "email": user['email'],
                "first_name": user.get('first_name'),
                "last_name": user.get('last_name'),
                "role": user.get('role', 'viewer'),
                "organization_id": str(user.get('organization_id', '')),
                "workspace_id": str(user.get('workspace_id', ''))
            }
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JsonResponse({"error": "Internal server error."}, status=500)

@csrf_exempt
def api_logout(request):
    """API for User Logout."""
    user = get_current_user(request)
    user_id = user['id'] if user else None
    
    # Clear session
    if 'access_token' in request.session:
        del request.session['access_token']
        
    if user_id:
        log_user_activity(user_id, "LOGOUT", "User logged out.", request)
        
    return JsonResponse({"message": "Logout successful."}, status=200)

@csrf_exempt
def api_verify_email(request, token):
    """Simulated verification endpoint."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    user = db.users.find_one({"verification_token": token})
    if not user:
        return JsonResponse({"error": "Invalid or expired verification token."}, status=400)
        
    db.users.update_one(
        {"_id": user['_id']},
        {"$set": {"is_verified": True, "updated_at": datetime.datetime.utcnow()}, "$unset": {"verification_token": ""}}
    )
    
    log_user_activity(str(user['_id']), "VERIFY_EMAIL", "Email verified successfully.", request)
    return JsonResponse({"message": "Email verified successfully. You can now login."}, status=200)

@csrf_exempt
@login_required_api
def api_profile(request):
    """Fetch current user's profile metadata."""
    # request.user_data is populated by login_required_api decorator
    return JsonResponse({"user": request.user_data}, status=200)

@csrf_exempt
@roles_allowed(['admin', 'manager'])
def api_audit_logs(request):
    """Fetch system audit logs for administrative overview."""
    if db is None:
        return JsonResponse({"error": "Database connection failure."}, status=500)
        
    # Fetch latest 100 audit logs
    logs = list(db.audit_logs.find().sort("timestamp", -1).limit(100))
    for log in logs:
        log['_id'] = str(log['_id'])
        if log.get('user_id'):
            log['user_id'] = str(log['user_id'])
            
    return JsonResponse({"logs": logs}, status=200)
