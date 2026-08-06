# 5. Integration Test Cases - AEDIP

**Date:** 2026-08-06  

---

## 5.1 Integration Test Cases Validation

### IT-201: Django Controller ↔ MongoDB Connection
*   **Methodology:** Verify that API actions write/retrieve documents from MongoDB collections.
*   **Verification:** `test_mongodb_connection` unit test executes successfully and connects to database `aedip`.
*   **Status:** PASS

### IT-202: AutoML ↔ Scikit-learn Model Serialization
*   **Methodology:** Train models using Scikit-learn, serialize to disk using `joblib`, and reload during prediction.
*   **Verification:** Training saves `.joblib` package inside `media/models/`. Inference view loads the model and aligns input features without data loss.
*   **Status:** PASS

### IT-203: Report Generator ↔ Matplotlib/Plotly Charts
*   **Methodology:** Collect chart figures or data tables and verify insertion into PDF/PPTX formats.
*   **Verification:** `ReportGenerator` constructs tables and paragraphs matching values in the `models` and `predictions` collections.
*   **Status:** PASS
