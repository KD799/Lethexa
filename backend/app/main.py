
from fastapi import FastAPI, HTTPException

from app.database import get_app_connection

from app.api.requests import router as requests_router
from app.api.verification import router as verification_router
from app.api.approvals import router as approvals_router
from app.api.deletion import router as deletion_router
from app.api.audit import router as audit_router
from app.api.reports import router as reports_router
from app.api.discovery import router as discovery_router
from app.api.auth import router as auth_router


app = FastAPI(
    title="PII Discovery & DSR Orchestrator",
    description="Backend system for privacy requests and PII discovery",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "message": "Welcome to PII Discovery Backend",
        "status": "running",
    }


@app.get("/health")
def health_check():

    conn = None

    try:
        conn = get_app_connection()

        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return {
            "status": "healthy",
            "service": "DSR Orchestrator",
            "database": "connected",
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "DSR Orchestrator",
                "database": "unavailable",
            },
        )

    finally:
        if conn:
            conn.close()


app.include_router(requests_router)
app.include_router(verification_router)
app.include_router(deletion_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(reports_router)
app.include_router(discovery_router)
app.include_router(auth_router)