import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.fraud_detection.tasks import run_anomaly_detection_task
from utilities.custom_logger import get_logger

logger = get_logger('fraud_anomaly_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_run_anomaly_detection(request):
    """Start unsupervised outlier and fraud detection asynchronously."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        dataset_id = data.get('dataset_id')
        feature_cols = data.get('features') # list of numerical columns
        contamination = float(data.get('contamination', 0.05)) # percentage of anomalies expected
        
        if not dataset_id or not feature_cols:
            return JsonResponse({"error": "dataset_id and features are required."}, status=400)
            
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        project_id = str(dataset.get('project_id'))
        
        # Verify columns exist
        schema = dataset.get('metadata', {}).get('schema', {})
        for col in feature_cols:
            if col not in schema:
                return JsonResponse({"error": f"Feature column '{col}' not found in dataset schema."}, status=400)
                
        # Trigger Celery Task
        user_id = request.user_data['id']
        task = run_anomaly_detection_task.delay(project_id, dataset_id, feature_cols, contamination, user_id)
        
        # Log Audit
        log_user_activity(
            user_id,
            "ANOMALY_TRIGGER",
            f"Triggered anomaly detection on dataset {dataset_id} for features {feature_cols}.",
            request
        )
        
        return JsonResponse({
            "message": "Anomaly and fraud detection pipeline initiated.",
            "task_id": task.id
        }, status=202)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to initiate anomaly detection: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_get_anomaly_results(request, project_id):
    """Retrieve anomaly detection records for a project workspace."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    results = list(db.predictions.find({
        "project_id": ObjectId(project_id),
        "type": "anomaly"
    }).sort("created_at", -1))
    
    for r in results:
        r['_id'] = str(r['_id'])
        r['project_id'] = str(r['project_id'])
        r['dataset_id'] = str(r['dataset_id'])
        
    return JsonResponse({"results": results}, status=200)
