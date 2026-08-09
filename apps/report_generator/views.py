import os
import json
import datetime
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.template.loader import render_to_string
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
        logger.error(f"Report generation error: {str(e)}")
        return JsonResponse({"error": f"Report compilation failed: {str(e)}"}, status=500)

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
        content_type = {
            '.pdf': 'application/pdf',
            '.html': 'text/html',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }.get(ext, 'application/octet-stream')
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    else:
        return JsonResponse({"error": "Report file missing from disk."}, status=404)

@csrf_exempt
@login_required_api
def api_view_report(request, report_id):
    """Preview a compiled report inline in the browser."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        return JsonResponse({"error": "Database offline."}, status=500)

    report = db.reports.find_one({"_id": ObjectId(report_id)})
    if not report or not report.get('file_path'):
        return JsonResponse({"error": "Report file not found."}, status=404)

    file_path = report.get('file_path')
    if not os.path.exists(file_path):
        return JsonResponse({"error": "Report file missing from disk."}, status=404)

    ext = os.path.splitext(file_path)[1].lower()
    content_type = {
        '.pdf': 'application/pdf',
        '.html': 'text/html',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }.get(ext, 'application/octet-stream')

    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    return response

@csrf_exempt
@login_required_api
def api_generate_datastudio_report(request):
    """Generate a standalone HTML Data Studio report embedding pinned dashboard widgets."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')

        if not project_id:
            return JsonResponse({"error": "project_id is required."}, status=400)

        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return JsonResponse({"error": "Project not found."}, status=404)

        project_name = project.get('name', 'General Workspace')

        # Collect pinned dashboard widgets (charts) for the Data Studio report
        widgets = list(db.dashboards.find({"project_id": ObjectId(project_id)}).sort("created_at", 1))
        embedded_widgets = []
        for w in widgets:
            cfg = w.get('config', {})
            if not cfg.get('data'):
                continue
            embedded_widgets.append({
                "title": w.get('title', 'Custom Chart'),
                "data": cfg['data']
            })

        # Collect project datasets for reference metadata
        datasets = list(db.datasets.find({"project_id": ObjectId(project_id)}).sort("created_at", -1))
        dataset_meta = [{"name": d.get('filename', 'dataset.csv')} for d in datasets]

        html = render_to_string('reports/datastudio_report.html', {
            "project_name": project_name,
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "widget_count": len(embedded_widgets),
            "dataset_count": len(dataset_meta),
            "datasets": dataset_meta,
            "widgets_json": json.dumps(embedded_widgets)
        })

        filename = f"datastudio_{project_name.lower().replace(' ', '_')}_{int(datetime.datetime.utcnow().timestamp())}.html"
        file_path = os.path.join(REPORT_DIR, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

        report_id = str(ObjectId())
        db.reports.insert_one({
            "_id": ObjectId(report_id),
            "project_id": ObjectId(project_id),
            "name": f"Data Studio Report - {project_name}",
            "format": "html",
            "file_path": file_path,
            "created_at": datetime.datetime.utcnow()
        })

        log_user_activity(
            request.user_data['id'],
            "REPORT_DATASSTUDIO",
            f"Generated Data Studio HTML report for project {project_id}.",
            request
        )

        return JsonResponse({
            "message": "Data Studio report compiled successfully.",
            "report_id": report_id
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Data Studio report error: {str(e)}")
        return JsonResponse({"error": f"Data Studio report failed: {str(e)}"}, status=500)

@csrf_exempt
@login_required_api
def api_delete_report(request, report_id):
    """Delete a compiled report record and its file from disk."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    report = db.reports.find_one({"_id": ObjectId(report_id)})
    if not report:
        return JsonResponse({"error": "Report not found."}, status=404)

    file_path = report.get('file_path')
    db.reports.delete_one({"_id": ObjectId(report_id)})
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Failed to remove report file {file_path}: {str(e)}")

    log_user_activity(request.user_data['id'], "REPORT_DELETE", f"Deleted report {report_id}.", request)
    return JsonResponse({"message": "Report deleted successfully."}, status=200)
