import os
import datetime
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('ai_engine_personas')
db = get_db()

class PersonaEngine:
    @staticmethod
    def segment_entities(df: pd.DataFrame, num_clusters=4) -> dict:
        # Select numerical columns for clustering
        num_cols = list(df.select_dtypes(include=[np.number]).columns)
        
        # Remove primary ID-like columns if present
        cleaned_num_cols = [c for c in num_cols if not any(k in c.lower() for k in ['id', 'index', 'key'])]
        
        if len(cleaned_num_cols) < 2 or len(df) < 10:
            # Fallback to rule-based segmentation or error out gracefully
            return {
                "segmented": False,
                "error": "Dataset does not contain enough numerical features or rows for clustering."
            }

        # Scale data
        temp_df = df[cleaned_num_cols].fillna(df[cleaned_num_cols].median())
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(temp_df)
        
        # Fit K-Means
        kmeans = KMeans(n_clusters=min(num_clusters, len(df)), random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaled_data)
        
        df_copy = df.copy()
        df_copy['cluster'] = labels
        
        # Segment profiling
        centroids = kmeans.cluster_centers_
        cluster_profiles = []
        
        # Map centroids back to original scale averages for explanation
        avg_original = scaler.inverse_transform(centroids)
        
        # Identify key KPI column for labelling (e.g. Sales, Profit, Amount)
        kpi_col = None
        for col in cleaned_num_cols:
            if any(k in col.lower() for k in ['sales', 'profit', 'amount', 'spend', 'revenue', 'value']):
                kpi_col = col
                break
        if not kpi_col:
            kpi_col = cleaned_num_cols[0]
            
        kpi_idx = cleaned_num_cols.index(kpi_col)
        
        # Sort clusters by average KPI value descending
        cluster_order = np.argsort(avg_original[:, kpi_idx])[::-1]
        
        persona_names = ["High-Value Champions", "Loyal Mainstreamers", "Emerging/Budget Group", "Declining/At-Risk Segment"]
        recs_map = {
            "High-Value Champions": [
                "Establish VIP loyalty rewards and direct communication channels.",
                "Cross-sell premium additions and early-access catalogs."
            ],
            "Loyal Mainstreamers": [
                "Provide volume discounts or free-shipping thresholds to increase average order values.",
                "Implement email retargeting based on previous purchases."
            ],
            "Emerging/Budget Group": [
                "Recommend budget-conscious alternatives and flash sales promotions.",
                "Target with social media discount campaigns."
            ],
            "Declining/At-Risk Segment": [
                "Deploy win-back re-engagement surveys and major promotional codes (e.g. 20% off).",
                "Audit transaction friction points or customer service satisfaction ratings."
            ]
        }
        
        for rank, c_idx in enumerate(cluster_order):
            p_name = persona_names[min(rank, len(persona_names)-1)]
            count = int(np.sum(labels == c_idx))
            pct = round((count / len(df)) * 100, 2)
            
            # Get centroid averages for explanation
            metrics = {
                cleaned_num_cols[i]: round(float(avg_original[c_idx][i]), 2)
                for i in range(len(cleaned_num_cols))
            }
            
            cluster_profiles.append({
                "cluster_index": int(c_idx),
                "persona_name": p_name,
                "count": count,
                "percentage": pct,
                "metrics": metrics,
                "recommendations": recs_map.get(p_name, ["Promote engagement campaigns."])
            })
            
        return {
            "segmented": True,
            "features_used": cleaned_num_cols,
            "target_kpi_indicator": kpi_col,
            "segments": cluster_profiles
        }

@csrf_exempt
@login_required_api
def api_get_business_personas(request, dataset_id):
    """API endpoint to run segmentation and retrieve business personas."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)

        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file not found on server disk."}, status=404)

        # Read data
        ext = os.path.splitext(file_path)[1].lower()
        df = pd.read_csv(file_path) if ext == '.csv' else pd.read_excel(file_path)

        segmentation = PersonaEngine.segment_entities(df)
        
        if segmentation.get('segmented'):
            # Save segment results
            db.business_personas.update_one(
                {"dataset_id": ObjectId(dataset_id)},
                {"$set": {
                    "project_id": dataset['project_id'],
                    "segmentation": segmentation,
                    "created_at": datetime.datetime.utcnow()
                }},
                upsert=True
            )
            
        return JsonResponse(segmentation, status=200)

    except Exception as e:
        logger.error(f"Persona engine failed: {str(e)}")
        return JsonResponse({"error": f"Failed to run persona segmentation: {str(e)}"}, status=500)
