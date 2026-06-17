"""
payment_service.py — Core business logic for payment tracking.

Responsibilities:
    1. Auto-create a PaymentRecord when an invoice reaches AUTO_APPROVED / VERIFIED
    2. Auto-detect payment direction (PAYABLE/RECEIVABLE) by comparing
       invoice GSTINs against the user's org_gstin
    3. Add payment transactions (partial or full payments)
    4. Recalculate balance and flip status after every transaction
    5. Nightly status check — flip PENDING → OVERDUE for past-due records
    6. Manual standalone payment entry creation
"""
import uuid
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment import PaymentRecord, PaymentTransaction
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Direction detection ───────────────────────────────────────────────────────

def detect_payment_direction(
    invoice: Invoice,
    org_gstin: Optional[str],
) -> str:
    """
    Compare the invoice's seller/buyer GSTINs against the user's org_gstin
    to determine whether the invoice is a RECEIVABLE or PAYABLE.

    Logic:
        - vendor_gstin in data_json == org_gstin  → RECEIVABLE (we are the seller)
        - buyer_gstin  in data_json == org_gstin  → PAYABLE    (we are the buyer)
        - org_gstin is None or not found in invoice → UNKNOWN

    Returns one of: "RECEIVABLE" | "PAYABLE" | "UNKNOWN"
    """
    if not org_gstin:
        logger.debug("org_gstin not set — direction = UNKNOWN")
        return "UNKNOWN"

    data = invoice.data_json or {}
    org = org_gstin.strip().upper()

    # data_json stores ConfidenceField dicts: {"value": "...", "confidence": 0.9}
    # Extract raw value safely from either format
    def _get(field: str) -> Optional[str]:
        raw = data.get(field)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return str(raw.get("value", "") or "").strip().upper()
        return str(raw).strip().upper()

    vendor_gstin = _get("vendor_gstin")
    buyer_gstin  = _get("buyer_gstin")

    if vendor_gstin and vendor_gstin == org:
        return "RECEIVABLE"
    if buyer_gstin and buyer_gstin == org:
        return "PAYABLE"

    logger.debug(
        f"org_gstin={org} not found in vendor_gstin={vendor_gstin} "
        f"or buyer_gstin={buyer_gstin} — direction = UNKNOWN"
    )
    return "UNKNOWN"


# ── Counterparty extraction ───────────────────────────────────────────────────

def extract_counterparty(invoice: Invoice, direction: str) -> dict:
    """
    Extract counterparty name and GSTIN from invoice data_json.

    For RECEIVABLE: counterparty is the buyer  (money coming from them)
    For PAYABLE:    counterparty is the vendor  (money going to them)
    For UNKNOWN:    attempt vendor first, fall back to buyer
    """
    data = invoice.data_json or {}

    def _get_val(field: str) -> Optional[str]:
        raw = data.get(field)
        if raw is None:
            return None
        if isinstance(raw, dict):
            v = raw.get("value")
            return str(v).strip() if v else None
        return str(raw).strip() if raw else None

    if direction == "RECEIVABLE":
        name  = _get_val("buyer_name")
        gstin = _get_val("buyer_gstin")
    elif direction == "PAYABLE":
        name  = _get_val("vendor_name")
        gstin = _get_val("vendor_gstin")
    else:
        name  = _get_val("vendor_name") or _get_val("buyer_name")
        gstin = _get_val("vendor_gstin") or _get_val("buyer_gstin")

    return {"name": name, "gstin": gstin}


# ── Due date extraction ───────────────────────────────────────────────────────

def extract_due_date(invoice: Invoice) -> Optional[date]:
    """
    Try to pull a due date from the invoice's data_json.
    Falls back to None — user can set it manually afterwards.

    Checks these fields in order: due_date, payment_due_date, payment_terms
    """
    data = invoice.data_json or {}

    def _get_val(field: str) -> Optional[str]:
        raw = data.get(field)
        if raw is None:
            return None
        if isinstance(raw, dict):
            v = raw.get("value")
            return str(v).strip() if v else None
        return str(raw).strip() if raw else None

    for field in ("due_date", "payment_due_date"):
        raw = _get_val(field)
        if raw:
            try:
                # Try common date formats
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except ValueError:
                        continue
            except Exception:
                pass

    return None


# ── Total amount extraction ───────────────────────────────────────────────────

def extract_total_amount(invoice: Invoice) -> float:
    """Pull total_amount from data_json. Falls back to 0.0."""
    data = invoice.data_json or {}
    raw = data.get("total_amount")
    if raw is None:
        return 0.0
    if isinstance(raw, dict):
        try:
            return float(raw.get("value") or 0.0)
        except (ValueError, TypeError):
            return 0.0
    try:
        return float(raw)
    except (ValueError, TypeError):
        return 0.0


# ── Core: create PaymentRecord from an approved invoice ──────────────────────

