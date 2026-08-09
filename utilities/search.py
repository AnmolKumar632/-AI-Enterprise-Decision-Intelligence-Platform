import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('global_search')
db = get_db()

@csrf_exempt
@login_required_api
def api_global_search(request):
    """API endpoint to run a global keyword search across project datasets, models, reports, alerts, and chats."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    project_id = request.GET.get('project_id')
    query = request.GET.get('q', '').strip()

    if not project_id:
        return JsonResponse({"error": "project_id parameter is required."}, status=400)

    if not query:
        return JsonResponse({
            "datasets": [],
            "models": [],
            "reports": [],
            "alerts": [],
            "conversations": []
        }, status=200)

    try:
        pid = ObjectId(project_id)
        # Create case-insensitive regex pattern
        regex_pat = re.compile(query, re.IGNORECASE)

        results = {
            "datasets": [],
            "models": [],
            "reports": [],
            "alerts": [],
            "conversations": []
        }

        # 1. Search Datasets
        datasets = list(db.datasets.find({"project_id": pid, "filename": regex_pat}))
        for ds in datasets:
            results["datasets"].append({
                "id": str(ds['_id']),
                "name": ds['filename'],
                "version": ds.get('version', 1),
                "quality_score": ds.get('data_quality_score', 80.0),
                "type": "dataset"
            })

        # 2. Search Models
        models = list(db.models.find({
            "project_id": pid,
            "$or": [{"name": regex_pat}, {"target_column": regex_pat}]
        }))
        for m in models:
            results["models"].append({
                "id": str(m['_id']),
                "name": m['name'],
                "target_column": m.get('target_column'),
                "problem_type": m.get('problem_type'),
                "score": m.get('metrics', {}).get('accuracy') or m.get('metrics', {}).get('r2_score', 0.0),
                "type": "model"
            })

        # 3. Search Reports
        reports = list(db.reports.find({"project_id": pid, "name": regex_pat}))
        for r in reports:
            results["reports"].append({
                "id": str(r['_id']),
                "name": r['name'],
                "format": r.get('format', 'pdf'),
                "type": "report"
            })

        # 4. Search Alerts
        alerts = list(db.alerts.find({
            "project_id": pid,
            "$or": [{"event": regex_pat}, {"explanation": regex_pat}]
        }))
        for al in alerts:
            results["alerts"].append({
                "id": str(al['_id']),
                "event": al['event'],
                "severity": al.get('severity', 'info'),
                "explanation": al.get('explanation'),
                "is_read": al.get('is_read', False),
                "type": "alert"
            })

        # 5. Search Conversations
        conversations = list(db.conversations.find({"project_id": pid, "title": regex_pat}))
        for cv in conversations:
            results["conversations"].append({
                "id": str(cv['_id']),
                "title": cv['title'],
                "type": "conversation"
            })

        return JsonResponse(results, status=200)

    except Exception as e:
        logger.error(f"Global search failed: {str(e)}")
        return JsonResponse({"error": f"Failed to execute global search: {str(e)}"}, status=500)
