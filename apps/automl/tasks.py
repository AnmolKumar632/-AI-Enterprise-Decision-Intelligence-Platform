import os
import datetime
import joblib
import numpy as np
import pandas as pd
from celery import shared_task
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.custom_logger import get_logger

# Machine Learning imports
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support, roc_curve, auc, confusion_matrix,
    r2_score, mean_squared_error, mean_absolute_error
)

# Classifiers
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, ExtraTreesClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

# Regressors
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from apps.ai_engine.preprocessing import DataPreprocessor

logger = get_logger('automl_tasks')
db = get_db()

MODEL_DIR = os.path.join(settings_media_root := os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'media', 'models'), '')
os.makedirs(MODEL_DIR, exist_ok=True)

def notify_user(user_id, title, message):
    """Create in-app notification helper."""
    if db is None:
        return
    db.notifications.insert_one({
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": datetime.datetime.utcnow()
    })

@shared_task(name="apps.automl.tasks.train_automl_models_task")
def train_automl_models_task(project_id, dataset_id, target_col, problem_type, user_id):
    """Celery background task to run AutoML pipeline."""
    if db is None:
        logger.error("AutoML task failed: Database connection offline.")
        return
        
    try:
        # 1. Load Dataset
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            logger.error(f"Dataset {dataset_id} not found.")
            return
            
        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            logger.error(f"Dataset file {file_path} not found.")
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        if target_col not in df.columns:
            logger.error(f"Target column '{target_col}' not found in dataset columns.")
            return
            
        # 2. Preprocess, encode, and scale
        preprocessor = DataPreprocessor(df)
        processed_df, encoders = preprocessor.scale_and_encode(target_col=target_col)
        
        # Split features and target
        X = processed_df.drop(columns=[target_col])
        y = processed_df[target_col]
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 3. Model configurations based on problem type
        leaderboard = []
        best_model_obj = None
        best_model_name = ""
        best_score = -1.0
        best_metrics = {}
        best_feature_importance = {}
        
        feature_names = list(X.columns)
        
        if problem_type == 'classification':
            models_config = {
                "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
                "Decision Tree": DecisionTreeClassifier(random_state=42),
                "Gradient Boosting": GradientBoostingClassifier(random_state=42),
                "Extra Trees": ExtraTreesClassifier(n_estimators=100, random_state=42),
                "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
                "XGBoost": XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
            }
            
            for name, model in models_config.items():
                try:
                    logger.info(f"AutoML: Training {name} Classifier...")
                    model.fit(X_train, y_train)
                    preds = model.predict(X_test)
                    
                    # Evaluate
                    acc = float(accuracy_score(y_test, preds))
                    precision, recall, f1, _ = precision_recall_fscore_support(y_test, preds, average='weighted', zero_division=0)
                    
                    # Store metrics
                    metrics = {
                        "accuracy": round(acc, 4),
                        "precision": round(float(precision), 4),
                        "recall": round(float(recall), 4),
                        "f1_score": round(float(f1), 4)
                    }
                    
                    # ROC and Confusion Matrix for leaderboard metadata
                    conf_matrix = confusion_matrix(y_test, preds).tolist()
                    metrics["confusion_matrix"] = conf_matrix
                    
                    # ROC Curve for binary classification
                    unique_classes = np.unique(y_test)
                    if len(unique_classes) == 2:
                        try:
                            probs = model.predict_proba(X_test)[:, 1]
                            fpr, tpr, _ = roc_curve(y_test, probs)
                            roc_auc = float(auc(fpr, tpr))
                            metrics["roc_auc"] = round(roc_auc, 4)
                            metrics["roc_curve"] = {
                                "fpr": [float(x) for x in fpr],
                                "tpr": [float(x) for x in tpr]
                            }
                        except Exception:
                            pass
                            
                    leaderboard.append({
                        "model_name": name,
                        "score": round(acc, 4),  # Classification sorting score
                        "metrics": metrics
                    })
                    
                    # Track Best
                    if acc > best_score:
                        best_score = acc
                        best_model_obj = model
                        best_model_name = name
                        best_metrics = metrics
                        
                        # Calculate Feature Importance
                        importances = None
                        if hasattr(model, 'feature_importances_'):
                            importances = model.feature_importances_
                        elif hasattr(model, 'coef_'):
                            importances = np.abs(model.coef_[0])
                            
                        if importances is not None:
                            best_feature_importance = {
                                feature_names[i]: round(float(importances[i]), 4)
                                for i in range(len(feature_names))
                            }
                except Exception as ex:
                    logger.error(f"Failed to train classification model {name}: {str(ex)}")
                    
        else:  # Regression
            models_config = {
                "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42),
                "Decision Tree": DecisionTreeRegressor(random_state=42),
                "Gradient Boosting": GradientBoostingRegressor(random_state=42),
                "Extra Trees": ExtraTreesRegressor(n_estimators=100, random_state=42),
                "Linear Regression": LinearRegression(),
                "XGBoost": XGBRegressor(random_state=42)
            }
            
            for name, model in models_config.items():
                try:
                    logger.info(f"AutoML: Training {name} Regressor...")
                    model.fit(X_train, y_train)
                    preds = model.predict(X_test)
                    
                    # Evaluate
                    r2 = float(r2_score(y_test, preds))
                    mse = float(mean_squared_error(y_test, preds))
                    mae = float(mean_absolute_error(y_test, preds))
                    
                    metrics = {
                        "r2_score": round(r2, 4),
                        "mse": round(mse, 4),
                        "mae": round(mae, 4)
                    }
                    
                    leaderboard.append({
                        "model_name": name,
                        "score": round(r2, 4),  # Regression sorting score (R2)
                        "metrics": metrics
                    })
                    
                    # Track Best (closest to 1.0)
                    if r2 > best_score:
                        best_score = r2
                        best_model_obj = model
                        best_model_name = name
                        best_metrics = metrics
                        
                        # Feature Importance
                        importances = None
                        if hasattr(model, 'feature_importances_'):
                            importances = model.feature_importances_
                        elif hasattr(model, 'coef_'):
                            importances = np.abs(model.coef_)
                            
                        if importances is not None:
                            best_feature_importance = {
                                feature_names[i]: round(float(importances[i]), 4)
                                for i in range(len(feature_names))
                            }
                except Exception as ex:
                    logger.error(f"Failed to train regression model {name}: {str(ex)}")
                    
        # 4. Save best model and document in MongoDB
        if best_model_obj is not None:
            # Sort leaderboard
            leaderboard = sorted(leaderboard, key=lambda x: x['score'], reverse=True)
            
            # Serialize model
            model_id = str(ObjectId())
            model_filename = f"model_{model_id}.joblib"
            model_file_path = os.path.join(MODEL_DIR, model_filename)
            
            # Save package pipeline (model & data encoders)
            model_package = {
                "model": best_model_obj,
                "encoders": encoders,
                "target_col": target_col,
                "feature_names": feature_names,
                "problem_type": problem_type
            }
            joblib.dump(model_package, model_file_path)
            
            # Insert model document into MongoDB
            model_doc = {
                "_id": ObjectId(model_id),
                "project_id": ObjectId(project_id),
                "dataset_id": ObjectId(dataset_id),
                "name": f"{best_model_name} ({problem_type.capitalize()})",
                "problem_type": problem_type,
                "target_column": target_col,
                "metrics": best_metrics,
                "leaderboard": leaderboard,
                "file_path": model_file_path,
                "status": "completed",
                "feature_importance": best_feature_importance,
                "created_at": datetime.datetime.utcnow()
            }
            db.models.insert_one(model_doc)
            
            # Create notification
            notify_user(
                user_id,
                "AutoML Job Completed",
                f"AutoML model training finished for dataset '{dataset.get('filename')}'. Best model: {best_model_name} with score {round(best_score, 4)}."
            )
            logger.info(f"AutoML training completed. Best model: {best_model_name} (ID: {model_id})")
        else:
            raise ValueError("No models trained successfully.")
            
    except Exception as e:
        logger.error(f"AutoML Task Exception: {str(e)}")
        # If possible, notify user of failure
        notify_user(user_id, "AutoML Job Failed", f"Model training failed: {str(e)}")
