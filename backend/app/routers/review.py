"""
Review queue router for InvoiceAI.

BUG-22: Audit log stores diff-only for EDITED, minimal payloads for APPROVED/REJECTED.
"""
import logging
from typing import Optional, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.database import get_db
from app.models.user import User
from app.models.invoice import Invoice
from app.models.review_log import ReviewLog
from app.middleware.auth import get_current_user
from app.services.confidence_engine import compute_confidence
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["Review Queue"])


class ReviewSubmit(BaseModel):
    action: Literal["APPROVED", "REJECTED", "EDITED"]
    corrected_data: Optional[dict] = None
    notes: Optional[str] = None


# ── BUG-22: Diff-only audit storage ───────────────────────────────────────

def _compute_diff(before: dict, after: dict) -> dict:
    """Returns only the keys that changed between before and after."""
    diff = {}
    all_keys = set(list((before or {}).keys()) + list((after or {}).keys()))
    for k in all_keys:
        b_val = (before or {}).get(k)
        a_val = (after or {}).get(k)
        if b_val != a_val:
            diff[k] = {"before": b_val, "after": a_val}
    return diff


@router.get("/queue")
def get_review_queue(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skip = (page - 1) * limit

    query = db.query(Invoice).filter(
        Invoice.user_id == current_user.id,
        Invoice.status.in_(["NEEDS_REVIEW", "HUMAN_REQUIRED"]),
    )

    total = query.count()

    # BUG-34: Sort by priority — HUMAN_REQUIRED first, then NEEDS_REVIEW, then by date
    priority_order = case(
        (Invoice.status == "HUMAN_REQUIRED", 0),
        (Invoice.status == "NEEDS_REVIEW", 1),
        else_=2,
    )
    invoices = (
        query
        .order_by(priority_order, Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for inv in invoices:
        flags = []
        if inv.gst_rules_json and isinstance(inv.gst_rules_json, dict) and "flags" in inv.gst_rules_json:
            flags = inv.gst_rules_json["flags"]

        items.append({
            "id": inv.id,
            "status": inv.status,
            "confidence_score": inv.confidence,
            "original_filename": inv.original_filename,
            "created_at": utc_iso(inv.created_at),
            "gst_flags": flags,
        })

    return {
        "items": items,
        "total": total,
        "total_pending": total,
        "page": page,
    }


@router.post("/{invoice_id}/submit")
def submit_review(
    invoice_id: str,
    payload: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id,
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if invoice.status not in ["NEEDS_REVIEW", "HUMAN_REQUIRED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice cannot be reviewed. Current status: {invoice.status}",
        )

    before_data = invoice.data_json
    after_data = invoice.data_json
    new_status = invoice.status
    new_ingestion = invoice.ingestion_method

    # BUG-22: Prepare diff-only audit log entries
    log_before = None
    log_after = None

    if payload.action == "APPROVED":
        new_status = "VERIFIED"
        new_ingestion = "HUMAN"
        # BUG-22: Minimal payload for approvals
        log_before = {"status": "approved_as_is"}
        log_after = {"reviewer": current_user.id}

    elif payload.action == "REJECTED":
        new_status = "REJECTED"
        # BUG-22: Minimal payload for rejections
        log_before = {
            "invoice_id": invoice.id,
            "original_filename": invoice.original_filename,
        }
        log_after = {"reason": payload.notes}

    elif payload.action == "EDITED":
        if not payload.corrected_data:
            raise HTTPException(status_code=400, detail="corrected_data is required when action is EDITED.")
        after_data = payload.corrected_data
        conf_result = compute_confidence(after_data)
        invoice.data_json = after_data
        invoice.confidence = conf_result["overall_score"]
        new_status = "VERIFIED"
        new_ingestion = "HUMAN"

        # Re-run GST rules on corrected data for consistency
        from app.services.gst_rules import run_gst_rules
        invoice.gst_rules_json = run_gst_rules(after_data)

        # Save corrections to vendor cache for future invoices
        from app.services.corrections_cache import save_correction
        try:
            save_correction(
                db=db,
                invoice_id=invoice.id,
                user_id=current_user.id,
                before_data=before_data,
                after_data=after_data,
            )
        except Exception as e:
            # Don't fail the review if cache save fails
            logger.warning(f"[review:{invoice.id}] Failed to cache correction: {e}")

        # BUG-22: Store only the diff — not full before/after blobs
        log_before = _compute_diff(before_data or {}, after_data or {})
        log_after = None  # diff already captures both

    log_entry = ReviewLog(
        invoice_id=invoice.id,
        reviewer_user_id=current_user.id,
        action=payload.action,
        before_data=log_before,
        after_data=log_after,
        notes=payload.notes,
    )

    invoice.status = new_status
    invoice.ingestion_method = new_ingestion
    db.add(log_entry)
    db.commit()
    db.refresh(invoice)

    logger.info(
        f"[invoice:{invoice.id}] Reviewed by user:{current_user.id} "
        f"action={payload.action} status_updated={new_status}"
    )

    return {
        "id": invoice.id,
        "status": invoice.status,
        "confidence_score": invoice.confidence,
        "original_filename": invoice.original_filename,
        "ingestion_method": invoice.ingestion_method,
        "data_json": invoice.data_json,
    }


@router.get("/{invoice_id}/history")
def get_review_history(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id,
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    logs = db.query(ReviewLog).filter(
        ReviewLog.invoice_id == invoice_id,
    ).order_by(ReviewLog.created_at.asc()).all()

    return [
        {
            "id": log.id,
            "invoice_id": log.invoice_id,
            "reviewer_user_id": log.reviewer_user_id,
            "action": log.action,
            "notes": log.notes,
            "created_at": utc_iso(log.created_at),
        }
        for log in logs
    ]
