"""
InvoiceAI — FastAPI Application Entry Point.

BUG-15: Hardened CORS + HSTS headers.
BUG-16: Stuck invoice cleanup background task.
BUG-17: Content-Length limit middleware (20MB).
BUG-21: pyzbar startup health check.

[NEW] Payment reminder scheduler (APScheduler) — runs reminder_service.run_reminder_scan()
every settings.REMINDER_SCHEDULER_INTERVAL_HOURS hours.
"""
import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.routers import auth, invoices, review, webhooks, payments, reminders

logger = logging.getLogger("invoiceai")

# ── BUG-21: Track QR detection availability ────────────────────────────────
_qr_detection_ok = True

# ── BUG-B5: Bounded thread pool for invoice pipeline background tasks ───────
# Starlette's default executor is shared with FastAPI internals and is
# effectively unbounded. A dedicated pool with an explicit cap prevents
# thread exhaustion under concurrent uploads.
_pipeline_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="invoice-pipeline")

# ── [NEW] Global scheduler instance for payment reminders ───────────────────
_reminder_scheduler: AsyncIOScheduler | None = None


# ── BUG-16: Lifespan — startup/shutdown tasks ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup checks + background cleanup tasks."""
    global _qr_detection_ok, _reminder_scheduler

    # Ensure all models are imported so SQLAlchemy creates tables
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.review_log import ReviewLog  # noqa: F401
    from app.models.vendor_correction import VendorCorrection  # noqa: F401
    from app.models.payment import (  # noqa: F401
        PaymentRecord,
        PaymentTransaction,
        ReminderSettings,
        ReminderLog,
        InAppNotification,
    )
    from app.database import engine, Base
    Base.metadata.create_all(bind=engine)

    # BUG-B6: Auto-run Alembic migrations on every startup.
    # This eliminates the "forgotten migration" class of deploy failures.
    # create_all() above is retained as a safety net for tests/SQLite;
    # Alembic is authoritative for PostgreSQL production schemas.
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info("[startup] Alembic migrations applied successfully")
        else:
            logger.error(f"[startup] Alembic migration FAILED:\n{result.stderr}")
    except Exception as alembic_err:
        logger.error(f"[startup] Could not run Alembic migrations: {alembic_err}")


    # WIN-01: Check zxing-cpp (Windows-native, replaces pyzbar) and cv2 availability at startup.
    try:
        import zxingcpp  # noqa: F401
        import cv2  # noqa: F401
        _qr_detection_ok = True
        logger.info("[startup] QR detection libraries loaded successfully (zxing-cpp + OpenCV)")
    except ImportError as e:
        _qr_detection_ok = False
        logger.warning(f"[startup] QR detection DISABLED — missing library: {e}")
        logger.warning("[startup] Run: pip install zxing-cpp opencv-contrib-python")
    except AttributeError as e:
        # NumPy 2.x removed numpy.core.multiarray — OpenCV 4.9.x crashes on import.
        # Fix: pip install 'numpy<2.0'
        _qr_detection_ok = False
        logger.warning(
            f"[startup] QR detection DISABLED — NumPy/OpenCV version conflict: {e}"
        )
        logger.warning(
            "[startup] Fix: pip install 'numpy<2.0'  "
            "(opencv-contrib-python 4.9.x requires NumPy < 2.0)"
        )

    # BUG-16: Start stuck invoice cleanup task
    cleanup_task = asyncio.create_task(_cleanup_stuck_invoices())

    # ── [NEW] Start payment reminder scheduler ───────────────────────────────
    # Runs reminder_service.run_reminder_scan() every
    # settings.REMINDER_SCHEDULER_INTERVAL_HOURS hours (default 6).
    # Also runs once shortly after startup (60s delay) so reminders aren't
    # delayed by a full interval on a fresh restart.
    from app.config import settings as app_settings

    _reminder_scheduler = AsyncIOScheduler(timezone="UTC")
    _reminder_scheduler.add_job(
        _run_reminder_scan_job,
        trigger="interval",
        hours=app_settings.REMINDER_SCHEDULER_INTERVAL_HOURS,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        id="payment_reminder_scan",
        replace_existing=True,
        max_instances=1,  # never run two scans concurrently
    )
    _reminder_scheduler.start()
    logger.info(
        f"[startup] Payment reminder scheduler started — "
        f"runs every {app_settings.REMINDER_SCHEDULER_INTERVAL_HOURS}h "
        f"(first run in 60s)"
    )

    yield

    # ── Shutdown: cancel background tasks ─────────────────────────────────────
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    if _reminder_scheduler is not None:
        _reminder_scheduler.shutdown(wait=False)
        logger.info("[shutdown] Payment reminder scheduler stopped")


async def _cleanup_stuck_invoices():
    """BUG-16: Periodically marks invoices stuck in 'processing' for >15 min as HUMAN_REQUIRED."""
    while True:
        await asyncio.sleep(5 * 60)  # Run every 5 minutes
        try:
            from app.database import SessionLocal
            from app.models.invoice import Invoice

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            db = SessionLocal()
            try:
                stuck = db.query(Invoice).filter(
                    Invoice.status == "processing",
                    Invoice.created_at < cutoff
                ).all()
                for inv in stuck:
                    inv.status = "HUMAN_REQUIRED"
                    inv.error_detail = "Processing timed out after 15 minutes"
                    logger.warning(f"[cleanup] Invoice {inv.id} marked HUMAN_REQUIRED (stuck)")
                if stuck:
                    db.commit()
                    logger.info(f"[cleanup] Cleaned up {len(stuck)} stuck invoice(s)")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[cleanup] Stuck invoice cleanup error: {e}")


