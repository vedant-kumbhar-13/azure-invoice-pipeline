"""
Unified invoice processing pipeline for InvoiceAI.

Steps:
    1. Check for prior human corrections (vendor cache + same-invoice protection)
    2. QR detection (zero Azure AI cost)
    3. If no QR: Azure AI OCR
    4. Merge vendor corrections into extracted data
    5. GST rules validation
    6. Confidence scoring + status assignment
    7. DB save
    8. Auto-create PaymentRecord if invoice is approved
    9. [NEW] Run an immediate reminder scan for this user (in addition to
       the 6-hour scheduled scan) so newly-uploaded invoices with near-term
       due dates trigger in-app/email reminders right away instead of
       waiting for the next scheduled run.
    10. Webhook notifications
"""
import time
import logging

from app.database import SessionLocal
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

# Statuses that trigger automatic PaymentRecord creation.
# AUTO_APPROVED = high confidence, no human needed
# VERIFIED = human reviewer confirmed the data
PAYMENT_TRIGGER_STATUSES = {"AUTO_APPROVED", "VERIFIED"}


def run_invoice_pipeline(invoice_id: str, blob_url: str, filename: str):
    """
    Full processing pipeline — used by both initial upload and reprocess.

    Now includes:
    - Corrections cache integration
    - Automatic PaymentRecord creation on approval (Step 8)
    - Immediate reminder scan after payment record creation (Step 9)

    Args:
        invoice_id: UUID of the invoice record
        blob_url: SAS URL for downloading the file (for QR/OCR)
        filename: Original filename (for extension-based QR detection)
    """
    start_time = time.monotonic()
    db = SessionLocal()
    try:
        logger.info(f"[pipeline:{invoice_id}] Processing started")

        from app.services.qr_detector import detect_gst_qr
        from app.services.azure_ai import analyze_invoice
        from app.services.invoice_mapper import map_fields, map_gst_qr_to_canonical
        from app.services.confidence_engine import compute_confidence
        from app.services.gst_rules import run_gst_rules
        from app.services.corrections_cache import (
            get_corrections_for_vendor,
            merge_corrections,
            _extract_value,
        )

        # Load current invoice record
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error(f"[pipeline:{invoice_id}] Invoice record not found in DB")
            return

        # ── STEP 0: Same-invoice protection ──────────────────────────────────
        # If this invoice was already human-verified, preserve the corrections
        # and re-apply them after OCR (don't silently discard human work)
        prior_human_data = None
        if invoice.status == "VERIFIED" and invoice.ingestion_method == "HUMAN":
            prior_human_data = invoice.data_json
            logger.info(
                f"[pipeline:{invoice_id}] Invoice was human-verified — "
                f"corrections will be preserved and re-applied after OCR"
            )

        # ── STEP 1: QR Detection (try first — zero AI cost) ──────────────────
        qr_data = detect_gst_qr(blob_url, filename)

        if qr_data:
            logger.info(f"[pipeline:{invoice_id}] QR code detected — skipping Azure AI")
            mapped_data = map_gst_qr_to_canonical(qr_data)
            source_type = "GST_EINVOICE"
            ingestion_method = "QR"
        else:
            logger.info(f"[pipeline:{invoice_id}] No QR — sending to Azure AI OCR")
            raw_fields = analyze_invoice(blob_url)
            mapped_data = map_fields(raw_fields)
            source_type = "GST_PDF"
            ingestion_method = "OCR"

        # ── STEP 2: Apply corrections from cache ─────────────────────────────
        corrections_applied = False

        # Priority 1: If this specific invoice was human-verified before,
        # use those corrections (strongest signal)
        if prior_human_data:
            mapped_data = merge_corrections(mapped_data, prior_human_data)
            corrections_applied = True
            ingestion_method = "OCR+HUMAN"
            logger.info(f"[pipeline:{invoice_id}] Re-applied prior human corrections")

        # Priority 2: Check vendor corrections cache for similar invoices
        if not corrections_applied:
            vendor_gstin = _extract_value(mapped_data, "vendor_gstin")
            vendor_name  = _extract_value(mapped_data, "vendor_name")

            correction_record = get_corrections_for_vendor(
                db=db,
                user_id=invoice.user_id,
                vendor_gstin=vendor_gstin,
                vendor_name=vendor_name,
            )

            if correction_record:
                mapped_data = merge_corrections(
                    mapped_data,
                    correction_record.corrected_fields,
                )
                correction_record.times_applied = (
                    correction_record.times_applied or 0
                ) + 1
                corrections_applied = True
                ingestion_method = f"{ingestion_method}+CACHE"
                logger.info(
                    f"[pipeline:{invoice_id}] Applied vendor corrections from cache "
                    f"(source invoice: {correction_record.source_invoice_id}, "
                    f"times applied: {correction_record.times_applied})"
                )

        # ── STEP 3: GST Rules validation ──────────────────────────────────────
        gst_result = run_gst_rules(mapped_data)

        # ── STEP 4: Confidence scoring and routing ────────────────────────────
        conf_result = compute_confidence(mapped_data)

        # ── STEP 5: Save invoice ──────────────────────────────────────────────
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        invoice.data_json        = mapped_data
        invoice.confidence       = conf_result["overall_score"]
        invoice.status           = conf_result["status"]
        invoice.source_type      = source_type
        invoice.ingestion_method = ingestion_method
        invoice.gst_rules_json   = gst_result
        invoice.processing_time_ms = elapsed_ms
        invoice.error_detail     = None
        db.commit()

        logger.info(
            f"[pipeline:{invoice_id}] Done. status={invoice.status} "
            f"confidence={invoice.confidence} source={source_type} "
            f"ingestion={ingestion_method} corrections={corrections_applied} "
            f"time={elapsed_ms}ms"
        )

        # ── STEP 6: Auto-create PaymentRecord if invoice is approved ──────────
        # Triggered only for AUTO_APPROVED and VERIFIED — not for NEEDS_REVIEW
        # or HUMAN_REQUIRED since those still need human confirmation.
        # payment_service handles duplicate-guard internally, so reprocessing
        # an already-approved invoice is safe.
        if invoice.status in PAYMENT_TRIGGER_STATUSES:
            try:
                from app.services.payment_service import (
                    create_payment_record_from_invoice,
                )
                payment_record = create_payment_record_from_invoice(
                    db=db,
                    invoice=invoice,
                )
                if payment_record:
                    logger.info(
                        f"[pipeline:{invoice_id}] PaymentRecord created: "
                        f"{payment_record.id} | direction={payment_record.direction} "
                        f"| amount={payment_record.total_amount}"
                    )

                    # ── STEP 7: [NEW] Immediate reminder scan ──────────────────
                    # Runs the same scan logic as the 6-hour scheduled job, but
                    # right now, so a freshly-created PaymentRecord with a
                    # near-term due date (matches days_before_due, is due
                    # today, or is already overdue) fires its in-app/email
                    # reminder immediately instead of waiting for the next
                    # scheduled scan.
                    #
                    # Wrapped in its own try/except: a reminder failure must
                    # never affect invoice processing or payment record
                    # creation, both of which have already succeeded by this
                    # point.
                    try:
                        from app.services.reminder_service import run_reminder_scan
                        summary = run_reminder_scan(db)
                        logger.info(
                            f"[pipeline:{invoice_id}] Immediate reminder scan "
                            f"after upload: {summary}"
                        )
                    except Exception as reminder_exc:
                        logger.error(
                            f"[pipeline:{invoice_id}] Immediate reminder scan "
                            f"failed (non-fatal, scheduled scan will retry): "
                            f"{reminder_exc}",
                            exc_info=True,
                        )

            except Exception as payment_exc:
                # Payment record creation failure must NEVER fail the invoice pipeline.
                # Log the error and continue — the user can manually create/fix the
                # payment record from the Payments page.
                logger.error(
                    f"[pipeline:{invoice_id}] PaymentRecord creation failed "
                    f"(invoice pipeline continues): {payment_exc}",
                    exc_info=True,
                )

        # ── STEP 8: Trigger webhooks on success ───────────────────────────────
        from app.services.webhook_service import trigger_webhooks_for_invoice
        trigger_webhooks_for_invoice(invoice.id, invoice.user_id, "invoice.completed")

        # ── STEP 9: Check if this was the last invoice in a batch ─────────────
        if invoice.batch_id:
            remaining = db.query(Invoice).filter(
                Invoice.batch_id == invoice.batch_id,
                Invoice.status == "processing",
            ).count()
            if remaining == 0:
                trigger_webhooks_for_invoice(
                    invoice.id,
                    invoice.user_id,
                    "batch.completed",
                    extra_data={"batch_id": invoice.batch_id},
                )
                logger.info(f"[pipeline] Batch {invoice.batch_id} fully completed")

    except Exception as e:
        logger.error(f"[pipeline:{invoice_id}] Failed: {e}", exc_info=True)
        db.rollback()
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if inv:
            inv.status       = "HUMAN_REQUIRED"
            inv.error_detail = str(e)[:500]
            db.commit()
    finally:
        db.close()