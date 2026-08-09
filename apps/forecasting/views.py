import json
import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.forecasting.tasks import run_forecasting_task
from utilities.custom_logger import get_logger

logger = get_logger('forecasting_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_run_forecast(request):
    """API endpoint to run time-series forecasting asynchronously."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        dataset_id = data.get('dataset_id')
        date_col = data.get('date_column')
        target_col = data.get('target_column')
        periods = int(data.get('periods', 12))
        freq = data.get('frequency', 'M') # 'D' for daily, 'M' for monthly (uses 'ME' resample in pandas)
        
        if not dataset_id or not date_col or not target_col:
            return JsonResponse({"error": "dataset_id, date_column, and target_column are required."}, status=400)
            
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        project_id = str(dataset.get('project_id'))
        
        # Match columns case-insensitively and whitespace-insensitively
        columns_list = dataset.get('metadata', {}).get('columns', [])
        for col in columns_list:
            if col.strip().lower() == date_col.strip().lower():
                date_col = col
            if col.strip().lower() == target_col.strip().lower():
                target_col = col
                
        # Verify columns exist
        schema = dataset.get('metadata', {}).get('schema', {})
        if date_col not in schema or target_col not in schema:
            return JsonResponse({"error": "Provided date or target column not found in dataset schema."}, status=400)
            
        # Resample frequency matching (Pandas monthly resample is 'ME', daily is 'D')
        pd_freq = 'ME' if freq == 'M' else 'D'
        
        # Trigger task
        user_id = request.user_data['id']
        task = run_forecasting_task.delay(project_id, dataset_id, date_col, target_col, periods, pd_freq, user_id)
        
        # Log Audit
        log_user_activity(
            user_id,
            "FORECAST_TRIGGER",
            f"Triggered forecast model on dataset {dataset_id} for target '{target_col}' with periods={periods}.",
            request
        )
        
        return JsonResponse({
            "message": "Forecasting model training initiated.",
            "task_id": task.id
        }, status=202)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to initiate forecasting: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_get_forecast_results(request, project_id):
    """Retrieve forecasting results for a project workspace."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    # Get latest forecasting results
    forecasts = list(db.predictions.find({
        "project_id": ObjectId(project_id),
        "type": "forecasting"
    }).sort("created_at", -1))
    
    for f in forecasts:
        f['_id'] = str(f['_id'])
        f['project_id'] = str(f['project_id'])
        f['dataset_id'] = str(f['dataset_id'])
        
    return JsonResponse({"forecasts": forecasts}, status=200)

@csrf_exempt
@login_required_api
def api_delete_prediction(request, prediction_id):
    """Delete a stored prediction result (forecast or anomaly scan)."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    prediction = db.predictions.find_one({"_id": ObjectId(prediction_id)})
    if not prediction:
        return JsonResponse({"error": "Prediction result not found."}, status=404)

    ptype = prediction.get('type', 'prediction')
    db.predictions.delete_one({"_id": ObjectId(prediction_id)})

    log_user_activity(
        request.user_data['id'],
        "PREDICTION_DELETE",
        f"Deleted {ptype} result {prediction_id}.",
        request
    )

    return JsonResponse({"message": "Prediction result deleted successfully."}, status=200)
