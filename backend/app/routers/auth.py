"""
Auth router for InvoiceAI.

BUG-06: JWT refresh tokens + 60 min access token + httpOnly cookie.

[NEW] Org profile endpoints — GET/PUT /auth/profile for org_gstin etc.
      Used by payment_service to auto-detect payment direction.
"""
import os
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserCreate, UserResponse, TokenResponse,
    OrgProfileUpdate, UserProfileResponse,
)
from app.services.auth_service import (
    hash_password, verify_password, create_jwt, generate_api_key,
    create_refresh_token, decode_refresh_token, hash_token,
)
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Fast-path check: catches most duplicates cheaply without hitting the DB constraint.
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        api_key=generate_api_key(),
    )
    db.add(new_user)

    # BUG-D4: Catch IntegrityError from the DB-level UNIQUE constraint.
    # This closes the race condition where two concurrent registrations both pass
    # the app-level check above before either has committed.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=TokenResponse)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Accepts standard OAuth2 form: username (email) + password.
    Returns JWT access token AND sets httpOnly refresh token cookie.
    BUG-06: Access token = 60 min, Refresh token = 7 days via cookie.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_jwt(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(user_id=str(user.id))

    # Store hash of refresh token — never store raw
    user.refresh_token_hash = hash_token(refresh_token)
    db.commit()

    # BUG-B2: secure flag is automatic — never a hardcoded False that someone
    # can forget to update. True in production (HTTPS required), False in dev.
    _secure_cookie = os.getenv("ENVIRONMENT", "dev") == "production"

    # Set refresh token as httpOnly cookie (not accessible via JS)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="strict",
        max_age=7 * 24 * 3600,  # 7 days
        secure=_secure_cookie,
        path="/auth",  # Only sent to /auth endpoints
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email},
    }


@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    BUG-06: Refresh endpoint — reads refresh token from httpOnly cookie.
    Issues a new access token if the refresh token is valid.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    user_id = decode_refresh_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Verify the stored hash matches
    if user.refresh_token_hash != hash_token(token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    # Issue new access token
    new_access_token = create_jwt(data={"sub": str(user.id)})

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email},
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    BUG-06: Logout — clears refresh token cookie and revokes the token in DB.
    """
    token = request.cookies.get("refresh_token")
    if token:
        user_id = decode_refresh_token(token)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.refresh_token_hash = None
                db.commit()

    response.delete_cookie("refresh_token", path="/auth")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── [NEW] Organisation profile endpoints ──────────────────────────────────────
# Used by the payment tracking feature: org_gstin lets payment_service
# auto-detect whether an invoice is a RECEIVABLE or PAYABLE by comparing
# it against the invoice's vendor_gstin / buyer_gstin.

@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the current user's full profile including org details."""
    return current_user


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    payload: OrgProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update organisation details (name, GSTIN, address, email).

    Setting org_gstin enables automatic payment direction detection for
    all future invoice uploads. Existing invoices are not retroactively
    updated — reprocess them if you want direction detection applied.
    """
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user