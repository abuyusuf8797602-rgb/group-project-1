from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr


class SignatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signer_name: str
    signer_email: str
    signed_at: datetime
    signed_sha256: str
    hmac_signature: str
    rsa_signature: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    filename: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime


class DocumentDetail(DocumentOut):
    signature: SignatureOut | None = None


class LayerCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class VerificationResult(BaseModel):
    filename: str
    file_sha256: str
    matched: bool
    verified: bool = False
    document: DocumentOut | None = None
    signature: SignatureOut | None = None
    checks: list[LayerCheck] = []
