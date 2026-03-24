from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend import dependencies
from backend.models.user import User


@pytest.mark.asyncio
async def test_get_current_device_returns_403_when_branch_inactive() -> None:
    db = cast(AsyncSession, MagicMock())
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=SimpleNamespace(id=9, is_active=False))

    with (
        patch.object(
            dependencies,
            "decode_access_token",
            return_value={"type": "device", "sub": "9"},
        ),
        patch.object(dependencies, "BranchRepository", return_value=repo),
    ):
        with pytest.raises(HTTPException) as exc:
            await dependencies.get_current_device(token="valid-device-token", db=db)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Cihaz devre dışı"


@pytest.mark.asyncio
async def test_get_current_device_returns_401_for_wrong_token_type() -> None:
    db = cast(AsyncSession, MagicMock())

    with patch.object(
        dependencies,
        "decode_access_token",
        return_value={"type": "user", "sub": "1"},
    ):
        with pytest.raises(HTTPException) as exc:
            await dependencies.get_current_device(token="user-token", db=db)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.value.detail == "Geçersiz veya süresi dolmuş cihaz token'ı"


def test_parse_subject_as_int_raises_when_sub_is_missing() -> None:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid",
    )

    with pytest.raises(HTTPException) as exc:
        dependencies._parse_subject_as_int(payload={}, credentials_exc=credentials_exc)

    assert exc.value is credentials_exc


def test_parse_subject_as_int_raises_when_sub_is_not_int() -> None:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid",
    )

    with pytest.raises(HTTPException) as exc:
        dependencies._parse_subject_as_int(
            payload={"sub": "not-an-int"},
            credentials_exc=credentials_exc,
        )

    assert exc.value is credentials_exc


@pytest.mark.asyncio
async def test_verify_vendor_admin_returns_403_for_non_admin() -> None:
    user = cast(User, SimpleNamespace(is_vendor_admin=False))

    with pytest.raises(HTTPException) as exc:
        await dependencies.verify_vendor_admin(current_user=user)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Yetersiz yetki"
