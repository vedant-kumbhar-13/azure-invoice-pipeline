"""
Azure Blob Storage integration for InvoiceAI.

VUL-01: Returns blob_name (not raw URL) from upload. SAS URLs generated on demand.
BUG-10: Singleton BlobServiceClient via @lru_cache to reuse connection pool.
"""
import uuid
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from app.config import settings

logger = logging.getLogger(__name__)

# ── MIME type map for inline preview ──────────────────────────────────────────
_MIME_TYPES = {
    '.pdf':  'application/pdf',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
}

def _mime_for(filename: str) -> str:
    ext = os.path.splitext(filename)[-1].lower()
    return _MIME_TYPES.get(ext, 'application/octet-stream')

# ── Singleton client (BUG-10) ──────────────────────────────────────────────
_container_ensured = False


@lru_cache(maxsize=1)
def _get_blob_service_client() -> BlobServiceClient:
    """Returns a singleton BlobServiceClient — reuses HTTP connection pool + TLS session."""
    logger.info("[blob] BlobServiceClient created (singleton)")
    return BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    )


def _ensure_container() -> None:
    """Create the container once if it doesn't exist. Idempotent after first call."""
    global _container_ensured
    if _container_ensured:
        return
    try:
        client = _get_blob_service_client()
        container = client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)
        if not container.exists():
            container.create_container()
            logger.info(f"[blob] Created container: {settings.AZURE_STORAGE_CONTAINER_NAME}")
        _container_ensured = True
    except Exception as e:
        error_msg = str(e)
        if "AccountIsDisabled" in error_msg:
            logger.error("[blob] Azure Storage account is DISABLED. Re-enable it in the Azure portal.")
            raise RuntimeError(
                "Azure Storage account is disabled. Please re-enable it in the Azure portal "
                "or update AZURE_STORAGE_CONNECTION_STRING in your .env file."
            ) from e
        logger.error(f"[blob] Container check failed: {e}")
        raise


# ── SAS URL generation (VUL-01) ────────────────────────────────────────────

def get_blob_sas_url(blob_name: str, expiry_hours: int = 1) -> str:
    """
    Generates a time-limited Shared Access Signature URL for a blob.
    Called on-demand by API endpoints — never stored in DB.

    Sets Content-Disposition=inline and the correct Content-Type so the
    browser renders the file in-page instead of downloading it (FIX: auto-download bug).

    Args:
        blob_name: The UUID.ext filename stored in the database (e.g. "abc123.pdf")
        expiry_hours: SAS token validity window (default: 1 hour)

    Returns:
        Full Azure Blob URL with SAS token appended
    """
    client = _get_blob_service_client()
    account_name = client.credential.account_name
    account_key = client.credential.account_key

    content_type = _mime_for(blob_name)

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        # FIX: inline prevents the browser from downloading the file
        content_disposition=f'inline; filename="{blob_name}"',
        content_type=content_type,
    )
    return (
        f"https://{account_name}.blob.core.windows.net/"
        f"{settings.AZURE_STORAGE_CONTAINER_NAME}/{blob_name}?{sas_token}"
    )


# ── Upload (returns blob_name, NOT full URL) ───────────────────────────────

def upload_file_to_blob(file_bytes: bytes, original_filename: str) -> str:
    """
    Uploads a file to Azure Blob Storage and returns the blob_name.

    VUL-01: Returns only the blob_name (e.g. "a1b2c3d4.pdf"), NOT the full URL.
             The caller stores this in invoice.file_url (column name kept to avoid migration).
             SAS URLs are generated on demand via get_blob_sas_url().

    Args:
        file_bytes: Raw file content
        original_filename: User's original filename (used for extension extraction)

    Returns:
        blob_name: UUID-based filename stored in Azure (e.g. "a1b2c3d4.pdf")

    Raises:
        RuntimeError: If Azure Storage account is disabled or unreachable
    """
    _ensure_container()

    file_extension = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
    blob_name = f"{uuid.uuid4()}.{file_extension}"

    try:
        client = _get_blob_service_client()
        container = client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(file_bytes, overwrite=True)
    except Exception as e:
        error_msg = str(e)
        if "AccountIsDisabled" in error_msg:
            logger.error("[blob] Azure Storage account is DISABLED — cannot upload files.")
            raise RuntimeError(
                "Azure Storage account is disabled. Re-enable it in the Azure portal."
            ) from e
        logger.error(f"[blob] Upload failed for {blob_name}: {e}")
        raise

    logger.info(f"[blob] Uploaded {blob_name} ({len(file_bytes)} bytes)")

    # VUL-01: Return blob_name, NOT the full URL
    return blob_name


def delete_blob(blob_name: str) -> None:
    """
    Deletes a blob from Azure Storage.

    BUG-A3: Called before DB deletion to ensure blobs are not left orphaned
    in storage after an invoice is deleted (cost leak + erasure compliance).

    Raises:
        Exception: Propagates storage errors so the caller can decide to log/swallow.
    """
    client = _get_blob_service_client()
    container = client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)
    container.delete_blob(blob_name)
    logger.info(f"[blob] Deleted blob: {blob_name}")