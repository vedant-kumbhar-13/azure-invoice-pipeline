"""
Reminders + Notifications router for InvoiceAI.

Endpoints:
    GET   /reminders/settings              → get user's reminder preferences
    PUT   /reminders/settings              → update reminder preferences
    GET   /reminders/                      → reminder log (sent history)
    POST  /reminders/{id}/snooze           → snooze future reminders for a payment record
    POST  /reminders/{id}/acknowledge      → mark a reminder log entry as acknowledged
    POST  /reminders/run-now               → manually trigger a reminder scan (testing/debug)

    GET   /notifications/                  → bell dropdown: list + unread count
    POST  /notifications/{id}/read         → mark one notification as read
    POST  /notifications/mark-all-read     → mark all notifications as read
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.payment import ReminderLog, InAppNotification
from app.middleware.auth import get_current_user
from app.schemas.payment import (
    ReminderSettingsResponse,
    ReminderSettingsUpdate,
    ReminderLogResponse,
    ReminderSnoozeRequest,
    InAppNotificationResponse,
    NotificationListResponse,
)
from app.services.reminder_service import (
    get_or_create_reminder_settings,
    snooze_reminders,
    run_reminder_scan,
)

logger = logging.getLogger("invoiceai.reminders")

router = APIRouter(tags=["Reminders & Notifications"])


# ── Reminder settings ──────────────────────────────────────────────────────────

@router.get("/reminders/settings", response_model=ReminderSettingsResponse)
def get_reminder_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = get_or_create_reminder_settings(db, current_user.id)
    return settings_row


@router.put("/reminders/settings", response_model=ReminderSettingsResponse)
def update_reminder_settings(
    payload: ReminderSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = get_or_create_reminder_settings(db, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings_row, field, value)

    db.commit()
    db.refresh(settings_row)
    return settings_row


# ── Reminder log (history) ────────────────────────────────────────────────────

@router.get("/reminders/", response_model=list[ReminderLogResponse])
def list_reminder_logs(
    payment_record_id: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ReminderLog).filter(ReminderLog.user_id == current_user.id)

    if payment_record_id:
        query = query.filter(ReminderLog.payment_record_id == payment_record_id)

    logs = (
        query
        .order_by(ReminderLog.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return logs


# ── Snooze ──────────────────────────────────────────────────────────────────────

@router.post("/reminders/{payment_record_id}/snooze")
def snooze_payment_reminders(
    payment_record_id: str,
    payload: ReminderSnoozeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = snooze_reminders(
        db=db,
        payment_record_id=payment_record_id,
        user_id=current_user.id,
        snooze_days=payload.snooze_days,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    return {
        "message": f"Reminders snoozed for {payload.snooze_days} day(s).",
        "payment_record_id": payment_record_id,
    }


# ── Acknowledge a reminder log entry ──────────────────────────────────────────

@router.post("/reminders/{reminder_log_id}/acknowledge", response_model=ReminderLogResponse)
def acknowledge_reminder(
    reminder_log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = db.query(ReminderLog).filter(
        ReminderLog.id == reminder_log_id,
        ReminderLog.user_id == current_user.id,
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Reminder log entry not found.")

    log.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(log)
    return log


# ── Manual trigger (debugging / testing) ──────────────────────────────────────

@router.post("/reminders/run-now")
def run_reminder_scan_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger a reminder scan for testing without waiting for the
    APScheduler interval. Scans ALL users' records (not just current_user)
    since reminders are system-wide — but this is gated behind auth so only
    logged-in users can trigger it.
    """
    summary = run_reminder_scan(db)
    return {"message": "Reminder scan completed", "summary": summary}


# ════════════════════════════════════════════════════════════════════════════
# Notifications (bell icon)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/notifications/", response_model=NotificationListResponse)
def list_notifications(
    limit: int = 20,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(InAppNotification).filter(InAppNotification.user_id == current_user.id)

    if unread_only:
        query = query.filter(InAppNotification.is_read == False)  # noqa: E712

    items = (
        query
        .order_by(InAppNotification.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )

    unread_count = (
        db.query(InAppNotification)
        .filter(
            InAppNotification.user_id == current_user.id,
            InAppNotification.is_read == False,  # noqa: E712
        )
        .count()
    )

    return {"items": items, "unread_count": unread_count}


@router.post("/notifications/{notification_id}/read", response_model=InAppNotificationResponse)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.query(InAppNotification).filter(
        InAppNotification.id == notification_id,
        InAppNotification.user_id == current_user.id,
    ).first()

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notif)

    return notif


@router.post("/notifications/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    updated = (
        db.query(InAppNotification)
        .filter(
            InAppNotification.user_id == current_user.id,
            InAppNotification.is_read == False,  # noqa: E712
        )
        .update({"is_read": True, "read_at": now}, synchronize_session=False)
    )

    db.commit()
    return {"message": f"{updated} notification(s) marked as read."}