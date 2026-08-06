import os
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.eda.analysis import (
    get_summary_statistics, 
    get_correlation_matrix, 
    get_missing_value_positions,
    get_distribution_data
)
from utilities.custom_logger import get_logger

logger = get_logger('eda_views')
db = get_db()

def _load_dataset_df(dataset_id: str):
    """Load pandas DataFrame from database ID, prioritizing cleaned file path."""
    if db is None:
        raise ValueError("Database offline.")
        
    dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        raise ValueError("Dataset not found.")
        
    file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file path not found: {file_path}")
        
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
        
    return df, dataset

@csrf_exempt
@login_required_api
def api_eda_summary(request, dataset_id):
    """Fetch high-level and detailed summary statistics for columns."""
    try:
        df, dataset = _load_dataset_df(dataset_id)
        stats = get_summary_statistics(df)
        missing_map = get_missing_value_positions(df)
        
        return JsonResponse({
            "dataset_name": dataset.get("filename"),
            "quality_score": dataset.get("data_quality_score", 0.0),
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "statistics": stats,
            "missing_heatmap": missing_map
        }, status=200)
    except Exception as e:
        logger.error(f"EDA Summary API failed: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_eda_correlation(request, dataset_id):
    """Fetch correlation matrix for numerical features."""
    try:
        df, _ = _load_dataset_df(dataset_id)
        corr_data = get_correlation_matrix(df)
        return JsonResponse(corr_data, status=200)
    except Exception as e:
        logger.error(f"EDA Correlation API failed: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_eda_chart_data(request, dataset_id, column):
    """Fetch histogram/bar distribution data for a specific column."""
    try:
        df, _ = _load_dataset_df(dataset_id)
        chart_data = get_distribution_data(df, column)
        return JsonResponse(chart_data, status=200)
    except Exception as e:
        logger.error(f"EDA Chart Data API failed for {column}: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
