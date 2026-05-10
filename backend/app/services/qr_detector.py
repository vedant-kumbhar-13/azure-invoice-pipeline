"""
QR code detection for GST e-Invoices.

VUL-03: Accepts URL strings (downloads first 5MB) to avoid holding file_bytes in memory.
BUG-18: Lowered Pillow pixel limit to 20M and catches DecompressionBombError.
BUG-22 / WIN-01: 3-layer decoder stack, all Windows-native (no Linux DLLs required):
          Layer 1 — zxing-cpp        (self-contained Windows wheel; handles QR/DataMatrix/PDF417)
          Layer 2 — OpenCV WeChat    (ML-based; Windows-native; high accuracy on blurry QR codes)
          Layer 3 — OpenCV standard  (built-in; handles clean/simple QR codes)
        Each layer logs its own result so failures are observable.

SECURITY: No credentials, endpoints, or internal paths are logged.
          Filename fragments are truncated to 50 chars before logging.
          Downloaded content is capped at _MAX_DOWNLOAD_BYTES.
"""
import io
import json
import base64
import logging
import binascii
from typing import Optional, Union

import requests as http_requests

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024  # 5 MB hard cap


# ─────────────────────────────────────────────────────────────────────────────
# QR Payload Parsers
# ─────────────────────────────────────────────────────────────────────────────

def parse_jwt_payload(payload_str: str) -> Optional[dict]:
    """Decodes the payload segment of a GST e-Invoice JWT and parses it as JSON.

    SECURITY: Only accesses payload (index 1) — ignores header/signature.
    """
    try:
        padding_needed = len(payload_str) % 4
        if padding_needed:
            payload_str += "=" * (4 - padding_needed)
        decoded_bytes = base64.urlsafe_b64decode(payload_str)
        decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
        return json.loads(decoded_str)
    except (ValueError, binascii.Error, json.JSONDecodeError):
        return None


def extract_qr_data(qr_text: str) -> Optional[dict]:
    """Attempts to parse QR text as a JWT or plain JSON payload.

    Supports:
      - Signed GST e-Invoice tokens (JWT: header.payload.signature)
      - Plain JSON objects embedded in QR
    Returns None for any other format (UPI, URLs, plain text) which are
    payment QRs and do not contain invoice field data.
    """
    if not qr_text:
        return None
    qr_text = qr_text.strip()

    # Attempt JWT decode — GST e-Invoice IRN tokens are JWTs
    parts = qr_text.split(".")
    if len(parts) >= 2:
        data = parse_jwt_payload(parts[1])
        if data:
            return data

    # Attempt plain JSON
    try:
        return json.loads(qr_text)
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Secure File Downloader
# ─────────────────────────────────────────────────────────────────────────────

