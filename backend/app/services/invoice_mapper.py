"""
Invoice field mapper — Azure Document Intelligence raw fields → canonical API contract.

Properly parses Azure's TaxDetails array for CGST/SGST/IGST extraction,
with fallback to total tax splitting when individual breakdowns aren't available.
"""
import re
import logging

logger = logging.getLogger(__name__)


def _get_field(fields: dict, key: str, value_type: str = "value_string") -> dict:
    """Safely extracts field values and confidence from Azure's raw data object."""
    field = fields.get(key)
    if not field:
        return {"value": None, "confidence": 0.0}

    try:
        confidence = getattr(field, "confidence", 0.0) or 0.0

        if value_type == "value_currency":
            currency_obj = getattr(field, "value_currency", None)
            val = getattr(currency_obj, "amount", None) if currency_obj else None
        elif value_type == "value_date":
            val = getattr(field, "value_date", None)
            if val:
                val = str(val)
        elif value_type == "value_number":
            val = getattr(field, "value_number", None)
        else:
            val = getattr(field, value_type, None)

        return {"value": val, "confidence": round(float(confidence), 4)}
    except Exception:
        return {"value": None, "confidence": 0.0}


def _extract_tax_details(raw_fields: dict) -> dict:
    """
    Parses Azure's TaxDetails array to extract CGST, SGST, and IGST.

    Azure's prebuilt-invoice model returns tax breakdowns inside a TaxDetails
    array. Each item can have:
      - Amount (currency) — the tax amount
      - Rate (string/number) — the tax rate percentage
      - TaxType (string) — free-text description like "CGST", "SGST", "IGST"

    We match tax types using regex patterns to handle variations like
    "CGST @9%", "Central GST", "State GST", "Integrated GST", etc.
    """
    result = {
        "cgst": {"value": None, "confidence": 0.0},
        "sgst": {"value": None, "confidence": 0.0},
        "igst": {"value": None, "confidence": 0.0},
        "found": False,
    }

    tax_details_field = raw_fields.get("TaxDetails")
    if not tax_details_field:
        return result

    # TaxDetails is an array field
    tax_array = getattr(tax_details_field, "value_array", None) or []
    if not tax_array:
        return result

    # Regex patterns to identify tax types from free-text descriptions
    cgst_pattern = re.compile(r"\b(cgst|central\s*gst|c\.gst)\b", re.IGNORECASE)
    sgst_pattern = re.compile(r"\b(sgst|state\s*gst|s\.gst|utgst|ut\s*gst)\b", re.IGNORECASE)
    igst_pattern = re.compile(r"\b(igst|integrated\s*gst|i\.gst)\b", re.IGNORECASE)

    for item in tax_array:
        item_obj = getattr(item, "value_object", None) or {}
        if not item_obj:
            continue

        # Extract the amount
        amount_field = item_obj.get("Amount")
        if not amount_field:
            continue

        confidence = getattr(amount_field, "confidence", 0.0) or 0.0
        currency_obj = getattr(amount_field, "value_currency", None)
        amount_val = getattr(currency_obj, "amount", None) if currency_obj else None

        if amount_val is None:
            continue

        # Try to identify tax type from the TaxType or Description field
        tax_type_str = ""
        for type_key in ["TaxType", "Description", "Tax"]:
            type_field = item_obj.get(type_key)
            if type_field:
                type_val = getattr(type_field, "value_string", None) or ""
                if type_val:
                    tax_type_str = type_val
                    break

        if not tax_type_str:
            # Some Azure responses put it in content
            tax_type_str = getattr(item, "content", "") or ""

        # Match against patterns
        if cgst_pattern.search(tax_type_str):
            result["cgst"] = {"value": round(float(amount_val), 2), "confidence": round(float(confidence), 4)}
            result["found"] = True
        elif sgst_pattern.search(tax_type_str):
            result["sgst"] = {"value": round(float(amount_val), 2), "confidence": round(float(confidence), 4)}
            result["found"] = True
        elif igst_pattern.search(tax_type_str):
            result["igst"] = {"value": round(float(amount_val), 2), "confidence": round(float(confidence), 4)}
            result["found"] = True
        else:
            logger.debug(f"[tax_details] Unrecognized tax type: '{tax_type_str}' with amount {amount_val}")

    return result


def _split_gst(total_tax_val, vendor_gstin: str, buyer_gstin: str):
    """
    Splits total tax into CGST/SGST (intra-state) or IGST (inter-state).
    Uses first 2 digits of GSTINs as state codes.
    Returns (cgst, sgst, igst) as floats.
    """
    if total_tax_val is None:
        return None, None, None

    amount = float(total_tax_val)
    half = round(amount / 2, 2)

    # Determine if inter-state from GSTIN state codes
    vendor_state = (vendor_gstin or "")[:2]
    buyer_state = (buyer_gstin or "")[:2]

    if vendor_state and buyer_state and vendor_state != buyer_state:
        # Inter-state → IGST
        return None, None, round(amount, 2)
    else:
        # Intra-state → CGST + SGST
        return half, half, None