def create_payment_record_from_invoice(
    db: Session,
    invoice: Invoice,
) -> Optional[PaymentRecord]:
    """
    Called by processing_pipeline.py after an invoice reaches
    AUTO_APPROVED or VERIFIED status.

    Steps:
        1. Check if a PaymentRecord already exists for this invoice
           (handles re-processing without creating duplicates)
        2. Load the user to get org_gstin
        3. Auto-detect direction
        4. Extract counterparty, due date, total amount from data_json
        5. Write PaymentRecord + update Invoice payment fields
        6. Commit and return the new record

    Returns the created PaymentRecord, or the existing one if already present.
    """
    # Guard: don't create duplicates on reprocess
    existing = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.invoice_id == invoice.id)
        .first()
    )
    if existing:
        logger.info(
            f"[payment_service] PaymentRecord already exists for invoice "
            f"{invoice.id} — skipping creation"
        )
        return existing

    # Load user for org_gstin
    user = db.query(User).filter(User.id == invoice.user_id).first()
    org_gstin = user.org_gstin if user else None

    # Detect direction
    direction = detect_payment_direction(invoice, org_gstin)

    # Extract fields from invoice data
    counterparty = extract_counterparty(invoice, direction)
    due_date     = extract_due_date(invoice)
    total_amount = extract_total_amount(invoice)

    # Update Invoice model with payment fields (denormalised for fast queries)
    invoice.payment_direction  = direction
    invoice.payment_due_date   = due_date
    invoice.counterparty_name  = counterparty["name"]
    invoice.counterparty_gstin = counterparty["gstin"]

    # Create the PaymentRecord
    record = PaymentRecord(
        id                = str(uuid.uuid4()),
        invoice_id        = invoice.id,
        user_id           = invoice.user_id,
        direction         = direction,
        status            = "PENDING",
        total_amount      = total_amount,
        paid_amount       = 0.0,
        balance           = total_amount,
        due_date          = due_date,
        counterparty_name  = counterparty["name"],
        counterparty_gstin = counterparty["gstin"],
        is_manual         = False,
        created_by        = invoice.user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        f"[payment_service] Created PaymentRecord {record.id} for invoice "
        f"{invoice.id} | direction={direction} | amount={total_amount} "
        f"| due={due_date} | counterparty={counterparty['name']}"
    )
    return record


# ── Core: create manual standalone PaymentRecord ─────────────────────────────

def create_manual_payment_record(
    db: Session,
    user_id: str,
    direction: str,
    total_amount: float,
    due_date: Optional[date] = None,
    counterparty_name: Optional[str] = None,
    counterparty_gstin: Optional[str] = None,
    counterparty_email: Optional[str] = None,
    manual_description: Optional[str] = None,
    manual_invoice_ref: Optional[str] = None,
    notes: Optional[str] = None,
) -> PaymentRecord:
    """
    Create a standalone payment record not linked to any invoice.
    Used for advances, retainers, manual entries, etc.
    """
    record = PaymentRecord(
        id                  = str(uuid.uuid4()),
        invoice_id          = None,        # no linked invoice
        user_id             = user_id,
        direction           = direction,
        status              = "PENDING",
        total_amount        = round(total_amount, 2),
        paid_amount         = 0.0,
        balance             = round(total_amount, 2),
        due_date            = due_date,
        counterparty_name   = counterparty_name,
        counterparty_gstin  = counterparty_gstin,
        counterparty_email  = counterparty_email,
        is_manual           = True,
        manual_description  = manual_description,
        manual_invoice_ref  = manual_invoice_ref,
        notes               = notes,
        created_by          = user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        f"[payment_service] Created manual PaymentRecord {record.id} "
        f"| user={user_id} | direction={direction} | amount={total_amount}"
    )
    return record


# ── Core: add a transaction and recalculate balance ──────────────────────────

