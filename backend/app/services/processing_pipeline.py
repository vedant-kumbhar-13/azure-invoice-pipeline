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
    8. Webhook notifications
"""
import time
import logging

from app.database import SessionLocal
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


def run_invoice_pipeline(invoice_id: str, blob_url: str, filename: str):
    """
    Full processing pipeline — used by both initial upload and reprocess.

    Now includes corrections cache integration:
    - Protects VERIFIED invoices from losing human corrections on reprocess
    - Applies vendor-specific corrections from prior human reviews
    - Merges corrections with OCR data using confidence-aware strategy

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

        # ── STEP 0: Same-invoice protection ──
        # If this invoice was already human-verified, preserve the corrections
        # and re-apply them after OCR (don't silently discard human work)
        prior_human_data = None
        if invoice.status == "VERIFIED" and invoice.ingestion_method == "HUMAN":
            prior_human_data = invoice.data_json
            logger.info(
                f"[pipeline:{invoice_id}] Invoice was human-verified — "
                f"corrections will be preserved and re-applied after OCR"
            )

        # STEP 1: QR Detection (try first — zero AI cost)
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

        # ── STEP 2: Apply corrections from cache ──
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
            vendor_name = _extract_value(mapped_data, "vendor_name")

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
                correction_record.times_applied = (correction_record.times_applied or 0) + 1
                corrections_applied = True
                ingestion_method = f"{ingestion_method}+CACHE"
                logger.info(
                    f"[pipeline:{invoice_id}] Applied vendor corrections from cache "
                    f"(source invoice: {correction_record.source_invoice_id}, "
                    f"times applied: {correction_record.times_applied})"
                )

        # STEP 3: GST Rules validation
        gst_result = run_gst_rules(mapped_data)

        # STEP 4: Confidence scoring and routing
        conf_result = compute_confidence(mapped_data)

        # STEP 5: Save
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        invoice.data_json = mapped_data
        invoice.confidence = conf_result["overall_score"]
        invoice.status = conf_result["status"]
        invoice.source_type = source_type
        invoice.ingestion_method = ingestion_method
        invoice.gst_rules_json = gst_result
        invoice.processing_time_ms = elapsed_ms
        invoice.error_detail = None
        db.commit()
        logger.info(
            f"[pipeline:{invoice_id}] Done. status={invoice.status} "
            f"confidence={invoice.confidence} source={source_type} "
            f"ingestion={ingestion_method} corrections={corrections_applied} time={elapsed_ms}ms"
        )

        # STEP 6: Trigger webhooks on success
        from app.services.webhook_service import trigger_webhooks_for_invoice
        trigger_webhooks_for_invoice(invoice.id, invoice.user_id, "invoice.completed")

        # STEP 7: Check if this was the last invoice in a batch
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
            inv.status = "HUMAN_REQUIRED"
            inv.error_detail = str(e)[:500]
            db.commit()
    finally:
        db.close()
