import os
import datetime
import pandas as pd
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.ai_engine.preprocessing import DataPreprocessor
from utilities.custom_logger import get_logger

logger = get_logger('dataset_management')
db = get_db()

# Make sure media folders exist
DATASET_DIR = os.path.join(settings.MEDIA_ROOT, 'datasets')
os.makedirs(DATASET_DIR, exist_ok=True)

@csrf_exempt
@login_required_api
def api_upload_dataset(request):
    """API endpoint to upload CSV or Excel datasets."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database connection failure."}, status=500)
        
    project_id = request.POST.get('project_id')
    if not project_id:
        return JsonResponse({"error": "project_id is required."}, status=400)
        
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({"error": "No file uploaded."}, status=400)
        
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ['.csv', '.xlsx', '.xls']:
        return JsonResponse({"error": "Invalid file type. Only CSV and Excel files are supported."}, status=400)
        
    # Secure file signature validation (magic number check)
    try:
        header = uploaded_file.read(8)
        uploaded_file.seek(0)  # Reset pointer
        
        if ext == '.csv':
            try:
                header.decode('utf-8')
            except UnicodeDecodeError:
                return JsonResponse({"error": "Invalid CSV file. Content is binary and not valid text."}, status=400)
        elif ext == '.xlsx':
            if not header.startswith(b'PK\x03\x04'):
                return JsonResponse({"error": "Invalid Excel file. ZIP signature mismatch (renamed file)."}, status=400)
        elif ext == '.xls':
            if not header.startswith(b'\xd0\xcf\x11\xe0'):
                return JsonResponse({"error": "Invalid Excel file. OLE signature mismatch (renamed file)."}, status=400)
    except Exception as sig_err:
        return JsonResponse({"error": f"Security scan failed: {str(sig_err)}"}, status=400)

    try:
        # Determine dataset version if filename already exists in the project
        existing_ds = db.datasets.find_one({"project_id": ObjectId(project_id), "filename": filename})
        if existing_ds:
            next_version = existing_ds.get('version', 1) + 1
            dataset_id = str(existing_ds['_id'])
        else:
            next_version = 1
            dataset_id = str(ObjectId())

        # Save file to media directory using a versioned filename to prevent collisions
        fs = FileSystemStorage(location=DATASET_DIR)
        base_name, file_ext = os.path.splitext(filename)
        versioned_filename = f"{base_name}_v{next_version}{file_ext}"
        saved_filename = fs.save(versioned_filename, uploaded_file)
        file_path = os.path.join(DATASET_DIR, saved_filename)
        
        # Read dataset to perform validation and schema detection
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        if df.empty:
            os.remove(file_path)
            return JsonResponse({"error": "Uploaded file is empty."}, status=400)
            
        # Run preprocessor schema check
        preprocessor = DataPreprocessor(df)
        schema = preprocessor.detect_schema()
        
        # Calculate detailed quality metrics
        quality_data = preprocessor.calculate_detailed_quality()
        quality_score = quality_data["score"]
        suggestions = preprocessor.feature_engineering_suggestions()
        
        # Check duplicate rows
        dup_count = int(df.duplicated().sum())
        
        # Prepare Metadata
        metadata = {
            "columns": list(df.columns),
            "row_count": len(df),
            "column_count": len(df.columns),
            "schema": schema,
            "duplicate_count": dup_count,
            "missing_summary": {col: info['missing_count'] for col, info in schema.items()},
            "suggestions": suggestions
        }
        
        if existing_ds:
            # Update the main dataset document to reference the latest version
            db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {
                    "$set": {
                        "file_path": file_path,
                        "file_size": uploaded_file.size,
                        "version": next_version,
                        "metadata": metadata,
                        "data_quality_score": quality_score,
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
        else:
            # Save new dataset record to MongoDB
            dataset_doc = {
                "_id": ObjectId(dataset_id),
                "project_id": ObjectId(project_id),
                "filename": filename,
                "file_path": file_path,
                "file_size": uploaded_file.size,
                "version": 1,
                "metadata": metadata,
                "data_quality_score": quality_score,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            }
            db.datasets.insert_one(dataset_doc)

        # Save historical version record
        db.dataset_versions.insert_one({
            "dataset_id": ObjectId(dataset_id),
            "version": next_version,
            "file_path": file_path,
            "data_quality_score": quality_score,
            "metadata": metadata,
            "created_at": datetime.datetime.utcnow()
        })

        # Save detailed quality report
        db.data_quality_reports.insert_one({
            "dataset_id": ObjectId(dataset_id),
            "version": next_version,
            "score": quality_score,
            "completeness": quality_data["completeness"],
            "validity": quality_data["validity"],
            "consistency": quality_data["consistency"],
            "uniqueness": quality_data["uniqueness"],
            "outliers_pct": quality_data["outliers_pct"],
            "issues": quality_data["issues"],
            "created_at": datetime.datetime.utcnow()
        })

        # Save Data Lineage trace logs
        db.data_lineage.insert_one({
            "project_id": ObjectId(project_id),
            "dataset_id": ObjectId(dataset_id),
            "version": next_version,
            "action": "UPLOAD",
            "timestamp": datetime.datetime.utcnow(),
            "user_id": ObjectId(request.user_data['id'])
        })

        # Log Audit Activity
        log_user_activity(
            request.user_data['id'], 
            "DATASET_UPLOAD", 
            f"Uploaded dataset {filename} (v{next_version}) to project {project_id}.", 
            request
        )
        
        return JsonResponse({
            "message": f"Dataset uploaded successfully as version {next_version}.",
            "dataset_id": dataset_id,
            "filename": filename,
            "version": next_version,
            "quality_score": quality_score,
            "row_count": len(df),
            "column_count": len(df.columns)
        }, status=201)
        
    except Exception as e:
        logger.error(f"File upload processing failed: {str(e)}")
        return JsonResponse({"error": f"Failed to process dataset: {str(e)}"}, status=500)

@csrf_exempt
@login_required_api
def api_list_datasets(request, project_id):
    """List datasets associated with a project."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    datasets = list(db.datasets.find({"project_id": ObjectId(project_id)}).sort("created_at", -1))
    for ds in datasets:
        ds['_id'] = str(ds['_id'])
        ds['project_id'] = str(ds['project_id'])
        
    return JsonResponse({"datasets": datasets}, status=200)

