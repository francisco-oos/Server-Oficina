from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_settings
from app.db.models import SessionToken, User


SCHEME = "scrypt"


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"{SCHEME}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
        if scheme != SCHEME:
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_session(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(40)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    hours = load_settings().session_hours
    db.add(SessionToken(user_id=user.id, token_hash=token_hash, expires_at=datetime.now(timezone.utc) + timedelta(hours=hours)))
    db.commit()
    return raw


def user_from_session(db: Session, raw: str | None) -> User | None:
    if not raw:
        return None
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if not token:
        return None
    expiry = token.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        db.delete(token)
        db.commit()
        return None
    return db.get(User, token.user_id)


def destroy_session(db: Session, raw: str | None) -> None:
    if not raw:
        return
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if token:
        db.delete(token)
        db.commit()


def permission_codes(user: User) -> set[str]:
    return {p.code for role in user.roles for p in role.permissions}
