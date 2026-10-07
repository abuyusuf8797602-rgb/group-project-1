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
    document_key = relationship(
        "DocumentKey",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    key_exchange = relationship(
        "KeyExchange",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def encrypted(self) -> bool:
        """True once the stored file is an AES-256-GCM envelope."""
        return self.document_key is not None


class EncryptionKey(Base):
    """Single-row table holding the service master key.

    The master key never encrypts documents directly: it wraps each document's
    own data key, so re-keying the service does not require re-encrypting files.
    """

    __tablename__ = "encryption_keys"

    id = Column(Integer, primary_key=True)
    # 32 raw AES-256 bytes, base64 encoded
    master_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DocumentKey(Base):
    """The per-document data key, stored wrapped by the master key."""

    __tablename__ = "document_keys"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True, nullable=False)
    # nonce || wrapped key || tag, base64 encoded
    wrapped_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="document_key")


class KeyExchange(Base):
    """A document key wrapped for one recipient via X25519 ECDH + HKDF.

    Stores only public values: the recipient's public key, the ephemeral public
    key of this exchange, the HKDF salt and the wrapped data key. The recipient's
    private key is never sent to the service.
    """

    __tablename__ = "key_exchanges"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True, nullable=False)

    recipient_name = Column(String(200), nullable=False)
    recipient_email = Column(String(320), nullable=False)
    recipient_public_key = Column(Text, nullable=False)
    # SHA-256 of the recipient's DER public key
    recipient_fingerprint = Column(String(64), nullable=False, index=True)

    ephemeral_public_key = Column(Text, nullable=False)
    salt = Column(Text, nullable=False)
    wrapped_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="key_exchange")


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
