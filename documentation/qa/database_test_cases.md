# 7. Database Test Cases - AEDIP

**Date:** 2026-08-07  

---

## 7.1 Database Audits & Constraints

### DB-101: Unique Email Constraint
*   **Test:** Attempt to register two users with the email `test@company.com`.
*   **Expected Result:** The second registration must fail with a `DuplicateKeyError` or a validation status 400.
*   **Actual Result:** MongoDB index uniqueness index prevents duplicate emails. View raises "Email is already registered."
*   **Status:** PASS

### DB-102: Collection Indexes Verification
*   **Test:** Verify that start-up index creation commands successfully set indexes.
*   **Verification:** `db.users` has index `email` (unique). `db.projects` has index `owner_id`. `db.datasets` has index `project_id`.
*   **Status:** PASS
