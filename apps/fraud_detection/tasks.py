import os
import datetime
import pandas as pd
import numpy as np
from celery import shared_task
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.custom_logger import get_logger
from apps.automl.tasks import notify_user
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

logger = get_logger('fraud_anomaly_tasks')
db = get_db()

@shared_task(name="apps.fraud_detection.tasks.run_anomaly_detection_task")
def run_anomaly_detection_task(project_id, dataset_id, feature_cols, contamination, user_id):
    """Celery background task to run unsupervised anomaly and fraud detection."""
    if db is None:
        logger.error("Anomaly task failed: Database connection offline.")
        return
        
    try:
        # Load Dataset
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            logger.error(f"Dataset {dataset_id} not found.")
            return
            
        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            logger.error(f"Dataset file {file_path} not found.")
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        df = pd.read_csv(file_path) if ext == '.csv' else pd.read_excel(file_path)
        
        # Filter numerical features
        available_features = [col for col in feature_cols if col in df.columns]
        num_df = df[available_features].select_dtypes(include=[np.number]).copy()
        
        if num_df.empty or len(num_df) < 5:
            raise ValueError("Insufficient numerical data points for training anomaly detection models.")
            
        # Impute and Scale
        num_df = num_df.fillna(num_df.median())
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(num_df)
        
        # Fit Isolation Forest
        logger.info("Fitting Isolation Forest for anomaly detection...")
        iso = IsolationForest(contamination=contamination, random_state=42)
        iso_preds = iso.fit_predict(scaled_data)
        scores = iso.decision_function(scaled_data)
        
        # Convert decision scores to a Risk Score from 0 to 100
        # Isolation Forest decision function is normally between -0.5 and 0.5.
        # Lower score represents more anomalous (outlier).
        # Shift and scale: score of -0.5 is 100% risk, score of 0.5 is 0% risk.
        min_s, max_s = scores.min(), scores.max()
        if max_s - min_s > 0:
            risk_scores = [round(float((1 - (x - min_s) / (max_s - min_s)) * 100), 2) for x in scores]
        else:
            risk_scores = [50.0] * len(scores)
            
        # Fit Local Outlier Factor
        logger.info("Fitting Local Outlier Factor...")
        lof = LocalOutlierFactor(n_neighbors=min(20, len(scaled_data)-1), contamination=contamination)
        lof_preds = lof.fit_predict(scaled_data)
        
        # Combine predictions
        anomalies_detected = []
        anomaly_count = 0
        
        for idx in range(len(df)):
            is_anomaly = bool(iso_preds[idx] == -1 or lof_preds[idx] == -1)
            if is_anomaly:
                anomaly_count += 1
                
            # Keep track of riskier rows or sample data
            if is_anomaly or risk_scores[idx] > 70:
                row_data = df.iloc[idx].replace({np.nan: None}).to_dict()
                anomalies_detected.append({
                    "row_index": idx,
                    "risk_score": risk_scores[idx],
                    "details": {col: row_data[col] for col in available_features},
                    "full_row": row_data
                })
                
        # Sort anomalies by risk score descending
        anomalies_detected = sorted(anomalies_detected, key=lambda x: x['risk_score'], reverse=True)
        
        # Summary
        summary = {
            "total_rows_analyzed": len(df),
            "anomaly_count": anomaly_count,
            "anomaly_percentage": round((anomaly_count / len(df)) * 100, 2) if len(df) > 0 else 0.0,
            "features_used": available_features,
            "contamination_parameter": contamination
        }
        
        # Save results in predictions collection with a type of anomaly
        anomaly_doc = {
            "project_id": ObjectId(project_id),
            "dataset_id": ObjectId(dataset_id),
            "type": "anomaly",
            "summary": summary,
            "anomalies": anomalies_detected[:100],  # Keep top 100 anomalous records
            "created_at": datetime.datetime.utcnow()
        }
        
        db.predictions.insert_one(anomaly_doc)
        
        # Notify
        notify_user(
            user_id,
            "Anomaly Detection Job Completed",
            f"Unsupervised anomaly detection finished. Found {anomaly_count} potential anomalies ({summary['anomaly_percentage']}% of dataset)."
        )
        logger.info(f"Anomaly detection task completed. Found {anomaly_count} outliers.")
        
    except Exception as e:
        logger.error(f"Anomaly detection task failed: {str(e)}")
        notify_user(user_id, "Anomaly Detection Job Failed", f"Anomaly run failed: {str(e)}")
