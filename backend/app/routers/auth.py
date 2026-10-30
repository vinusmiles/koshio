from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pydantic import BaseModel

from .. import ai
from ..config import get_settings
from ..db import get_db
from ..models import User
from ..schemas import Credentials, LoginRequest, Token
from ..security import create_token, current_user, hash_password, login_limiter, verify_password
from ..seed import seed_new_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def registration_status(db: Session = Depends(get_db)):
    """Tells the sign-in page whether to offer 'Create account'."""
    s = get_settings()
    has_users = db.scalar(select(func.count(User.id))) > 0
    return {"registration_open": s.allow_registration and (not has_users or s.allow_multiple_users)}


@router.post("/register", response_model=Token, status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)):
    s = get_settings()
    has_users = db.scalar(select(func.count(User.id))) > 0
    if not s.allow_registration or (has_users and not s.allow_multiple_users):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is closed for this Koshio.")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    seed_new_user(db, user.id)
    db.commit()
    return Token(access_token=create_token(user.id))


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    key = body.email.lower()
    if login_limiter.blocked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many failed attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == key))
    if user is None or not verify_password(body.password, user.password_hash):
        login_limiter.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    login_limiter.reset(key)
    return Token(access_token=create_token(user.id))


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "ai_available": ai.available(),
            "ai_categorise": user.ai_categorise}


class SettingsIn(BaseModel):
    ai_categorise: bool


@router.patch("/me")
def update_me(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.ai_categorise = body.ai_categorise
    db.commit()
    return me(user)
