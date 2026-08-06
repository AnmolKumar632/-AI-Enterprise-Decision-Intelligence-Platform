import json
import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_ui, login_required_api
from apps.authentication.views import log_user_activity
from utilities.custom_logger import get_logger

logger = get_logger('dashboard_views')
db = get_db()

@login_required_ui
def dashboard_index(request):
    """Render the primary Glassmorphism analytics dashboard workspace."""
    # request.user_data is populated by login_required_ui decorator
    return render(request, 'dashboard.html', {"user": request.user_data})

@csrf_exempt
@login_required_api
def api_create_project(request):
    """API endpoint to initialize a new project workspace."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return JsonResponse({"error": "Project name is required."}, status=400)
            
        project_doc = {
            "name": name,
            "description": description,
            "owner_id": ObjectId(request.user_data['id']),
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        result = db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "PROJECT_CREATE",
            f"Created project workspace '{name}' ({project_id}).",
            request
        )
        
        return JsonResponse({
            "message": "Project workspace created successfully.",
            "project_id": project_id,
            "name": name
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to create project: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_list_projects(request):
    """Retrieve all project workspaces belonging to the logged-in user."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    user_id = request.user_data['id']
    projects = list(db.projects.find({"owner_id": ObjectId(user_id)}).sort("created_at", -1))
    
    for p in projects:
        p['_id'] = str(p['_id'])
        p['owner_id'] = str(p['owner_id'])
        
    return JsonResponse({"projects": projects}, status=200)
