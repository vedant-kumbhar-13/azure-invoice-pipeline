"""
Vendor Corrections Cache — stores human-verified field corrections
keyed by vendor identifier (GSTIN or normalized name) so that future
invoices from the same vendor can benefit from prior human review.

This enables application-level learning without requiring Azure model retraining.
"""
import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, JSON, Integer, Index
from sqlalchemy.sql import func
from app.database import Base


class VendorCorrection(Base):
    __tablename__ = "vendor_corrections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Vendor identifier — primarily GSTIN, fallback to normalized vendor name
    vendor_key = Column(String(255), nullable=False, index=True)
    vendor_key_type = Column(String(20), nullable=False)  # "gstin" or "name"

    # The user who created this correction
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # The invoice that was corrected (source of truth)
    source_invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False)

    # The corrected field values (canonical format: {"field": {"value": x, "confidence": 1.0}})
    corrected_fields = Column(JSON, nullable=False)

    # How many times this correction has been applied to new invoices
    times_applied = Column(Integer, default=0)

    # Track usage
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Composite index for efficient vendor + user lookups
        Index("ix_vendor_corrections_vendor_user", "vendor_key", "user_id"),
    )
