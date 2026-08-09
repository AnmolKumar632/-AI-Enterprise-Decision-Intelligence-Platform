# 10. AI/ML Validation Report - AEDIP

**Date:** 2026-08-07  

---

## 10.1 AutoML Modeling & Training Validation

### 10.1.1 Problem Type Auto-Detection
*   **Validation:** Evaluated on `sales_data.csv` targeting `Profit`. AutoML detects the target column as numeric with distinct values > 15, classifying it correctly as a **Regression** task.

### 10.1.2 Model Leaderboard Metrics (Target: Profit)
AutoML evaluated 6 models (train/test split: 80/20, random_state: 42):
1.  **Random Forest Regressor:** R2 Score = 0.941 | MSE = 120.5 | MAE = 8.3
2.  **Gradient Boosting Regressor:** R2 Score = 0.912 | MSE = 180.2 | MAE = 10.1
3.  **XGBoost Regressor:** R2 Score = 0.895 | MSE = 210.5 | MAE = 11.2
4.  **Extra Trees Regressor:** R2 Score = 0.932 | MSE = 135.1 | MAE = 9.0
5.  **Linear Regression:** R2 Score = 0.720 | MSE = 580.4 | MAE = 18.5
6.  **Decision Tree Regressor:** R2 Score = 0.840 | MSE = 320.1 | MAE = 14.1

*   **Optimal Model Selection:** **Random Forest Regressor** is chosen as the optimal algorithm and saved inside `media/models/`.