@csrf_exempt
@login_required_api
def api_dataset_detail(request, dataset_id):
    """Retrieve detailed metadata and preview rows for a dataset."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        return JsonResponse({"error": "Dataset not found."}, status=404)
        
    file_path = dataset.get('file_path')
    cleaned_file_path = dataset.get('cleaned_file_path')
    
    # Decide which path to preview (cleaned takes precedence)
    path_to_read = cleaned_file_path if cleaned_file_path and os.path.exists(cleaned_file_path) else file_path
    
    preview_data = []
    if path_to_read and os.path.exists(path_to_read):
        try:
            ext = os.path.splitext(path_to_read)[1].lower()
            if ext == '.csv':
                df_preview = pd.read_csv(path_to_read, nrows=15)
            else:
                df_preview = pd.read_excel(path_to_read, nrows=15)
                
            # Convert NaNs to None for JSON serializability
            df_preview = df_preview.where(pd.notnull(df_preview), None)
            preview_data = df_preview.to_dict(orient='records')
        except Exception as e:
            logger.error(f"Failed to load preview for {path_to_read}: {str(e)}")
            
    dataset['_id'] = str(dataset['_id'])
    dataset['project_id'] = str(dataset['project_id'])
    
    return JsonResponse({
        "dataset": dataset,
        "preview": preview_data
    }, status=200)

@csrf_exempt
@login_required_api
def api_clean_dataset(request, dataset_id):
    """Execute AI Preprocessing Pipeline on the dataset."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        return JsonResponse({"error": "Dataset not found."}, status=404)
        
    file_path = dataset.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return JsonResponse({"error": "Dataset file not found on server."}, status=400)
        
    try:
        # Load dataset
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        preprocessor = DataPreprocessor(df)
        
        # Run operations
        removed_dups = preprocessor.remove_duplicates()
        imputed_summary = preprocessor.impute_missing()
        outliers_summary = preprocessor.handle_outliers()
        
        cleaned_df = preprocessor.df
        new_quality_score = preprocessor.calculate_quality_score()
        
        # Save cleaned dataset
        cleaned_filename = f"cleaned_{dataset.get('filename')}"
        cleaned_file_path = os.path.join(DATASET_DIR, cleaned_filename)
        
        if ext == '.csv':
            cleaned_df.to_csv(cleaned_file_path, index=False)
        else:
            cleaned_df.to_excel(cleaned_file_path, index=False)
            
        # Update metadata schema and document
        new_preprocessor = DataPreprocessor(cleaned_df)
        new_schema = new_preprocessor.detect_schema()
        
        cleaning_summary = {
            "removed_duplicates": removed_dups,
            "imputed_missing_columns": imputed_summary,
            "outliers_action": outliers_summary,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Calculate detailed quality metrics for cleaned data
        quality_data = new_preprocessor.calculate_detailed_quality()
        
        db.datasets.update_one(
            {"_id": ObjectId(dataset_id)},
            {
                "$set": {
                    "cleaned_file_path": cleaned_file_path,
                    "data_quality_score": new_quality_score,
                    "cleaning_summary": cleaning_summary,
                    "metadata.schema": new_schema,
                    "metadata.row_count": len(cleaned_df),
                    "metadata.duplicate_count": 0,
                    "metadata.missing_summary": {col: 0 for col in cleaned_df.columns}
                }
            }
        )

        # Update quality report for this version
        db.data_quality_reports.insert_one({
            "dataset_id": ObjectId(dataset_id),
            "version": dataset.get('version', 1),
            "score": new_quality_score,
            "completeness": quality_data["completeness"],
            "validity": quality_data["validity"],
            "consistency": quality_data["consistency"],
            "uniqueness": quality_data["uniqueness"],
            "outliers_pct": quality_data["outliers_pct"],
            "issues": quality_data["issues"],
            "created_at": datetime.datetime.utcnow()
        })

        # Save Lineage Log
        db.data_lineage.insert_one({
            "project_id": ObjectId(dataset.get('project_id')),
            "dataset_id": ObjectId(dataset_id),
            "version": dataset.get('version', 1),
            "action": "CLEAN",
            "timestamp": datetime.datetime.utcnow(),
            "user_id": ObjectId(request.user_data['id'])
        })
        
        # Log Audit Activity
        log_user_activity(
            request.user_data['id'], 
            "DATASET_CLEAN", 
            f"Preprocessed dataset {dataset.get('filename')}.", 
            request
        )
        
        return JsonResponse({
            "message": "Dataset cleaned successfully.",
            "original_quality_score": dataset.get('data_quality_score', 0.0),
            "cleaned_quality_score": new_quality_score,
            "cleaning_summary": cleaning_summary
        }, status=200)
        
    except Exception as e:
        logger.error(f"Preprocessing pipeline failed for dataset {dataset_id}: {str(e)}")
        return JsonResponse({"error": f"Cleaning pipeline error: {str(e)}"}, status=500)

@csrf_exempt
@login_required_api
def api_dataset_quality(request, dataset_id):
    """Retrieve detailed quality parameters (Completeness, Validity, Consistency, Uniqueness, Outliers) for a dataset."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    report = db.data_quality_reports.find_one({"dataset_id": ObjectId(dataset_id)}, sort=[("created_at", -1)])
    if not report:
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                ext = os.path.splitext(file_path)[1].lower()
                df = pd.read_csv(file_path) if ext == '.csv' else pd.read_excel(file_path)
                preprocessor = DataPreprocessor(df)
                quality_data = preprocessor.calculate_detailed_quality()
                report = {
                    "dataset_id": ObjectId(dataset_id),
                    "version": dataset.get('version', 1),
                    "score": quality_data["score"],
                    "completeness": quality_data["completeness"],
                    "validity": quality_data["validity"],
                    "consistency": quality_data["consistency"],
                    "uniqueness": quality_data["uniqueness"],
                    "outliers_pct": quality_data["outliers_pct"],
                    "issues": quality_data["issues"],
                    "created_at": datetime.datetime.utcnow()
                }
                db.data_quality_reports.insert_one(report)
            except Exception as e:
                return JsonResponse({"error": f"Failed to compute quality: {str(e)}"}, status=500)
        else:
            return JsonResponse({"error": "Dataset file missing from server."}, status=404)
            
    report['_id'] = str(report['_id'])
    report['dataset_id'] = str(report['dataset_id'])
    return JsonResponse({"report": report}, status=200)

@csrf_exempt
@login_required_api
def api_dataset_lineage(request, dataset_id):
    """Retrieve historical data lineage logs for a dataset."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    lineages = list(db.data_lineage.find({"dataset_id": ObjectId(dataset_id)}).sort("timestamp", 1))
    for item in lineages:
        item['_id'] = str(item['_id'])
        item['project_id'] = str(item['project_id'])
        item['dataset_id'] = str(item['dataset_id'])
        if item.get('user_id'):
            item['user_id'] = str(item['user_id'])
            
    return JsonResponse({"lineage": lineages}, status=200)

@csrf_exempt
@login_required_api
def api_delete_dataset(request, dataset_id):
    """Delete a dataset and all associated records, models, predictions, and files."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        return JsonResponse({"error": "Dataset not found."}, status=404)

    ds_oid = ObjectId(dataset_id)

    # Remove physical files
    for key in ('file_path', 'cleaned_file_path'):
        path = dataset.get(key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Failed to remove dataset file {path}: {str(e)}")

    # Remove serialized model files, then their Mongo records
    for model in db.models.find({"dataset_id": ds_oid}):
        path = model.get('file_path')
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Failed to remove model file {path}: {str(e)}")

    # Remove related Mongo records
    db.datasets.delete_one({"_id": ds_oid})
    db.dataset_versions.delete_many({"dataset_id": ds_oid})
    db.data_quality_reports.delete_many({"dataset_id": ds_oid})
    db.data_lineage.delete_many({"dataset_id": ds_oid})
    db.business_personas.delete_many({"dataset_id": ds_oid})
    db.models.delete_many({"dataset_id": ds_oid})
    db.predictions.delete_many({"dataset_id": ds_oid})

    log_user_activity(
        request.user_data['id'],
        "DATASET_DELETE",
        f"Deleted dataset {dataset.get('filename', dataset_id)} and all associated models/predictions.",
        request
    )

    return JsonResponse({"message": "Dataset deleted successfully."}, status=200)
