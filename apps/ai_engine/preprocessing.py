import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.ensemble import IsolationForest
from utilities.custom_logger import get_logger

logger = get_logger('ai_engine_preprocessing')

class DataPreprocessor:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.original_df = df.copy()
        
    def detect_schema(self):
        """Analyze columns, types, distinct counts, and missingness."""
        schema = {}
        row_count = len(self.df)
        
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            missing_count = int(self.df[col].isnull().sum())
            missing_pct = float((missing_count / row_count) * 100) if row_count > 0 else 0.0
            distinct_count = int(self.df[col].nunique())
            
            # Estimate semantic type
            semantic_type = 'categorical'
            if pd.api.types.is_numeric_dtype(self.df[col]):
                if distinct_count > 10 or distinct_count / row_count > 0.05:
                    semantic_type = 'numerical'
                else:
                    semantic_type = 'categorical/ordinal'
            elif 'date' in col.lower() or 'time' in col.lower() or dtype == 'datetime64[ns]':
                try:
                    pd.to_datetime(self.df[col], errors='raise')
                    semantic_type = 'datetime'
                except Exception:
                    pass
            
            schema[col] = {
                "dtype": dtype,
                "semantic_type": semantic_type,
                "missing_count": missing_count,
                "missing_pct": round(missing_pct, 2),
                "distinct_count": distinct_count,
                "sample_values": self.df[col].dropna().head(3).tolist()
            }
        return schema

    def calculate_quality_score(self) -> float:
        """Compute an index score from 0 to 100 representing data hygiene."""
        quality_data = self.calculate_detailed_quality()
        return quality_data["score"]

    def calculate_detailed_quality(self) -> dict:
        """Compute detailed data quality dimensions (Completeness, Validity, Consistency, Uniqueness, Outliers)."""
        if self.df.empty:
            return {
                "score": 0.0,
                "completeness": 0.0,
                "validity": 0.0,
                "consistency": 0.0,
                "uniqueness": 0.0,
                "outliers_pct": 0.0,
                "issues": ["Dataset is empty."]
            }

        total_elements = self.df.size
        total_missing = int(self.df.isnull().sum().sum())
        completeness = round((1 - (total_missing / total_elements)) * 100, 2) if total_elements > 0 else 100.0

        # Uniqueness
        total_rows = len(self.df)
        duplicate_rows = int(self.df.duplicated().sum())
        uniqueness = round((1 - (duplicate_rows / total_rows)) * 100, 2) if total_rows > 0 else 100.0

        # Consistency and Validity checks
        schema = self.detect_schema()
        validity_issues = 0
        consistency_issues = 0
        issues_list = []

        for col, info in schema.items():
            # Missingness checks
            if info['missing_pct'] > 5.0:
                issues_list.append(f"Column '{col}' has {info['missing_pct']}% missing values.")

            # Validity & Consistency checks
            if info['semantic_type'] == 'numerical':
                # Check for extreme negatives in columns that should be positive (e.g. Sales, Price)
                if any(k in col.lower() for k in ['sales', 'price', 'revenue', 'profit', 'quantity', 'amount']):
                    neg_count = int((self.df[col] < 0).sum())
                    if neg_count > 0:
                        validity_issues += neg_count
                        issues_list.append(f"Column '{col}' contains {neg_count} negative values, which may be invalid for monetary/quantity fields.")
            elif info['semantic_type'] == 'datetime':
                # Check for parsing anomalies
                parsed = pd.to_datetime(self.df[col], errors='coerce')
                nat_count = int(parsed.isna().sum() - info['missing_count'])
                if nat_count > 0:
                    consistency_issues += nat_count
                    issues_list.append(f"Column '{col}' has {nat_count} rows with inconsistent date formats.")

        validity = round((1 - (validity_issues / total_elements)) * 100, 2) if total_elements > 0 else 100.0
        consistency = round((1 - (consistency_issues / total_elements)) * 100, 2) if total_elements > 0 else 100.0

        # Outlier check
        outliers_count = 0
        num_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(num_cols) > 0 and total_rows > 5:
            try:
                temp_df = self.df[num_cols].fillna(self.df[num_cols].median())
                iso = IsolationForest(n_estimators=50, random_state=42)
                preds = iso.fit_predict(temp_df)
                outliers_count = int(np.sum(preds == -1))
            except Exception:
                pass

        outliers_pct = round((outliers_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
        if outliers_pct > 5.0:
            issues_list.append(f"High outlier contamination ({outliers_pct}%) detected across numerical columns.")

        # Compute combined score
        score = (completeness * 0.3) + (uniqueness * 0.25) + (validity * 0.2) + (consistency * 0.15) + ((100.0 - outliers_pct) * 0.1)
        score = round(max(0.0, min(100.0, score)), 2)

        return {
            "score": score,
            "completeness": completeness,
            "validity": validity,
            "consistency": consistency,
            "uniqueness": uniqueness,
            "outliers_pct": outliers_pct,
            "issues": issues_list[:10]  # Limit to top 10 issues
        }

    def impute_missing(self, strategy='auto'):
        """Handle missing values using central tendency methods."""
        imputed_counts = {}
        for col in self.df.columns:
            missing_count = int(self.df[col].isnull().sum())
            if missing_count == 0:
                continue
                
            imputed_counts[col] = missing_count
            if strategy == 'auto':
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    # For numerical, use median
                    fill_val = self.df[col].median()
                else:
                    # For categorical, use mode
                    mode_val = self.df[col].mode()
                    fill_val = mode_val[0] if not mode_val.empty else "Unknown"
                self.df[col] = self.df[col].fillna(fill_val)
        return imputed_counts

    def remove_duplicates(self) -> int:
        """Remove exact duplicates and return count removed."""
        before = len(self.df)
        self.df = self.df.drop_duplicates().reset_index(drop=True)
        after = len(self.df)
        return before - after

    def handle_outliers(self, method='isolation_forest') -> dict:
        """Flag and clip outliers for numerical features."""
        outlier_summary = {}
        num_cols = self.df.select_dtypes(include=[np.number]).columns
        
        if len(num_cols) == 0 or len(self.df) < 10:
            return outlier_summary
            
        if method == 'isolation_forest':
            try:
                # Run Isolation Forest on scaled numerical values
                temp_df = self.df[num_cols].fillna(self.df[num_cols].median())
                scaler = StandardScaler()
                scaled_data = scaler.fit_transform(temp_df)
                
                iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
                outlier_preds = iso.fit_predict(scaled_data)
                
                outlier_indices = np.where(outlier_preds == -1)[0]
                outlier_summary["total_outliers_detected"] = len(outlier_indices)
                
                # Clip values to 1st and 99th percentiles for numerical columns
                for col in num_cols:
                    lower = self.df[col].quantile(0.01)
                    upper = self.df[col].quantile(0.99)
                    self.df[col] = np.clip(self.df[col], lower, upper)
                    
                outlier_summary["action"] = "Clipped extreme outliers to 1st and 99th percentiles."
            except Exception as e:
                logger.error(f"Outlier processing failed: {str(e)}")
                outlier_summary["error"] = str(e)
                
        return outlier_summary

    def feature_engineering_suggestions(self) -> list:
        """Identify potential feature transformations."""
        suggestions = []
        schema = self.detect_schema()
        
        for col, info in schema.items():
            if info['semantic_type'] == 'datetime':
                suggestions.append({
                    "column": col,
                    "type": "datetime_extraction",
                    "suggestion": f"Extract Year, Month, Day, and Day of Week from '{col}' to capture seasonality."
                })
            elif info['semantic_type'] == 'categorical' and info['distinct_count'] > 2 and info['distinct_count'] < 15:
                suggestions.append({
                    "column": col,
                    "type": "one_hot_encoding",
                    "suggestion": f"One-hot encode categorical feature '{col}' for machine learning algorithms."
                })
            elif info['semantic_type'] == 'numerical' and info['distinct_count'] > 100:
                # Check for skewness
                skew = self.df[col].skew()
                if abs(skew) > 1.5:
                    suggestions.append({
                        "column": col,
                        "type": "log_transformation",
                        "suggestion": f"Apply log transform to skewed numerical column '{col}' (skewness: {round(skew, 2)})."
                    })
        return suggestions

    def scale_and_encode(self, target_col=None) -> tuple:
        """Encode categorical labels and scale features for AutoML models.
        Returns scaled/encoded DataFrame and a dictionary of fitted LabelEncoders.
        """
        processed_df = self.df.copy()
        encoders = {}
        
        # 1. Fill remaining NaNs if any
        self.impute_missing()
        
        # 2. Encode categorical columns
        for col in processed_df.columns:
            if col == target_col:
                # If target is string, label encode it
                if not pd.api.types.is_numeric_dtype(processed_df[col]):
                    le = LabelEncoder()
                    processed_df[col] = le.fit_transform(processed_df[col].astype(str))
                    encoders[col] = le
                continue
                
            if not pd.api.types.is_numeric_dtype(processed_df[col]):
                # Attempt to parse as date first
                try:
                    dates = pd.to_datetime(processed_df[col], errors='raise')
                    processed_df[f'{col}_year'] = dates.dt.year
                    processed_df[f'{col}_month'] = dates.dt.month
                    processed_df[f'{col}_day'] = dates.dt.day
                    processed_df = processed_df.drop(columns=[col])
                    continue
                except Exception:
                    pass
                
                # Otherwise Encode
                le = LabelEncoder()
                processed_df[col] = le.fit_transform(processed_df[col].astype(str))
                encoders[col] = le
                
        # 3. Scale numerical features (excluding target if present)
        num_cols = processed_df.select_dtypes(include=[np.number]).columns
        if target_col in num_cols:
            num_cols = num_cols.drop(target_col)
            
        if len(num_cols) > 0:
            scaler = StandardScaler()
            processed_df[num_cols] = scaler.fit_transform(processed_df[num_cols])
            
        return processed_df, encoders
