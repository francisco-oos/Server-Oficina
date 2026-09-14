from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import permission_codes, user_from_session
from app.db.base import get_db
from app.db.models import User


def current_user(session_id: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    user = user_from_session(db, session_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión requerida")
    return user


def require(permission: str):
    def dep(user: User = Depends(current_user)) -> User:
        if permission not in permission_codes(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permiso requerido: {permission}")
        return user
    return dep


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
