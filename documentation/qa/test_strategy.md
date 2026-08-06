# 2. Test Strategy - AEDIP

**Date:** 2026-08-06  

---

## 2.1 Testing Methodologies
AEDIP enforces a multi-tiered validation hierarchy:
1.  **Unit Testing:** Individual function isolation using python's `unittest` framework.
2.  **Integration Testing:** Verifying communication bridges between Django views, PyMongo services, and AutoML training routines.
3.  **System Testing:** End-to-end user workflows (registration to report download).
4.  **Smoke Testing:** Post-deployment checklist ensuring server launch, database connection, and dashboard loading.
5.  **Sanity & Regression Testing:** Targeting code blocks after bug fixes (e.g. statsmodels/pandas StringDtype adjustments).
6.  **User Acceptance Testing (UAT):** Verifying business usefulness, responsiveness, and download accuracy.

## 2.2 Test Automation Config
*   Test Runner: `unittest.TextTestRunner`
*   Target execution: Automated suite runner script `utilities/run_qa_suite.py`.
*   Pass Criteria: 100% critical test cases must pass.
