import os
import json
import datetime
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.report_generator.generator import ReportGenerator
from utilities.custom_logger import get_logger

logger = get_logger('report_views')
db = get_db()

REPORT_DIR = os.path.join(settings.MEDIA_ROOT, 'reports')
os.makedirs(REPORT_DIR, exist_ok=True)

@csrf_exempt
@login_required_api
def api_generate_report(request):
    """Trigger PDF and PPTX executive report generation."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        dataset_id = data.get('dataset_id')
        
        if not project_id or not dataset_id:
            return JsonResponse({"error": "project_id and dataset_id are required."}, status=400)
            
        # 1. Fetch Project and Dataset metadata
        project = db.projects.find_one({"_id": ObjectId(project_id)})
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        
        if not project or not dataset:
            return JsonResponse({"error": "Project or Dataset not found."}, status=404)
            
        project_name = project.get('name', 'General Workspace')
        dataset_name = dataset.get('filename', 'dataset.csv')
        quality_score = dataset.get('data_quality_score', 80.0)
        
        # 2. Fetch Best Model
        best_model = db.models.find_one(
            {"project_id": ObjectId(project_id), "dataset_id": ObjectId(dataset_id), "status": "completed"},
            sort=[("metrics.accuracy", -1), ("metrics.r2_score", -1)] # Sort best metric
        )
        
        model_name = "N/A"
        model_metrics = {}
        if best_model:
            model_name = best_model.get('name', 'Optimized Model')
            model_metrics = best_model.get('metrics', {})
        else:
            model_name = "No model trained yet (AutoML run pending)"
            model_metrics = {"status": "unresolved"}
            
        # 3. Fetch Forecast findings
        forecast = db.predictions.find_one(
            {"project_id": ObjectId(project_id), "dataset_id": ObjectId(dataset_id), "type": "forecasting"},
            sort=[("created_at", -1)]
        )
        forecast_summary = "No forecasting predictions ran for this dataset."
        if forecast:
            t_col = forecast.get('target_column', 'metric')
            f_vals = forecast.get('forecast_values', [])
            f_dates = forecast.get('forecast_dates', [])
            if f_vals:
                forecast_summary = (
                    f"A time-series forecasting model was fit on column '{t_col}'. "
                    f"The projection spans from {f_dates[0]} to {f_dates[-1]} ({len(f_vals)} intervals). "
                    f"The forecasted mean value is {round(sum(f_vals)/len(f_vals), 2)}, with a final projected value of {round(f_vals[-1], 2)}."
                )
                
        # 4. Fetch Anomaly findings
        anomaly = db.predictions.find_one(
            {"project_id": ObjectId(project_id), "dataset_id": ObjectId(dataset_id), "type": "anomaly"},
            sort=[("created_at", -1)]
        )
        anomaly_summary = "No anomaly/fraud risk runs performed on this dataset."
        recs = [
            "Perform AutoML training to establish solid predictive baselines.",
            "Review features for high skewness and execute standard cleaning pipelines.",
            "Maintain safety inventory levels to account for baseline seasonal fluctuations."
        ]
        if anomaly:
            sum_data = anomaly.get('summary', {})
            cnt = sum_data.get('anomaly_count', 0)
            pct = sum_data.get('anomaly_percentage', 0.0)
            anomaly_summary = (
                f"Unsupervised anomaly detection evaluated {sum_data.get('total_rows_analyzed', 0)} transaction records. "
                f"A total of {cnt} records were flagged as statistical outliers ({pct}% of dataset), representing anomalous behaviors."
            )
            # Add dynamic recommendations based on anomalies
            if pct > 10.0:
                recs.insert(0, "CRITICAL: High anomaly rate (>10%) detected. Initiate immediate fraud transaction audits and security protocol reviews.")
            elif cnt > 0:
                recs.insert(0, f"Verify top {min(5, cnt)} flagged outlier rows with high risk scores (>80%) on the dashboard.")
                
        # 5. Generate Reports
        generator = ReportGenerator(REPORT_DIR)
        
        pdf_path = generator.generate_pdf(
            project_name, dataset_name, quality_score, model_name, 
            model_metrics, forecast_summary, anomaly_summary, recs
        )
        
        pptx_path = generator.generate_pptx(
            project_name, dataset_name, quality_score, model_name, model_metrics, recs
        )
        
        # Save records in MongoDB
        pdf_report_id = str(ObjectId())
        db.reports.insert_one({
            "_id": ObjectId(pdf_report_id),
            "project_id": ObjectId(project_id),
            "name": f"Executive Summary - {project_name} (PDF)",
            "format": "pdf",
            "file_path": pdf_path,
            "created_at": datetime.datetime.utcnow()
        })
        
        pptx_report_id = str(ObjectId())
        db.reports.insert_one({
            "_id": ObjectId(pptx_report_id),
            "project_id": ObjectId(project_id),
            "name": f"Executive Slide Deck - {project_name} (PPTX)",
            "format": "pptx",
            "file_path": pptx_path,
            "created_at": datetime.datetime.utcnow()
        })
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "REPORT_GENERATE",
            f"Generated PDF and PPTX executive reports for project {project_id}.",
            request
        )
        
        return JsonResponse({
            "message": "Reports compiled successfully.",
            "pdf_report_id": pdf_report_id,
            "pptx_report_id": pptx_report_id
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to generate reports: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_list_reports(request, project_id):
    """List compiled report records for a project."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    reports = list(db.reports.find({"project_id": ObjectId(project_id)}).sort("created_at", -1))
    for r in reports:
        r['_id'] = str(r['_id'])
        r['project_id'] = str(r['project_id'])
        # strip absolute file path for api exposure
        r['filename'] = os.path.basename(r.get('file_path', ''))
        
    return JsonResponse({"reports": reports}, status=200)

@csrf_exempt
def api_download_report(request, report_id):
    """Download a compiled report file."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    report = db.reports.find_one({"_id": ObjectId(report_id)})
    if not report or not report.get('file_path'):
        return JsonResponse({"error": "Report file not found."}, status=404)
        
    file_path = report.get('file_path')
    if os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        content_type = 'application/pdf' if ext == '.pdf' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    else:
        return JsonResponse({"error": "Report file missing from disk."}, status=404)
