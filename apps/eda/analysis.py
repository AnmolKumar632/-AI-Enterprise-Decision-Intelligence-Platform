import pandas as pd
import numpy as np
from utilities.custom_logger import get_logger

logger = get_logger('eda_analysis')

def get_summary_statistics(df: pd.DataFrame) -> dict:
    """Compute detailed summary statistics for numerical and categorical features."""
    summary = {}
    row_count = len(df)
    
    # Numerical features statistics
    num_cols = df.select_dtypes(include=[np.number]).columns
    summary["numerical"] = {}
    for col in num_cols:
        desc = df[col].describe()
        summary["numerical"][col] = {
            "mean": round(float(desc.get("mean", 0)), 2),
            "std": round(float(desc.get("std", 0)), 2),
            "min": round(float(desc.get("min", 0)), 2),
            "max": round(float(desc.get("max", 0)), 2),
            "median": round(float(df[col].median()), 2),
            "skewness": round(float(df[col].skew()), 2) if not df[col].isnull().all() else 0.0,
            "q25": round(float(desc.get("25%", 0)), 2),
            "q75": round(float(desc.get("75%", 0)), 2),
        }
        
    # Categorical features statistics
    cat_cols = df.select_dtypes(exclude=[np.number]).columns
    summary["categorical"] = {}
    for col in cat_cols:
        val_counts = df[col].value_counts().head(10).to_dict()
        summary["categorical"][col] = {
            "unique_count": int(df[col].nunique()),
            "most_frequent": str(df[col].mode().iloc[0]) if not df[col].mode().empty else "N/A",
            "top_categories": {str(k): int(v) for k, v in val_counts.items()}
        }
        
    return summary

def get_correlation_matrix(df: pd.DataFrame) -> dict:
    """Compute Pearson correlation matrix for numerical features."""
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) < 2:
        return {"columns": [], "matrix": []}
        
    try:
        # Fill missing values temporarily with median for correlation check
        temp_df = df[num_cols].fillna(df[num_cols].median())
        corr = temp_df.corr().round(3)
        
        columns = list(corr.columns)
        matrix = corr.values.tolist()
        
        # Replace NaNs with 0
        matrix = [[0 if np.isnan(val) else val for val in row] for row in matrix]
        
        return {
            "columns": columns,
            "matrix": matrix
        }
    except Exception as e:
        logger.error(f"Correlation calculation failed: {str(e)}")
        return {"columns": [], "matrix": [], "error": str(e)}

def get_missing_value_positions(df: pd.DataFrame, max_rows=500) -> dict:
    """Generate coordinate points showing where missing values reside in the file."""
    # Sub-sample if dataset is too large
    sample_df = df.head(max_rows) if len(df) > max_rows else df
    
    cols = list(sample_df.columns)
    missing_map = []
    
    for r_idx, (_, row) in enumerate(sample_df.iterrows()):
        row_missing = []
        for c_idx, col in enumerate(cols):
            if pd.isnull(row[col]):
                row_missing.append(c_idx)
        if row_missing:
            missing_map.append({"row": r_idx, "cols": row_missing})
            
    return {
        "columns": cols,
        "total_rows_sampled": len(sample_df),
        "missing_map": missing_map
    }

def get_distribution_data(df: pd.DataFrame, column: str) -> dict:
    """Generate histogram or category distribution values for a column."""
    if column not in df.columns:
        return {}
        
    col_data = df[column].dropna()
    if len(col_data) == 0:
        return {"type": "empty"}
        
    if pd.api.types.is_numeric_dtype(df[column]):
        # Generate histogram bins
        counts, bin_edges = np.histogram(col_data, bins='auto')
        bin_labels = []
        for i in range(len(bin_edges)-1):
            bin_labels.append(f"{round(bin_edges[i], 2)} - {round(bin_edges[i+1], 2)}")
            
        return {
            "type": "numerical",
            "labels": bin_labels,
            "values": [int(x) for x in counts]
        }
    else:
        # Category counts
        counts = col_data.value_counts().head(20).to_dict()
        return {
            "type": "categorical",
            "labels": [str(k) for k in counts.keys()],
            "values": [int(v) for v in counts.values()]
        }
