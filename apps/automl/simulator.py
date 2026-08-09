import os
import json
import joblib
import datetime
import pandas as pd
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('automl_simulator')
db = get_db()

@csrf_exempt
@login_required_api
def api_run_simulation(request):
    """Run What-If Decision Simulation on model targets based on user adjustments."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        data = json.loads(request.body)
        model_id = data.get('model_id')
        dataset_id = data.get('dataset_id')
        modifications = data.get('modifications', {})  # e.g., {"Price": 950, "Discount": 10}

        if not model_id or not dataset_id:
            return JsonResponse({"error": "model_id and dataset_id are required."}, status=400)

        # 1. Load model metadata and file
        model_doc = db.models.find_one({"_id": ObjectId(model_id)})
        if not model_doc:
            return JsonResponse({"error": "Model not found."}, status=404)

        model_file = model_doc.get('file_path')
        if not model_file or not os.path.exists(model_file):
            return JsonResponse({"error": "Model file not found on disk."}, status=404)

        # 2. Load dataset
        dataset_doc = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset_doc:
            return JsonResponse({"error": "Dataset not found."}, status=404)

        data_file = dataset_doc.get('cleaned_file_path') or dataset_doc.get('file_path')
        if not data_file or not os.path.exists(data_file):
            return JsonResponse({"error": "Dataset file not found on disk."}, status=404)

        # 3. Load Model Package
        package = joblib.load(model_file)
        model = package["model"]
        encoders = package["encoders"]
        target_col = package["target_col"]
        feature_names = package["feature_names"]
        problem_type = package["problem_type"]

        # Read base dataframe
        ext = os.path.splitext(data_file)[1].lower()
        df_base = pd.read_csv(data_file) if ext == '.csv' else pd.read_excel(data_file)
        
        # 4. Helper function to preprocess and encode data
        def process_for_inference(df_raw):
            df_proc = df_raw.copy()
            # Drop target if present to prevent target leakage
            df_proc = df_proc.drop(columns=[target_col], errors='ignore')
            
            # Fill NaNs
            for col in df_proc.columns:
                if pd.api.types.is_numeric_dtype(df_proc[col]):
                    df_proc[col] = df_proc[col].fillna(df_proc[col].median() if not df_proc[col].empty else 0)
                else:
                    df_proc[col] = df_proc[col].fillna("Unknown")

            # Encode categoricals using training encoders
            for col, le in encoders.items():
                if col in df_proc.columns:
                    # Handle unseen labels by mapping them to the most frequent label
                    most_frequent = le.classes_[0]
                    df_proc[col] = df_proc[col].apply(lambda val: val if val in le.classes_ else most_frequent)
                    df_proc[col] = le.transform(df_proc[col].astype(str))

            # Encode datetime and remaining categoricals
            for col in df_proc.columns:
                if not pd.api.types.is_numeric_dtype(df_proc[col]):
                    # Check if date-like
                    try:
                        dates = pd.to_datetime(df_proc[col], errors='raise')
                        df_proc[f'{col}_year'] = dates.dt.year
                        df_proc[f'{col}_month'] = dates.dt.month
                        df_proc[f'{col}_day'] = dates.dt.day
                        df_proc = df_proc.drop(columns=[col])
                        continue
                    except Exception:
                        pass
                    
                    # Convert to numeric codes
                    df_proc[col] = pd.Categorical(df_proc[col]).codes

            # Ensure all training feature names are present and in the exact order
            for name in feature_names:
                if name not in df_proc.columns:
                    df_proc[name] = 0.0

            df_proc = df_proc[feature_names]
            return df_proc

        # 5. Run Baseline predictions
        df_base_inference = process_for_inference(df_base)
        baseline_preds = model.predict(df_base_inference)

        # 6. Apply Modifications to create Simulated dataset
        df_sim = df_base.copy()
        for col, new_val in modifications.items():
            if col in df_sim.columns:
                # Cast new_val to correct dtype
                col_dtype = df_sim[col].dtype
                try:
                    df_sim[col] = col_dtype.type(new_val)
                except Exception:
                    df_sim[col] = new_val

        # Run Simulated predictions
        df_sim_inference = process_for_inference(df_sim)
        simulated_preds = model.predict(df_sim_inference)

        # 7. Compare results
        if problem_type == 'regression':
            base_avg = float(np.mean(baseline_preds))
            sim_avg = float(np.mean(simulated_preds))
            diff = sim_avg - base_avg
            pct_change = (diff / base_avg * 100) if base_avg != 0 else 0.0
            
            # Confidence Interval Proxy (standard error of predictions)
            std_err = float(np.std(simulated_preds) / np.sqrt(len(simulated_preds))) if len(simulated_preds) > 0 else 0.0
            lower_bound = max(0.0, sim_avg - 1.96 * std_err)
            upper_bound = sim_avg + 1.96 * std_err
            
            comparison = {
                "base_avg": round(base_avg, 2),
                "simulated_avg": round(sim_avg, 2),
                "difference": round(diff, 2),
                "percentage_change": round(pct_change, 2),
                "lower_bound": round(lower_bound, 2),
                "upper_bound": round(upper_bound, 2),
            }

            # Generate AI recommendations
            recs = []
            direction = "increase" if pct_change > 0 else "decrease"
            recs.append(f"The simulation predicts a **{abs(round(pct_change, 1))}% {direction}** in target metric '{target_col}'.")
            if pct_change > 5.0:
                recs.append("This is a positive shift. The model suggests adjusting variables to this simulated state to boost KPI outputs.")
            elif pct_change < -5.0:
                recs.append("WARNING: This change is projected to negatively impact performance. Proceed with caution as it introduces margin risks.")
            else:
                recs.append("The adjusted variables are expected to maintain stable performance levels with minimal variance.")
            
        else: # Classification
            # Compare class distribution ratio changes
            base_classes, base_counts = np.unique(baseline_preds, return_counts=True)
            sim_classes, sim_counts = np.unique(simulated_preds, return_counts=True)
            
            total_b = len(baseline_preds)
            total_s = len(simulated_preds)
            
            # Convert class indices to strings (reversing label encoder if available)
            target_encoder = encoders.get(target_col)
            
            def get_dist_dict(classes, counts, total):
                dist = {}
                for idx, count in zip(classes, counts):
                    label = str(idx)
                    if target_encoder and idx < len(target_encoder.classes_):
                        label = str(target_encoder.classes_[idx])
                    dist[label] = {
                        "count": int(count),
                        "percentage": round((count / total) * 100, 2)
                    }
                return dist

            base_dist = get_dist_dict(base_classes, base_counts, total_b)
            sim_dist = get_dist_dict(sim_classes, sim_counts, total_s)
            
            comparison = {
                "baseline_distribution": base_dist,
                "simulated_distribution": sim_dist
            }

            recs = ["Simulation indicates a shift in class membership distributions.", "Verify classification ratios on the simulator metrics card."]

        # Save Scenario to DB
        scenario_doc = {
            "project_id": ObjectId(model_doc['project_id']),
            "model_id": ObjectId(model_id),
            "modifications": modifications,
            "comparison": comparison,
            "problem_type": problem_type,
            "created_at": datetime.datetime.utcnow()
        }
        db.scenarios.insert_one(scenario_doc)

        return JsonResponse({
            "message": "What-If decision simulation executed successfully.",
            "problem_type": problem_type,
            "comparison": comparison,
            "recommendations": recs,
            "is_estimate": True
        }, status=200)

    except Exception as e:
        logger.error(f"Simulation failed: {str(e)}")
        return JsonResponse({"error": f"Decision simulator error: {str(e)}"}, status=500)
