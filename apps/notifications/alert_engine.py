import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api, roles_allowed
from utilities.custom_logger import get_logger

logger = get_logger('alert_engine')
db = get_db()

class AlertEngine:
    @staticmethod
    def scan_for_alerts(project_id: str) -> int:
        """Scan project assets and generate alerts in the db. Returns count of new alerts generated."""
        if db is None:
            return 0
            
        pid = ObjectId(project_id)
        new_alerts_count = 0

        # Helper to insert unique alert
        def add_alert(event, severity, metric, explanation, action):
            nonlocal new_alerts_count
            # Check if alert already exists to prevent duplicate notifications
            existing = db.alerts.find_one({
                "project_id": pid,
                "event": event,
                "metric": metric,
                "is_read": False
            })
            if not existing:
                db.alerts.insert_one({
                    "project_id": pid,
                    "event": event,
                    "severity": severity,
                    "metric": metric,
                    "explanation": explanation,
                    "action_recommended": action,
                    "is_read": False,
                    "timestamp": datetime.datetime.utcnow()
                })
                # Send to general notifications collection too
                db.notifications.insert_one({
                    "user_id": None, # Global broadcast alert
                    "title": f"{severity.upper()}: {event}",
                    "message": explanation,
                    "is_read": False,
                    "created_at": datetime.datetime.utcnow()
                })
                new_alerts_count += 1

        # Check if project has auto retrain enabled
        project_setting = db.projects.find_one({"_id": pid}) or {}
        auto_retrain_enabled = project_setting.get("auto_retrain_enabled", True)

        # 1. Scan Data Quality
        datasets = list(db.datasets.find({"project_id": pid}).sort("created_at", -1))
        for ds in datasets:
            score = ds.get('data_quality_score', 100.0)
            if score < 75.0:
                severity = "CRITICAL" if score < 60.0 else "HIGH"
                add_alert(
                    event="Data Quality Degradation",
                    severity=severity,
                    metric="Data Quality Score",
                    explanation=f"Dataset '{ds['filename']}' registered a low quality score of {score}%. Issues detected in values completeness or outliers.",
                    action="Run the AI Preprocessing pipeline to clean duplicates, impute nulls, and clip extreme outliers."
                )
                
                # Auto-retrain trigger on CRITICAL quality drop
                if severity == "CRITICAL" and auto_retrain_enabled:
                    model = db.models.find_one({"project_id": pid, "dataset_id": ds["_id"]})
                    if model:
                        try:
                            from apps.automl.tasks import train_automl_models_task
                            train_automl_models_task(
                                project_id=str(pid),
                                dataset_id=str(ds["_id"]),
                                target_col=model.get("target_column"),
                                problem_type=model.get("problem_type"),
                                user_id=str(model.get("owner_id", "system"))
                            )
                            db.data_lineage.insert_one({
                                "dataset_id": ds["_id"],
                                "operation": "AUTO_RETRAIN_TRIGGERED",
                                "details": f"Automatically retrained model '{model.get('name')}' due to Critical Data Quality score ({score}%).",
                                "timestamp": datetime.datetime.utcnow()
                            })
                        except Exception as retrain_ex:
                            logger.error(f"Failed to auto-retrain model on quality alert: {str(retrain_ex)}")

        # 2. Scan Forecasting downswings
        forecasts = list(db.predictions.find({"project_id": pid, "type": "forecasting"}).sort("created_at", -1))
        for f in forecasts:
            if f.get('status') == 'success' and f.get('forecast_values'):
                hist_avg = sum(f['historical_values'][-6:]) / len(f['historical_values'][-6:]) if len(f['historical_values']) >= 6 else sum(f['historical_values']) / len(f['historical_values'])
                fore_avg = sum(f['forecast_values']) / len(f['forecast_values'])
                change = ((fore_avg - hist_avg) / hist_avg * 100) if hist_avg > 0 else 0.0
                
                if change < -10.0:
                    add_alert(
                        event="Revenue/KPI Forecast Decline",
                        severity="HIGH",
                        metric=f"Forecast Trend ({f.get('target_column')})",
                        explanation=f"Time-series projections for '{f.get('target_column')}' show a MoM average contraction of {round(abs(change), 2)}%.",
                        action="Launch Root Cause Analysis to identify underperforming segments and adjust price variables in Simulator."
                    )

        # 3. Scan Model Monitoring Drift
        monitoring = list(db.predictions.find({"project_id": pid, "type": "monitoring"}).sort("created_at", -1))
        for m in monitoring:
            metrics = m.get('metrics', {})
            status = metrics.get('status')
            if status in ["at_risk", "critical"]:
                severity = "CRITICAL" if status == "critical" else "MEDIUM"
                add_alert(
                    event="Predictive Model Drift",
                    severity=severity,
                    metric="Feature Data Drift",
                    explanation=f"Inference calculations flag significant input feature drift of {metrics.get('data_drift_percentage')}% on model '{metrics.get('model_id')[:8]}...'.",
                    action="Model retraining is highly recommended. Retrain the model on the latest dataset using AutoML pipelines."
                )
                
                # Auto-retrain trigger on Feature Drift
                if auto_retrain_enabled and metrics.get('model_id'):
                    try:
                        target_model = db.models.find_one({"_id": ObjectId(metrics.get('model_id'))})
                        if target_model:
                            from apps.automl.tasks import train_automl_models_task
                            train_automl_models_task(
                                project_id=str(pid),
                                dataset_id=str(target_model["dataset_id"]),
                                target_col=target_model.get("target_column"),
                                problem_type=target_model.get("problem_type"),
                                user_id=str(target_model.get("owner_id", "system"))
                            )
                            db.data_lineage.insert_one({
                                "dataset_id": target_model["dataset_id"],
                                "operation": "AUTO_RETRAIN_TRIGGERED",
                                "details": f"Automatically retrained model '{target_model.get('name')}' due to Feature Drift ({metrics.get('data_drift_percentage')}%).",
                                "timestamp": datetime.datetime.utcnow()
                            })
                    except Exception as retrain_ex:
                        logger.error(f"Failed to auto-retrain model on drift alert: {str(retrain_ex)}")

        # 4. Scan Flagged Anomalies
        anomalies = list(db.predictions.find({"project_id": pid, "type": "anomaly"}).sort("created_at", -1))
        for an in anomalies:
            summary = an.get('summary', {})
            pct = summary.get('anomaly_percentage', 0.0)
            if pct > 8.0:
                add_alert(
                    event="Unusual Fraud/Outliers Count",
                    severity="HIGH",
                    metric="Flagged Anomalies Ratio",
                    explanation=f"Unsupervised scanner flagged {summary.get('anomaly_count')} statistical outliers, representing {pct}% of transaction rows.",
                    action="Export and audit row records flagged with extreme risk scores (>80%) on the Anomalies tab."
                )

        return new_alerts_count


@csrf_exempt
@login_required_api
def api_list_alerts(request, project_id):
    """List alerts associated with a project workspace."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    alerts = list(db.alerts.find({"project_id": ObjectId(project_id)}).sort("timestamp", -1))
    for al in alerts:
        al['_id'] = str(al['_id'])
        al['project_id'] = str(al['project_id'])
        
    return JsonResponse({"alerts": alerts}, status=200)

@csrf_exempt
@login_required_api
def api_mark_alert_read(request):
    """Mark an alert or all alerts as read."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    import json
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')
        project_id = data.get('project_id')
        
        if alert_id:
            db.alerts.update_one({"_id": ObjectId(alert_id)}, {"$set": {"is_read": True}})
        elif project_id:
            db.alerts.update_many({"project_id": ObjectId(project_id)}, {"$set": {"is_read": True}})
            
        return JsonResponse({"message": "Alert status updated successfully."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_trigger_scan_alerts(request):
    """Trigger a manual scan of project metrics for alerts."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    import json
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        if not project_id:
            return JsonResponse({"error": "project_id is required."}, status=400)
            
        count = AlertEngine.scan_for_alerts(project_id)
        return JsonResponse({"message": "Scan completed.", "new_alerts_found": count}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
