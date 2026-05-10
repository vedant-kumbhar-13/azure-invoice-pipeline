import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Text, JSON, Integer
from sqlalchemy.sql import func
from app.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    status = Column(String, default="processing")
    original_filename = Column(String)
    # BUG-D2: TECH DEBT — this column stores a blob_name (e.g. "a1b2c3d4.pdf"),
    # NOT a URL. The column name is kept as file_url to avoid a data migration
    # right now, but a future migration should:
    #   1. op.alter_column('invoices', 'file_url', new_column_name='blob_name')
    #   2. Update all references in blob_storage.py, invoices.py, processing_pipeline.py
    # SAS URLs are generated on-demand via get_blob_sas_url(); never store them.
    file_url = Column(String)
    raw_json = Column(Text)
    data_json = Column(JSON)
    confidence = Column(Float)
    error_detail = Column(String, nullable=True)   

    source_type = Column(String, nullable=True) # GST_EINVOICE, GST_PDF, NON_GST, HANDWRITTEN, UNKNOWN
    ingestion_method = Column(String, nullable=True) # QR, OCR, HUMAN
    gst_rules_json = Column(JSON, nullable=True)
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)
    processing_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # BUG-11: Added server_default so updated_at is never NULL on initial insert
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())