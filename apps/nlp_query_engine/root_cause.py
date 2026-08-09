import os
import datetime
import pandas as pd
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('root_cause_engine')
db = get_db()

class RootCauseAnalysis:
    @staticmethod
    def analyze_kpi_drop(df: pd.DataFrame, target_col: str, date_col: str) -> dict:
        """Analyze changes in target_col and find the root cause segments that contributed to drops."""
        # 1. Parse date and sort
        df_copy = df.copy()
        df_copy[date_col] = pd.to_datetime(df_copy[date_col])
        df_copy = df_copy.sort_values(by=date_col)
        
        # 2. Resample monthly
        monthly = df_copy.set_index(date_col).resample('ME')[target_col].sum().reset_index()
        
        if len(monthly) < 2:
            return {
                "success": False,
                "error": "Dataset requires at least 2 monthly periods to analyze growth changes."
            }

        # Find the latest month and the previous month
        curr_row = monthly.iloc[-1]
        prev_row = monthly.iloc[-2]
        
        curr_date = curr_row[date_col]
        prev_date = prev_row[date_col]
        
        curr_val = float(curr_row[target_col])
        prev_val = float(prev_row[target_col])
        
        diff = curr_val - prev_val
        pct_change = (diff / prev_val * 100) if prev_val > 0 else 0.0

        if diff >= 0:
            return {
                "success": True,
                "message": f"KPI '{target_col}' increased by {round(pct_change, 2)}% in the latest period. No decline detected.",
                "pct_change": pct_change,
                "decline_detected": False
            }

        # 3. KPI Declined -> Drill down into categorical dimensions
        cat_cols = list(df_copy.select_dtypes(include=['object', 'category']).columns)
        # Include low-cardinality numericals as segments
        for col in df_copy.columns:
            if col != target_col and col != date_col:
                if df_copy[col].nunique() < 15 and col not in cat_cols:
                    cat_cols.append(col)

        findings = []

        # Filter rows belonging to current vs previous month
        df_prev = df_copy[(df_copy[date_col].dt.month == prev_date.month) & (df_copy[date_col].dt.year == prev_date.year)]
        df_curr = df_copy[(df_copy[date_col].dt.month == curr_date.month) & (df_copy[date_col].dt.year == curr_date.year)]

        for col in cat_cols:
            prev_grouped = df_prev.groupby(col)[target_col].sum()
            curr_grouped = df_curr.groupby(col)[target_col].sum()
            
            # Compare differences
            diff_series = prev_grouped - curr_grouped
            # Remove negative differences (means they increased)
            diff_series = diff_series[diff_series > 0]
            
            if not diff_series.empty:
                worst_segment = diff_series.idxmax()
                segment_drop = float(diff_series.max())
                total_drop = abs(diff)
                contribution_pct = round((segment_drop / total_drop) * 100, 2)
                
                findings.append({
                    "dimension": col,
                    "segment": str(worst_segment),
                    "segment_drop_value": round(segment_drop, 2),
                    "contribution_percentage": contribution_pct,
                    "previous_value": round(float(prev_grouped.get(worst_segment, 0.0)), 2),
                    "current_value": round(float(curr_grouped.get(worst_segment, 0.0)), 2)
                })

        # Sort dimensions by contribution percentage
        findings = sorted(findings, key=lambda x: x['contribution_percentage'], reverse=True)
        
        # Determine main root cause
        if findings:
            main = findings[0]
            root_cause_explanation = (
                f"The overall drop in {target_col} of ${round(abs(diff), 2)} (-{round(abs(pct_change), 1)}%) "
                f"was primarily driven by the **'{main['segment']}'** segment under the **'{main['dimension']}'** dimension. "
                f"This segment contracted by **${round(main['segment_drop_value'], 2)}**, explaining "
                f"**{main['contribution_percentage']}%** of the total decline."
            )
            recs = [
                f"Audit operational performance and customer retention in segment '{main['segment']}'.",
                f"Run marketing promotions targeting '{main['segment']}' to stabilize demand contraction.",
                f"Review pricing structures or supplier margins for '{main['segment']}' to address profitability drops."
            ]
        else:
            root_cause_explanation = "A general decline was observed, but it was evenly distributed across all segments."
            recs = ["Review macro pricing variables and market seasonal cycles."]

        return {
            "success": True,
            "decline_detected": True,
            "target_kpi": target_col,
            "period": f"{prev_date.strftime('%B %Y')} ➔ {curr_date.strftime('%B %Y')}",
            "overall_change": round(diff, 2),
            "percentage_change": round(pct_change, 2),
            "root_cause_explanation": root_cause_explanation,
            "drilldown_dimensions": findings,
            "recommendations": recs
        }

@csrf_exempt
@login_required_api
def api_run_root_cause(request):
    """API view to run automated root cause diagnostics on a dataset KPI drop."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        data = request.GET
        dataset_id = data.get('dataset_id')
        target_col = data.get('target_column')
        date_col = data.get('date_column')

        if not dataset_id:
            return JsonResponse({"error": "dataset_id is required."}, status=400)

        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)

        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file missing from server disk."}, status=404)

        ext = os.path.splitext(file_path)[1].lower()
        df = pd.read_csv(file_path) if ext == '.csv' else pd.read_excel(file_path)

        # Resolve columns dynamically if not specified
        if not target_col or target_col not in df.columns:
            # Look for Sales / Profit
            for col in df.columns:
                if any(k in col.lower() for k in ['sales', 'profit', 'revenue', 'spend']):
                    target_col = col
                    break
            if not target_col:
                target_col = df.select_dtypes(include=[np.number]).columns[-1]

        if not date_col or date_col not in df.columns:
            # Look for Date / Month / Timestamp
            for col in df.columns:
                if any(k in col.lower() for k in ['date', 'time', 'month', 'year', 'timestamp']):
                    date_col = col
                    break
            if not date_col:
                return JsonResponse({"error": "Could not identify a date-time column. Please specify date_column."}, status=400)

        analysis = RootCauseAnalysis.analyze_kpi_drop(df, target_col, date_col)
        
        # Save RCA report to predictions collection
        if analysis.get('success'):
            db.predictions.insert_one({
                "project_id": dataset['project_id'],
                "dataset_id": ObjectId(dataset_id),
                "type": "root_cause",
                "analysis": analysis,
                "created_at": datetime.datetime.utcnow()
            })

        return JsonResponse(analysis, status=200)

    except Exception as e:
        logger.error(f"RCA failed: {str(e)}")
        return JsonResponse({"error": f"Failed to execute Root Cause Analysis: {str(e)}"}, status=500)
