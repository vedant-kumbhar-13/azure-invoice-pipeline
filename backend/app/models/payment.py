import uuid
from sqlalchemy import (
    Column, String, Float, ForeignKey, DateTime,
    Date, Boolean, Integer, Text
)
from sqlalchemy.sql import func
from app.database import Base


# ── PaymentRecord ─────────────────────────────────────────────────────────────
# One record per invoice (created automatically by payment_service when an
# invoice reaches AUTO_APPROVED or VERIFIED status) OR created manually by the
# user as a standalone entry (is_manual=True, invoice_id=None).
#
# Direction values:
#   RECEIVABLE  → money coming in  (we sent the invoice)
#   PAYABLE     → money going out  (we received the invoice)
#
# Status flow:
#   PENDING → PARTIAL → PAID
#   PENDING → OVERDUE        (flipped nightly by reminder_service)
#   Any    → CANCELLED       (manual user action)

class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), index=True
    )

    # FK to Invoice — NULL for manual standalone entries
    invoice_id = Column(
        String(36), ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # The user who owns this payment record
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # RECEIVABLE or PAYABLE
    direction = Column(String(12), nullable=False, index=True)

    # PENDING | PARTIAL | PAID | OVERDUE | CANCELLED
    status = Column(String(12), nullable=False, default="PENDING", index=True)

    # Financial amounts
    total_amount = Column(Float, nullable=False)          # full invoice amount
    paid_amount = Column(Float, nullable=False, default=0.0)  # sum of all transactions
    balance = Column(Float, nullable=False)               # total_amount - paid_amount

    # Dates
    due_date = Column(Date, nullable=True, index=True)
    paid_date = Column(Date, nullable=True)               # set when status → PAID

    # Counterparty info (denormalised for fast display without JOIN to invoices)
    counterparty_name = Column(String(255), nullable=True)
    counterparty_gstin = Column(String(15), nullable=True)
    # [NEW] Counterparty email — used as the reminder recipient for
    # RECEIVABLE payments (they owe us, so they get reminded to pay).
    # For PAYABLE payments this is informational only; reminders always
    # go to the org's own email since it's a reminder for US to pay them.
    counterparty_email = Column(String(255), nullable=True)

    # Manual entry fields
    # is_manual=True means no linked invoice; all fields entered by user
    is_manual = Column(Boolean, nullable=False, default=False)
    manual_description = Column(String(500), nullable=True)  # e.g. "Advance to vendor XYZ"
    manual_invoice_ref = Column(String(100), nullable=True)  # optional ref number

    # General notes
    notes = Column(Text, nullable=True)

    # Audit
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now()
    )


# ── PaymentTransaction ────────────────────────────────────────────────────────
# Each row is one actual payment made against a PaymentRecord.
# Supports partial payments: multiple transactions can exist per PaymentRecord
# until balance reaches 0 (status → PAID).
#
# Payment modes:
#   BANK_TRANSFER | UPI | CASH | CHEQUE | NEFT | RTGS | DD | OTHER

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), index=True
    )

    payment_record_id = Column(
        String(36), ForeignKey("payment_records.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Amount paid in this single transaction
    amount = Column(Float, nullable=False)

    # Payment mode
    payment_mode = Column(String(20), nullable=False, default="BANK_TRANSFER")

    # UTR number, cheque number, UPI transaction ID, etc.
    reference_no = Column(String(100), nullable=True)

    transaction_date = Column(Date, nullable=False)

    # Optional proof of payment (blob name stored in Azure, SAS URL generated on demand)
    proof_blob_name = Column(String(255), nullable=True)

    notes = Column(Text, nullable=True)

    recorded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── ReminderSettings ──────────────────────────────────────────────────────────
# One row per user. Stores their reminder preferences.
# Created with defaults when a user first accesses reminder settings.
# days_before stores JSON-like comma-separated string "7,3,1" for SQLite
# compatibility (avoids ARRAY type which needs PostgreSQL).

class ReminderSettings(Base):
    __tablename__ = "reminder_settings"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )

    # Comma-separated days before due date to send reminder e.g. "7,3,1"
    # Default: 7 days, 3 days, 1 day before due
    days_before_due = Column(String(50), nullable=False, default="7,3,1")

    # Reminder channels
    email_enabled = Column(Boolean, nullable=False, default=True)
    in_app_enabled = Column(Boolean, nullable=False, default=True)

    # Also remind on the due date itself (day 0)
    remind_on_due_date = Column(Boolean, nullable=False, default=True)

    # Also remind for OVERDUE payments (every N days after due date)
    overdue_reminder_enabled = Column(Boolean, nullable=False, default=True)
    overdue_reminder_interval_days = Column(Integer, nullable=False, default=3)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now()
    )


# ── ReminderLog ───────────────────────────────────────────────────────────────
# Audit trail of every reminder that was fired (or attempted).
# reminder_service writes one row per reminder sent.
#
# reminder_type values: DUE_SOON | DUE_TODAY | OVERDUE
# channel values:       IN_APP | EMAIL
# channel_status:       SENT | FAILED | PENDING

class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), index=True
    )

    payment_record_id = Column(
        String(36), ForeignKey("payment_records.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # DUE_SOON | DUE_TODAY | OVERDUE
    reminder_type = Column(String(20), nullable=False)

    # How many days before (or after, if negative) due date this was sent
    # e.g. 7 = sent 7 days before due, -2 = sent 2 days after due (overdue)
    days_offset = Column(Integer, nullable=False)

    # IN_APP or EMAIL
    channel = Column(String(10), nullable=False)

    # SENT | FAILED | PENDING
    channel_status = Column(String(10), nullable=False, default="PENDING")

    # Error message if channel_status = FAILED
    error_detail = Column(String(500), nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Set when user clicks "Mark as read" or "Acknowledge" in the UI
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Snoozed: if user snoozes, we set a new fire time and skip until then
    snoozed_until = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── InAppNotification ─────────────────────────────────────────────────────────
# Powers the bell icon in the frontend.
# Every in-app reminder creates one row here.
# The bell count = SELECT COUNT(*) WHERE user_id=? AND is_read=False.

class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()), index=True
    )

    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Link back to the reminder log entry that created this notification
    reminder_log_id = Column(
        String(36), ForeignKey("reminder_logs.id", ondelete="CASCADE"),
        nullable=True
    )

    # Link to the payment record so the frontend can navigate directly
    payment_record_id = Column(
        String(36), ForeignKey("payment_records.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    title = Column(String(255), nullable=False)   # e.g. "Payment due in 3 days"
    body = Column(String(500), nullable=False)    # e.g. "₹45,000 from Tata Consultancy..."
    icon = Column(String(20), nullable=False, default="bell")  # for frontend icon mapping

    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)