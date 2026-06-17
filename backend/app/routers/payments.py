"""
Payments router for InvoiceAI.

Endpoints:
    GET    /payments/                  → list, filterable by direction/status/due range
    GET    /payments/stats             → dashboard summary cards
    GET    /payments/overdue           → overdue records only
    GET    /payments/{id}              → detail incl. transactions
    POST   /payments/manual            → create standalone payment entry
    PATCH  /payments/{id}              → update direction/status/dates/notes
    POST   /payments/{id}/transactions → add a payment transaction (partial/full)
    GET    /payments/export/xlsx       → export payment records to Excel
"""
import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.payment import PaymentRecord, PaymentTransaction
from app.middleware.auth import get_current_user
from app.schemas.payment import (
    PaymentRecordCreate,
    PaymentRecordUpdate,
    PaymentRecordResponse,
    PaymentRecordListResponse,
    PaymentTransactionCreate,
    PaymentTransactionResponse,
    PaymentStats,
)
from app.services.payment_service import (
    create_manual_payment_record,
    add_transaction,
    get_payment_stats,
)

logger = logging.getLogger("invoiceai.payments")

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── List with filters ─────────────────────────────────────────────────────────

@router.get("/", response_model=PaymentRecordListResponse)
def list_payments(
    direction: str = Query(None, description="RECEIVABLE | PAYABLE"),
    status_filter: str = Query(None, alias="status", description="PENDING | PARTIAL | PAID | OVERDUE | CANCELLED"),
    due_before: date = Query(None, description="Only records due on or before this date"),
    due_after: date = Query(None, description="Only records due on or after this date"),
    search: str = Query(None, description="Search counterparty name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PaymentRecord)
    query = query.filter(PaymentRecord.user_id == current_user.id)

    if direction:
        direction = direction.upper()
        if direction not in ("RECEIVABLE", "PAYABLE"):
            raise HTTPException(status_code=400, detail="direction must be RECEIVABLE or PAYABLE")
        query = query.filter(PaymentRecord.direction == direction)

    if status_filter:
        status_filter = status_filter.upper()
        valid_statuses = {"PENDING", "PARTIAL", "PAID", "OVERDUE", "CANCELLED"}
        if status_filter not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")
        query = query.filter(PaymentRecord.status == status_filter)

    if due_before:
        query = query.filter(PaymentRecord.due_date <= due_before)

    if due_after:
        query = query.filter(PaymentRecord.due_date >= due_after)

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(PaymentRecord.counterparty_name.ilike(search_term))

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)

    records = (
        query
        .order_by(PaymentRecord.due_date.asc().nullslast(), PaymentRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Attach transactions for each record (lightweight — usually few per record)
    items = []
    for r in records:
        txns = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.payment_record_id == r.id)
            .order_by(PaymentTransaction.transaction_date.desc())
            .all()
        )
        record_dict = PaymentRecordResponse.model_validate(r).model_dump()
        record_dict["transactions"] = [
            PaymentTransactionResponse.model_validate(t) for t in txns
        ]
        items.append(record_dict)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ── Stats (dashboard) ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=PaymentStats)
def payment_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_payment_stats(db, current_user.id)


# ── Overdue list ────────────────────────────────────────────────────────────────

@router.get("/overdue")
def overdue_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = (
        db.query(PaymentRecord)
        .filter(
            PaymentRecord.user_id == current_user.id,
            PaymentRecord.status == "OVERDUE",
        )
        .order_by(PaymentRecord.due_date.asc())
        .all()
    )

    return {
        "items": [PaymentRecordResponse.model_validate(r) for r in records],
        "total": len(records),
    }


# ── Detail (with transactions) ───────────────────────────────────────────────

@router.get("/{payment_id}", response_model=PaymentRecordResponse)
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.user_id == current_user.id,
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    txns = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.payment_record_id == record.id)
        .order_by(PaymentTransaction.transaction_date.desc())
        .all()
    )

    result = PaymentRecordResponse.model_validate(record).model_dump()
    result["transactions"] = [PaymentTransactionResponse.model_validate(t) for t in txns]
    return result


# ── Create manual standalone entry ───────────────────────────────────────────

