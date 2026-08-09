import os
import datetime
import pandas as pd
import numpy as np
from celery import shared_task
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.custom_logger import get_logger
from apps.automl.tasks import notify_user

# Statsmodels time-series forecasting
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

logger = get_logger('forecasting_tasks')
db = get_db()

@shared_task(name="apps.forecasting.tasks.run_forecasting_task")
def run_forecasting_task(project_id, dataset_id, date_col, target_col, periods, freq, user_id):
    """Celery background task to run time-series forecasting."""
    if db is None:
        logger.error("Forecasting task failed: Database connection offline.")
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
        
        # Validations
        if date_col not in df.columns or target_col not in df.columns:
            logger.error(f"Required columns '{date_col}' or '{target_col}' not found.")
            return
            
        # Smart Date Parsing & Sequence Fallback
        if pd.api.types.is_numeric_dtype(df[date_col]):
            min_val = df[date_col].min()
            max_val = df[date_col].max()
            if min_val >= 1900 and max_val <= 2100:
                df[date_col] = pd.to_datetime(df[date_col].astype(int).astype(str) + '-01-01', errors='coerce')
            else:
                start_dt = pd.Timestamp("2026-01-01")
                df = df.sort_values(by=date_col)
                df[date_col] = [start_dt + pd.Timedelta(days=int(i)) for i in range(len(df))]
        else:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            if df[date_col].isnull().all():
                start_dt = pd.Timestamp("2026-01-01")
                df[date_col] = [start_dt + pd.Timedelta(days=int(i)) for i in range(len(df))]
                
        df = df.sort_values(by=date_col).dropna(subset=[date_col, target_col])
        
        # Resample to align frequency (Daily: 'D', Monthly: 'ME')
        resampled_df = df.set_index(date_col).resample(freq)[target_col].sum().to_frame()
        resampled_df = resampled_df.ffill().fillna(0) # Forward fill missing resampled points
        
        # Fallback to Daily frequency if Monthly frequency yields too few data points
        if len(resampled_df) < 5 and freq == 'ME':
            logger.info("Monthly frequency yields insufficient points. Falling back to Daily ('D') frequency.")
            freq = 'D'
            resampled_df = df.set_index(date_col).resample(freq)[target_col].sum().to_frame()
            resampled_df = resampled_df.ffill().fillna(0)
            
        if len(resampled_df) < 5:
            raise ValueError(f"Insufficient data points for forecasting (got {len(resampled_df)} after frequency alignment). Need at least 5 points.")
            
        historical_series = resampled_df[target_col]
        historical_dates = [d.strftime('%Y-%m-%d') for d in resampled_df.index]
        historical_values = [float(x) for x in historical_series.values]
        
        # Fit candidate forecasting models and select the one with the lowest historical Mean Squared Error (MSE)
        best_forecast_values = None
        best_lower_bounds = None
        best_upper_bounds = None
        selected_model_name = ""
        min_mse = float('inf')

        # Model 1: Holt-Winters Exponential Smoothing
        try:
            logger.info("Forecasting: Fitting Exponential Smoothing...")
            seasonal_periods = 7 if freq == 'D' else 12
            if len(historical_series) > seasonal_periods * 2:
                model_hw = ExponentialSmoothing(historical_series, trend='add', seasonal='add', seasonal_periods=seasonal_periods)
            else:
                model_hw = ExponentialSmoothing(historical_series, trend='add', seasonal=None)
            fitted_hw = model_hw.fit()
            forecast_hw = fitted_hw.forecast(steps=periods)
            residuals_hw = fitted_hw.resid
            mse_hw = np.mean(residuals_hw ** 2)
            
            if mse_hw < min_mse:
                min_mse = mse_hw
                selected_model_name = "Holt-Winters"
                best_forecast_values = [float(x) for x in forecast_hw.values]
                std_err = residuals_hw.std()
                best_lower_bounds = [max(0.0, float(x - 1.96 * std_err)) for x in forecast_hw]
                best_upper_bounds = [float(x + 1.96 * std_err) for x in forecast_hw]
        except Exception as hw_err:
            logger.warning(f"Exponential Smoothing fit failed: {str(hw_err)}")

        # Model 2: Custom Prophet-like Fourier Seasonality Model (Linear Trend + Sine/Cosine harmonics)
        try:
            logger.info("Forecasting: Fitting Custom Prophet-like Fourier Curve...")
            X_trend = np.arange(len(historical_series)).reshape(-1, 1)
            y = historical_series.values
            period_val = 7.0 if freq == 'D' else 12.0
            
            sin_f = np.sin(2 * np.pi * X_trend / period_val)
            cos_f = np.cos(2 * np.pi * X_trend / period_val)
            X_features = np.hstack([X_trend, sin_f, cos_f])
            
            from sklearn.linear_model import Ridge
            model_ridge = Ridge(alpha=1.0)
            model_ridge.fit(X_features, y)
            
            # Predict historical and compute residuals
            hist_preds = model_ridge.predict(X_features)
            residuals_ridge = y - hist_preds
            mse_ridge = np.mean(residuals_ridge ** 2)
            
            if mse_ridge < min_mse:
                min_mse = mse_ridge
                selected_model_name = "Prophet-like Fourier Curve"
                
                # Project future steps
                future_idx = np.arange(len(historical_series), len(historical_series) + periods).reshape(-1, 1)
                sin_future = np.sin(2 * np.pi * future_idx / period_val)
                cos_future = np.cos(2 * np.pi * future_idx / period_val)
                X_future = np.hstack([future_idx, sin_future, cos_future])
                
                forecast_ridge = model_ridge.predict(X_future)
                best_forecast_values = [float(x) for x in forecast_ridge]
                std_err = residuals_ridge.std()
                best_lower_bounds = [max(0.0, float(x - 1.96 * std_err)) for x in forecast_ridge]
                best_upper_bounds = [float(x + 1.96 * std_err) for x in forecast_ridge]
        except Exception as ridge_err:
            logger.warning(f"Prophet-like Fourier Curve fit failed: {str(ridge_err)}")

        # Model 3: SARIMAX (ARIMA Baseline fallback/contender)
        try:
            logger.info("Forecasting: Fitting SARIMAX baseline...")
            model_sarimax = SARIMAX(historical_series, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0))
            fitted_sarimax = model_sarimax.fit(disp=False)
            forecast_pred = fitted_sarimax.get_forecast(steps=periods)
            residuals_sarimax = fitted_sarimax.resid
            mse_sarimax = np.mean(residuals_sarimax ** 2)
            
            if mse_sarimax < min_mse or best_forecast_values is None:
                min_mse = mse_sarimax
                selected_model_name = "SARIMAX (1,1,1)"
                best_forecast_values = [float(x) for x in forecast_pred.predicted_mean]
                conf_int = forecast_pred.conf_int(alpha=0.05)
                best_lower_bounds = [max(0.0, float(x)) for x in conf_int.iloc[:, 0]]
                best_upper_bounds = [float(x) for x in conf_int.iloc[:, 1]]
        except Exception as sar_err:
            logger.warning(f"SARIMAX fit failed: {str(sar_err)}")
            
        if best_forecast_values is None:
            raise ValueError("All candidate time-series models failed to fit.")

        forecast_values = best_forecast_values
        lower_bounds = best_lower_bounds
        upper_bounds = best_upper_bounds
        logger.info(f"Forecasting model selected: {selected_model_name} (MSE: {round(min_mse, 4)})")
            
        # Build Forecast Dates
        last_date = resampled_df.index[-1]
        forecast_dates = []
        for i in range(1, periods + 1):
            if freq == 'D':
                next_date = last_date + datetime.timedelta(days=i)
            else: # Monthly
                # Add month
                year = last_date.year + (last_date.month + i - 1) // 12
                month = (last_date.month + i - 1) % 12 + 1
                next_date = datetime.datetime(year, month, 1)
            forecast_dates.append(next_date.strftime('%Y-%m-%d'))
            
        # Business Recommendation Generation
        hist_avg = np.mean(historical_values[-6:]) if len(historical_values) >= 6 else np.mean(historical_values)
        fore_avg = np.mean(forecast_values)
        pct_change = ((fore_avg - hist_avg) / hist_avg * 100) if hist_avg > 0 else 0
        
        direction = "increase" if pct_change > 0 else "decrease"
        recommendations = [
            f"Historical average (recent): {round(hist_avg, 2)}. Forecasted average: {round(fore_avg, 2)} ({round(abs(pct_change), 1)}% {direction}).",
        ]
        
        if pct_change > 5:
            recommendations.append(
                f"Peak sales/demand is projected. Recommend increasing inventory levels and staffing capacity by 10-15% during peak forecast windows."
            )
        elif pct_change < -5:
            recommendations.append(
                "A downswing in demand is forecasted. Suggest running promotional marketing campaigns and optimizing operations to conserve overhead."
            )
        else:
            recommendations.append(
                "Demand is expected to remain stable. Focus on standard operational efficiency and maintaining safety stock levels."
            )
            
        # Save results in predictions collection with a type flag
        forecast_doc = {
            "project_id": ObjectId(project_id),
            "dataset_id": ObjectId(dataset_id),
            "type": "forecasting",
            "status": "success",
            "target_column": target_col,
            "historical_dates": historical_dates,
            "historical_values": historical_values,
            "forecast_dates": forecast_dates,
            "forecast_values": forecast_values,
            "lower_bounds": lower_bounds,
            "upper_bounds": upper_bounds,
            "recommendations": recommendations,
            "created_at": datetime.datetime.utcnow()
        }
        
        # Save to database
        db.predictions.insert_one(forecast_doc)
        
        # Notify
        notify_user(
            user_id,
            "Forecasting Model Completed",
            f"Time-series forecast finished successfully for column '{target_col}' in dataset '{dataset.get('filename')}'."
        )
        logger.info(f"Forecasting task finished successfully for target '{target_col}'.")
        
    except Exception as e:
        logger.error(f"Forecasting task failed: {str(e)}")
        notify_user(user_id, "Forecasting Job Failed", f"Time-series forecast failed: {str(e)}")
        try:
            forecast_doc = {
                "project_id": ObjectId(project_id),
                "dataset_id": ObjectId(dataset_id),
                "type": "forecasting",
                "status": "failed",
                "error_message": str(e),
                "created_at": datetime.datetime.utcnow()
            }
            db.predictions.insert_one(forecast_doc)
        except Exception as db_err:
            logger.error(f"Failed to save forecast error to database: {str(db_err)}")
