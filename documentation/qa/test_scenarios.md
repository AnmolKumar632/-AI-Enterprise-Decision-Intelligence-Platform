# 3. Test Scenarios - AEDIP

**Date:** 2026-08-06  

---

## 3.1 End-to-End Test Scenarios

### Scenario TS-01: Full User Analytical Journey
*   **Objective:** Validate the complete path from signup to executive report download.
*   **Pre-conditions:** MongoDB and Django server active.
*   **Steps:**
    1.  User registers at `/auth/register-page/` and completes simulated email verification.
    2.  User logs in at `/auth/login-page/` using email/password.
    3.  User creates a new project workspace.
    4.  User uploads a sample sales dataset (`sales_data.csv`).
    5.  User runs the **One-click preprocessing pipeline** to clean the data.
    6.  User reviews the Automated EDA summary, correlation matrix, and column distributions.
    7.  User triggers **AutoML Model Training** for target column `Profit`.
    8.  User verifies the model leaderboard and download functionality.
    9.  User submits NLP questions in the query panel.
    10. User compiles and downloads the executive PDF and PowerPoint reports.
*   **Expected Result:** Every module responds with successful status codes; visualizations render correctly; files compile without error.
