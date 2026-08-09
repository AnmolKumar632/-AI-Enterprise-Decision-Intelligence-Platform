import os
import joblib
import pandas as pd
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.ai_engine.explainable_ai import ExplainableAI
from utilities.custom_logger import get_logger

logger = get_logger('ai_engine_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_get_explainability(request, model_id, dataset_id, row_index):
    """API endpoint to get prediction explanation for a specific dataset row."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        row_idx = int(row_index)
        
        # 1. Fetch Model metadata
        model_doc = db.models.find_one({"_id": ObjectId(model_id)})
        if not model_doc:
            return JsonResponse({"error": "Model not found."}, status=404)

        model_file = model_doc.get('file_path')
        if not model_file or not os.path.exists(model_file):
            return JsonResponse({"error": "Model file missing from disk."}, status=404)

        # 2. Fetch Dataset
        dataset_doc = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset_doc:
            return JsonResponse({"error": "Dataset not found."}, status=404)

        data_file = dataset_doc.get('cleaned_file_path') or dataset_doc.get('file_path')
        if not data_file or not os.path.exists(data_file):
            return JsonResponse({"error": "Dataset file missing from disk."}, status=404)

        # 3. Load Model Package
        package = joblib.load(model_file)
        model = package["model"]
        encoders = package["encoders"]
        target_col = package["target_col"]
        feature_names = package["feature_names"]
        problem_type = package["problem_type"]

        # 4. Load Dataframe row
        ext = os.path.splitext(data_file)[1].lower()
        df = pd.read_csv(data_file) if ext == '.csv' else pd.read_excel(data_file)

        if row_idx < 0 or row_idx >= len(df):
            return JsonResponse({"error": f"Row index {row_idx} is out of bounds (len: {len(df)})."}, status=400)

        raw_row = df.iloc[[row_idx]].copy()
        
        # Calculate summary statistics from baseline dataframe for perturbation thresholds
        summary_stats = {}
        for col in feature_names:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                summary_stats[col] = {
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std()),
                    "median": float(df[col].median())
                }

        # 5. Process row to match model feature signatures
        row_proc = raw_row.copy()
        row_proc = row_proc.drop(columns=[target_col], errors='ignore')
        
        for col in row_proc.columns:
            if pd.api.types.is_numeric_dtype(row_proc[col]):
                row_proc[col] = row_proc[col].fillna(df[col].median() if col in df.columns else 0.0)
            else:
                row_proc[col] = row_proc[col].fillna("Unknown")

        # Apply encoders
        for col, le in encoders.items():
            if col in row_proc.columns:
                val = row_proc.iloc[0][col]
                most_frequent = le.classes_[0]
                val_encoded = val if val in le.classes_ else most_frequent
                row_proc[col] = le.transform([str(val_encoded)])

        # Datetime transformations
        for col in row_proc.columns:
            if not pd.api.types.is_numeric_dtype(row_proc[col]):
                try:
                    dates = pd.to_datetime(row_proc[col], errors='raise')
                    row_proc[f'{col}_year'] = dates.dt.year
                    row_proc[f'{col}_month'] = dates.dt.month
                    row_proc[f'{col}_day'] = dates.dt.day
                    row_proc = row_proc.drop(columns=[col])
                    continue
                except Exception:
                    pass
                # categoricals
                row_proc[col] = pd.Categorical(row_proc[col]).codes

        # Re-index to ensure alignment
        for name in feature_names:
            if name not in row_proc.columns:
                row_proc[name] = 0.0

        row_proc = row_proc[feature_names]

        # 6. Compute LFP Explanation
        explanation = ExplainableAI.explain_prediction(
            model, encoders, row_proc, summary_stats, problem_type
        )
        explanation["row_index"] = row_idx
        explanation["original_values"] = raw_row.replace({np.nan: None}).to_dict(orient='records')[0]

        return JsonResponse(explanation, status=200)

    except Exception as e:
        logger.error(f"XAI API failed: {str(e)}")
        return JsonResponse({"error": f"Failed to calculate explainability contributions: {str(e)}"}, status=500)
