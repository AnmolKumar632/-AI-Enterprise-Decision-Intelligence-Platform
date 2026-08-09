import os
import pandas as pd
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('automl_advisor')
db = get_db()

class ModelAdvisor:
    @staticmethod
    def generate_recommendations(df: pd.DataFrame, target_col: str, problem_type: str) -> dict:
        row_count = len(df)
        col_count = len(df.columns)

        recommendations = []
        
        if problem_type == 'classification':
            target_counts = df[target_col].value_counts()
            distinct_classes = len(target_counts)
            
            business_summary = f"Predicting Category Column ('{target_col}'): You are predicting discrete groups or outcomes ({distinct_classes} distinct classes found). Tree Ensembles (XGBoost, Random Forest) are recommended because they discover hidden decision rules between customer attributes without requiring complex data transformations."

            # 1. XGBoost Recommendation
            recommendations.append({
                "model_name": "XGBoost",
                "display_name": "XGBoost (Gradient Boosted Decision Trees)",
                "badge": "🏆 Best Overall Accuracy",
                "recommended_for_user": True,
                "suitability": "★★★★★",
                "plain_english_advice": "Top recommendation for predicting business categories. It builds successive smart decision trees to achieve maximum predictive accuracy.",
                "business_impact": "Reduces false prediction errors by up to 25% on complex dataset patterns.",
                "best_when": "When accuracy is your #1 priority."
            })

            # 2. Random Forest Recommendation
            recommendations.append({
                "model_name": "Random Forest",
                "display_name": "Random Forest (Ensemble Averaging)",
                "badge": "🛡️ Most Reliable & Explainable",
                "recommended_for_user": True,
                "suitability": "★★★★★" if row_count < 10000 else "★★★★☆",
                "plain_english_advice": "Combines hundreds of independent decision trees to produce reliable, trustworthy predictions resistant to data errors.",
                "business_impact": "Extremely stable; provides clear reports on which features drive outcomes most.",
                "best_when": "When you need clean explanations for business stakeholders."
            })

            # 3. LightGBM Recommendation
            recommendations.append({
                "model_name": "LightGBM",
                "display_name": "LightGBM (High-Speed Gradient Booster)",
                "badge": "🚀 Ultra Fast Training",
                "recommended_for_user": False,
                "suitability": "★★★★★" if row_count > 2000 else "★★★☆☆",
                "plain_english_advice": "Optimized high-speed boosting algorithm built for very large business datasets.",
                "business_impact": "Trains in seconds even on large datasets with hundreds of thousands of records.",
                "best_when": "When processing massive datasets quickly."
            })

            # 4. Neural Network Recommendation
            recommendations.append({
                "model_name": "Neural Network",
                "display_name": "Neural Network (Multi-Layer Perceptron)",
                "badge": "🧠 Deep Pattern Matcher",
                "recommended_for_user": False,
                "suitability": "★★★★☆" if row_count > 5000 else "★★☆☆☆",
                "plain_english_advice": "Deep artificial neural network that learns multi-layered complex interactions.",
                "business_impact": "Captures intricate non-linear relationships across many columns.",
                "best_when": "When you have large datasets with complex relationships."
            })

        else: # Regression
            business_summary = f"Predicting Numerical Metric ('{target_col}'): You are forecasting continuous numeric numbers (e.g. Sales, Revenue, Prices). Random Forest & XGBoost Regressors are recommended because they average predictions smoothly without being thrown off by unusual data spikes or outliers."

            # 1. Random Forest Regressor
            recommendations.append({
                "model_name": "Random Forest",
                "display_name": "Random Forest Regressor",
                "badge": "🎯 Top Recommendation for Numbers",
                "recommended_for_user": True,
                "suitability": "★★★★★",
                "plain_english_advice": "Averages predictions across multiple decision trees to produce smooth, realistic numeric estimates.",
                "business_impact": "Handles outliers gracefully without over-reacting to temporary price spikes.",
                "best_when": "When estimating financial amounts or sales numbers."
            })

            # 2. XGBoost Regressor
            recommendations.append({
                "model_name": "XGBoost",
                "display_name": "XGBoost Regressor",
                "badge": "🏆 Precision Numerical Forecasting",
                "recommended_for_user": True,
                "suitability": "★★★★★",
                "plain_english_advice": "State-of-the-art numerical prediction engine that fine-tunes error margins iteratively.",
                "business_impact": "Delivers tight confidence bounds and high predictive precision.",
                "best_when": "When minimizing dollar-value prediction errors."
            })

            # 3. Linear Regression
            recommendations.append({
                "model_name": "Linear Regression",
                "display_name": "Linear Regression Baseline",
                "badge": "⚡ Simple Linear Trend",
                "recommended_for_user": False,
                "suitability": "★★★☆☆",
                "plain_english_advice": "Simple straight-line mathematical baseline.",
                "business_impact": "Extremely fast baseline comparison.",
                "best_when": "When target varies strictly proportionally with inputs."
            })

            # 4. LightGBM Regressor
            recommendations.append({
                "model_name": "LightGBM",
                "display_name": "LightGBM Regressor",
                "badge": "🚀 High Speed Regressor",
                "recommended_for_user": False,
                "suitability": "★★★★☆",
                "plain_english_advice": "High-performance leaf-wise regression booster.",
                "business_impact": "Accelerates model training on large numerical datasets.",
                "best_when": "When speed is paramount."
            })

        return {
            "business_summary": business_summary,
            "models": recommendations
        }

@csrf_exempt
@login_required_api
def api_model_advisor(request, dataset_id):
    """API endpoint to get plain-English non-technical model recommendations for a dataset."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    try:
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)

        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file not found on disk."}, status=404)

        ext = os.path.splitext(file_path)[1].lower()
        df = pd.read_csv(file_path) if ext == '.csv' else pd.read_excel(file_path)

        target_col = request.GET.get('target_column')
        if target_col:
            for col in df.columns:
                if col.strip().lower() == target_col.strip().lower():
                    target_col = col
                    break
                    
        if not target_col or target_col not in df.columns:
            target_col = df.columns[-1]

        schema = dataset.get('metadata', {}).get('schema', {}).get(target_col, {})
        semantic_type = schema.get('semantic_type', 'categorical')
        distinct_count = schema.get('distinct_count', 2)

        if semantic_type == 'numerical' and distinct_count > 15:
            problem_type = 'regression'
        else:
            problem_type = 'classification'

        advisor_data = ModelAdvisor.generate_recommendations(df, target_col, problem_type)

        return JsonResponse({
            "dataset_id": dataset_id,
            "target_column": target_col,
            "detected_problem_type": problem_type,
            "business_summary": advisor_data["business_summary"],
            "recommendations": advisor_data["models"]
        }, status=200)

    except Exception as e:
        logger.error(f"Advisor API failed: {str(e)}")
        return JsonResponse({"error": f"Failed to generate advisor details: {str(e)}"}, status=500)

