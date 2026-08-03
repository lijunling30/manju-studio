"""FastAPI 依赖注入：JWT 鉴权 + 当前用户。"""
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    exc = HTTPException(status_code=401, detail="登录凭证无效或已过期", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(token)
        uid = int(payload.get("sub", -1))
    except Exception:
        raise exc
    user = db.get(User, uid)
    if not user:
        raise exc
    return user