def add_transaction(
    db: Session,
    payment_record_id: str,
    user_id: str,
    amount: float,
    payment_mode: str,
    transaction_date: date,
    reference_no: Optional[str] = None,
    proof_blob_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> PaymentTransaction:
    """
    Add a payment transaction to a PaymentRecord.

    After adding:
        - paid_amount is recalculated as sum of all transactions
        - balance = total_amount - paid_amount
        - status is updated:
            paid_amount >= total_amount → PAID
            0 < paid_amount < total_amount → PARTIAL
            paid_amount == 0 → PENDING (unchanged)

    Raises ValueError if the record is not found, is already PAID, or
    the transaction amount exceeds the remaining balance.
    """
    record = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_record_id,
        PaymentRecord.user_id == user_id,
    ).first()

    if not record:
        raise ValueError(f"PaymentRecord {payment_record_id} not found")

    if record.status == "CANCELLED":
        raise ValueError("Cannot add transaction to a CANCELLED payment record")

    if record.status == "PAID":
        raise ValueError(
            "Payment record is already fully PAID. "
            "If this is a correction, cancel the record and create a new one."
        )

    amount = round(amount, 2)
    if amount > round(record.balance, 2):
        raise ValueError(
            f"Transaction amount ₹{amount:,.2f} exceeds remaining balance "
            f"₹{record.balance:,.2f}. Use the exact balance amount to mark as fully paid."
        )

    # Create the transaction row
    txn = PaymentTransaction(
        id                = str(uuid.uuid4()),
        payment_record_id = payment_record_id,
        amount            = amount,
        payment_mode      = payment_mode,
        reference_no      = reference_no,
        transaction_date  = transaction_date,
        proof_blob_name   = proof_blob_name,
        notes             = notes,
        recorded_by       = user_id,
    )
    db.add(txn)

    # Recalculate totals from all transactions (authoritative sum, not incremental)
    db.flush()   # ensure new txn is visible in this session
    all_txn_amounts = (
        db.query(PaymentTransaction.amount)
        .filter(PaymentTransaction.payment_record_id == payment_record_id)
        .all()
    )
    new_paid = round(sum(r.amount for r in all_txn_amounts), 2)
    new_balance = round(record.total_amount - new_paid, 2)

    # Clamp balance to 0 (floating point safety)
    new_balance = max(0.0, new_balance)

    # Determine new status
    if new_balance == 0.0:
        new_status = "PAID"
        record.paid_date = transaction_date
    elif new_paid > 0:
        new_status = "PARTIAL"
    else:
        new_status = record.status  # unchanged

    record.paid_amount = new_paid
    record.balance     = new_balance
    record.status      = new_status

    db.commit()
    db.refresh(txn)

    logger.info(
        f"[payment_service] Transaction {txn.id} added to record {payment_record_id} "
        f"| amount={amount} | new_status={new_status} | balance={new_balance}"
    )
    return txn


# ── Nightly job: flip PENDING → OVERDUE ──────────────────────────────────────

def mark_overdue_payments(db: Session) -> int:
    """
    Scan all PENDING and PARTIAL records with a due_date in the past
    and flip their status to OVERDUE.

    Called by reminder_service.py APScheduler job every 6 hours.
    Returns the count of records updated.
    """
    today = date.today()
    records = (
        db.query(PaymentRecord)
        .filter(
            PaymentRecord.status.in_(["PENDING", "PARTIAL"]),
            PaymentRecord.due_date < today,
            PaymentRecord.due_date.isnot(None),
        )
        .all()
    )

    count = 0
    for record in records:
        record.status = "OVERDUE"
        count += 1

    if count:
        db.commit()
        logger.info(f"[payment_service] Marked {count} payment records as OVERDUE")

    return count


# ── Get payment stats for dashboard ──────────────────────────────────────────

def get_payment_stats(db: Session, user_id: str) -> dict:
    """
    Aggregate stats for the Payments dashboard page.
    Returns a dict matching the PaymentStats schema.
    """
    from datetime import timedelta

    today     = date.today()
    in_7_days = today + timedelta(days=7)

    records = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.user_id == user_id)
        .all()
    )

    stats = {
        "total_receivable":        0.0,
        "total_receivable_overdue": 0.0,
        "total_received":           0.0,
        "total_payable":            0.0,
        "total_payable_overdue":    0.0,
        "total_paid_out":           0.0,
        "pending_count":  0,
        "overdue_count":  0,
        "paid_count":     0,
        "partial_count":  0,
        "due_next_7_days":        0.0,
        "due_next_7_days_count":   0,
    }

    for r in records:
        s  = r.status
        d  = r.direction
        b  = r.balance
        pa = r.paid_amount

        if s == "PENDING":  stats["pending_count"]  += 1
        if s == "OVERDUE":  stats["overdue_count"]  += 1
        if s == "PAID":     stats["paid_count"]     += 1
        if s == "PARTIAL":  stats["partial_count"]  += 1

        if d == "RECEIVABLE":
            if s in ("PENDING", "PARTIAL", "OVERDUE"):
                stats["total_receivable"] += b
            if s == "OVERDUE":
                stats["total_receivable_overdue"] += b
            if s == "PAID":
                stats["total_received"] += pa

        if d == "PAYABLE":
            if s in ("PENDING", "PARTIAL", "OVERDUE"):
                stats["total_payable"] += b
            if s == "OVERDUE":
                stats["total_payable_overdue"] += b
            if s == "PAID":
                stats["total_paid_out"] += pa

        # Due in next 7 days (exclude already PAID/CANCELLED)
        if (
            r.due_date
            and today <= r.due_date <= in_7_days
            and s not in ("PAID", "CANCELLED")
        ):
            stats["due_next_7_days"]       += b
            stats["due_next_7_days_count"] += 1

    # Round all float values
    for k, v in stats.items():
        if isinstance(v, float):
            stats[k] = round(v, 2)

    return stats