<div align="center">

<img src="https://img.shields.io/badge/Azure_Invoice_Pipeline-Enterprise%20GST%20Platform-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" alt="Azure Invoice Pipeline"/>

# ⚡ Azure Invoice Pipeline — Enterprise GST Processing

**Automate GST invoice ingestion · QR decoding · OCR extraction · Compliance validation · Human review**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev/)
[![Azure AI](https://img.shields.io/badge/Azure-Document%20Intelligence-0078D4?style=flat-square&logo=microsoftazure)](https://azure.microsoft.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript)](https://typescriptlang.org/)

</div>

---

## 📌 What is Azure Invoice Pipeline?

**Azure Invoice Pipeline** is a production-ready, full-stack platform built for Indian GST compliance. It eliminates manual invoice data entry by combining:

- 🔍 **3-Layer QR Decoder** — reads GST e-Invoice JWT QR codes instantly (Windows-native, no Linux DLLs)
- 🤖 **Azure Document Intelligence** — state-of-the-art OCR fallback for non-QR invoices
- ✅ **GST Compliance Engine** — validates GSTIN, tax math, line items, and place of supply
- 📊 **Confidence Scoring** — per-field confidence with visual indicators
- 👤 **Human Review Workflow** — side-by-side PDF viewer + editable form for flagged invoices
- 🔒 **Security-First Architecture** — SAS-tokenised blob access, JWT auth, SSRF protection

---

## 🖥️ Platform Walkthrough

### 1. 🔐 Login Page
> Secure JWT-based authentication. Users register with email + password (bcrypt hashed). Tokens auto-refresh in the background.

![Login Page](docs/screenshots/login_page.png)

**Features:**
- Email/password login with validation
- Secure JWT access token (30 min) + refresh token (7 days)
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
> Drag-and-drop invoice uploader with file preview and one-click processing trigger.

![Upload Invoice](docs/screenshots/upload_invoice.png)

**Features:**
- Drag-and-drop or click-to-browse file selection (PDF, JPEG, PNG — max 20 MB)
- Live file preview (PDF rendered inline, images displayed immediately)
- Idempotency key prevents accidental duplicate submissions
- "Upload & Process" button disables after first click to prevent double-submission
- Clear button resets the form for a new upload

---

### 4. ⚙️ Processing in Progress
> After upload, the background pipeline runs asynchronously. The UI polls every 2 seconds and displays a live status indicator.

![Processing](docs/screenshots/proccesig.png)

**Features:**
- Live status badge: `PROCESSING` → `AUTO_APPROVED` / `NEEDS_REVIEW` / `HUMAN_REQUIRED`
- 10-minute polling timeout with automatic escalation to `HUMAN_REQUIRED`
- Animated spinner while Azure AI processes the document
- Non-blocking — user can navigate away and return; status updates on re-visit
- Processing time displayed on completion (e.g. `18.7s`)

---

### 5. 📋 Invoice History
> Paginated, filterable table of all processed invoices with an inline slide-out preview panel.

![Invoice History](docs/screenshots/INVOICE_HISTORY.png)

**Features:**
- Server-side filtering by status: All · Processing · Auto-Approved · Needs Review · Failed
- Full-text search by filename, vendor name, invoice number, or GSTIN
- Confidence bar per row (green · amber · red colour coding)
- **👁 Eye icon** → opens the slide-out `InvoicePreviewPanel` without navigating away
- **↗ External link icon** → navigates to the full Invoice Detail page
- **🗑 Trash icon** → delete with confirmation dialog
- Highlighted selected row in blue when preview panel is open
- 20 items per page with Prev/Next pagination

---

### 6. 🔍 Invoice Preview Panel
> Click any row in the Invoice History to slide open this panel — view the original document and all extracted data side-by-side without leaving the page.

![Human Review](docs/screenshots/human%20review.png)

**Features:**
- **Left pane (55%)** — PDF rendered inline via Azure SAS URL (no download triggered)
- **Right pane (45%)** — all extracted fields with per-field confidence bars:
  - Vendor Name & GSTIN · Buyer Name & GSTIN
  - Invoice Number & Date
  - CGST · SGST · IGST · Grand Total
- Animated confidence ring showing overall score
- GST compliance flags shown in red if any violations detected
- Close with ✕, Escape key, or click outside — or open Full Detail with ↗

---

### 7. 🛡️ Review Queue
> Centralised queue for all invoices flagged for human attention, sorted by urgency (HUMAN_REQUIRED first, then NEEDS_REVIEW).

![Review Queue](docs/screenshots/REVIEW_PAGE.png)

**Features:**
- Priority-sorted queue: `HUMAN_REQUIRED` (red) → `NEEDS_REVIEW` (amber)
- Confidence score and GST compliance flags shown per card
- Red badge in sidebar navigation shows pending count (updates every 30 seconds)
- Click any card to open the full Human Override modal
- Queue auto-refreshes after each review decision

---

### 8. ✍️ Human Override Modal
> When an invoice needs human intervention, this full-screen modal shows the original document alongside an editable form.

**Features (from the same Human Review screenshot above):**
- **Left panel** — original invoice PDF rendered inline (SAS URL with `Content-Disposition: inline`)
- **Right panel** — pre-populated editable form:
  - Vendor Name, Vendor GSTIN (with format validation)
  - Invoice Number, Invoice Date
  - Total Amount, CGST, SGST, IGST
- Three action buttons:
  - ✅ **Approve As-Is** — mark as VERIFIED without edits
  - 💾 **Save Form Edits** — correct data and mark as VERIFIED
  - ❌ **Reject** — mark as REJECTED with optional notes
- Full audit log entry written on every decision (diff-only for EDITED)

---

### 9. ⚙️ Settings Page
> Manage your account, API keys, and webhook integrations.

![Settings](docs/screenshots/SETTINGS.png)

**Features:**
- Account information display (email, organisation)
- API key management (generate, view, revoke)
- Webhook endpoint configuration — register URLs for invoice processing events
- Webhook event filtering (select which status changes trigger callbacks)
- Delivery log for webhook history

---

### 10. 📊 Excel Export
> Download all processed invoice data as a structured Excel file for accounting and ERP workflows.

![Excel Export](docs/screenshots/EXEL_DATA.png)

**Features:**
- Single-click export from the Invoices or Settings page
- All fields exported: Vendor, GSTIN, Invoice #, Date, Line Items, CGST, SGST, IGST, Total
- Confidence scores included per field
- Status column for audit trail
- Compatible with Microsoft Excel, Google Sheets, and accounting tools

---

## 🔄 Processing Pipeline

```
User uploads PDF / JPEG / PNG
            │
            ▼
   POST /invoices/upload
   ├─ Idempotency check (SHA-256 key dedup)
   ├─ Upload to Azure Blob Storage (private)
   └─ Trigger BackgroundTask (non-blocking)
            │
            ▼
   ┌─────────────────────────────┐
   │   3-Layer QR Decoder        │
   │  Layer 1: zxing-cpp         │ ──► GST JWT found?
   │  Layer 2: OpenCV WeChat ML  │         │
   │  Layer 3: OpenCV Standard   │         │ YES → Parse JWT
   └─────────────────────────────┘         │         confidence = 1.0
            │ NO QR found                  │         status = AUTO_APPROVED
            ▼                              │
   Azure Document Intelligence OCR         │
   └─ Extract: Vendor · GSTIN ·            │
      Buyer · Invoice# · Line Items ─────►─┘
      · CGST · SGST · IGST · Total
            │
            ▼
   GST Compliance Engine
   ├─ GSTIN format + checksum
   ├─ Tax math: CGST+SGST+IGST = Total
   ├─ Line-item subtotal cross-check
   └─ Invoice date range validation
            │
            ├─ confidence ≥ 0.90 ──► AUTO_APPROVED ✅
            ├─ confidence 0.60–0.90 ─► NEEDS_REVIEW ⚠️
            └─ confidence < 0.60 ───► HUMAN_REQUIRED 🔴
```

---

## 🛠️ Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------| 
| **Backend API** | FastAPI | 0.135 |
| **ORM** | SQLAlchemy | 2.0 |
| **DB Migrations** | Alembic | 1.18 |
| **Database** | SQLite (dev) / PostgreSQL (prod) | — |
| **Frontend** | React + TypeScript + Vite | 18 / 5 |
| **State Management** | TanStack Query (React Query) | v5 |
| **Styling** | Tailwind CSS | v3 |
| **Cloud — OCR** | Azure Document Intelligence | 1.0.2 SDK |
| **Cloud — Storage** | Azure Blob Storage | 12.28 SDK |
| **QR Layer 1** | zxing-cpp (Windows-native) | 2.2.0 |
| **QR Layer 2** | OpenCV WeChat QR (ML-based) | 4.9.0 |
| **QR Layer 3** | OpenCV Standard QR | 4.9.0 |
| **PDF Rendering** | PyMuPDF (fitz) | 1.24 |
| **Auth** | python-jose (JWT) + Passlib (bcrypt) | — |
| **Export** | openpyxl | 3.1 |

---

## ⚙️ Quick Start — Local Setup

### Prerequisites
- Python 3.11 or 3.12 · Node.js 18+ · Git
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
INVOICE_DATE_MAX_AGE_DAYS=1095
```

> ⚠️ **Important:** `JWT_SECRET` must be **at least 32 characters** long. Generate one with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. Database Migrations
```bash
cd backend
alembic upgrade head
```

### 5. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
# API docs → http://localhost:8001/docs
```

### 6. Start Frontend
```bash
cd frontend
npm install
npm run dev
# App → http://localhost:5173
```

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login → JWT tokens |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/invoices/upload` | Upload invoice file |
| `GET` | `/invoices/` | List invoices (paginated + filtered) |
| `GET` | `/invoices/stats` | Dashboard statistics |
| `GET` | `/invoices/{id}` | Invoice detail + fresh SAS URL |
| `DELETE` | `/invoices/{id}` | Delete invoice + blob |
| `GET` | `/review/queue` | Pending human review queue |
| `POST` | `/review/{id}/submit` | Submit review decision |
| `GET` | `/health` | DB + Azure + QR library health |

---

## 🔐 Security Architecture

| Control | Implementation |
|---------|---------------|
| **Authentication** | Stateless JWT (30 min access + 7 day refresh) |
| **Passwords** | bcrypt hashing via Passlib |
| **Blob Access** | Time-limited SAS URLs (1 hr) — raw Azure URLs never exposed |
| **File Preview** | `Content-Disposition: inline` prevents auto-download |
| **Uploads** | 20 MB Content-Length limit middleware |
| **Deduplication** | SHA-256 idempotency key per upload |
| **SSRF Protection** | External URL downloads capped at 5 MB |
| **CORS** | Explicit allowed-origin list only |
| **Rate Limiting** | Redis-backed per-user limits |

---

## 📁 Project Structure

```
Redivivus-invoiceai/
├── backend/                        # FastAPI backend
│   ├── app/
│   │   ├── main.py                 # App entry, middleware, lifespan tasks
│   │   ├── config.py               # Pydantic settings (reads .env)
│   │   ├── database.py             # SQLAlchemy engine + session
│   │   ├── routers/                # auth · invoices · review · webhooks
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/               # pipeline · qr_detector · azure_ai · blob_storage
│   │   ├── middleware/             # JWT auth · rate limiting
│   │   └── utils/                  # datetime_utils.py (UTC-aware IST serialisation)
│   ├── alembic/                    # DB migration scripts
│   ├── alembic.ini                 # Alembic configuration
│   ├── scripts/                    # seed_demo_data.py
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Environment variable template
│   └── .env                        # Local env vars (gitignored)
├── frontend/                       # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/                  # Dashboard · Upload · Invoices · Review · Detail
│   │   ├── components/             # InvoicePreviewPanel · ReviewModal · FileDropzone
│   │   ├── hooks/                  # useInvoiceStatus · useUploadInvoice · useReviewQueue
│   │   ├── store/                  # Zustand auth store
│   │   ├── api/                    # Axios client with JWT interceptors
│   │   └── utils/                  # IST formatters · URL resolver
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.local                  # VITE_API_URL (gitignored)
├── docs/
│   ├── screenshots/                # Application screenshots for README
│   ├── guides/                     # Implementation & bug-fix guides
│   └── sample-invoices/            # Sample PDF invoices for testing
├── .gitignore
└── README.md
```

---

## 🛡️ Production Hardening & Security Features

The platform has been extensively hardened for production deployments:

| Area | Feature |
|------|---------|
| **Core Architecture** | Fully Dockerised with multi-worker Uvicorn and PostgreSQL. Bounded thread-pool executors prevent event-loop blocking during heavy OCR loads. |
| **Data Privacy** | Health endpoints redact infrastructure errors. Raw internal blob names are never exposed; the frontend exclusively uses time-limited SAS URLs. |
| **Authentication** | Secure, httpOnly cookies for refresh tokens. JWT access tokens are kept in memory (Zustand) and never persisted to localStorage to prevent XSS exfiltration. |
| **API Security** | Strict CORS configurations with environment-bound allowed origins. Webhook signatures use raw secret HMAC validation with Pydantic minimum length constraints. |
| **Cost Optimisation** | Smart QR detector pre-checks extensions and caps PDF downloads to 1MB (first page only) to prevent massive egress costs on non-QR invoices. |
| **Resilience** | Redis-backed rate limiting with graceful fallback to in-memory deque limits. Automated schema migrations on startup. Database constraints prevent registration race conditions. |

---

## 📄 License

MIT License © 2026 Sumit Patil / Redivivus Technologies

---

<div align="center">
  <sub>⚡ Built for Indian GST compliance · Powered by Azure AI Document Intelligence</sub><br/>
  <sub>🔒 Security-hardened · 🌏 IST timezone-aware · 🪟 Windows-native QR decoding</sub>
</div>
