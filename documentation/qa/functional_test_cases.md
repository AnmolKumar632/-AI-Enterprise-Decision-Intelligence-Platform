# 4. Functional Test Cases - AEDIP

**Date:** 2026-08-07  

---

## 4.1 Test Cases Registry

| Test ID | Module | Title | Description | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FT-101 | Auth | User Registration | Submit registration payload with admin/manager role. | Doc created in `users` collection; verification token issued. | PASS |
| FT-102 | Auth | User Login | Submit credentials of registered user. | JWT access token returned; token set in session. | PASS |
| FT-201 | Datasets | CSV File Upload | Upload `sales_data.csv` to active project. | File saved in `media/datasets`; metadata document written to database. | PASS |
| FT-202 | Datasets | One-Click Preprocessing | Trigger cleaning pipeline on uploaded dataset. | Duplicates dropped; NaNs imputed; outliers clipped; quality score increases. | PASS |
| FT-301 | AutoML | Pipeline Trigger | Start AutoML training for numeric target `Profit`. | Problem type auto-detected as regression; Celery starts training. | PASS |
| FT-401 | NLP Chat | Business Query | Submit query "Why did sales decrease in June?". | Heuristics engine drills down MoM drop and returns text + Plotly line chart. | PASS |
| FT-501 | Reports | Report Compilation | Click "Compile Reports & Slides". | PDF report compiled via ReportLab; PPTX slide deck saved; database log entries written. | PASS |
