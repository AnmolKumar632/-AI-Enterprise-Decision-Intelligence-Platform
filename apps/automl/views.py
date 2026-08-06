import os
import json
import pandas as pd
import numpy as np
import joblib
import datetime
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.automl.tasks import train_automl_models_task
from utilities.custom_logger import get_logger

logger = get_logger('automl_views')
db = get_db()

PRED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'media', 'predictions')
os.makedirs(PRED_DIR, exist_ok=True)

@csrf_exempt
@login_required_api
def api_trigger_training(request):
    """Start the AutoML training pipeline as an asynchronous background task."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        dataset_id = data.get('dataset_id')
        target_col = data.get('target_column')
        
        if not dataset_id or not target_col:
            return JsonResponse({"error": "dataset_id and target_column are required."}, status=400)
            
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        project_id = str(dataset.get('project_id'))
        
        # 1. Load dataset preview or schema to determine problem type
        schema = dataset.get('metadata', {}).get('schema', {}).get(target_col)
        if not schema:
            return JsonResponse({"error": f"Target column '{target_col}' not found in metadata schema."}, status=400)
            
        distinct_count = schema.get('distinct_count', 0)
        semantic_type = schema.get('semantic_type', '')
        
        # Determine classification vs regression
        if semantic_type == 'numerical' and distinct_count > 15:
            problem_type = 'regression'
        else:
            problem_type = 'classification'
            
        # Trigger Celery Task
        user_id = request.user_data['id']
        task = train_automl_models_task.delay(project_id, dataset_id, target_col, problem_type, user_id)
        
        # Log Audit activity
        log_user_activity(
            user_id,
            "AUTOML_TRAIN_TRIGGER",
            f"Triggered AutoML training for target '{target_col}' on dataset {dataset_id}.",
            request
        )
        
        return JsonResponse({
            "message": "AutoML training triggered successfully.",
            "task_id": task.id,
            "detected_problem_type": problem_type
        }, status=202)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to trigger AutoML training: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_get_leaderboard(request, project_id):
    """Retrieve leaderboard of all trained models for a project."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    models = list(db.models.find({"project_id": ObjectId(project_id)}).sort("created_at", -1))
    for m in models:
        m['_id'] = str(m['_id'])
        m['project_id'] = str(m['project_id'])
        m['dataset_id'] = str(m['dataset_id'])
        
    return JsonResponse({"models": models}, status=200)

@csrf_exempt
@login_required_api
def api_run_predictions(request):
    """Run batch predictions using a trained model package on a dataset."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        model_id = data.get('model_id')
        dataset_id = data.get('dataset_id')
        
        if not model_id or not dataset_id:
            return JsonResponse({"error": "model_id and dataset_id are required."}, status=400)
            
        # Load model metadata
        model_doc = db.models.find_one({"_id": ObjectId(model_id)})
        if not model_doc:
            return JsonResponse({"error": "Model not found."}, status=404)
            
        model_file = model_doc.get('file_path')
        if not model_file or not os.path.exists(model_file):
            return JsonResponse({"error": "Model file not found on disk."}, status=404)
            
        # Load dataset
        dataset_doc = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset_doc:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        data_file = dataset_doc.get('cleaned_file_path') or dataset_doc.get('file_path')
        if not data_file or not os.path.exists(data_file):
            return JsonResponse({"error": "Dataset file not found on disk."}, status=404)
            
        # Unpickle package
        package = joblib.load(model_file)
        model = package["model"]
        encoders = package["encoders"]
        target_col = package["target_col"]
        feature_names = package["feature_names"]
        problem_type = package["problem_type"]
        
        # Load target dataframe
        ext = os.path.splitext(data_file)[1].lower()
        df = pd.read_csv(data_file) if ext == '.csv' else pd.read_excel(data_file)
        
        # Drop target if present to prevent target leakage during inference
        df_inference = df.drop(columns=[target_col], errors='ignore')
        
        # Apply encoding and scaling matching the training features
        # Note: We align features to the expected feature names
        missing_features = set(feature_names) - set(df_inference.columns)
        if missing_features:
            return JsonResponse({
                "error": f"Uploaded dataset is missing required features: {list(missing_features)}"
            }, status=400)
            
        # Filter and align columns
        df_aligned = df_inference[feature_names].copy()
        
        # Fill missing values
        for col in df_aligned.columns:
            if df_aligned[col].isnull().sum() > 0:
                if pd.api.types.is_numeric_dtype(df_aligned[col]):
                    df_aligned[col] = df_aligned[col].fillna(df_aligned[col].median() if not df_aligned[col].empty else 0)
                else:
                    df_aligned[col] = df_aligned[col].fillna("Unknown")
                    
        # Apply Label Encoding
        for col, encoder in encoders.items():
            if col in df_aligned.columns:
                # Handle unseen labels by mapping them to 0 or default
                classes = list(encoder.classes_)
                df_aligned[col] = df_aligned[col].astype(str).apply(
                    lambda x: encoder.transform([x])[0] if x in classes else 0
                )
                
        # Call Predict
        preds = model.predict(df_aligned)
        
        # Create output DataFrame
        df_output = df.copy()
        df_output[f"predicted_{target_col}"] = preds
        
        # Save output predictions file
        pred_filename = f"predictions_{model_id}_{ObjectId()}.csv"
        pred_file_path = os.path.join(PRED_DIR, pred_filename)
        df_output.to_csv(pred_file_path, index=False)
        
        # Calculate local explainability (SHAP/LIME-like contribution weights per row)
        # For simplicity, we multiply standard feature values by their model coefficient/importance
        # to estimate positive/negative contribution.
        contributions = []
        importances = model_doc.get('feature_importance', {})
        
        for idx in range(min(5, len(df_aligned))):  # Preview first 5 row explanations
            row_exp = {}
            for col in feature_names:
                importance = importances.get(col, 0.0)
                feature_value = float(df_aligned.iloc[idx][col])
                # Estimate contribution
                contribution_score = feature_value * importance
                row_exp[col] = round(contribution_score, 4)
                
            contributions.append({
                "row_index": idx,
                "prediction": float(preds[idx]) if problem_type == 'regression' else int(preds[idx]),
                "explanations": row_exp
            })
            
        # Save prediction run record to MongoDB
        pred_doc = {
            "model_id": ObjectId(model_id),
            "dataset_id": ObjectId(dataset_id),
            "predictions_file_path": pred_file_path,
            "explainability_data": contributions,
            "created_at": datetime.datetime.utcnow()
        }
        result = db.predictions.insert_one(pred_doc)
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "MODEL_PREDICTION",
            f"Ran predictions with model {model_id} on dataset {dataset_id}.",
            request
        )
        
        return JsonResponse({
            "message": "Predictions completed.",
            "prediction_id": str(result.inserted_id),
            "sample_predictions": [float(x) if problem_type == 'regression' else int(x) for x in preds[:10]],
            "explainability_preview": contributions
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Prediction inference failed: {str(e)}")
        return JsonResponse({"error": f"Prediction failed: {str(e)}"}, status=500)

@csrf_exempt
def api_download_model(request, model_id):
    """Download serialized model package file (.joblib)."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    model = db.models.find_one({"_id": ObjectId(model_id)})
    if not model or not model.get('file_path'):
        return JsonResponse({"error": "Model file not found."}, status=404)
        
    file_path = model.get('file_path')
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    else:
        return JsonResponse({"error": "Model file missing from disk."}, status=404)
