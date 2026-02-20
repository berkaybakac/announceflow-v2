from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import create_access_token, verify_password
from backend.core.settings import settings
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.repositories.branch_repository import BranchRepository
from backend.repositories.user_repository import UserRepository
from backend.schemas.auth import HandshakeRequest, HandshakeResponse, TokenResponse
from backend.schemas.user import UserRead

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    repo = UserRepository(db)
    user = await repo.get_by_username(form_data.username)

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hesap devre dışı",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "type": "user",
            "is_vendor_admin": user.is_vendor_admin,
        },
    )
    return TokenResponse(access_token=token)


@router.post("/agent/handshake", response_model=HandshakeResponse)
async def agent_handshake(
    body: HandshakeRequest,
    db: AsyncSession = Depends(get_db),
) -> HandshakeResponse:
    repo = BranchRepository(db)
    branch = await repo.get_by_token(body.device_token)

    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz cihaz token'ı",
        )

    if not branch.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cihaz devre dışı",
        )

    token = create_access_token(
        data={
            "sub": str(branch.id),
            "type": "device",
        },
        expires_delta=timedelta(days=settings.DEVICE_TOKEN_EXPIRE_DAYS),
    )
    return HandshakeResponse(access_token=token, branch_id=branch.id)


@router.get("/auth/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
