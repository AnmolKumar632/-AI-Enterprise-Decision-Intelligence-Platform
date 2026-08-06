# 8. Security Test Cases - AEDIP

**Date:** 2026-08-06  

---

## 8.1 Security Validation & OWASP Checks

### SEC-101: SQL/NoSQL Injection Check
*   **Test:** Submit values containing injection strings (e.g. `{"$gt": ""}`) in the email field.
*   **Result:** Python PyMongo handles parameters cleanly without dynamic string queries, avoiding NoSQL injection.
*   **Status:** PASS

### SEC-102: JWT Token Authentication Check
*   **Test:** Send requests to `/datasets/api/upload/` without the Bearer token in the `Authorization` header.
*   **Result:** Request blocked by custom decorator `login_required_api` with status 401.
*   **Status:** PASS

### SEC-103: Role-Based Access Control (RBAC)
*   **Test:** Sign in as a `viewer` and query `/auth/api/audit-logs/`.
*   **Result:** Request blocked by custom decorator `roles_allowed(['admin', 'manager'])` with status 403.
*   **Status:** PASS
