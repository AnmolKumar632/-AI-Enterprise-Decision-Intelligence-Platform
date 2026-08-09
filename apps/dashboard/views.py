import json
import datetime
import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_ui, login_required_api
from apps.authentication.views import log_user_activity
from utilities.custom_logger import get_logger

logger = get_logger('dashboard_views')
db = get_db()

@login_required_ui
def dashboard_index(request):
    """Render the primary Glassmorphism analytics dashboard workspace."""
    # request.user_data is populated by login_required_ui decorator
    return render(request, 'dashboard.html', {"user": request.user_data})

@csrf_exempt
@login_required_api
def api_create_project(request):
    """API endpoint to initialize a new project workspace."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return JsonResponse({"error": "Project name is required."}, status=400)
            
        project_doc = {
            "name": name,
            "description": description,
            "owner_id": ObjectId(request.user_data['id']),
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        result = db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "PROJECT_CREATE",
            f"Created project workspace '{name}' ({project_id}).",
            request
        )
        
        return JsonResponse({
            "message": "Project workspace created successfully.",
            "project_id": project_id,
            "name": name
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"Failed to create project: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_list_projects(request):
    """Retrieve all project workspaces belonging to the logged-in user."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    user_id = request.user_data['id']
    projects = list(db.projects.find({"owner_id": ObjectId(user_id)}).sort("created_at", -1))
    
    for p in projects:
        p['_id'] = str(p['_id'])
        p['owner_id'] = str(p['owner_id'])
        
    return JsonResponse({"projects": projects}, status=200)

import os
import pandas as pd
import numpy as np

