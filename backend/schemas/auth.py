from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HandshakeRequest(BaseModel):
    device_token: str


class HandshakeResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    branch_id: int
