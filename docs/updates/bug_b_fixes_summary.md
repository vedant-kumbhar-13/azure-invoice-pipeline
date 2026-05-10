# Bug Fix Report — BUG-B1 through BUG-B6

## BUG-B1 · CORS production config — placeholder domain + localhost ✅ Fixed

**Root cause:** `main.py` hardcoded `["https://yourdomain.com", "http://localhost:5173"]` for production.

**Fix — 3 files:**
- `config.py` — new `FRONTEND_URL: str = ""` setting
- `.env.example` — documents `FRONTEND_URL` as required for production
- `main.py` — production CORS branch reads `settings.FRONTEND_URL`; raises `RuntimeError` at startup if it's blank

```python
# Before
origins = ["https://yourdomain.com", "http://localhost:5173"]

# After
if not settings.FRONTEND_URL:
    raise RuntimeError("FRONTEND_URL must be set in .env when ENVIRONMENT != 'dev'.")
origins = [settings.FRONTEND_URL]
```

> [!IMPORTANT]
> Add `FRONTEND_URL=https://your-actual-aws-url.com` to your production `.env` before deploying.

---

## BUG-B2 · Refresh token cookie `secure=False` hardcoded ✅ Fixed

**Root cause:** `auth.py` had `secure=False` with a comment that was not code.

**Fix — `auth.py`:**
```python
# Before
secure=False,  # Set to True in production with HTTPS

# After
_secure_cookie = os.getenv("ENVIRONMENT", "dev") == "production"
response.set_cookie(..., secure=_secure_cookie, ...)
```

The flag is now automatic — setting `ENVIRONMENT=production` in `.env` is the only required action.

---

## BUG-B3 · JWT access token in localStorage — XSS vulnerable ✅ Fixed

**Root cause:** `authStore.ts` persisted the token to `localStorage` and `client.ts` read it from there. Any XSS could steal it.

**Fix — 3 files:**

| File | Change |
|---|---|
| `authStore.ts` | Token stored in Zustand state only. Removed all `localStorage.get/setItem` for token. Added `setToken()` action for the interceptor. `isHydrated` starts `false`. |
| `client.ts` | Request interceptor reads `useAuthStore.getState().token`. Refresh interceptor calls `login()` / `setToken()` (not localStorage). Added startup IIFE that calls `POST /auth/refresh` to recover token from httpOnly cookie on page load. |
| `ProtectedRoute.tsx` | Checks `isHydrated` first — renders `null` during the async silent-refresh window to avoid flash-redirect to `/login`. |

> [!NOTE]
> **Trade-off:** After a hard refresh there's a ~100–300 ms window where the user is briefly "unauthenticated" while the silent refresh completes. The app renders nothing (not a redirect) during this window. This is the standard pattern used by Auth0, Supabase, and similar providers.

> [!WARNING]
> **Clean-up:** Any other file that still reads `localStorage.getItem('invoiceai_token')` will find `null`. Grep for `invoiceai_token` and remove those reads if any exist in other components.

---

## BUG-B4 · Rate limiter claims sliding window but is fixed window ✅ Fixed

**Root cause:** Module docstring and `rate_limited_user` docstring both said "sliding window". The Redis implementation uses `rate:{uid}:{epoch//60}` — a fixed wall-clock minute.

**Fix — `rate_limit.py` (comment-only, no logic change):**

The module docstring and function docstring now accurately state:
- Redis path = **fixed 60-second window** (not sliding)
- In-memory deque path = true sliding window
- Note that ZSET-based sliding window is a future task

> [!TIP]
> To upgrade to a true sliding window: replace the `INCR/EXPIRE` block with a Redis ZSET approach: `ZADD rate:{uid} now now`, `ZREMRANGEBYSCORE rate:{uid} 0 (now-60)`, `ZCARD rate:{uid}` for the count.

---

## BUG-B5 · Background tasks block event loop under concurrent uploads ✅ Fixed

**Root cause:** `background_tasks.add_task()` uses Starlette's shared default executor, which is unbounded and shared with FastAPI internals.

**Fix — 2 files:**

- `main.py` — creates `_pipeline_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="invoice-pipeline")`
- `invoices.py` — both `upload_invoice` and `reprocess_invoice` now call `_pipeline_executor.submit(...)` instead of `background_tasks.add_task(...)`. `BackgroundTasks` parameter removed from both signatures.

```python
# Before
background_tasks.add_task(_run_pipeline_task, ...)

# After
_pipeline_executor.submit(_run_pipeline_task, invoice_id, blob_name, filename)
```

> [!NOTE]
> `max_workers=10` is a conservative default. Tune this based on your instance's vCPU count and expected Azure AI call latency. On a 2-core instance with 10–15 s Azure calls, 10 threads allows ~1 upload/second throughput before queuing begins.

---

## BUG-B6 · No auto-migration on startup ✅ Fixed

**Root cause:** `alembic upgrade head` was not called automatically. A forgotten manual step on any deploy meant the app started with the old schema.

**Fix — `main.py` lifespan handler:**

```python
result = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    capture_output=True, text=True
)
if result.returncode == 0:
    logger.info("[startup] Alembic migrations applied successfully")
else:
    logger.error(f"[startup] Alembic migration FAILED:\n{result.stderr}")
```

- `Base.metadata.create_all()` is **retained** as a safety net for unit tests and SQLite dev environments.
- Alembic is **authoritative** for PostgreSQL production schemas.
- Migration failures are **logged as errors** but do not crash the server (to avoid a circular failure on a broken migration — the operator must intervene).

> [!WARNING]
> If a migration fails, the app will start but may crash on the first DB operation that touches the missing column. Monitor the startup logs in CloudWatch / Azure Monitor.
