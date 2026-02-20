from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    is_vendor_admin: bool = False


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    is_vendor_admin: bool
    is_active: bool