def map_fields(raw_fields: dict) -> dict:
    """
    Maps Azure's prebuilt-invoice fields to our canonical API contract.

    Tax extraction priority:
    1. Parse TaxDetails array (Azure's native tax breakdown)
    2. Fallback: derive from TotalTax using GSTIN state codes (lower confidence)
    """
    if not raw_fields:
        return {}

    vendor_gstin_data = _get_field(raw_fields, "VendorTaxId", "value_string")
    buyer_gstin_data = _get_field(raw_fields, "CustomerTaxId", "value_string")
    total_tax_data = _get_field(raw_fields, "TotalTax", "value_currency")

    vendor_gstin_val = vendor_gstin_data.get("value")
    buyer_gstin_val = buyer_gstin_data.get("value")
    total_tax_val = total_tax_data.get("value")
    tax_conf = total_tax_data.get("confidence", 0.0)

    # ── Step 1: Try parsing Azure's TaxDetails array ──
    tax_details = _extract_tax_details(raw_fields)

    if tax_details["found"]:
        # Direct extraction from TaxDetails array — high confidence
        cgst = tax_details["cgst"]
        sgst = tax_details["sgst"]
        igst = tax_details["igst"]
        tax_method = "direct"
        logger.info(
            f"[mapper] Tax extracted from TaxDetails: "
            f"CGST={cgst['value']} SGST={sgst['value']} IGST={igst['value']}"
        )
    elif total_tax_val is not None:
        # ── Step 2: Derive from TotalTax ──
        if float(total_tax_val) == 0:
            # TotalTax is explicitly 0 — Bill of Supply / exempt.
            # Set CGST=0, SGST=0 with HIGH confidence (Azure confirmed zero tax).
            cgst = {"value": 0.0, "confidence": round(tax_conf * 0.9, 4)}
            sgst = {"value": 0.0, "confidence": round(tax_conf * 0.9, 4)}
            igst = {"value": None, "confidence": 0.0}
            tax_method = "derived_zero"
            logger.info("[mapper] TotalTax=0 — Bill of Supply / exempt supply detected")
        else:
            # Non-zero TotalTax — split based on GSTIN state codes
            cgst_val, sgst_val, igst_val = _split_gst(total_tax_val, vendor_gstin_val, buyer_gstin_val)
            cgst = {"value": cgst_val, "confidence": round(tax_conf * 0.6, 4)}
            sgst = {"value": sgst_val, "confidence": round(tax_conf * 0.6, 4)}
            igst = {"value": igst_val, "confidence": round(tax_conf * 0.6, 4)}
            tax_method = "derived"
            logger.info(
                f"[mapper] Tax derived from TotalTax ({total_tax_val}): "
                f"CGST={cgst_val} SGST={sgst_val} IGST={igst_val}"
            )
    else:
        # ── Step 3: TotalTax not extracted at all ──
        # Try multiple heuristics to determine if this is a zero-tax invoice.
        subtotal_data = _get_field(raw_fields, "SubTotal", "value_currency")
        total_data = _get_field(raw_fields, "InvoiceTotal", "value_currency")
        subtotal_val = subtotal_data.get("value")
        total_val = total_data.get("value")

        # Heuristic A: SubTotal ≈ InvoiceTotal → no tax applied
        if (subtotal_val is not None and total_val is not None
                and abs(float(subtotal_val) - float(total_val)) < 1.0):
            cgst = {"value": 0.0, "confidence": 0.7}
            sgst = {"value": 0.0, "confidence": 0.7}
            igst = {"value": None, "confidence": 0.0}
            tax_method = "inferred_zero"
            logger.info(
                f"[mapper] Subtotal ({subtotal_val}) ≈ Total ({total_val}) — "
                f"inferred zero tax (Bill of Supply)"
            )

        # Heuristic B: Sum of line item amounts ≈ InvoiceTotal → no tax
        elif total_val is not None:
            items_field = raw_fields.get("Items")
            line_item_sum = 0.0
            has_line_items = False
            if items_field:
                items_array = getattr(items_field, "value_array", []) or []
                for item in items_array:
                    item_dict = getattr(item, "value_object", {}) or {}
                    amt_field = item_dict.get("Amount")
                    if amt_field:
                        currency = getattr(amt_field, "value_currency", None)
                        amt = getattr(currency, "amount", None) if currency else None
                        if amt is not None:
                            line_item_sum += float(amt)
                            has_line_items = True

            if has_line_items and abs(line_item_sum - float(total_val)) < 2.0:
                # Line items sum to approximately the total → no tax added
                cgst = {"value": 0.0, "confidence": 0.65}
                sgst = {"value": 0.0, "confidence": 0.65}
                igst = {"value": None, "confidence": 0.0}
                tax_method = "inferred_zero_lineitems"
                logger.info(
                    f"[mapper] Line items sum ({line_item_sum}) ≈ Total ({total_val}) — "
                    f"inferred zero tax from line items"
                )
            else:
                # Genuinely missing tax data — no way to determine
                cgst = {"value": None, "confidence": 0.0}
                sgst = {"value": None, "confidence": 0.0}
                igst = {"value": None, "confidence": 0.0}
                tax_method = "missing"
                logger.info("[mapper] No tax data available — all taxes set to null")
        else:
            # No total, no subtotal, no TotalTax — nothing to work with
            cgst = {"value": None, "confidence": 0.0}
            sgst = {"value": None, "confidence": 0.0}
            igst = {"value": None, "confidence": 0.0}
            tax_method = "missing"
            logger.info("[mapper] No tax or total data available — all taxes set to null")

    data = {
        "vendor_name": _get_field(raw_fields, "VendorName", "value_string"),
        "vendor_gstin": vendor_gstin_data,
        "invoice_number": _get_field(raw_fields, "InvoiceId", "value_string"),
        "invoice_date": _get_field(raw_fields, "InvoiceDate", "value_date"),
        "due_date": _get_field(raw_fields, "DueDate", "value_date"),
        "buyer_name": _get_field(raw_fields, "CustomerName", "value_string"),
        "buyer_gstin": buyer_gstin_data,
        "subtotal": _get_field(raw_fields, "SubTotal", "value_currency"),
        "total_amount": _get_field(raw_fields, "InvoiceTotal", "value_currency"),
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "tax_method": tax_method,
        "line_items": [],
    }

    items_field = raw_fields.get("Items")
    if items_field:
        items_array = getattr(items_field, "value_array", []) or []
        for item in items_array:
            item_dict = getattr(item, "value_object", {}) or {}
            if not item_dict:
                continue
            data["line_items"].append({
                "description": _get_field(item_dict, "Description", "value_string").get("value"),
                "quantity": _get_field(item_dict, "Quantity", "value_number").get("value"),
                "rate": _get_field(item_dict, "UnitPrice", "value_currency").get("value"),
                "amount": _get_field(item_dict, "Amount", "value_currency").get("value"),
                "hsn_code": _get_field(item_dict, "ProductCode", "value_string").get("value"),
            })

    return data

