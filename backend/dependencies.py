from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.models.branch import Branch
from backend.models.user import User
from backend.repositories.branch_repository import BranchRepository
from backend.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _parse_subject_as_int(
    payload: dict[str, Any],
    credentials_exc: HTTPException,
) -> int:
    sub = payload.get("sub")
    if sub is None:
        raise credentials_exc
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise credentials_exc from None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except (ExpiredSignatureError, InvalidTokenError):
        raise credentials_exc from None

    if payload.get("type") != "user":
        raise credentials_exc

    user_id = _parse_subject_as_int(payload, credentials_exc)

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exc

    return user


async def verify_vendor_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_vendor_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yetersiz yetki",
        )
    return current_user


async def get_current_device(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Branch:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş cihaz token'ı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except (ExpiredSignatureError, InvalidTokenError):
        raise credentials_exc from None

    if payload.get("type") != "device":
        raise credentials_exc

    branch_id = _parse_subject_as_int(payload, credentials_exc)

    repo = BranchRepository(db)
    branch = await repo.get_by_id(branch_id)
    if branch is None:
        raise credentials_exc

    if not branch.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cihaz devre dışı",
        )

    return branch
