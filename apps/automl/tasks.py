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
def train_automl_models_task(project_id, dataset_id, target_col, problem_type, user_id, job_id=None, selected_models=None):
    """Celery background task to run AutoML pipeline with progress tracking."""
    if db is None:
        logger.error("AutoML task failed: Database connection offline.")
        return

    def update_job_progress(pct, step, active_model=""):
        if job_id and db is not None:
            try:
                db.automl_jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {
                        "progress_pct": pct,
                        "current_step": step,
                        "active_model": active_model,
                        "updated_at": datetime.datetime.utcnow()
                    }}
                )
            except Exception:
                pass

    try:
        update_job_progress(10, "Loading and preprocessing dataset...")
        
        # 1. Load Dataset
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            logger.error(f"Dataset {dataset_id} not found.")
            if job_id:
                update_job_progress(0, "Dataset not found.")
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
        
        # Ensure target is clean and encoded for classification
        if problem_type == 'classification':
            from sklearn.preprocessing import LabelEncoder
            le_target = LabelEncoder()
            y = le_target.fit_transform(y.astype(str))
            encoders[target_col] = le_target
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 3. Model configurations based on problem type
        leaderboard = []
        best_model_obj = None
        best_model_name = ""
        best_score = -1.0
        best_metrics = {}
        best_feature_importance = {}
        err_messages = []
        
        feature_names = list(X.columns)
        
        if problem_type == 'classification':
            from sklearn.neural_network import MLPClassifier
            import lightgbm as lgb
            
            models_config = {
                "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
                "Decision Tree": DecisionTreeClassifier(random_state=42),
                "Gradient Boosting": GradientBoostingClassifier(random_state=42),
                "Extra Trees": ExtraTreesClassifier(n_estimators=100, random_state=42),
                "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
                "XGBoost": XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42),
                "LightGBM": lgb.LGBMClassifier(random_state=42, verbose=-1),
                "Neural Network": MLPClassifier(hidden_layer_sizes=(100, 50), max_iter=500, random_state=42)
            }
            
            if selected_models and isinstance(selected_models, list) and len(selected_models) > 0:
                sel_lower = [m.lower().strip() for m in selected_models]
                if 'linear regression' in sel_lower:
                    sel_lower.append('logistic regression')
                filtered = {name: model for name, model in models_config.items() if name.lower().strip() in sel_lower}
                if filtered:
                    models_config = filtered
            
            total_models = len(models_config)
            idx = 0
            for name, model in models_config.items():
                idx += 1
                pct = int(15 + (idx / total_models) * 70)
                update_job_progress(pct, f"Fitting {name} Classifier ({idx}/{total_models})...", active_model=name)
                try:
                    logger.info(f"AutoML: Training {name} Classifier...")
                    model.fit(X_train, y_train)
                    preds = model.predict(X_test)
                    
                    # Evaluate
                    acc = float(accuracy_score(y_test, preds))
                    precision, recall, f1, _ = precision_recall_fscore_support(y_test, preds, average='weighted', zero_division=0)
                    
                    # Compute Cross-Validation Score
                    from sklearn.model_selection import cross_val_score
                    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
                    cv_mean = float(cv_scores.mean())
                    
                    metrics = {
                        "accuracy": round(acc, 4),
                        "precision": round(float(precision), 4),
                        "recall": round(float(recall), 4),
                        "f1_score": round(float(f1), 4),
                        "cv_score": round(cv_mean, 4)
                    }
                    
                    conf_matrix = confusion_matrix(y_test, preds).tolist()
                    metrics["confusion_matrix"] = conf_matrix
                    
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
                        "score": round(acc, 4),
                        "metrics": metrics
                    })
                    
                    if acc > best_score:
                        best_score = acc
                        best_model_obj = model
                        best_model_name = name
                        best_metrics = metrics
                        
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
                    err_messages.append(f"{name}: {str(ex)}")
                    logger.error(f"Failed to train classification model {name}: {str(ex)}")
                    
        else:  # Regression
            from sklearn.neural_network import MLPRegressor
            import lightgbm as lgb
            
            models_config = {
                "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42),
                "Decision Tree": DecisionTreeRegressor(random_state=42),
                "Gradient Boosting": GradientBoostingRegressor(random_state=42),
                "Extra Trees": ExtraTreesRegressor(n_estimators=100, random_state=42),
                "Linear Regression": LinearRegression(),
                "XGBoost": XGBRegressor(random_state=42),
                "LightGBM": lgb.LGBMRegressor(random_state=42, verbose=-1),
                "Neural Network": MLPRegressor(hidden_layer_sizes=(100, 50), max_iter=500, random_state=42)
            }
            
            if selected_models and isinstance(selected_models, list) and len(selected_models) > 0:
                sel_lower = [m.lower().strip() for m in selected_models]
                if 'logistic regression' in sel_lower:
                    sel_lower.append('linear regression')
                filtered = {name: model for name, model in models_config.items() if name.lower().strip() in sel_lower}
                if filtered:
                    models_config = filtered
            
            total_models = len(models_config)
            idx = 0
            for name, model in models_config.items():
                idx += 1
                pct = int(15 + (idx / total_models) * 70)
                update_job_progress(pct, f"Fitting {name} Regressor ({idx}/{total_models})...", active_model=name)
                try:
                    logger.info(f"AutoML: Training {name} Regressor...")
                    model.fit(X_train, y_train)
                    preds = model.predict(X_test)
                    
                    r2 = float(r2_score(y_test, preds))
                    mse = float(mean_squared_error(y_test, preds))
                    mae = float(mean_absolute_error(y_test, preds))
                    
                    from sklearn.model_selection import cross_val_score
                    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
                    cv_mean = float(cv_scores.mean())
                    
                    metrics = {
                        "r2_score": round(r2, 4),
                        "mse": round(mse, 4),
                        "mae": round(mae, 4),
                        "cv_score": round(cv_mean, 4)
                    }
                    
                    leaderboard.append({
                        "model_name": name,
                        "score": round(r2, 4),
                        "metrics": metrics
                    })
                    
                    if r2 > best_score:
                        best_score = r2
                        best_model_obj = model
                        best_model_name = name
                        best_metrics = metrics
                        
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
                    err_messages.append(f"{name}: {str(ex)}")
                    logger.error(f"Failed to train regression model {name}: {str(ex)}")
                    
        # Hyperparameter Tuning on Selected Best Model
        if best_model_obj is not None:
            update_job_progress(92, f"Running GridSearchCV hyperparameter tuning on optimal model '{best_model_name}'...", active_model=best_model_name)
            from sklearn.model_selection import GridSearchCV
            param_grid = {}
            if "Random Forest" in best_model_name:
                param_grid = {"n_estimators": [50, 100], "max_depth": [5, 10, None]}
            elif "XGBoost" in best_model_name:
                param_grid = {"n_estimators": [50, 100], "max_depth": [3, 6]}
            elif "LightGBM" in best_model_name:
                param_grid = {"n_estimators": [50, 100], "max_depth": [-1, 5]}

            if param_grid:
                try:
                    logger.info(f"AutoML tuning: Running GridSearchCV on optimal model '{best_model_name}'...")
                    grid_search = GridSearchCV(
                        best_model_obj, 
                        param_grid, 
                        cv=3, 
                        scoring='accuracy' if problem_type == 'classification' else 'r2',
                        n_jobs=-1
                    )
                    grid_search.fit(X_train, y_train)
                    best_model_obj = grid_search.best_estimator_
                    
                    preds = best_model_obj.predict(X_test)
                    if problem_type == 'classification':
                        best_score = float(accuracy_score(y_test, preds))
                        precision, recall, f1, _ = precision_recall_fscore_support(y_test, preds, average='weighted', zero_division=0)
                        
                        best_metrics["accuracy"] = round(best_score, 4)
                        best_metrics["precision"] = round(float(precision), 4)
                        best_metrics["recall"] = round(float(recall), 4)
                        best_metrics["f1_score"] = round(float(f1), 4)
                    else:
                        best_score = float(r2_score(y_test, preds))
                        best_metrics["r2_score"] = round(best_score, 4)
                        best_metrics["mse"] = round(float(mean_squared_error(y_test, preds)), 4)
                        best_metrics["mae"] = round(float(mean_absolute_error(y_test, preds)), 4)
                except Exception as grid_ex:
                    logger.warning(f"GridSearchCV tuning skipped: {str(grid_ex)}")
                    
        # 4. Save best model and document in MongoDB
        if best_model_obj is not None:
            update_job_progress(97, "Registering model package and saving metadata...")
            leaderboard = sorted(leaderboard, key=lambda x: x['score'], reverse=True)
            
            model_id = str(ObjectId())
            model_filename = f"model_{model_id}.joblib"
            model_file_path = os.path.join(MODEL_DIR, model_filename)
            
            model_package = {
                "model": best_model_obj,
                "encoders": encoders,
                "target_col": target_col,
                "feature_names": feature_names,
                "problem_type": problem_type
            }
            joblib.dump(model_package, model_file_path)
            
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
            
            notify_user(
                user_id,
                "AutoML Job Completed",
                f"AutoML model training finished for dataset '{dataset.get('filename')}'. Best model: {best_model_name} with score {round(best_score, 4)}."
            )
            logger.info(f"AutoML training completed. Best model: {best_model_name} (ID: {model_id})")

            if job_id and db is not None:
                db.automl_jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {
                        "status": "completed",
                        "progress_pct": 100,
                        "current_step": f"AutoML training finished! Best model: {best_model_name}",
                        "best_model_name": best_model_name,
                        "best_score": round(best_score, 4),
                        "model_id": model_id,
                        "updated_at": datetime.datetime.utcnow()
                    }}
                )
        else:
            detailed_err = " | ".join(err_messages) if err_messages else "No compatible algorithms selected for this target type."
            raise ValueError(f"No models trained successfully. Details: {detailed_err}")
            
    except Exception as e:
        logger.error(f"AutoML Task Exception: {str(e)}")
        if job_id and db is not None:
            db.automl_jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "status": "failed",
                    "error": str(e),
                    "current_step": f"Task failed: {str(e)}",
                    "updated_at": datetime.datetime.utcnow()
                }}
            )
        notify_user(user_id, "AutoML Job Failed", f"Model training failed: {str(e)}")

