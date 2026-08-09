# 6. API Test Cases - AEDIP

**Date:** 2026-08-07  

---

## 6.1 API Endpoints Specification & Testing

| Endpoint | Method | Required Payload | Expected Status | Validation Assertions |
| :--- | :--- | :--- | :--- | :--- |
| `/auth/api/register/` | POST | email, password, first_name, last_name, role | 211 Created | Email is unique; verification token returned. |
| `/auth/api/login/` | POST | email, password | 200 OK | Hashed match succeeds; JWT access token returned. |
| `/datasets/api/upload/` | POST | file, project_id | 211 Created | Ext in ['.csv', '.xlsx']; file saved; metadata schema extracted. |
| `/datasets/api/clean/<id>/`| POST | None (uses path parameter) | 200 OK | Columns cleaned; new quality score returned. |
| `/automl/api/train/` | POST | dataset_id, target_column | 202 Accepted | Problem type detected; Celery background task started. |
| `/nlp/api/query/` | POST | dataset_id, query | 200 OK | Text explanation and JSON chart data returned. |
