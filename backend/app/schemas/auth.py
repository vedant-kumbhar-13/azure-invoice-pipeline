from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    # BUG-12: Server-side password strength enforcement
    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    api_key: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None  # {id, email} — for frontend hydration


# ── Organisation profile schemas (added for payment direction auto-detection) ─

class OrgProfileUpdate(BaseModel):
    """
    Body for PUT /auth/profile
    Users set their org GSTIN here. payment_service uses it to auto-detect
    whether a processed invoice is PAYABLE or RECEIVABLE.
    """
    org_name: Optional[str] = None
    org_gstin: Optional[str] = None
    org_address: Optional[str] = None
    org_email: Optional[str] = None     # used as From address in reminder emails

    @field_validator("org_gstin")
    @classmethod
    def gstin_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 15:
            raise ValueError("org_gstin must be exactly 15 characters")
        return v


class UserProfileResponse(BaseModel):
    """
    Extended user response including org fields.
    Returned by GET /auth/profile and PUT /auth/profile.
    """
    id: str
    email: str
    api_key: Optional[str] = None
    org_name: Optional[str] = None
    org_gstin: Optional[str] = None
    org_address: Optional[str] = None
    org_email: Optional[str] = None

    class Config:
        from_attributes = True