def map_gst_qr_to_canonical(qr_data: dict) -> dict:
    """Takes a raw GST QR JSON payload and formats it to the canonical API structure."""
    if not qr_data:
        return {}

    def _val(keys, default=None):
        for k in keys:
            if k in qr_data:
                return qr_data[k]
        return default

    # Date usually DD/MM/YYYY. We map to YYYY-MM-DD.
    raw_date = _val(["DocDt", "InvDt", "Date"])
    formatted_date = None
    if raw_date and isinstance(raw_date, str):
        if "/" in raw_date:
            parts = raw_date.split("/")
            if len(parts) == 3:
                formatted_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        elif "-" in raw_date:
            parts = raw_date.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                formatted_date = raw_date
            elif len(parts) == 3:
                formatted_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

    def _make(val):
        return {"value": val, "confidence": 1.0} if val is not None else {"value": None, "confidence": 0.0}

    # BUG-10: Parse ItemList from GST e-Invoice QR codes
    item_list = qr_data.get("ItemList", [])
    line_items = []
    for item in (item_list if isinstance(item_list, list) else []):
        line_items.append({
            "description": item.get("PrdDesc") or item.get("Nm"),
            "quantity": item.get("Qty"),
            "rate": item.get("UnitPrice") or item.get("UntPrice"),
            "amount": item.get("TotAmt") or item.get("AssAmt"),
            "hsn_code": item.get("HsnCd"),
        })

    return {
        "vendor_name": _make(_val(["SellerNm", "SellerName", "TrdNm"])),
        "vendor_gstin": _make(_val(["SellerGstin", "Gstin", "SupGstin"])),
        "invoice_number": _make(_val(["DocNo", "InvNo"])),
        "invoice_date": _make(formatted_date),
        "due_date": _make(None),
        "buyer_name": _make(_val(["BuyNm", "BuyerName", "LglNm"])),
        "buyer_gstin": _make(_val(["BuyerGstin", "BuyGstin"])),
        "subtotal": _make(_val(["AssVal", "TotAssVal"])),
        "total_amount": _make(_val(["TotInvVal", "InvVal", "TotVal"])),
        "cgst": _make(_val(["CgstVal", "TotCgst"])),
        "sgst": _make(_val(["SgstVal", "TotSgst"])),
        "igst": _make(_val(["IgstVal", "TotIgst"])),
        "tax_method": "direct",  # QR data is always direct
        "line_items": line_items
    }