from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class SigningKey(Base):
    """Single-row table holding the service's signing material.

    Generated once by the one-shot `migrate` service and reused for every
    signature, so signatures stay verifiable across restarts.
    """

    __tablename__ = "signing_keys"

    id = Column(Integer, primary_key=True)
    private_key_pem = Column(Text, nullable=False)
    certificate_pem = Column(Text, nullable=False)
    hmac_secret = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    # Bearer token that forms the unique signing link: /sign/<token>
    token = Column(String(64), unique=True, index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(255), nullable=False, default="application/octet-stream")
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    signature = relationship(
        "Signature",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Signature(Base):
    __tablename__ = "signatures"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True, nullable=False)

    # Layer 1 - acknowledgement record
    signer_name = Column(String(200), nullable=False)
    signer_email = Column(String(320), nullable=False)
    signed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    signer_ip = Column(String(64), nullable=True)

    # Layers 2 and 3 - cryptographic signatures over the document hash
    signed_sha256 = Column(String(64), nullable=False)
    hmac_signature = Column(String(128), nullable=False)
    rsa_signature = Column(Text, nullable=False)
    certificate_pem = Column(Text, nullable=False)

    document = relationship("Document", back_populates="signature")
