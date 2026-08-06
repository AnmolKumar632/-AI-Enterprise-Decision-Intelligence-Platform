# 11. Explainable AI Validation Report - AEDIP

**Date:** 2026-08-06  

---

## 11.1 Explainability Metrics & Contributions
Explainability is computed using native Python/Scikit-learn model parameters. 

### 11.1.1 Feature Importance (Gini Importance - Random Forest)
*   **Quantity:** 0.452 (Highest positive contributor to sales/profit variance)
*   **Unit Price:** 0.385
*   **Category:** 0.095
*   **Region:** 0.068

### 11.1.2 Local Explanations Preview
For the first prediction index:
*   **Predicted Profit:** $120.50
*   **Contributions:**
    *   Quantity (+2 units): +$45.00
    *   Unit Price ($80.00): +$65.00
    *   Other factors: +$10.50
