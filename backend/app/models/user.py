import uuid
from sqlalchemy import Column, String
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # Changed from Postgres UUID to standard String
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True)

    # BUG-06: Store SHA-256 hash of refresh token — never store raw token
    refresh_token_hash = Column(String(64), nullable=True)

    # ── Organisation profile (added for payment direction auto-detection) ──
    # org_gstin is used by payment_service to auto-detect whether a processed
    # invoice is a PAYABLE (we are the buyer) or RECEIVABLE (we are the seller).
    # Format: 15-char GST registration number e.g. 27AAPFU0939F1ZV
    # nullable=True so existing users are not broken; they set it via
    # PUT /auth/profile after registering.
    org_name = Column(String(255), nullable=True)
    org_gstin = Column(String(15), nullable=True, index=True)
    org_address = Column(String(500), nullable=True)
    org_email = Column(String(255), nullable=True)  # used as "From" in reminder emails