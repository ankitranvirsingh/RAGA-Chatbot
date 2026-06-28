"""
app/dependencies.py
FastAPI dependencies:
  - verify_admin: checks JWT Bearer token (issued by /admin/login)
  - get_db: async SQLAlchemy session

Replaces the original single-header API key with proper JWT auth so tokens
can expire and be issued without exposing the password in every request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.models.database import get_db  # re-export for convenience

settings = get_settings()

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_admin(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — raises 401 if token invalid or expired."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username != settings.ADMIN_USERNAME:
            raise credentials_exc
        return username
    except JWTError:
        raise credentials_exc
