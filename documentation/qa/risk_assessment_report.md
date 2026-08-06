# 18. Risk Assessment Report - AEDIP

**Date:** 2026-08-06  

---

## 18.1 System Risks & Mitigation Strategies

### Risk R-01: Network Disconnect / Database Outage
*   **Likelihood:** Low  
*   **Impact:** Critical (API failures, no model data saved)  
*   **Mitigation:** `db_connection.py` includes a `serverSelectionTimeoutMS` limit. API handles connection drops gracefully with standard error JSONs.

### Risk R-02: Celery Worker/Redis Offline
*   **Likelihood:** Medium (if Docker Desktop isn't launched)  
*   **Impact:** High (AutoML models remain in "training" status forever)  
*   **Mitigation:** Implemented dynamic **Celery Eager Execution fallback** (`CELERY_TASK_ALWAYS_EAGER = True`). This executes training tasks synchronously on the main thread when Redis is offline.
