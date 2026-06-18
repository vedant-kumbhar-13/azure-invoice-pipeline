<div align="center">

<img src="https://img.shields.io/badge/Azure_Invoice_Pipeline-Enterprise%20GST%20Platform-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" alt="Azure Invoice Pipeline"/>

# ⚡ Azure Invoice Pipeline — Enterprise GST Processing

**Automate GST invoice ingestion · QR decoding · OCR extraction · Compliance validation · Payment tracking · Reminders**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react)](https://react.dev/)
[![Azure AI](https://img.shields.io/badge/Azure-Document%20Intelligence-0078D4?style=flat-square&logo=microsoftazure)](https://azure.microsoft.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript)](https://typescriptlang.org/)
[![Neon](https://img.shields.io/badge/Neon-PostgreSQL-3ECF8E?style=flat-square&logo=postgresql)](https://neon.tech/)
[![Deploy](https://img.shields.io/badge/Deploy-Render%20%2B%20Vercel-46E3B7?style=flat-square)](https://render.com/)

</div>

---

## 📌 What is Azure Invoice Pipeline?

**Azure Invoice Pipeline** is a production-ready, full-stack platform built for Indian GST compliance. It eliminates manual invoice data entry by combining:

- 🔍 **3-Layer QR Decoder** — reads GST e-Invoice JWT QR codes instantly (Windows-native, no Linux DLLs)
- 🤖 **Azure Document Intelligence** — state-of-the-art OCR fallback for non-QR invoices
- ✅ **GST Compliance Engine** — validates GSTIN, tax math, line items, and place of supply
- 📊 **Confidence Scoring** — per-field confidence with visual indicators
- 👤 **Human Review Workflow** — side-by-side PDF viewer + editable form for flagged invoices
- 💰 **Payment Tracking** — auto-creates payment records from approved invoices with direction detection (Payable/Receivable)
- 🔔 **Smart Reminders** — in-app + email reminders for upcoming due dates (configurable schedule)
- 🔒 **Security-First Architecture** — SAS-tokenised blob access, JWT auth with httpOnly refresh, SSRF protection

---

## 🖥️ Platform Walkthrough

### 1. 🔐 Login Page
> Secure JWT-based authentication. Users register with email + password (bcrypt hashed). Tokens auto-refresh in the background.

![Login Page](docs/screenshots/login_page.png)

**Features:**
- Email/password login with validation
- Secure JWT access token (60 min) + refresh token (7 days, httpOnly cookie)
- Password strength enforcement (8+ chars, uppercase, digit, special character)
- Register new account with organisation details
- Auto-redirect after successful login

---

### 2. 📊 Dashboard — Overview
> Real-time command centre showing processing stats, method breakdown (QR vs OCR), average confidence ring, and the 10 most recent invoices.

![Dashboard](docs/screenshots/dashbourd.png)

**Features:**
- **Total Processed** · **Auto-Approved** · **Awaiting Review** · **Failed** stat cards
- QR Detection vs AI OCR processing method breakdown with animated progress bars
- Average confidence score ring (colour-coded: green ≥90% · amber ≥60% · red <60%)
- Recent invoices table with vendor, invoice number, amount, status, and date
- Click any row to jump directly to its detail page

---

### 3. 📤 Upload Invoice
> Drag-and-drop invoice uploader with file preview, **single or bulk mode**, and one-click processing trigger.

![Upload Invoice](docs/screenshots/upload_invoice.png)

**Features:**
- **Mode toggle**: "Single Invoice" or "Bulk Upload (up to 20 files)" — switch with one click
- Drag-and-drop or click-to-browse file selection (PDF, JPEG, PNG — max 20 MB per file)
- **Bulk mode**: file list with per-file remove, total size, and "Add More Files" button
- **Non-blocking upload**: HTTP 202 returns instantly — blob upload + pipeline run in background thread pool
- Idempotency key prevents accidental duplicate submissions (single mode)
- Magic bytes validation prevents disguised file uploads

---

### 4. ⚙️ Processing in Progress
> After upload, the background pipeline runs asynchronously. The UI polls every 2–3 seconds and displays a live status indicator.

![Processing](docs/screenshots/proccesig.png)

**Features:**
- Live status badge: `PROCESSING` → `AUTO_APPROVED` / `NEEDS_REVIEW` / `HUMAN_REQUIRED`
- 10-minute polling timeout with automatic escalation to `HUMAN_REQUIRED`
- Backend cleanup task marks stuck invoices after 15 minutes
- Processing time displayed on completion (e.g. `18.7s`)
- **Batch monitoring page**: progress bar, stats, and live-updating table for bulk uploads
- Auto-creates PaymentRecord for approved invoices with direction detection

---

### 5. 📋 Invoice History
> Paginated, filterable table of all processed invoices with an inline slide-out preview panel.

![Invoice History](docs/screenshots/INVOICE_HISTORY.png)

**Features:**
- Server-side filtering by status: All · Processing · Auto-Approved · Needs Review · Failed
- Full-text search across vendor name, invoice number, GSTIN, and filename
- Confidence bar per row (green · amber · red colour coding)
- **👁 Eye icon** → opens the slide-out `InvoicePreviewPanel` without navigating away
- **↗ External link icon** → navigates to the full Invoice Detail page
- **🗑 Trash icon** → delete with confirmation dialog (also deletes Azure blob)
- 20 items per page with Prev/Next pagination

---

### 6. 🔍 Invoice Preview Panel
> Click any row in the Invoice History to slide open this panel — view the original document and all extracted data side-by-side without leaving the page.

![Human Review](docs/screenshots/human%20review.png)

**Features:**
- **Left pane (55%)** — PDF rendered inline via Azure SAS URL (no download triggered)
- **Right pane (45%)** — all extracted fields with per-field confidence bars
- Animated confidence ring showing overall score
- GST compliance flags shown in red if any violations detected
- Close with ✕, Escape key, or click outside

---

### 7. 🛡️ Review Queue
> Centralised queue for all invoices flagged for human attention, sorted by urgency.

![Review Queue](docs/screenshots/REVIEW_PAGE.png)

**Features:**
- Priority-sorted queue: `HUMAN_REQUIRED` (red) → `NEEDS_REVIEW` (amber)
- Confidence score and GST compliance flags shown per card
- Three review actions: ✅ Approve As-Is · 💾 Save Edits · ❌ Reject
- Diff-only audit logging for edited reviews
- Vendor corrections cache — future invoices from the same vendor auto-apply corrections

---

### 8. 💰 Payment Tracking *(NEW)*
> Auto-creates payment records from approved invoices with intelligent direction detection.

**Features:**
- **Auto-detection**: compares invoice GSTIN against org profile to determine Payable vs Receivable
- Payment dashboard with stat cards (Total Outstanding · Overdue · Paid)
- Record partial and full payments with transaction history
- Filter by direction (Payable/Receivable), status (Pending/Partial/Paid/Overdue)
- Manual payment creation for invoices not in the system

---

### 9. 🔔 Smart Reminders *(NEW)*
> Never miss a payment deadline with configurable in-app and email reminders.

**Features:**
- Background scheduler runs every 6 hours (configurable) to scan for due payments
- Immediate scan on invoice upload for near-term due dates
- In-app notification bell with unread count
- Email reminders via configurable SMTP (Gmail, Outlook, or custom)
- Per-user customisable reminder schedule (e.g., 7, 3, 1 days before due date)

---

### 10. ⚙️ Settings Page
> Manage your account, API keys, organisation profile, and webhook integrations.

![Settings](docs/screenshots/SETTINGS.png)

**Features:**
- Organisation profile (name, GSTIN, address, email) for payment direction auto-detection
- API key management (generate, view, revoke)
- Webhook endpoint configuration with event filtering and delivery logs
- Reminder settings — customise notification schedule and email preferences

---

### 11. 📊 Excel Export
> Download all processed invoice data as a structured Excel file for accounting and ERP workflows.

![Excel Export](docs/screenshots/EXEL_DATA.png)

**Features:**
- **CSV**: Streaming export with batch processing (handles unlimited records)
- **XLSX**: Formatted export with bold headers, auto-column widths, and 10,000 row cap
- All fields exported: Vendor, GSTIN, Invoice #, Date, Amounts, Confidence, Status
- Compatible with Microsoft Excel, Google Sheets, and accounting tools

---

## 🔄 Processing Pipeline

```
User uploads PDF / JPEG / PNG (single or up to 20 files in bulk)
            │
            ▼
   POST /invoices/upload (single)  ─── or ─── POST /invoices/upload/bulk (batch)
   ├─ Validate file type, size, magic bytes
   ├─ Idempotency check (SHA-256 key dedup — single mode)
   ├─ Create Invoice DB record (status="processing")
   └─ Return HTTP 202 immediately (< 1 second)
            │
    ┌───────┴───────┐  (background thread pool — max 10 workers)
    │               │
    ▼               ▼
   Upload to        Upload to
   Azure Blob       Azure Blob (per file in batch)
            │
            ▼
   ┌─────────────────────────────┐
   │   3-Layer QR Decoder        │
   │  Layer 1: zxing-cpp         │ ──► GST JWT found?
   │  Layer 2: OpenCV WeChat ML  │         │
   │  Layer 3: OpenCV Standard   │         │ YES → Parse JWT
   └─────────────────────────────┘         │         confidence = 1.0
            │ NO QR found                  │
            ▼                              │
   Azure Document Intelligence OCR         │
   └─ Extract: Vendor · GSTIN ·            │
      Buyer · Invoice# · Line Items ─────►─┘
      · CGST · SGST · IGST · Total
            │
            ▼
   Vendor Corrections Cache
   └─ Apply prior human corrections for same vendor
            │
            ▼
   GST Compliance Engine
   ├─ GSTIN format + Luhn checksum
   ├─ Tax math: CGST+SGST vs IGST (place of supply)
   ├─ Line-item subtotal cross-check
   └─ Invoice date range (configurable, default 3 years)
            │
            ├─ confidence ≥ 0.90 ──► AUTO_APPROVED ✅
            ├─ confidence 0.60–0.90 ─► NEEDS_REVIEW ⚠️
            └─ confidence < 0.60 ───► HUMAN_REQUIRED 🔴
            │
            ▼
   Auto-create PaymentRecord (if approved)
   └─ Direction: PAYABLE / RECEIVABLE / UNKNOWN
            │
            ▼
   Immediate Reminder Scan (for near-term due dates)
            │
            ▼
   Webhook Notifications
   ├─ invoice.completed  (per invoice)
   └─ batch.completed    (when all invoices in batch finish)
```

---

## 🛠️ Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend API** | FastAPI | 0.135 |
| **ORM** | SQLAlchemy | 2.0 |
| **DB Migrations** | Alembic | 1.18 |
| **Database** | SQLite (dev) / Neon PostgreSQL (prod) | 16 |
| **Frontend** | React + TypeScript + Vite | 19 / 5.9 / 8 |
| **State Management** | TanStack Query + Zustand | v5 |
| **Styling** | Tailwind CSS | v3 |
| **Cloud — OCR** | Azure Document Intelligence | 1.0.2 SDK |
| **Cloud — Storage** | Azure Blob Storage | 12.28 SDK |
| **QR Layer 1** | zxing-cpp (Windows-native) | 2.2.0 |
| **QR Layer 2** | OpenCV WeChat QR (ML-based) | 4.9.0 |
| **QR Layer 3** | OpenCV Standard QR | 4.9.0 |
| **PDF Rendering** | PyMuPDF (fitz) | 1.24 |
| **Auth** | python-jose (JWT) + Passlib (bcrypt) | — |
| **Scheduler** | APScheduler | 3.10 |
| **Rate Limiting** | Redis (prod) / In-memory (dev) | 5.0 |
| **Export** | openpyxl (XLSX) + csv (streaming) | 3.1 |
| **Deployment** | Render (backend) + Vercel (frontend) | — |

---

## ⚙️ Quick Start — Local Setup

### Prerequisites
- Python 3.11+ · Node.js 18+ · Git
- Azure account with **Document Intelligence** and **Blob Storage** resources

### 1. Clone
```bash
git clone https://github.com/vedant-kumbhar-13/azure-invoice-pipeline.git
cd azure-invoice-pipeline
```

### 2. Backend Setup
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Backend Environment Variables
Create `backend/.env` (copy from `backend/.env.example`):
```env
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key_here
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=invoices-test
DATABASE_URL=sqlite:///./invoiceai.db
JWT_SECRET=your_secure_256bit_random_secret_string_here
ENVIRONMENT=dev
```

> ⚠️ **Important:** `JWT_SECRET` must be **at least 32 characters** long. Generate one with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
# API docs → http://localhost:8001/docs
# Health → http://localhost:8001/health
```

### 5. Start Frontend
```bash
cd frontend
npm install
npm run dev
# App → http://localhost:5173
```

---

## 🚀 Production Deployment (Render + Vercel + Neon)

### Database — Neon PostgreSQL
1. Create a project at [neon.tech](https://neon.tech)
2. Copy the **pooled connection string**

### Backend — Render
1. Create a **Web Service** at [render.com](https://render.com)
2. **Root Directory:** `backend` · **Runtime:** Python 3
3. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Your Azure AI endpoint |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Your Azure AI key |
| `AZURE_STORAGE_CONNECTION_STRING` | Your Azure Storage connection string |
| `JWT_SECRET` | New 64-char hex secret |
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | Your Vercel URL (e.g., `https://invoiceai.vercel.app`) |
| `EMAIL_ENABLED` | `false` (until SMTP configured) |

### Frontend — Vercel
1. Import the repo at [vercel.com](https://vercel.com)
2. **Root Directory:** `frontend` · **Framework:** Vite
3. Set environment variable: `VITE_API_URL` = your Render backend URL

> **Important:** After deploying both, go back to Render and set `FRONTEND_URL` to your Vercel URL for CORS.

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login → JWT tokens |
| `POST` | `/auth/refresh` | Refresh access token (httpOnly cookie) |
| `POST` | `/auth/logout` | Logout + revoke refresh token |
| `GET` | `/auth/profile` | Get user profile + org details |
| `PUT` | `/auth/profile` | Update org details (GSTIN for payment detection) |
| `POST` | `/invoices/upload` | Upload single invoice (HTTP 202) |
| `POST` | `/invoices/upload/bulk` | Upload up to 20 invoices (HTTP 202) |
| `GET` | `/invoices/batch/{batch_id}` | Live batch processing status |
| `GET` | `/invoices/` | List invoices (paginated + search + filter) |
| `GET` | `/invoices/stats` | Dashboard statistics |
| `GET` | `/invoices/{id}` | Invoice detail + fresh SAS URL |
| `DELETE` | `/invoices/{id}` | Delete invoice + Azure blob |
| `POST` | `/invoices/{id}/reprocess` | Re-run full pipeline (QR + OCR) |
| `GET` | `/invoices/export/csv` | Streaming CSV export |
| `GET` | `/invoices/export/xlsx` | XLSX export (10K row cap) |
| `GET` | `/review/queue` | Pending human review queue |
| `POST` | `/review/{id}/submit` | Submit review decision |
| `GET` | `/payments/` | List payment records |
| `GET` | `/payments/{id}` | Payment detail + transactions |
| `POST` | `/payments/{id}/transactions` | Record a payment transaction |
| `POST` | `/payments/manual` | Create manual payment record |
| `GET` | `/reminders/settings` | Get reminder preferences |
| `PUT` | `/reminders/settings` | Update reminder schedule |
| `GET` | `/reminders/notifications` | Get in-app notifications |
| `POST` | `/webhooks` | Register webhook endpoint |
| `GET` | `/health` | DB + Azure + QR + scheduler health |

---

## 🔐 Security Architecture

| Control | Implementation |
|---------|---------------|
| **Authentication** | JWT access token (60 min) + refresh token (7 days, httpOnly cookie) |
| **Token Storage** | In-memory Zustand store — never persisted to localStorage |
| **Passwords** | bcrypt hashing + server-side complexity validation |
| **Blob Access** | Time-limited SAS URLs (1 hr) — raw Azure URLs never exposed |
| **File Validation** | Extension check → magic bytes → Content-Length middleware (20 MB) |
| **Deduplication** | SHA-256 idempotency key per upload |
| **SSRF Protection** | DNS resolution + private IP denylist for webhook URLs |
| **CORS** | Environment-bound allowed origins (fails loudly in production if misconfigured) |
| **Security Headers** | HSTS · X-Content-Type-Options · X-Frame-Options · Cache-Control: no-store |
| **Rate Limiting** | Redis-backed per-user limits with in-memory fallback |
| **Error Handling** | Correlation IDs in responses — raw DB/stack traces never exposed |

---

## 📁 Project Structure

```
azure-invoice-pipeline/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── main.py                   # App entry, middleware, lifespan, scheduler
│   │   ├── config.py                 # Pydantic settings (reads .env)
│   │   ├── database.py               # SQLAlchemy engine + connection pooling
│   │   ├── routers/                  # auth · invoices · review · webhooks · payments · reminders
│   │   ├── models/                   # invoice · user · payment · review_log · webhook
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── services/                 # pipeline · qr_detector · azure_ai · blob_storage
│   │   │                              payment_service · reminder_service · webhook_service
│   │   ├── middleware/               # JWT auth · rate limiting (Redis + fallback)
│   │   └── utils/                    # datetime_utils.py
│   ├── alembic/                      # DB migration scripts
│   ├── Dockerfile                    # Multi-stage production Docker build
│   ├── docker-compose.yml            # Local dev with PostgreSQL + Redis
│   ├── requirements.txt              # Python dependencies
│   ├── start.sh                      # Startup script (dev/production modes)
│   └── .env.example                  # Environment variable template
├── frontend/                         # React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/                    # Dashboard · Upload · Invoices · Review · Payments · Reminders
│   │   ├── components/               # PreviewPanel · ReviewModal · FileDropzone · NotificationBell
│   │   ├── hooks/                    # useInvoiceStatus · usePayments · useReminders · useNotifications
│   │   ├── store/                    # Zustand auth store (memory-only tokens)
│   │   ├── api/                      # Axios client with JWT refresh interceptor
│   │   └── types/                    # TypeScript type definitions
│   ├── package.json
│   ├── vite.config.ts
│   ├── .env.production               # Production API URL template
│   └── .env.example                  # Local dev env template
├── docs/
│   ├── screenshots/                  # Application screenshots
│   ├── guides/                       # Implementation & bug-fix documentation
│   └── sample-invoices/              # Sample PDFs for testing
├── .gitignore
└── README.md
```

---

## 📄 License

MIT License © 2026

---

<div align="center">
  <sub>⚡ Built for Indian GST compliance · Powered by Azure AI Document Intelligence</sub><br/>
  <sub>🔒 Security-hardened · 💰 Payment tracking · 🔔 Smart reminders · 🪟 Windows-native QR decoding</sub>
</div>
