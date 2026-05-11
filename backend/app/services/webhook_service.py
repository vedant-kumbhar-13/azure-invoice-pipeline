"""
Webhook delivery service for InvoiceAI.

VUL-02: SSRF protection with DNS resolution validation.
BUG-07: Bounded thread pool for webhook delivery.
BUG-13: Single DB session per delivery to prevent connection pool exhaustion.
"""
import hmac
import hashlib
import json
import logging
import ipaddress
import socket
import requests
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from app.database import SessionLocal
from app.models.webhook import Webhook, WebhookDelivery
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

# ── BUG-07 fix: bounded thread pool instead of unbounded Thread().start() ──
_webhook_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="webhook")

# ── VUL-02: SSRF protection ────────────────────────────────────────────────
BLOCKED_HOSTNAMES = {'localhost', '127.0.0.1', '0.0.0.0', '::1', '169.254.169.254'}

# VUL-02: Blocked IP ranges — covers private, link-local, Azure metadata, shared address space
BLOCKED_PREFIXES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),    # Azure metadata / link-local
    ipaddress.ip_network("100.64.0.0/10"),     # Shared address space (CGN)
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 private
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def _is_safe_webhook_url(url: str) -> bool:
    """
    Validate a webhook URL to prevent SSRF attacks against internal services.

    VUL-02: Now performs DNS resolution to catch DNS rebinding attacks where
    attacker.com resolves to 169.254.169.254 (Azure metadata endpoint).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('https', 'http'):
            return False
        host = parsed.hostname or ''
        if not host:
            return False

        # Step 1: Block known dangerous hostnames
        if host in BLOCKED_HOSTNAMES:
            return False

        # Step 2: Block raw private IPs
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
            for prefix in BLOCKED_PREFIXES:
                if ip in prefix:
                    return False
        except ValueError:
            pass  # It's a hostname, not a raw IP — DNS resolution below handles it

        # Step 3 (VUL-02): DNS resolution — catch rebinding attacks
        # Set a 3-second timeout to prevent slow DNS attacks
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(3)
            resolved = socket.getaddrinfo(host, None)
            for res in resolved:
                ip_str = res[4][0]
                try:
                    ip_obj = ipaddress.ip_address(ip_str)
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                        logger.warning(
                            f"[webhook] SSRF blocked: {host} resolves to private IP {ip_str}"
                        )
                        return False
                    for prefix in BLOCKED_PREFIXES:
                        if ip_obj in prefix:
                            logger.warning(
                                f"[webhook] SSRF blocked: {host} resolves to blocked range {ip_str}"
                            )
                            return False
                except ValueError:
                    continue  # Skip unrecognized address formats
        except socket.gaierror:
            logger.warning(f"[webhook] DNS resolution failed for {host} — treating as unsafe")
            return False  # Cannot resolve = unsafe
        finally:
            socket.setdefaulttimeout(old_timeout)

        return True
    except Exception:
        return False


def compute_hmac_signature(payload_bytes: bytes, secret: str) -> str:
    """Returns hex HMAC-SHA256 signature for the payload."""
    return hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()


def deliver_webhook_sync(delivery_id: str, extra_data: dict | None = None):
    """
    Synchronous delivery function (called from thread pool).
    """
    max_attempts = 3
    retry_delay = 5  # seconds

    # BUG-13: Single DB session for all retry attempts — prevents connection pool exhaustion
    db = SessionLocal()
    try:
        for attempt in range(max_attempts):
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            if not delivery:
                logger.error(f"[webhook] Delivery {delivery_id} not found.")
                return

            if delivery.status in ["delivered", "failed"] and delivery.attempts >= max_attempts:
                return  # Already fully processed or failed

            webhook = db.query(Webhook).filter(Webhook.id == delivery.webhook_id).first()

            if not webhook:
                delivery.status = "failed"
                delivery.response_body = "Webhook record missing."
                delivery.attempts += 1
                delivery.last_attempt_at = datetime.now(timezone.utc)
                db.commit()
                return

            # VUL-02: Validate URL before making the outgoing request (includes DNS check)
            if not _is_safe_webhook_url(webhook.url):
                delivery.status = "failed"
                delivery.response_body = "Webhook URL blocked by SSRF policy."
                delivery.attempts += 1
                delivery.last_attempt_at = datetime.now(timezone.utc)
                db.commit()
                logger.warning(f"[webhook] Blocked SSRF attempt to {webhook.url}")
                return

            if delivery.invoice_id:
                invoice = db.query(Invoice).filter(Invoice.id == delivery.invoice_id).first()
                if not invoice:
                    delivery.status = "failed"
                    delivery.response_body = "Invoice record missing."
                    delivery.attempts += 1
                    delivery.last_attempt_at = datetime.now(timezone.utc)
                    db.commit()
                    return

                payload_dict = {
                    "invoice_id": invoice.id,
                    "status": invoice.status,
                    "source_type": invoice.source_type,
                    "ingestion_method": invoice.ingestion_method,
                    "data": invoice.data_json,
                    "confidence": invoice.confidence
                }
                if extra_data:
                    payload_dict.update(extra_data)
            else:
                payload_dict = {"event": "ping", "message": "Test webhook payload"}

            payload_bytes = json.dumps(payload_dict).encode('utf-8')
            signature = compute_hmac_signature(payload_bytes, webhook.secret)

            headers = {
                "Content-Type": "application/json",
                "X-InvoiceAI-Signature": f"sha256={signature}"
            }

            delivery.attempts += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)
            db.commit()

            try:
                response = requests.post(webhook.url, data=payload_bytes, headers=headers, timeout=10)
                delivery.http_status_code = response.status_code
                delivery.response_body = response.text[:500] if response.text else None

                if 200 <= response.status_code < 300:
                    delivery.status = "delivered"
                    db.commit()
                    logger.info(f"[webhook] Delivered successfully to {webhook.url}")
                    return
                else:
                    logger.warning(f"[webhook] Delivery failed with HTTP {response.status_code} on attempt {delivery.attempts}")

            except requests.exceptions.RequestException as e:
                delivery.response_body = str(e)[:500]
                logger.warning(f"[webhook] Network error on attempt {delivery.attempts}: {e}")

            if delivery.attempts >= max_attempts:
                delivery.status = "failed"
            else:
                delivery.status = "pending"

            db.commit()

            if delivery.status == "pending":
                time.sleep(retry_delay)
                continue
            else:
                return

    except Exception as e:
        logger.error(f"[webhook] Critical error processing delivery {delivery_id}: {e}", exc_info=True)
    finally:
        db.close()


def deliver_webhook(delivery_id: str):
    deliver_webhook_sync(delivery_id)


def trigger_webhooks_for_invoice(invoice_id: str, user_id: str, event: str, extra_data: dict | None = None):
    """
    Called after invoice processing completes.
    Uses bounded thread pool (BUG-07 fix) instead of unbounded Thread().start().

    Args:
        extra_data: Optional dict merged into the webhook payload (e.g. batch_id).
    """
    db = SessionLocal()
    try:
        webhooks = db.query(Webhook).filter(
            Webhook.user_id == user_id,
            Webhook.is_active == True
        ).all()

        for hook in webhooks:
            events_list = hook.events if isinstance(hook.events, list) else []
            if event in events_list or "*" in events_list:
                delivery = WebhookDelivery(
                    webhook_id=hook.id,
                    invoice_id=invoice_id,
                    status="pending"
                )
                db.add(delivery)
                db.commit()
                db.refresh(delivery)

                # BUG-07: Use bounded thread pool instead of Thread().start()
                _webhook_executor.submit(deliver_webhook_sync, delivery.id, extra_data)

    except Exception as e:
        logger.error(f"[webhook] Error triggering webhooks for invoice {invoice_id}: {e}")
    finally:
        db.close()

