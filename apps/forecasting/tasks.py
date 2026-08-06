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
            
        # Parse Dates and sort
        df[date_col] = pd.to_datetime(df[date_col])
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
        
        # Fit Holt-Winters Exponential Smoothing (highly robust, fits seasonal and trend elements)
        try:
            logger.info("Fitting Exponential Smoothing model...")
            # We automatically adapt seasonal periods based on frequency
            seasonal_periods = 7 if freq == 'D' else 12
            if len(historical_series) > seasonal_periods * 2:
                model = ExponentialSmoothing(
                    historical_series, 
                    trend='add', 
                    seasonal='add', 
                    seasonal_periods=seasonal_periods
                )
            else:
                model = ExponentialSmoothing(historical_series, trend='add', seasonal=None)
                
            fitted_model = model.fit()
            forecast = fitted_model.forecast(steps=periods)
            
            # Estimate confidence intervals using standard errors or standard deviations
            residuals = fitted_model.resid
            std_err = residuals.std()
            
            # Z-score for 95% confidence
            z_score = 1.96
            lower_bounds = [max(0.0, float(x - z_score * std_err)) for x in forecast]
            upper_bounds = [float(x + z_score * std_err) for x in forecast]
            forecast_values = [float(x) for x in forecast.values]
            
        except Exception as es_err:
            logger.warning(f"Exponential Smoothing failed: {str(es_err)}. Trying simple SARIMAX...")
            # Fallback to simple ARIMA/SARIMAX
            model = SARIMAX(historical_series, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0))
            fitted_model = model.fit(disp=False)
            
            pred = fitted_model.get_forecast(steps=periods)
            forecast_values = [float(x) for x in pred.predicted_mean]
            
            conf_int = pred.conf_int(alpha=0.05)
            lower_bounds = [max(0.0, float(x)) for x in conf_int.iloc[:, 0]]
            upper_bounds = [float(x) for x in conf_int.iloc[:, 1]]
            
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