@router.post("/manual", response_model=PaymentRecordResponse, status_code=status.HTTP_201_CREATED)
def create_manual_payment(
    payload: PaymentRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = create_manual_payment_record(
        db=db,
        user_id=current_user.id,
        direction=payload.direction.value,
        total_amount=payload.total_amount,
        due_date=payload.due_date,
        counterparty_name=payload.counterparty_name,
        counterparty_gstin=payload.counterparty_gstin,
        counterparty_email=payload.counterparty_email,
        manual_description=payload.manual_description,
        manual_invoice_ref=payload.manual_invoice_ref,
        notes=payload.notes,
    )

    result = PaymentRecordResponse.model_validate(record).model_dump()
    result["transactions"] = []
    return result


# ── Update record (direction/status/dates/notes) ──────────────────────────────

@router.patch("/{payment_id}", response_model=PaymentRecordResponse)
def update_payment(
    payment_id: str,
    payload: PaymentRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.user_id == current_user.id,
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(value, "value"):  # Enum -> str
            value = value.value
        setattr(record, field, value)

    # If status manually set to PAID without transactions, sync balance/paid_amount
    if update_data.get("status") == "PAID":
        record.paid_amount = record.total_amount
        record.balance = 0.0
        if not record.paid_date:
            record.paid_date = date.today()

    # If status manually set to CANCELLED, leave amounts as-is for audit trail

    db.commit()
    db.refresh(record)

    txns = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.payment_record_id == record.id)
        .order_by(PaymentTransaction.transaction_date.desc())
        .all()
    )
    result = PaymentRecordResponse.model_validate(record).model_dump()
    result["transactions"] = [PaymentTransactionResponse.model_validate(t) for t in txns]
    return result


# ── Add a transaction (partial or full payment) ───────────────────────────────

@router.post(
    "/{payment_id}/transactions",
    response_model=PaymentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_payment_transaction(
    payment_id: str,
    payload: PaymentTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        txn = add_transaction(
            db=db,
            payment_record_id=payment_id,
            user_id=current_user.id,
            amount=payload.amount,
            payment_mode=payload.payment_mode.value,
            transaction_date=payload.transaction_date,
            reference_no=payload.reference_no,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return txn


# ── Delete a transaction (correction) ─────────────────────────────────────────

@router.delete("/{payment_id}/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_transaction(
    payment_id: str,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a transaction and recalculate the parent record's balance/status.
    Useful for correcting data-entry mistakes.
    """
    record = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.user_id == current_user.id,
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.id == transaction_id,
        PaymentTransaction.payment_record_id == payment_id,
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    db.delete(txn)
    db.flush()

    # Recalculate
    remaining = (
        db.query(PaymentTransaction.amount)
        .filter(PaymentTransaction.payment_record_id == payment_id)
        .all()
    )
    new_paid = round(sum(r.amount for r in remaining), 2)
    new_balance = round(record.total_amount - new_paid, 2)
    new_balance = max(0.0, new_balance)

    record.paid_amount = new_paid
    record.balance = new_balance

    if new_balance == 0.0 and new_paid > 0:
        record.status = "PAID"
    elif new_paid > 0:
        record.status = "PARTIAL"
    else:
        # Back to PENDING (or OVERDUE if past due — let next reminder scan handle that)
        record.status = "PENDING"
        record.paid_date = None

    db.commit()


# ── Export to Excel ─────────────────────────────────────────────────────────────

@router.get("/export/xlsx")
def export_payments_xlsx(
    direction: str = Query(None),
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import openpyxl
    from openpyxl.styles import Font

    query = db.query(PaymentRecord).filter(PaymentRecord.user_id == current_user.id)

    if direction:
        query = query.filter(PaymentRecord.direction == direction.upper())
    if status_filter:
        query = query.filter(PaymentRecord.status == status_filter.upper())

    records = query.order_by(PaymentRecord.due_date.asc().nullslast()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Payments"

    headers = [
        "ID", "Direction", "Status", "Counterparty", "Counterparty GSTIN",
        "Total Amount", "Paid Amount", "Balance", "Due Date", "Paid Date",
        "Is Manual", "Notes", "Created At",
    ]
    ws.append(headers)

    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font
    ws.freeze_panes = "A2"

    for r in records:
        ws.append([
            r.id,
            r.direction,
            r.status,
            r.counterparty_name or "",
            r.counterparty_gstin or "",
            r.total_amount,
            r.paid_amount,
            r.balance,
            r.due_date.isoformat() if r.due_date else "",
            r.paid_date.isoformat() if r.paid_date else "",
            "Yes" if r.is_manual else "No",
            r.notes or "",
            r.created_at.isoformat() if r.created_at else "",
        ])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        ws.column_dimensions[column].width = min(max_length + 2, 50)

    b = io.BytesIO()
    wb.save(b)
    b.seek(0)

    return StreamingResponse(
        b,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="payments.xlsx"'},
    )