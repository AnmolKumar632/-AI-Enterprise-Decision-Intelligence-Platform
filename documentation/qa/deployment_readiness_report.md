# 19. Deployment Readiness Report - AEDIP

**Date:** 2026-08-06  

---

## 19.1 Pre-deployment checklist

*   **DEP-01: Environment Variables Check**
    *   Verify `SECRET_KEY`, `MONGO_URI`, and `MEDIA_ROOT` are set.
    *   *Status:* VERIFIED
*   **DEP-02: SQLite Database Migrations**
    *   Verify tables contenttypes, auth, admin, and sessions are created in `db.sqlite3`.
    *   *Status:* VERIFIED
*   **DEP-03: Media & Static Folder Permissions**
    *   Verify write permissions on `media/datasets/`, `media/models/`, and `media/reports/`.
    *   *Status:* VERIFIED
*   **DEP-04: WSGI/ASGI configurations**
    *   Verify `gunicorn` starts.
    *   *Status:* VERIFIED
