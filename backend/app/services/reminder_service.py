"""
reminder_service.py — Due-date reminder engine for payment tracking.

Responsibilities:
    1. Scan all active PaymentRecords (PENDING / PARTIAL / OVERDUE)
    2. For each user, check their ReminderSettings (days_before_due, channels)
    3. Determine if a reminder is due (DUE_SOON / DUE_TODAY / OVERDUE)
    4. Avoid duplicate sends — check ReminderLog before firing
    5. Create InAppNotification rows (bell icon)
    6. Send emails via smtplib (Gmail / any SMTP server)
    7. Write ReminderLog entries for every attempt (SENT/FAILED)
    8. Flip PENDING/PARTIAL → OVERDUE for past-due records

Scheduling:
    Registered as an APScheduler job in main.py, runs every
    settings.REMINDER_SCHEDULER_INTERVAL_HOURS hours (default 6).
"""
import smtplib
import logging
import uuid
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.payment import (
    PaymentRecord,
    ReminderSettings,
    ReminderLog,
    InAppNotification,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Reminder settings helper ──────────────────────────────────────────────────

def get_or_create_reminder_settings(db: Session, user_id: str) -> ReminderSettings:
    """
    Fetch the user's ReminderSettings, creating a default row if none exists.
    Defaults come from settings.REMINDER_DEFAULT_DAYS_BEFORE ("7,3,1").
    """
    rs = db.query(ReminderSettings).filter(
        ReminderSettings.user_id == user_id
    ).first()

    if rs:
        return rs

    rs = ReminderSettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        days_before_due=settings.REMINDER_DEFAULT_DAYS_BEFORE,
        email_enabled=True,
        in_app_enabled=True,
        remind_on_due_date=True,
        overdue_reminder_enabled=True,
        overdue_reminder_interval_days=3,
    )
    db.add(rs)
    db.commit()
    db.refresh(rs)
    return rs


def _parse_days_before(days_str: str) -> list[int]:
    """Parse '7,3,1' -> [7, 3, 1]. Returns [] on bad input."""
    try:
        return [int(d.strip()) for d in days_str.split(",") if d.strip().isdigit()]
    except Exception:
        return []


# ── Email sending (smtplib) ───────────────────────────────────────────────────