@csrf_exempt
@login_required_api
def api_get_visualization_data(request):
    """Generate dynamic chart series data or correlation matrices for datasets."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    
    dataset_id = request.GET.get('dataset_id')
    x_col = request.GET.get('x_col')
    y_col = request.GET.get('y_col')
    chart_type = request.GET.get('chart_type', 'bar').lower()
    agg_func = request.GET.get('aggregation', 'SUM').upper()
    group_by_col = request.GET.get('group_by')
    
    if not dataset_id:
        return JsonResponse({"error": "dataset_id is required."}, status=400)
        
    try:
        ds = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not ds:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        file_path = ds.get('cleaned_file_path') or ds.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file missing."}, status=404)
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        all_cols = df.columns.tolist()
        
        # 1. Heatmap / Correlation Matrix
        if chart_type == 'heatmap':
            if len(numeric_cols) < 2:
                return JsonResponse({"error": "At least 2 numeric columns required for heatmap."}, status=400)
            corr_df = df[numeric_cols].corr().round(3).fillna(0)
            return JsonResponse({
                "chart_type": "heatmap",
                "x_labels": numeric_cols,
                "y_labels": numeric_cols,
                "z_values": corr_df.values.tolist(),
                "numeric_columns": numeric_cols,
                "all_columns": all_cols,
                "total_records": int(len(df))
            }, status=200)
            
        # 2. Histogram / Distribution
        if chart_type == 'histogram':
            col = x_col or (numeric_cols[0] if numeric_cols else all_cols[0])
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            counts, bin_edges = np.histogram(series, bins=15)
            labels = [f"{round(bin_edges[i], 1)}-{round(bin_edges[i+1], 1)}" for i in range(len(counts))]
            return JsonResponse({
                "chart_type": "histogram",
                "title": f"Distribution of {col}",
                "labels": labels,
                "values": counts.tolist(),
                "all_columns": all_cols,
                "numeric_columns": numeric_cols,
                "total_records": int(len(df))
            }, status=200)
            
        # 3. Standard chart types
        if not x_col or x_col not in df.columns:
            x_col = all_cols[0]
            
        if chart_type == 'scatter':
            if not y_col or y_col not in df.columns:
                y_col = numeric_cols[0] if numeric_cols else all_cols[-1]
            valid_df = df[[x_col, y_col]].dropna().head(500)
            return JsonResponse({
                "chart_type": "scatter",
                "title": f"{y_col} vs {x_col}",
                "x_values": valid_df[x_col].tolist(),
                "y_values": valid_df[y_col].tolist(),
                "x_label": x_col,
                "y_label": y_col,
                "all_columns": all_cols,
                "numeric_columns": numeric_cols,
                "total_records": int(len(df))
            }, status=200)
            
        if chart_type == 'box':
            if not y_col or y_col not in df.columns:
                y_col = numeric_cols[0] if numeric_cols else all_cols[-1]
            groups = {}
            for name, group in df.groupby(x_col):
                groups[str(name)] = pd.to_numeric(group[y_col], errors='coerce').dropna().tolist()
            return JsonResponse({
                "chart_type": "box",
                "title": f"{y_col} Distribution by {x_col}",
                "box_groups": groups,
                "all_columns": all_cols,
                "numeric_columns": numeric_cols,
                "total_records": int(len(df))
            }, status=200)
            
        # Bar, Line, Area, Pie aggregation
        if not y_col or y_col not in df.columns:
            y_col = numeric_cols[0] if numeric_cols else all_cols[-1]
            
        df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
        agg_map = {
            'SUM': 'sum', 'AVG': 'mean', 'COUNT': 'count',
            'MIN': 'min', 'MAX': 'max', 'MEDIAN': 'median'
        }
        py_agg = agg_map.get(agg_func, 'mean')
        
        if group_by_col and group_by_col in df.columns and group_by_col != x_col:
            grouped = df.groupby([x_col, group_by_col])[y_col].agg(py_agg).unstack().fillna(0)
            series_list = []
            for col in grouped.columns:
                series_list.append({
                    "name": str(col),
                    "data": grouped[col].round(2).tolist()
                })
            labels = [str(idx) for idx in grouped.index]
            return JsonResponse({
                "chart_type": chart_type,
                "title": f"{agg_func}({y_col}) by {x_col} & {group_by_col}",
                "labels": labels,
                "multi_series": series_list,
                "all_columns": all_cols,
                "numeric_columns": numeric_cols,
                "total_records": int(len(df))
            }, status=200)
        else:
            grouped = df.groupby(x_col)[y_col].agg(py_agg).round(2).head(50)
            return JsonResponse({
                "chart_type": chart_type,
                "title": f"{agg_func}({y_col}) by {x_col}",
                "labels": [str(idx) for idx in grouped.index],
                "values": grouped.values.tolist(),
                "all_columns": all_cols,
                "numeric_columns": numeric_cols,
                "total_records": int(len(df))
            }, status=200)
            
    except Exception as e:
        logger.error(f"Visualization data error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_save_dashboard_widget(request):
    """Save or update a custom pinned widget in db.dashboards."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed."}, status=405)
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        title = data.get('title', 'Custom Widget')
        widget_type = data.get('widget_type', 'chart')
        config = data.get('config', {})
        
        if not project_id:
            return JsonResponse({"error": "project_id is required."}, status=400)
            
        doc = {
            "project_id": ObjectId(project_id),
            "owner_id": ObjectId(request.user_data['id']),
            "title": title,
            "widget_type": widget_type,
            "config": config,
            "updated_at": datetime.datetime.utcnow()
        }
        
        widget_id = data.get('widget_id')
        if widget_id:
            db.dashboards.update_one({"_id": ObjectId(widget_id)}, {"$set": doc})
        else:
            doc["created_at"] = datetime.datetime.utcnow()
            res = db.dashboards.insert_one(doc)
            widget_id = str(res.inserted_id)
            
        return JsonResponse({"message": "Widget saved successfully.", "widget_id": widget_id}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_get_workspace_dashboard(request, project_id):
    """Retrieve all custom widgets pinned for a project workspace."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        widgets = list(db.dashboards.find({"project_id": ObjectId(project_id)}).sort("created_at", 1))
        for w in widgets:
            w['_id'] = str(w['_id'])
            w['project_id'] = str(w['project_id'])
            w['owner_id'] = str(w['owner_id'])
            
        return JsonResponse({"widgets": widgets}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_delete_dashboard_widget(request):
    """Delete a pinned dashboard widget."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed."}, status=405)
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        widget_id = data.get('widget_id')
        if not widget_id:
            return JsonResponse({"error": "widget_id is required."}, status=400)
            
        db.dashboards.delete_one({"_id": ObjectId(widget_id)})
        return JsonResponse({"message": "Widget deleted successfully."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_delete_project(request, project_id):
    """Delete a project workspace and ALL of its associated data (datasets, models, reports, etc.)."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    project = db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        return JsonResponse({"error": "Project not found."}, status=404)

    # Only the owning user can delete their workspace
    if str(project.get('owner_id')) != str(request.user_data['id']):
        return JsonResponse({"error": "Forbidden. You do not own this workspace."}, status=403)

    proj_oid = ObjectId(project_id)

    # Remove dataset physical files + their records
    for ds in db.datasets.find({"project_id": proj_oid}):
        for key in ('file_path', 'cleaned_file_path'):
            path = ds.get(key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Failed to remove dataset file {path}: {str(e)}")
    db.datasets.delete_many({"project_id": proj_oid})

    # Remove report physical files + their records
    for rep in db.reports.find({"project_id": proj_oid}):
        path = rep.get('file_path')
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Failed to remove report file {path}: {str(e)}")
    db.reports.delete_many({"project_id": proj_oid})

    # Remove serialized model files, then their records
    for model in db.models.find({"project_id": proj_oid}):
        path = model.get('file_path')
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Failed to remove model file {path}: {str(e)}")
    db.models.delete_many({"project_id": proj_oid})
    db.predictions.delete_many({"project_id": proj_oid})
    db.dashboards.delete_many({"project_id": proj_oid})
    db.conversations.delete_many({"project_id": proj_oid})
    db.messages.delete_many({"project_id": proj_oid})
    db.saved_queries.delete_many({"project_id": proj_oid})
    db.alerts.delete_many({"project_id": proj_oid})
    db.automl_jobs.delete_many({"project_id": proj_oid})
    db.data_quality_reports.delete_many({"project_id": proj_oid})
    db.data_lineage.delete_many({"project_id": proj_oid})
    db.dataset_versions.delete_many({"project_id": proj_oid})
    db.business_personas.delete_many({"project_id": proj_oid})

    db.projects.delete_one({"_id": proj_oid})

    log_user_activity(
        request.user_data['id'],
        "PROJECT_DELETE",
        f"Deleted workspace '{project.get('name', project_id)}' and all associated data.",
        request
    )

    return JsonResponse({"message": "Workspace deleted successfully."}, status=200)

