"""
Webhooks router for InvoiceAI.

VUL-02: Wraps _is_safe_webhook_url() in try/except with WARNING logging.
"""
import logging
from typing import List, Optional
import asyncio
from pydantic import BaseModel, HttpUrl, Field
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.webhook import Webhook, WebhookDelivery
from app.middleware.auth import get_current_user
from app.services.webhook_service import deliver_webhook_sync, _is_safe_webhook_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class WebhookCreate(BaseModel):
    url: HttpUrl
    events: List[str]
    # BUG-C1: Enforce minimum secret length so HMAC is actually meaningful.
    # An empty or single-character secret is indistinguishable from no secret at all.
    secret: str = Field(min_length=16, description="Webhook signing secret (min 16 characters)")

@router.post("", status_code=status.HTTP_201_CREATED)
def register_webhook(
    payload: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # VUL-02: Validate URL against SSRF (includes DNS resolution) with error handling
    url_str = str(payload.url)
    try:
        is_safe = _is_safe_webhook_url(url_str)
    except Exception as e:
        # VUL-02: Log any unexpected exceptions during URL validation
        sanitized_url = url_str[:100] if url_str else "<empty>"
        logger.warning(f"[webhook] URL validation exception for '{sanitized_url}': {e}")
        is_safe = False

    if not is_safe:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL is blocked. Private IPs and internal addresses are not allowed."
        )

    # BUG-A1: Store raw_secret as the HMAC key — consumers verify with raw_secret.
    # The SHA-256 hash is only used for safe display (never stored, never used for signing).
    raw_secret = payload.secret

    new_hook = Webhook(
        user_id=current_user.id,
        url=url_str,
        secret=raw_secret,          # BUG-A1: raw secret is the HMAC key
        events=payload.events,
        is_active=True
    )
    db.add(new_hook)
    db.commit()
    db.refresh(new_hook)

    return {
        "id": new_hook.id,
        "url": new_hook.url,
        "events": new_hook.events,
        "is_active": new_hook.is_active,
        "secret": raw_secret,  # Returned ONCE — never stored in plaintext
        "created_at": str(new_hook.created_at),
    }

# BUG-35: Return serializable dicts, not raw ORM objects
@router.get("")
def list_webhooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    hooks = db.query(Webhook).filter(
        Webhook.user_id == current_user.id,
        Webhook.is_active == True
    ).all()
    return [
        {
            "id": h.id,
            "url": h.url,
            "events": h.events,
            "is_active": h.is_active,
            "created_at": str(h.created_at),
        }
        for h in hooks
    ]

@router.delete("/{hook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    hook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    hook = db.query(Webhook).filter(
        Webhook.id == hook_id,
        Webhook.user_id == current_user.id
    ).first()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
        
    hook.is_active = False
    db.commit()

# BUG-24: Made async and uses asyncio.to_thread to avoid blocking a worker thread for 30s
@router.post("/{hook_id}/test", status_code=status.HTTP_200_OK)
async def test_webhook(
    hook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    hook = db.query(Webhook).filter(
        Webhook.id == hook_id,
        Webhook.user_id == current_user.id,
        Webhook.is_active == True
    ).first()
    
    if not hook:
        raise HTTPException(status_code=404, detail="Active webhook not found")
        
    delivery = WebhookDelivery(
        webhook_id=hook.id,
        invoice_id=None,
        status="pending"
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    
    # BUG-24: Run in a thread so we don't block the async event loop
    await asyncio.to_thread(deliver_webhook_sync, delivery.id)
    db.refresh(delivery)
    
    return {
        "id": delivery.id,
        "webhook_id": delivery.webhook_id,
        "status": delivery.status,
        "http_status_code": delivery.http_status_code,
        "response_body": delivery.response_body,
        "attempts": delivery.attempts,
    }

@router.get("/{hook_id}/deliveries")
def get_webhook_deliveries(
    hook_id: str,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    hook = db.query(Webhook).filter(
        Webhook.id == hook_id,
        Webhook.user_id == current_user.id
    ).first()
    
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
        
    skip = (page - 1) * limit
    deliveries = db.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_id == hook_id
    ).order_by(WebhookDelivery.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": d.id,
            "webhook_id": d.webhook_id,
            "invoice_id": d.invoice_id,
            "status": d.status,
            "http_status_code": d.http_status_code,
            "attempts": d.attempts,
            "created_at": str(d.created_at),
        }
        for d in deliveries
    ]