def send_email_reminder(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send a reminder email via smtplib.

    Returns (success: bool, error_detail: Optional[str]).

    If settings.EMAIL_ENABLED is False, or SMTP credentials are not
    configured, returns (False, "email disabled or not configured")
    WITHOUT raising — caller logs this as a FAILED ReminderLog entry,
    but it does not crash the scheduler.
    """
    if not settings.EMAIL_ENABLED:
        return False, "EMAIL_ENABLED is False in settings"

    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        return False, "SMTP_USERNAME / SMTP_PASSWORD not configured in .env"

    if not to_email:
        return False, "Recipient email address is empty"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.smtp_from_address}>"
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        if settings.SMTP_USE_TLS:
            # STARTTLS flow — typical for port 587 (Gmail, Outlook)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.smtp_from_address, to_email, msg.as_string())
        else:
            # SSL flow — typical for port 465
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.smtp_from_address, to_email, msg.as_string())

        logger.info(f"[reminder_service] Email sent to {to_email}: {subject}")
        return True, None

    except smtplib.SMTPAuthenticationError as e:
        error = (
            "SMTP authentication failed. For Gmail, ensure you are using an "
            "App Password (not your normal password) — see config.py SMTP section. "
            f"Details: {e}"
        )
        logger.error(f"[reminder_service] {error}")
        return False, error[:500]

    except Exception as e:
        logger.error(f"[reminder_service] Failed to send email to {to_email}: {e}", exc_info=True)
        return False, str(e)[:500]


# ── In-app notification creation ──────────────────────────────────────────────

def create_in_app_notification(
    db: Session,
    user_id: str,
    payment_record_id: str,
    reminder_log_id: str,
    title: str,
    body: str,
    icon: str = "bell",
) -> InAppNotification:
    """Create a row in in_app_notifications — powers the bell dropdown."""
    notif = InAppNotification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        reminder_log_id=reminder_log_id,
        payment_record_id=payment_record_id,
        title=title,
        body=body,
        icon=icon,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


# ── Message builders ──────────────────────────────────────────────────────────

def _build_message(
    record: PaymentRecord,
    reminder_type: str,
    days_offset: int,
    org_name: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Build (title, body_text, body_html) for a reminder based on record + type.

    Wording adapts to who is actually receiving the email:
      RECEIVABLE + counterparty_email set -> counterparty is the recipient,
          so the message addresses THEM directly ("You owe ₹X to {org}").
      Otherwise -> org's own email is the recipient, so the message is
          phrased as a reminder to ourselves ("₹X {from/to} {counterparty}").
    """
    counterparty = record.counterparty_name or "Unknown party"
    amount_str = f"₹{record.balance:,.2f}"
    due_str = record.due_date.strftime("%B %d, %Y") if record.due_date else "N/A"
    org_label = org_name or "us"

    addressed_to_counterparty = (
        record.direction == "RECEIVABLE" and bool(record.counterparty_email)
    )

    if addressed_to_counterparty:
        # Email is going TO the counterparty — address them directly
        if reminder_type == "DUE_SOON":
            title = f"Payment due in {days_offset} day{'s' if days_offset != 1 else ''}"
            body_text = (
                f"This is a reminder that {amount_str} is due to {org_label} on {due_str} "
                f"({days_offset} day{'s' if days_offset != 1 else ''} from now)."
            )
        elif reminder_type == "DUE_TODAY":
            title = "Payment due today"
            body_text = f"This is a reminder that {amount_str} is due to {org_label} today ({due_str})."
        else:  # OVERDUE
            overdue_days = abs(days_offset)
            title = f"Payment overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}"
            body_text = (
                f"{amount_str} owed to {org_label} was due on {due_str} and is now "
                f"{overdue_days} day{'s' if overdue_days != 1 else ''} overdue. "
                f"Please arrange payment at your earliest convenience."
            )
    else:
        # Email is going to OUR org — phrase as our own reminder
        direction_label = "from" if record.direction == "RECEIVABLE" else "to"

        if reminder_type == "DUE_SOON":
            title = f"Payment due in {days_offset} day{'s' if days_offset != 1 else ''}"
            body_text = (
                f"{amount_str} {direction_label} {counterparty} is due on {due_str} "
                f"({days_offset} day{'s' if days_offset != 1 else ''} from now)."
            )
        elif reminder_type == "DUE_TODAY":
            title = "Payment due today"
            body_text = (
                f"{amount_str} {direction_label} {counterparty} is due today ({due_str})."
            )
        else:  # OVERDUE
            overdue_days = abs(days_offset)
            title = f"Payment overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}"
            body_text = (
                f"{amount_str} {direction_label} {counterparty} was due on {due_str} "
                f"and is now {overdue_days} day{'s' if overdue_days != 1 else ''} overdue."
            )

    if addressed_to_counterparty:
        detail_rows = f"""
            <tr><td style="padding: 4px 12px 4px 0;"><b>Amount due:</b></td><td>{amount_str}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0;"><b>Due date:</b></td><td>{due_str}</td></tr>
        """
    else:
        detail_rows = f"""
            <tr><td style="padding: 4px 12px 4px 0;"><b>Direction:</b></td><td>{record.direction}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0;"><b>Counterparty:</b></td><td>{counterparty}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0;"><b>Amount due:</b></td><td>{amount_str}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0;"><b>Due date:</b></td><td>{due_str}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0;"><b>Status:</b></td><td>{record.status}</td></tr>
        """

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px;">
        <h2 style="color: #1A3C6E;">{title}</h2>
        <p style="font-size: 15px; color: #1A1A2E;">{body_text}</p>
        <table style="margin-top: 12px; font-size: 14px; color: #555566;">
            {detail_rows}
        </table>
        <p style="margin-top: 16px; font-size: 12px; color: #888;">
            This is an automated reminder from Invoice Pipeline.
        </p>
    </div>
    """

    return title, body_text, body_html


# ── Duplicate-send guard ───────────────────────────────────────────────────────

def _already_sent_today(
    db: Session,
    payment_record_id: str,
    reminder_type: str,
    days_offset: int,
    channel: str,
) -> bool:
    """
    Check if a reminder of this exact type/offset/channel was already sent
    today for this payment record. Prevents duplicate sends if the scheduler
    runs multiple times in a day (every 6 hours = up to 4x/day).
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    existing = (
        db.query(ReminderLog)
        .filter(
            ReminderLog.payment_record_id == payment_record_id,
            ReminderLog.reminder_type == reminder_type,
            ReminderLog.days_offset == days_offset,
            ReminderLog.channel == channel,
            ReminderLog.channel_status == "SENT",
            ReminderLog.sent_at >= today_start,
        )
        .first()
    )
    return existing is not None


# ── Snooze check ────────────────────────────────────────────────────────────────

def _is_snoozed(db: Session, payment_record_id: str) -> bool:
    """Check if there's an active snooze for this payment record."""
    now = datetime.now(timezone.utc)
    snoozed = (
        db.query(ReminderLog)
        .filter(
            ReminderLog.payment_record_id == payment_record_id,
            ReminderLog.snoozed_until.isnot(None),
            ReminderLog.snoozed_until > now,
        )
        .first()
    )
    return snoozed is not None


# ── Core: process a single payment record ────────────────────────────────────

def _process_record(db: Session, record: PaymentRecord, today: date) -> int:
    """
    Check one PaymentRecord against its owner's ReminderSettings and fire
    any due reminders. Returns the number of reminders sent (any channel).
    """
    if not record.due_date:
        return 0  # nothing to remind about

    if record.status in ("PAID", "CANCELLED"):
        return 0

    if _is_snoozed(db, record.id):
        logger.debug(f"[reminder_service] Record {record.id} is snoozed — skipping")
        return 0

    settings_row = get_or_create_reminder_settings(db, record.user_id)
    days_list = _parse_days_before(settings_row.days_before_due)

    delta_days = (record.due_date - today).days  # positive = future, negative = overdue

    # Determine reminder_type + days_offset for this run
    reminder_type = None
    days_offset = None

    if delta_days > 0 and delta_days in days_list:
        reminder_type = "DUE_SOON"
        days_offset = delta_days
    elif delta_days == 0 and settings_row.remind_on_due_date:
        reminder_type = "DUE_TODAY"
        days_offset = 0
    elif delta_days < 0 and settings_row.overdue_reminder_enabled:
        overdue_days = abs(delta_days)
        interval = max(1, settings_row.overdue_reminder_interval_days)
        if overdue_days % interval == 0:
            reminder_type = "OVERDUE"
            days_offset = delta_days

    if reminder_type is None:
        return 0

    user = db.query(User).filter(User.id == record.user_id).first()
    org_name = (user.org_name or user.email) if user else None
    title, body_text, body_html = _build_message(record, reminder_type, days_offset, org_name)

    sent_count = 0

    # ── In-app channel ──
    if settings_row.in_app_enabled:
        if not _already_sent_today(db, record.id, reminder_type, days_offset, "IN_APP"):
            log = ReminderLog(
                id=str(uuid.uuid4()),
                payment_record_id=record.id,
                user_id=record.user_id,
                reminder_type=reminder_type,
                days_offset=days_offset,
                channel="IN_APP",
                channel_status="SENT",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            create_in_app_notification(
                db=db,
                user_id=record.user_id,
                payment_record_id=record.id,
                reminder_log_id=log.id,
                title=title,
                body=body_text,
                icon="alert" if reminder_type == "OVERDUE" else "bell",
            )
            sent_count += 1
            logger.info(
                f"[reminder_service] IN_APP reminder sent | record={record.id} "
                f"| type={reminder_type} | offset={days_offset}"
            )

    # ── Email channel ──
    # Recipient logic:
    #   RECEIVABLE -> counterparty owes us, so THEY get the reminder.
    #                 Use counterparty_email if set, else fall back to
    #                 our own org email (better to notify ourselves than
    #                 send nothing).
    #   PAYABLE    -> we owe the counterparty, so the reminder is for US
    #                 to pay them. Always goes to our own org email,
    #                 regardless of whether counterparty_email is set.
    if settings_row.email_enabled and user:
        if record.direction == "RECEIVABLE" and record.counterparty_email:
            recipient = record.counterparty_email
        else:
            recipient = user.org_email or user.email

        if not _already_sent_today(db, record.id, reminder_type, days_offset, "EMAIL"):
            success, error_detail = send_email_reminder(
                to_email=recipient,
                subject=f"[Invoice Pipeline] {title}",
                body_text=body_text,
                body_html=body_html,
            )

            log = ReminderLog(
                id=str(uuid.uuid4()),
                payment_record_id=record.id,
                user_id=record.user_id,
                reminder_type=reminder_type,
                days_offset=days_offset,
                channel="EMAIL",
                channel_status="SENT" if success else "FAILED",
                error_detail=error_detail,
                sent_at=datetime.now(timezone.utc) if success else None,
            )
            db.add(log)
            db.commit()

            if success:
                sent_count += 1
                logger.info(
                    f"[reminder_service] EMAIL reminder sent | record={record.id} "
                    f"| type={reminder_type} | offset={days_offset} | to={recipient}"
                )
            else:
                logger.warning(
                    f"[reminder_service] EMAIL reminder FAILED | record={record.id} "
                    f"| error={error_detail}"
                )

    return sent_count


# ── Main entry point — called by APScheduler ─────────────────────────────────

def run_reminder_scan(db: Session) -> dict:
    """
    Main scheduled job. Called every REMINDER_SCHEDULER_INTERVAL_HOURS hours.

    Steps:
        1. Flip overdue PENDING/PARTIAL records to OVERDUE
        2. Scan all active records and fire due reminders

    Returns a summary dict for logging.
    """
    from app.services.payment_service import mark_overdue_payments

    today = date.today()

    # Step 1: Flip statuses
    overdue_flipped = mark_overdue_payments(db)

    # Step 2: Scan records
    active_records = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.status.in_(["PENDING", "PARTIAL", "OVERDUE"]))
        .filter(PaymentRecord.due_date.isnot(None))
        .all()
    )

    total_reminders_sent = 0
    records_checked = len(active_records)

    for record in active_records:
        try:
            sent = _process_record(db, record, today)
            total_reminders_sent += sent
        except Exception as e:
            logger.error(
                f"[reminder_service] Error processing record {record.id}: {e}",
                exc_info=True,
            )

    summary = {
        "records_checked": records_checked,
        "reminders_sent": total_reminders_sent,
        "overdue_flipped": overdue_flipped,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[reminder_service] Scan complete: {summary}")
    return summary


# ── Snooze action (called by router) ──────────────────────────────────────────

def snooze_reminders(db: Session, payment_record_id: str, user_id: str, snooze_days: int) -> bool:
    """
    Snooze all future reminders for a payment record by writing a
    sentinel ReminderLog row with snoozed_until in the future.

    _is_snoozed() checks for this row and skips the record until then.
    """
    from datetime import timedelta

    record = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_record_id,
        PaymentRecord.user_id == user_id,
    ).first()

    if not record:
        return False

    snooze_until = datetime.now(timezone.utc) + timedelta(days=snooze_days)

    log = ReminderLog(
        id=str(uuid.uuid4()),
        payment_record_id=payment_record_id,
        user_id=user_id,
        reminder_type="SNOOZE",
        days_offset=0,
        channel="IN_APP",
        channel_status="PENDING",
        snoozed_until=snooze_until,
    )
    db.add(log)
    db.commit()

    logger.info(
        f"[reminder_service] Record {payment_record_id} snoozed until {snooze_until}"
    )
    return True