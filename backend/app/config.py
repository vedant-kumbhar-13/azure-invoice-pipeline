from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Azure Document Intelligence
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "invoices-test"

    # Database
    DATABASE_URL: str

    # Auth
    JWT_SECRET: str

    # Optional
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "INFO"
    # BUG-D3: APP_PORT is now consumed by:
    #   - start.sh (local/dev startup script)
    #   - Dockerfile ENV APP_PORT + CMD --port ${APP_PORT}
    #   - docker-compose.yml ports and environment sections
    # Previously this setting was declared but never read by anything.
    APP_PORT: int = 8001

    # BUG-B1: Production frontend URL — must be set in production .env.
    # In dev this is unused; in production it becomes the only allowed CORS origin.
    # Example: https://invoiceai.example.com
    FRONTEND_URL: str = ""

    # BUG-05: GST e-Invoice IRN must be generated within 30 days of invoice date.
    # But for reconciliation/audit uploads, India IT Act allows 3-year retention.
    # Set to 1095 (3 years) to support audit workflows.
    INVOICE_DATE_MAX_AGE_DAYS: int = 1095

    # BUG-08: Redis for distributed rate limiting across workers
    REDIS_URL: str = "redis://localhost:6379"
    UPLOAD_RATE_LIMIT_PER_MIN: int = 100

    # BUG-19: Database connection pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Validators ──────────────────────────
    @field_validator("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    @classmethod
    def endpoint_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT must start with https://")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters for security")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_format(cls, v: str) -> str:
        if not (v.startswith("postgresql://") or v.startswith("sqlite:///")):
            raise ValueError("DATABASE_URL must start with postgresql:// or sqlite:///")
        return v


# Create a global instance to be imported anywhere in your app
settings = Settings()