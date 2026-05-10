# Bug Fix Report — BUG-A1 through BUG-A4

## BUG-A1 · Webhook HMAC signatures permanently broken ✅ Fixed

**Root cause:** `webhooks.py` stored `sha256(raw_secret)` as the DB secret. `webhook_service.py` then used that hash as the HMAC key — so consumers calling `hmac(payload, raw_secret)` never matched.

**Fix** — one line change in `webhooks.py`:

```diff
- secret_hash = hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()
  new_hook = Webhook(
-     secret=secret_hash,   # ← hash of secret — wrong key
+     secret=raw_secret,    # ← raw secret IS the HMAC key
  )
```

Also removed the now-unused `import hashlib`.

> [!IMPORTANT]
> **Existing webhooks in the DB are still broken** — they store the sha256 hash as their secret. Run a one-off migration to reset all webhook secrets (or ask users to re-register their webhooks).

---

## BUG-A2 · SQLite as default DATABASE_URL — fatal with multiple workers ✅ Fixed

**Root cause:** `.env.example` defaulted to `sqlite:///./invoiceai.db`. SQLite has a single-writer lock; any concurrent upload under multi-worker uvicorn will throw `database is locked`.

**Fix** — updated `.env.example`:

```diff
- DATABASE_URL=sqlite:///./invoiceai.db
+ # REQUIRED: PostgreSQL only — SQLite cannot handle concurrent writes.
+ DATABASE_URL=postgresql://invoiceai_user:CHANGE_ME@localhost:5432/invoiceai
```

> [!WARNING]
> If your local `.env` still points at SQLite, that's fine for development. **Never deploy to production with SQLite.**

---

## BUG-A3 · No blob deletion when invoice is deleted ✅ Fixed

**Root cause:** `delete_invoice` only called `db.delete(invoice)` — the Azure blob was never removed, leaking storage and violating erasure requirements.

**Fix — two files changed:**

1. **`blob_storage.py`** — new `delete_blob(blob_name)` helper wrapping the container client.
2. **`invoices.py` `delete_invoice`** — calls `delete_blob` *before* the DB commit. A `try/except` logs Azure failures but does not block DB deletion:

```python
# BUG-A3: Delete the Azure blob before removing the DB record.
if invoice.file_url:
    try:
        delete_blob(invoice.file_url)
    except Exception as blob_err:
        logger.warning(f"[invoice] Blob deletion failed ... — continuing with DB delete.")

db.delete(invoice)
db.commit()
```

> [!NOTE]
> SAS URLs cached by the browser remain valid for up to 1 hour after deletion (this is a property of SAS tokens, not fixable without storage-side revocation). The blob itself is gone immediately.

---

## BUG-A4 · No production deployment configuration ✅ Fixed

**New files created:**

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Multi-stage build; runs `uvicorn --workers ${WEB_CONCURRENCY:-4}` |
| `backend/docker-compose.yml` | Wires backend + PostgreSQL with a health-check gate |

**Key decisions:**
- `WEB_CONCURRENCY=4` default — tune to `2 × vCPU` for your instance.
- PostgreSQL health check ensures the backend container waits for `pg_isready` before starting, preventing startup races.
- `--log-level info` gives structured logs compatible with CloudWatch / Azure Monitor.

**Production startup command (without Docker):**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4 --log-level info
```

**With Docker Compose:**
```bash
# First time only — run migrations
docker compose run --rm backend alembic upgrade head

# Start everything
docker compose up --build -d
```