def _download_file_bytes(url: str) -> Optional[bytes]:
    """VUL-03: Stream-download a file from a pre-signed SAS URL, capped at 5 MB.

    SECURITY: URL is NOT logged (may contain SAS token).
              Only the error type is logged on failure.
    """
    try:
        resp = http_requests.get(url, stream=True, timeout=15)
        resp.raise_for_status()
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.append(chunk)
            total += len(chunk)
            if total >= _MAX_DOWNLOAD_BYTES:
                logger.info("[qr] Download cap reached — truncating at 5 MB")
                break
        return b"".join(chunks)
    except Exception as e:
        # Log only the exception type — do NOT log the URL (contains SAS token)
        logger.warning(f"[qr] Failed to download file: {type(e).__name__}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3-Layer QR Decoder
# ─────────────────────────────────────────────────────────────────────────────

def _decode_with_zxingcpp(gray_np) -> list[str]:
    """Layer 1: zxing-cpp decoder (Windows-native, no external DLL required).
    Self-contained Windows wheel; supports QR, DataMatrix, PDF417 and more.
    Replaces pyzbar which required the Linux libzbar.dll.
    """
    try:
        import zxingcpp
        import numpy as np
        results = zxingcpp.read_barcodes(gray_np)
        return [r.text for r in results if r.text]
    except ImportError:
        logger.debug("[qr] zxing-cpp not available — skipping Layer 1")
        return []
    except Exception as e:
        logger.debug(f"[qr] zxing-cpp decode error: {type(e).__name__}")
        return []


def _decode_with_wechat(gray_np) -> list[str]:
    """Layer 2: OpenCV WeChat QR decoder (ML-based).
    Bundled with opencv-contrib-python — no external DLL required on Windows.
    Handles blurry, rotated, and small QR codes better than pyzbar.
    """
    try:
        import cv2
        detector = cv2.wechat_qrcode_WeChatQRCode()
        data_list, _ = detector.detectAndDecode(gray_np)
        return [d for d in data_list if d]
    except AttributeError:
        # wechat_qrcode not available — user has opencv-python, not opencv-contrib
        logger.debug("[qr] OpenCV WeChat module not available (need opencv-contrib-python) — skipping Layer 2")
        return []
    except Exception as e:
        logger.debug(f"[qr] OpenCV WeChat error: {type(e).__name__}")
        return []


def _decode_with_opencv_standard(gray_np) -> list[str]:
    """Layer 3: OpenCV built-in QR detector.
    Available in all opencv-python builds — always present as last resort.
    Works well on clean, high-contrast QR codes.
    """
    try:
        import cv2
        qr_decoder = cv2.QRCodeDetector()
        retval, decoded_info, _, _ = qr_decoder.detectAndDecodeMulti(gray_np)
        if retval and decoded_info:
            return [d for d in decoded_info if d]
        return []
    except Exception as e:
        logger.debug(f"[qr] OpenCV standard decoder error: {type(e).__name__}")
        return []


def _try_all_decoders(gray_np) -> Optional[str]:
    """Runs all 3 decoder layers in order and returns first successful decode."""
    # Layer 1: zxing-cpp (Windows-native, no external DLL)
    results = _decode_with_zxingcpp(gray_np)
    if results:
        logger.info("[qr] Decoded via Layer 1 (zxing-cpp)")
        return results[0]

    # Layer 2: OpenCV WeChat (ML-based, Windows-safe)
    results = _decode_with_wechat(gray_np)
    if results:
        logger.info("[qr] Decoded via Layer 2 (OpenCV WeChat)")
        return results[0]

    # Layer 3: OpenCV standard (last resort)
    results = _decode_with_opencv_standard(gray_np)
    if results:
        logger.info("[qr] Decoded via Layer 3 (OpenCV standard)")
        return results[0]

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Image Preprocessors for Better Detection
# ─────────────────────────────────────────────────────────────────────────────

def _preprocess_variants(gray_np):
    """Yields multiple preprocessed versions of a grayscale image.
    Improves detection on low-quality scans and compressed images.
    """
    import cv2
    yield gray_np                                                       # Raw grayscale

    _, otsu = cv2.threshold(gray_np, 0, 255,                           # Otsu binarize
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield otsu

    yield cv2.adaptiveThreshold(gray_np, 255,                          # Adaptive threshold
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)

    yield cv2.GaussianBlur(gray_np, (3, 3), 0)                         # Denoise


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def detect_gst_qr(file_input: Union[bytes, str], filename: str) -> Optional[dict]:
    """Scans a document for a GST e-Invoice QR code.

    Pipeline:
        0. Extension pre-check — skip unsupported formats before downloading (BUG-C5)
        1. Download file (if URL) — capped at 1 MB for PDFs, 5 MB for images (BUG-C5)
        2. Render to image(s) — first page of PDF, or the image itself
        3. For each page, try 3 decoder layers x 4 preprocessing variants
        4. Parse decoded text as JWT or JSON (GST e-Invoice formats)

    Args:
        file_input: Raw file bytes OR a pre-signed SAS URL string.
                    URL is never logged (VUL-03 / security).
        filename:   Original filename used only for extension detection.
                    Truncated to 50 chars in any log messages (BUG-18).

    Returns:
        Parsed QR payload dict, or None if no valid GST QR found.

    Security:
        - SAS URLs are never logged
        - Filenames are truncated before logging
        - Pillow pixel limit enforced (BUG-18)
        - DecompressionBombError caught and quarantined
    """
    safe_name = filename[:50]  # BUG-18: Never log full path
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # ── BUG-C5: Step 0 — Extension pre-check ─────────────────────────────────
    # Reject formats that can never contain a GST QR code before any download.
    # Saves full Azure egress cost on every audio/video/archive/doc upload.
    _SUPPORTED_EXTS = {"pdf", "jpg", "jpeg", "png", "tiff", "bmp", "gif", "webp"}
    if ext not in _SUPPORTED_EXTS:
        logger.info(f"[qr] Skipping QR scan — unsupported extension '{ext}': {safe_name}")
        return None

    # ── BUG-C5: Per-format download cap ──────────────────────────────────────
    # GST e-Invoice QR codes always appear on the first page.
    # PDFs: 1 MB is sufficient for the first page at any normal DPI.
    # Images: keep the original 5 MB cap (full image needed for scan).
    _pdf_cap = 1 * 1024 * 1024   # 1 MB
    _img_cap = _MAX_DOWNLOAD_BYTES  # 5 MB

    try:
        from PIL import Image, ImageFile
        import cv2
        import numpy as np

        # BUG-18: Enforce pixel limit to prevent decompression bomb attacks
        Image.MAX_IMAGE_PIXELS = 20_000_000
        ImageFile.LOAD_TRUNCATED_IMAGES = True

        # ── Step 1: Resolve input to bytes ───────────────────────────────────
        if isinstance(file_input, str):
            cap = _pdf_cap if ext == "pdf" else _img_cap
            logger.info(f"[qr] Downloading file for QR detection (cap={cap // 1024} KB)")

            def _capped_download(url: str, download_cap: int) -> Optional[bytes]:
                try:
                    resp = http_requests.get(url, stream=True, timeout=15)
                    resp.raise_for_status()
                    chunks, total = [], 0
                    for chunk in resp.iter_content(chunk_size=65536):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= download_cap:
                            logger.info(f"[qr] Download cap reached — truncating at {download_cap // 1024} KB")
                            break
                    return b"".join(chunks)
                except Exception as dl_err:
                    logger.warning(f"[qr] Failed to download file: {type(dl_err).__name__}")
                    return None

            file_bytes = _capped_download(file_input, cap)
            if file_bytes is None:
                return None
        else:
            file_bytes = file_input

        # ── Step 2: Render document to images ────────────────────────────────
        images: list[Image.Image] = []

        if ext == "pdf":
            try:
                import fitz
                with fitz.open("pdf", file_bytes) as doc:
                    if doc.page_count == 0:
                        logger.warning(f"[qr] PDF has no pages: {safe_name}")
                        return None
                    # Scan first page, last page, and page 2 (if they exist)
                    pages_to_scan = list(dict.fromkeys([
                        0,
                        min(1, doc.page_count - 1),
                        doc.page_count - 1,
                    ]))
                    for page_num in pages_to_scan:
                        page = doc.load_page(page_num)
                        mat = fitz.Matrix(3, 3)  # 3× zoom for small QR codes
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        images.append(img)
            except Exception as e:
                logger.warning(f"[qr] Failed to render PDF '{safe_name}': {type(e).__name__}")
                return None

        elif ext in {"jpg", "jpeg", "png", "tiff", "bmp", "gif", "webp"}:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                img.load()
                if img.mode != "RGB":
                    img = img.convert("RGB")
                images.append(img)
            except Image.DecompressionBombError:
                logger.warning(f"[qr] Decompression bomb in image: {safe_name}")
                return None
            except Exception as e:
                logger.warning(f"[qr] Failed to load image '{safe_name}': {type(e).__name__}")
                return None

        else:
            logger.warning(f"[qr] Unsupported file format: {safe_name}")
            return None

        # ── Step 3: Decode QR from each rendered page ─────────────────────────
        for img in images:
            try:
                img_np = np.array(img)
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

                for variant in _preprocess_variants(gray):
                    raw_text = _try_all_decoders(variant)
                    if raw_text:
                        parsed = extract_qr_data(raw_text)
                        if parsed:
                            logger.info("[qr] GST QR code successfully detected and parsed")
                            return parsed
            except Image.DecompressionBombError:
                logger.warning(f"[qr] Decompression bomb during scan: {safe_name}")
                return None
            except Exception as e:
                logger.warning(f"[qr] Error scanning page from '{safe_name}': {type(e).__name__}")
            finally:
                img.close()

        logger.info(f"[qr] No valid GST QR code found in: {safe_name}")
        return None

    except ImportError as e:
        logger.error(f"[qr] Missing required library for QR detection: {e}")
        return None
    except Exception as e:
        logger.exception(f"[qr] Unexpected error during QR detection: {type(e).__name__}")
        return None
