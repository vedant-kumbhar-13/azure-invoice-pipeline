"""
Pydantic schemas for the payment tracking feature.

Covers:
    - PaymentRecord  (create, update, response)
    - PaymentTransaction  (create, response)
    - ReminderSettings  (read, update)
    - ReminderLog  (response)
    - InAppNotification  (response)
    - PaymentStats  (dashboard summary)
    - ManualPaymentEntry  (standalone entry without an invoice)
"""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class PaymentDirection(str, Enum):
    RECEIVABLE = "RECEIVABLE"   # money coming in  (we sent the invoice)
    PAYABLE    = "PAYABLE"      # money going out  (we received the invoice)
    UNKNOWN    = "UNKNOWN"      # org_gstin not set or not found in invoice


class PaymentStatus(str, Enum):
    PENDING   = "PENDING"
    PARTIAL   = "PARTIAL"
    PAID      = "PAID"
    OVERDUE   = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentMode(str, Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    UPI           = "UPI"
    CASH          = "CASH"
    CHEQUE        = "CHEQUE"
    NEFT          = "NEFT"
    RTGS          = "RTGS"
    DD            = "DD"
    OTHER         = "OTHER"


class ReminderType(str, Enum):
    DUE_SOON  = "DUE_SOON"    # fired N days before due date
    DUE_TODAY = "DUE_TODAY"   # fired on due date itself
    OVERDUE   = "OVERDUE"     # fired after due date has passed


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL  = "EMAIL"


class ChannelStatus(str, Enum):
    SENT    = "SENT"
    FAILED  = "FAILED"
    PENDING = "PENDING"


# ── PaymentTransaction schemas ────────────────────────────────────────────────

class PaymentTransactionCreate(BaseModel):
    """Body for POST /payments/{id}/transactions"""
    amount: float
    payment_mode: PaymentMode = PaymentMode.BANK_TRANSFER
    reference_no: Optional[str] = None       # UTR, cheque no, UPI txn ID
    transaction_date: date
    notes: Optional[str] = None
    # proof_blob_name is set server-side after file upload; not accepted here

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be greater than zero")
        return round(v, 2)


class PaymentTransactionResponse(BaseModel):
    id: str
    payment_record_id: str
    amount: float
    payment_mode: str
    reference_no: Optional[str] = None
    transaction_date: date
    proof_blob_name: Optional[str] = None
    notes: Optional[str] = None
    recorded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── PaymentRecord schemas ─────────────────────────────────────────────────────

class PaymentRecordCreate(BaseModel):
    """
    Body for POST /payments/manual
    Used to create a standalone payment entry not linked to any invoice.
    """
    direction: PaymentDirection
    total_amount: float
    due_date: Optional[date] = None
    counterparty_name: Optional[str] = None
    counterparty_gstin: Optional[str] = None
    counterparty_email: Optional[str] = None
    manual_description: Optional[str] = None   # e.g. "Advance to vendor XYZ"
    manual_invoice_ref: Optional[str] = None   # optional reference number
    notes: Optional[str] = None

    @field_validator("total_amount")
    @classmethod
    def total_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Total amount must be greater than zero")
        return round(v, 2)

    @field_validator("counterparty_gstin")
    @classmethod
    def gstin_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 15:
            raise ValueError("GSTIN must be exactly 15 characters")
        return v

    @field_validator("counterparty_email")
    @classmethod
    def email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("counterparty_email must be a valid email address")
        return v


class PaymentRecordUpdate(BaseModel):
    """
    Body for PATCH /payments/{id}
    All fields optional — only provided fields are updated.
    """
    direction: Optional[PaymentDirection] = None
    status: Optional[PaymentStatus] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    counterparty_name: Optional[str] = None
    counterparty_gstin: Optional[str] = None
    counterparty_email: Optional[str] = None
    notes: Optional[str] = None
    manual_description: Optional[str] = None
    manual_invoice_ref: Optional[str] = None

    @model_validator(mode="after")
    def paid_date_requires_paid_status(self) -> "PaymentRecordUpdate":
        """If paid_date is set, status should be PAID or PARTIAL."""
        if self.paid_date and self.status not in (
            PaymentStatus.PAID, PaymentStatus.PARTIAL, None
        ):
            raise ValueError(
                "paid_date can only be set when status is PAID or PARTIAL"
            )
        return self


class PaymentDirectionOverride(BaseModel):
    """
    Body for PATCH /invoices/{id}/payment-direction
    Lets users manually override the auto-detected direction.
    """
    direction: PaymentDirection
    payment_due_date: Optional[date] = None
    counterparty_name: Optional[str] = None
    counterparty_gstin: Optional[str] = None


class PaymentRecordResponse(BaseModel):
    id: str
    invoice_id: Optional[str] = None
    user_id: str
    direction: str
    status: str
    total_amount: float
    paid_amount: float
    balance: float
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    counterparty_name: Optional[str] = None
    counterparty_gstin: Optional[str] = None
    counterparty_email: Optional[str] = None
    is_manual: bool
    manual_description: Optional[str] = None
    manual_invoice_ref: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Nested transactions — included when fetching detail
    transactions: List[PaymentTransactionResponse] = []

    class Config:
        from_attributes = True


class PaymentRecordListResponse(BaseModel):
    """Paginated list response for GET /payments/"""
    items: List[PaymentRecordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Payment stats (dashboard summary) ────────────────────────────────────────

class PaymentStats(BaseModel):
    """
    Response for GET /payments/stats
    Powers the summary cards on the Payments dashboard page.
    """
    # Receivables
    total_receivable: float          # total outstanding (PENDING + PARTIAL)
    total_receivable_overdue: float  # overdue receivables
    total_received: float            # total paid this period

    # Payables
    total_payable: float             # total outstanding (PENDING + PARTIAL)
    total_payable_overdue: float     # overdue payables
    total_paid_out: float            # total paid out this period

    # Counts
    pending_count: int
    overdue_count: int
    paid_count: int
    partial_count: int

    # Upcoming (next 7 days)
    due_next_7_days: float           # combined receivable + payable
    due_next_7_days_count: int


# ── Reminder settings schemas ─────────────────────────────────────────────────

class ReminderSettingsUpdate(BaseModel):
    """Body for PUT /reminders/settings"""
    days_before_due: Optional[str] = None    # comma-separated e.g. "7,3,1"
    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    remind_on_due_date: Optional[bool] = None
    overdue_reminder_enabled: Optional[bool] = None
    overdue_reminder_interval_days: Optional[int] = None

    @field_validator("days_before_due")
    @classmethod
    def validate_days_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parts = v.split(",")
        for p in parts:
            if not p.strip().isdigit():
                raise ValueError(
                    "days_before_due must be comma-separated integers e.g. '7,3,1'"
                )
        return v

    @field_validator("overdue_reminder_interval_days")
    @classmethod
    def interval_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("overdue_reminder_interval_days must be at least 1")
        return v


class ReminderSettingsResponse(BaseModel):
    id: str
    user_id: str
    days_before_due: str
    email_enabled: bool
    in_app_enabled: bool
    remind_on_due_date: bool
    overdue_reminder_enabled: bool
    overdue_reminder_interval_days: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── ReminderLog schema ────────────────────────────────────────────────────────

class ReminderLogResponse(BaseModel):
    id: str
    payment_record_id: str
    user_id: str
    reminder_type: str
    days_offset: int
    channel: str
    channel_status: str
    error_detail: Optional[str] = None
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderSnoozeRequest(BaseModel):
    """Body for POST /reminders/{id}/snooze"""
    snooze_days: int = 1   # defer by this many days

    @field_validator("snooze_days")
    @classmethod
    def snooze_positive(cls, v: int) -> int:
        if v < 1 or v > 30:
            raise ValueError("snooze_days must be between 1 and 30")
        return v


# ── InAppNotification schemas ─────────────────────────────────────────────────

class InAppNotificationResponse(BaseModel):
    id: str
    user_id: str
    reminder_log_id: Optional[str] = None
    payment_record_id: Optional[str] = None
    title: str
    body: str
    icon: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Response for GET /notifications/  (bell dropdown)"""
    items: List[InAppNotificationResponse]
    unread_count: int


# ── Updated auth schemas ──────────────────────────────────────────────────────
# These extend the existing auth.py schemas — import from here in auth router

class OrgProfileUpdate(BaseModel):
    """
    Body for PUT /auth/profile
    Lets users set their organisation details including GSTIN
    used for auto-detecting payment direction.
    """
    org_name: Optional[str] = None
    org_gstin: Optional[str] = None
    org_address: Optional[str] = None
    org_email: Optional[str] = None

    @field_validator("org_gstin")
    @classmethod
    def gstin_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 15:
            raise ValueError("org_gstin must be exactly 15 characters")
        return v


class UserProfileResponse(BaseModel):
    """Extended user response including org fields — for GET /auth/profile"""
    id: str
    email: str
    api_key: Optional[str] = None
    org_name: Optional[str] = None
    org_gstin: Optional[str] = None
    org_address: Optional[str] = None
    org_email: Optional[str] = None

    class Config:
        from_attributes = True