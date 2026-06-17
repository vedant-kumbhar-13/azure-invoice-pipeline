from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Azure Document Intelligence ──────────────────────────────────────────
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str

    # ── Azure Blob Storage ───────────────────────────────────────────────────
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "invoices-test"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Auth ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str

    # ── Optional / defaults ──────────────────────────────────────────────────
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "INFO"

    # BUG-D3: APP_PORT is now consumed by:
    #   - start.sh (local/dev startup script)
    #   - Dockerfile ENV APP_PORT + CMD --port ${APP_PORT}
    #   - docker-compose.yml ports and environment sections
    APP_PORT: int = 8001

    # BUG-B1: Production frontend URL — must be set in production .env.
    # In dev this is unused; in production it becomes the only allowed CORS origin.
    FRONTEND_URL: str = ""

    # BUG-05: GST e-Invoice IRN must be generated within 30 days of invoice date.
    # But for reconciliation/audit uploads, India IT Act allows 3-year retention.
    INVOICE_DATE_MAX_AGE_DAYS: int = 1095

    # BUG-08: Redis for distributed rate limiting across workers
    REDIS_URL: str = "redis://localhost:6379"
    UPLOAD_RATE_LIMIT_PER_MIN: int = 100

    # BUG-19: Database connection pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── SMTP / Email reminders ───────────────────────────────────────────────
    # Flexible smtplib configuration. Works with Gmail, Outlook, or any
    # custom SMTP server — just change these .env values.
    #
    # Gmail setup:
    #   1. Enable 2-Step Verification on your Google account.
    #   2. Go to Google Account → Security → App Passwords.
    #   3. Generate an App Password (select "Mail" + your device).
    #   4. Use that 16-char App Password as SMTP_PASSWORD below.
    #      Do NOT use your normal Gmail password — it will be rejected.
    #
    # Outlook / Office 365:
    #   SMTP_HOST=smtp.office365.com  SMTP_PORT=587  SMTP_USE_TLS=true
    #
    # Custom SMTP (e.g. Mailhog local dev):
    #   SMTP_HOST=localhost  SMTP_PORT=1025  SMTP_USE_TLS=false
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # STARTTLS (recommended, port 587). Set False + port 465 for SSL.
    SMTP_USE_TLS: bool = True

    # Gmail: use App Password, NOT your normal password
    SMTP_USERNAME: str = ""          # e.g. yourname@gmail.com
    SMTP_PASSWORD: str = ""          # App Password (16 chars, no spaces)

    # "From" name shown in recipient's inbox e.g. "Invoice Pipeline Reminders"
    SMTP_FROM_NAME: str = "Invoice Pipeline"

    # If SMTP_FROM_EMAIL is empty, SMTP_USERNAME is used as the From address
    SMTP_FROM_EMAIL: str = ""

    # Master switch — set False to disable all outgoing email (useful in dev/test)
    EMAIL_ENABLED: bool = True

    # ── Reminder scheduler ───────────────────────────────────────────────────
    # How often the reminder_service scans for due payments and fires reminders.
    # Value is in hours. Default: every 6 hours.
    REMINDER_SCHEDULER_INTERVAL_HOURS: int = 6

    # Default days before due date to send reminders (comma-separated).
    # This is the system default; each user can override in their reminder settings.
    REMINDER_DEFAULT_DAYS_BEFORE: str = "7,3,1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    @classmethod
    def endpoint_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT must start with https://"
            )
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters for security"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_format(cls, v: str) -> str:
        if not (v.startswith("postgresql://") or v.startswith("sqlite:///")):
            raise ValueError(
                "DATABASE_URL must start with postgresql:// or sqlite:///"
            )
        return v

    # ── Derived helpers (not env vars, computed at runtime) ──────────────────

    @property
    def smtp_from_address(self) -> str:
        """Returns the actual From email address, falling back to SMTP_USERNAME."""
        return self.SMTP_FROM_EMAIL or self.SMTP_USERNAME

    @property
    def reminder_days_list(self) -> list[int]:
        """
        Parses REMINDER_DEFAULT_DAYS_BEFORE into a sorted list of ints.
        e.g. "7,3,1" → [1, 3, 7]
        """
        try:
            return sorted(
                [int(d.strip()) for d in self.REMINDER_DEFAULT_DAYS_BEFORE.split(",")
                 if d.strip().isdigit()]
            )
        except Exception:
            return [1, 3, 7]


# Global settings instance — import this everywhere in the app
settings = Settings()