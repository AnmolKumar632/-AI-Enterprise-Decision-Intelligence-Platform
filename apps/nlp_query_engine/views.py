import os
import json
import datetime
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.nlp_query_engine.interpreter import NLQueryInterpreter
from utilities.custom_logger import get_logger

logger = get_logger('nlp_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_run_nlp_query(request):
    """Process natural language business analytics queries."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        dataset_id = data.get('dataset_id')
        query_text = data.get('query', '').strip()
        
        if not dataset_id or not query_text:
            return JsonResponse({"error": "dataset_id and query are required."}, status=400)
            
        # Retrieve dataset path
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file not found on server."}, status=400)
            
        # Read dataset
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        if df.empty:
            return JsonResponse({"error": "Dataset is empty."}, status=400)
            
        # Execute Interpreter
        interpreter = NLQueryInterpreter(df)
        result = interpreter.interpret(query_text)
        
        # Save query record to MongoDB
        query_doc = {
            "project_id": dataset.get("project_id"),
            "user_id": ObjectId(request.user_data['id']),
            "query": query_text,
            "response": result.get("text"),
            "chart_data": result.get("chart"),
            "created_at": datetime.datetime.utcnow()
        }
        db.saved_queries.insert_one(query_doc)
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "NLP_QUERY",
            f"Submitted natural language query: '{query_text}'.",
            request
        )
        
        return JsonResponse({
            "query": query_text,
            "text_response": result.get("text"),
            "chart_response": result.get("chart")
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"NLP query execution failed: {str(e)}")
        return JsonResponse({"error": f"Failed to execute query: {str(e)}"}, status=500)