async def _run_reminder_scan_job():
    """
    [NEW] APScheduler job wrapper for reminder_service.run_reminder_scan().

    Runs the (synchronous, DB-bound) reminder scan in the bounded thread pool
    so it doesn't block the asyncio event loop.
    """
    from app.database import SessionLocal
    from app.services.reminder_service import run_reminder_scan

    loop = asyncio.get_event_loop()

    def _scan():
        db = SessionLocal()
        try:
            return run_reminder_scan(db)
        finally:
            db.close()

    try:
        summary = await loop.run_in_executor(_pipeline_executor, _scan)
        logger.info(f"[scheduler] Reminder scan finished: {summary}")
    except Exception as e:
        logger.error(f"[scheduler] Reminder scan job failed: {e}", exc_info=True)


# ───────────────────────────────────────────────
# Application
# ───────────────────────────────────────────────
app = FastAPI(
    title="InvoiceAI API",
    description="AI-powered invoice processing for Indian GST compliance",
    version="1.0.0",
    lifespan=lifespan,
)


# ── BUG-17: Content-Length Limit Middleware ─────────────────────────────────

class ContentLengthLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length > 20MB before reading the body."""
    MAX_BYTES = 20 * 1024 * 1024  # 20MB

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and int(cl) > self.MAX_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "File exceeds 20MB limit."}
            )
        return await call_next(request)

app.add_middleware(ContentLengthLimitMiddleware)


# ───────────────────────────────────────────────
# BUG-15: Hardened Security Headers Middleware
# ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # BUG-15: Additional hardened headers
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cache-Control"] = "no-store"  # Prevents caching financial data
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ───────────────────────────────────────────────
# BUG-15: Narrowed CORS Configuration
# BUG-B1: Production CORS reads from settings.FRONTEND_URL — never a placeholder
# ───────────────────────────────────────────────
from app.config import settings

if settings.ENVIRONMENT == "dev":
    origins = [
        "http://127.0.0.1:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5500",
        "http://localhost:5501",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "http://localhost:5173",   # Vite React dev server
        "http://127.0.0.1:5173",
    ]
else:
    # BUG-B1: Production ONLY — no localhost, no placeholder.
    # If FRONTEND_URL is not set, fail loudly so misconfiguration is caught
    # at startup rather than silently rejecting all real frontend requests.
    if not settings.FRONTEND_URL:
        raise RuntimeError(
            "FRONTEND_URL must be set in .env when ENVIRONMENT != 'dev'. "
            "Example: FRONTEND_URL=https://invoiceai.yourdomain.com"
        )
    origins = [settings.FRONTEND_URL]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    # BUG-15: Explicit method/header lists instead of wildcards
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
)

# ───────────────────────────────────────────────
# Global Exception Handlers
# ───────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clean 422 with field-level errors — never leak internals."""
    errors = []
    for err in exc.errors():
        loc = " → ".join(str(l) for l in err.get("loc", []))
        errors.append({"field": loc, "message": err.get("msg", "Invalid value")})
    return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": errors})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Never expose raw DB errors to clients."""
    correlation_id = str(uuid.uuid4())[:8]
    logger.error(f"[{correlation_id}] Database error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred.", "correlation_id": correlation_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all: return correlation ID, log full traceback.
    BUG-33: Skip HTTPException — let FastAPI handle those natively."""
    from fastapi import HTTPException as _HTTPException
    if isinstance(exc, _HTTPException):
        raise exc
    correlation_id = str(uuid.uuid4())[:8]
    logger.error(f"[{correlation_id}] Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "correlation_id": correlation_id},
    )


# ───────────────────────────────────────────────
# Routers
# ───────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(invoices.router)
app.include_router(review.router)
app.include_router(webhooks.router)
app.include_router(payments.router)    # [NEW] payment tracking
app.include_router(reminders.router)   # [NEW] reminders + notifications

@app.get("/")
def root():
    return {
        "message": "InvoiceAI API v1.0",
        "docs": "/docs",
        "frontend": "http://localhost:5173",
    }


# ───────────────────────────────────────────────
# Health Check
# ───────────────────────────────────────────────
@app.get("/health")
def health():
    """Health check — verifies API + DB + Azure config + QR detection."""
    from app.database import SessionLocal
    from sqlalchemy import text

    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        # BUG-C2: Never expose raw DB exception details in a public endpoint.
        # Connection strings, table names, and internal IPs can appear in SQLAlchemy errors.
        logger.error(f"[health] Database connectivity check failed: {e}", exc_info=True)
        db_status = "error: database unavailable"

    azure_status = "configured"
    try:
        from app.config import settings
        if not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY:
            azure_status = "not_configured"
    except Exception:
        azure_status = "not_configured"

    # [NEW] Reminder scheduler status
    reminder_status = "running" if (
        _reminder_scheduler is not None and _reminder_scheduler.running
    ) else "stopped"

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "db": db_status,
        "azure_ai": azure_status,
        # BUG-21: Report QR detection library status
        "qr_detection": "ok" if _qr_detection_ok else "disabled (see startup log)",
        # [NEW] Report reminder scheduler status
        "reminder_scheduler": reminder_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }