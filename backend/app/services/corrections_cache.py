"""
Corrections Cache Service — application-level learning from human review.

Since Azure Document Intelligence's prebuilt models cannot be fine-tuned via API,
this service implements a corrections cache that:

1. Stores human-verified corrections keyed by vendor (GSTIN or name)
2. Retrieves and applies prior corrections when processing new invoices
3. Prevents verified invoices from being overwritten on reprocess
4. Merges corrections with OCR data using a confidence-based overlay strategy

Architecture:
    Human Review → save_correction() → VendorCorrection table
    New Invoice  → get_corrections()  → merge_corrections() → improved data
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.vendor_correction import VendorCorrection

logger = logging.getLogger(__name__)


# Fields that can be learned from corrections
CORRECTABLE_FIELDS = {
    "vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin",
    "invoice_number", "invoice_date", "due_date",
    "subtotal", "total_amount", "cgst", "sgst", "igst",
}

# Fields that are vendor-specific (same across invoices from same vendor)
# vs invoice-specific (unique to each invoice)
VENDOR_STABLE_FIELDS = {"vendor_name", "vendor_gstin"}
INVOICE_SPECIFIC_FIELDS = {
    "invoice_number", "invoice_date", "due_date",
    "subtotal", "total_amount", "cgst", "sgst", "igst",
    "buyer_name", "buyer_gstin",
}


def _normalize_vendor_key(gstin: Optional[str], vendor_name: Optional[str]) -> tuple:
    """
    Returns (vendor_key, key_type) for cache lookups.
    Prefers GSTIN (globally unique). Falls back to normalized vendor name.
    """
    if gstin and len(str(gstin).strip()) >= 15:
        return str(gstin).strip().upper(), "gstin"

    if vendor_name and len(str(vendor_name).strip()) >= 2:
        # Normalize: lowercase, strip extra whitespace
        normalized = " ".join(str(vendor_name).strip().lower().split())
        return normalized, "name"

    return None, None


def save_correction(
    db: Session,
    invoice_id: str,
    user_id: str,
    before_data: dict,
    after_data: dict,
) -> Optional[VendorCorrection]:
    """
    Saves human-reviewed corrections to the vendor corrections cache.

    Only stores fields that were actually changed (diff between before/after).
    Identifies the vendor from the corrected data (after_data) since the human
    may have also corrected the vendor GSTIN.

    Args:
        db: Database session
        invoice_id: The invoice that was corrected
        user_id: The reviewer who made the correction
        before_data: Original OCR-extracted data
        after_data: Human-corrected data

    Returns:
        VendorCorrection record if saved, None if nothing to cache
    """
    if not after_data:
        return None

    # Extract vendor key from corrected data
    vendor_gstin = _extract_value(after_data, "vendor_gstin")
    vendor_name = _extract_value(after_data, "vendor_name")
    vendor_key, key_type = _normalize_vendor_key(vendor_gstin, vendor_name)

    if not vendor_key:
        logger.warning(f"[corrections] Cannot cache correction for invoice {invoice_id}: no vendor identifier")
        return None

    # Build corrected fields dict (only fields that were changed or added)
    corrected_fields = {}
    for field in CORRECTABLE_FIELDS:
        after_val = _extract_value(after_data, field)
        before_val = _extract_value(before_data, field) if before_data else None

        if after_val is not None and after_val != before_val:
            # Store in canonical format with confidence=1.0 (human-verified)
            if isinstance(after_data.get(field), dict):
                corrected_fields[field] = after_data[field].copy()
                corrected_fields[field]["confidence"] = 1.0
            else:
                corrected_fields[field] = {"value": after_val, "confidence": 1.0}

    if not corrected_fields:
        logger.info(f"[corrections] No field changes detected for invoice {invoice_id}, skipping cache")
        return None

    # Upsert: update existing correction for this vendor+user, or create new
    existing = db.query(VendorCorrection).filter(
        VendorCorrection.vendor_key == vendor_key,
        VendorCorrection.user_id == user_id,
    ).first()

    if existing:
        # Merge new corrections into existing record
        merged = existing.corrected_fields or {}
        merged.update(corrected_fields)
        existing.corrected_fields = merged
        existing.source_invoice_id = invoice_id
        db.flush()
        logger.info(
            f"[corrections] Updated vendor correction for {key_type}={vendor_key} "
            f"({len(corrected_fields)} fields updated)"
        )
        return existing
    else:
        correction = VendorCorrection(
            vendor_key=vendor_key,
            vendor_key_type=key_type,
            user_id=user_id,
            source_invoice_id=invoice_id,
            corrected_fields=corrected_fields,
        )
        db.add(correction)
        db.flush()
        logger.info(
            f"[corrections] Saved new vendor correction for {key_type}={vendor_key} "
            f"({len(corrected_fields)} fields cached)"
        )
        return correction


def get_corrections_for_vendor(
    db: Session,
    user_id: str,
    vendor_gstin: Optional[str] = None,
    vendor_name: Optional[str] = None,
) -> Optional[dict]:
    """
    Retrieves the most recent human corrections for a vendor.

    Looks up by GSTIN first (exact match), then by normalized vendor name.
    Returns the corrected_fields dict or None if no prior corrections exist.
    """
    # Try GSTIN lookup first (most reliable)
    if vendor_gstin and len(str(vendor_gstin).strip()) >= 15:
        key = str(vendor_gstin).strip().upper()
        correction = db.query(VendorCorrection).filter(
            VendorCorrection.vendor_key == key,
            VendorCorrection.user_id == user_id,
        ).order_by(VendorCorrection.updated_at.desc()).first()

        if correction:
            logger.info(f"[corrections] Found vendor corrections by GSTIN: {key}")
            return correction

    # Fallback to vendor name
    if vendor_name and len(str(vendor_name).strip()) >= 2:
        normalized = " ".join(str(vendor_name).strip().lower().split())
        correction = db.query(VendorCorrection).filter(
            VendorCorrection.vendor_key == normalized,
            VendorCorrection.user_id == user_id,
        ).order_by(VendorCorrection.updated_at.desc()).first()

        if correction:
            logger.info(f"[corrections] Found vendor corrections by name: {normalized}")
            return correction

    return None


def merge_corrections(ocr_data: dict, corrections: dict) -> dict:
    """
    Merges human-verified corrections into OCR-extracted data.

    Strategy:
    - Vendor-stable fields (vendor_name, vendor_gstin): ALWAYS apply from cache
      because these are the same across all invoices from the same vendor.
    - Invoice-specific fields (amounts, dates, etc.): Only apply from cache if
      the OCR result is null/empty or has low confidence (<0.6). This avoids
      overwriting correct OCR results for new invoices with amounts from old ones.

    Args:
        ocr_data: Fresh OCR-extracted data
        corrections: Human-verified corrections from cache

    Returns:
        Merged data dict with corrections applied
    """
    if not corrections:
        return ocr_data

    merged = {}
    for key, value in ocr_data.items():
        merged[key] = value

    applied_count = 0

    for field, corrected_value in corrections.items():
        if field not in CORRECTABLE_FIELDS:
            continue

        if field in VENDOR_STABLE_FIELDS:
            # Always apply vendor-stable corrections
            merged[field] = corrected_value
            applied_count += 1
        elif field in INVOICE_SPECIFIC_FIELDS:
            # Only apply if OCR result is weak
            ocr_field = ocr_data.get(field, {})
            ocr_val = ocr_field.get("value") if isinstance(ocr_field, dict) else ocr_field
            ocr_conf = ocr_field.get("confidence", 0.0) if isinstance(ocr_field, dict) else 0.0

            if ocr_val is None or ocr_conf < 0.6:
                merged[field] = corrected_value
                applied_count += 1

    if applied_count > 0:
        logger.info(f"[corrections] Applied {applied_count} vendor corrections to OCR data")

    return merged


def _extract_value(data: dict, field: str):
    """Safely extract value from canonical {value, confidence} or raw format."""
    if not data:
        return None
    field_data = data.get(field)
    if isinstance(field_data, dict):
        return field_data.get("value")
    return field_data
