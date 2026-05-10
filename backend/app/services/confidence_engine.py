from typing import Dict, Any

FIELD_WEIGHTS = {
    "total_amount": 3,
    "vendor_gstin": 2,
    "invoice_date": 2,
    "invoice_number": 2,
    "line_items": 2,
    "vendor_name": 1,
    "buyer_name": 1,
    "buyer_gstin": 1,
    "subtotal": 1,
    # Tax fields weighted at 1 — many legitimate Indian invoice types
    # (Bills of Supply, exempt goods, zero-rated exports) have no tax.
    "cgst": 1,
    "sgst": 1,
    "igst": 1,
}

def _get_field_confidence(field_name: str, field_data: Any) -> float:
    """Pure function to extract or infer confidence for a given field."""
    # Special handling for line_items which is a list, not a confidence dict
    if field_name == "line_items":
        if isinstance(field_data, list) and len(field_data) > 0:
            return 1.0
        return 0.0
        
    # Standard field mapped as {"value": ..., "confidence": ...}
    if isinstance(field_data, dict):
        if field_data.get("value") is None:
            return 0.0
        return float(field_data.get("confidence", 0.0))
        
    # If the field is missing or unexpectedly formatted
    if field_data is None:
        return 0.0
        
    # Fallback for unexpected non-dict values that exist
    return 1.0


def compute_confidence(mapped_data: dict) -> dict:
    """
    Computes a weighted confidence score for a mapped invoice and returns
    its routing status based on predefined thresholds.

    Tax field handling: An invoice uses EITHER CGST+SGST (intra-state) OR
    IGST (inter-state), never both. We detect the tax regime and only score
    the applicable fields so that correctly-null fields don't drag the score.
    """
    total_weight = 0
    weighted_sum = 0.0
    field_scores: Dict[str, float] = {}
    
    if not mapped_data:
        # Edge case: empty dictionary
        return {
            "overall_score": 0.0,
            "status": "HUMAN_REQUIRED",
            "field_scores": {}
        }
    
    # Determine which tax fields to include in scoring.
    # Indian GST tax regimes:
    #   Intra-state: CGST + SGST present (even if 0) → skip IGST
    #   Inter-state: IGST present (even if 0) → skip CGST/SGST
    #   No tax data: all null → skip all tax fields (Bill of Supply / exempt)
    igst_data = mapped_data.get("igst")
    cgst_data = mapped_data.get("cgst")
    sgst_data = mapped_data.get("sgst")
    
    igst_val = igst_data.get("value") if isinstance(igst_data, dict) else igst_data
    cgst_val = cgst_data.get("value") if isinstance(cgst_data, dict) else cgst_data
    sgst_val = sgst_data.get("value") if isinstance(sgst_data, dict) else sgst_data
    
    # "Present" = extracted (even if 0). "Absent" = null/not extracted.
    igst_present = igst_val is not None
    csgst_present = cgst_val is not None or sgst_val is not None
    any_tax_present = igst_present or csgst_present
    
    # Fields to skip based on detected tax regime
    skip_fields = set()
    if not any_tax_present:
        # No tax data at all — Bill of Supply, exempt, or Azure didn't extract.
        # Skip all tax fields to avoid penalizing legitimate no-tax invoices.
        skip_fields = {"cgst", "sgst", "igst"}
    elif csgst_present and not igst_present:
        skip_fields = {"igst"}               # Intra-state: CGST+SGST (skip IGST)
    elif igst_present and not csgst_present:
        skip_fields = {"cgst", "sgst"}        # Inter-state: IGST only
    # If both present, score all (unusual — possible error)
    
    for field, weight in FIELD_WEIGHTS.items():
        if field in skip_fields:
            continue
        
        # Only consider fields that exist as keys in the mapped data
        if field in mapped_data:
            data = mapped_data[field]
            confidence = _get_field_confidence(field, data)
            
            field_scores[field] = confidence
            total_weight += weight
            weighted_sum += (confidence * weight)

            
    overall_score = 0.0
    if total_weight > 0:
        overall_score = weighted_sum / total_weight
        
    # Determine the status
    if overall_score >= 0.90:
        status = "AUTO_APPROVED"
    elif overall_score >= 0.60:
        status = "NEEDS_REVIEW"
    else:
        status = "HUMAN_REQUIRED"
        
    return {
        "overall_score": round(overall_score, 4),
        "status": status,
        "field_scores": field_scores
    }
