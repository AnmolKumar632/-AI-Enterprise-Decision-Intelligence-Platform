# 12. Defect Log - AEDIP

**Date:** 2026-08-07  

---

## 12.1 Defect Tracking Log

| Defect ID | Date Found | Component | Severity | Description | Status | Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| BUG-001 | 2026-08-07 | Forecasting | High | Missing module error `statsmodels` during import. | CLOSED | Installed `statsmodels` in venv and updated `requirements.txt`. |
| BUG-002 | 2026-08-07 | AI Engine | High | Numpy issubdtype error on pandas StringDtype. | CLOSED | Replaced `np.issubdtype` with `pd.api.types.is_numeric_dtype`. |
| BUG-003 | 2026-08-07 | Reports | Minor | PDF folder not found on fresh deployments. | CLOSED | Added `os.makedirs(REPORT_DIR, exist_ok=True)` in generator. |
