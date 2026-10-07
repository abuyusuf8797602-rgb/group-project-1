"""Envelope encryption and key management on top of :mod:`crypto`.

How the keys layer, so no single secret directly encrypts user data:

    master key   fresh 256-bit key in the single-row `encryption_keys` table
      wraps  ->  per-document data key (DEK, fresh 256-bit key per upload,
                 stored wrapped in `document_keys`)
      which  ->  encrypts the document bytes on the storage volume

Sharing a document does not export the DEK. A fresh ephemeral X25519 keypair is
generated per exchange, ECDH'd with the recipient's public key, run through
HKDF-SHA256, and the result wraps the DEK. The recipient re-derives the same
key from their own private key, so the service never holds it, and the wrapped
key is bound by AAD to the document token and the recipient key fingerprint.
"""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crypto, models, storage


class MasterKeyMissing(RuntimeError):
    """The service master key has not been initialised yet."""


def get_master_key(db: Session) -> bytes:
    row = db.execute(
        select(models.EncryptionKey).order_by(models.EncryptionKey.id)
    ).scalars().first()
    if row is None:
        raise MasterKeyMissing("The service encryption key is not initialised")
    return crypto.unb64(row.master_key)


def ensure_master_key(db: Session) -> None:
    """Create the master key once. Called by the one-shot migrate service."""
    if db.query(models.EncryptionKey).count() == 0:
        db.add(models.EncryptionKey(master_key=crypto.b64(crypto.new_key())))
        db.commit()


def encrypt_legacy_documents(db: Session) -> int:
    """Seal documents uploaded before encryption existed.

    Uploads that are already sealed are left alone, so this is safe to re-run.
    """
    master_key = get_master_key(db)
    migrated = 0
    for document in db.execute(select(models.Document)).scalars().all():
        if document.document_key is not None:
            continue
        try:
            blob = storage.read(document.token)
        except FileNotFoundError:
            continue  # row without a file on disk; nothing to seal
        if not blob.startswith(crypto.MAGIC):
            dek = crypto.new_key()
            storage.save(document.token, crypto.seal_document(blob, dek))
            db.add(
                models.DocumentKey(
                    document_id=document.id,
                    wrapped_key=crypto.b64(
                        crypto.wrap_key(master_key, dek, document_aad(document.token))
                    ),
                )
            )
            migrated += 1
    db.commit()
    return migrated


def store_document(db: Session, document: models.Document, data: bytes, master_key: bytes) -> None:
    """Encrypt a new upload at rest and store its wrapped data key."""
    dek = crypto.new_key()
    storage.save(document.token, crypto.seal_document(data, dek))
    db.add(
        models.DocumentKey(
            document_id=document.id,
            wrapped_key=crypto.b64(
                crypto.wrap_key(master_key, dek, document_aad(document.token))
            ),
        )
    )


def read_document(db: Session, document: models.Document, master_key: bytes) -> bytes:
    """Return the plaintext of a stored document."""
    blob = storage.read(document.token)
    if document.document_key is None:
        return blob  # stored before encryption was introduced
    dek = crypto.unwrap_key(
        master_key,
        crypto.unb64(document.document_key.wrapped_key),
        document_aad(document.token),
    )
    plaintext, _ = crypto.unseal_document(blob, dek)
    return plaintext


def document_aad(token: str) -> bytes:
    """Associated data binding a wrapped data key to its document."""
    return f"document:{token}".encode()


def exchange_aad(token: str, recipient_fingerprint: str) -> bytes:
    """Associated data binding a shared key to its document and recipient."""
    return f"key-exchange:{token}:{recipient_fingerprint}".encode()


def create_exchange(
    db: Session,
    document: models.Document,
    recipient_name: str,
    recipient_email: str,
    recipient_public_key: str,
    master_key: bytes,
) -> models.KeyExchange:
    """Wrap the document's data key for a recipient's X25519 public key."""
    if document.document_key is None:
        raise MasterKeyMissing("This document has no encrypted key to share")

    token = document.token
    fingerprint = crypto.fingerprint(recipient_public_key)
    dek = crypto.unwrap_key(
        master_key,
        crypto.unb64(document.document_key.wrapped_key),
        document_aad(token),
    )

    ephemeral_private_pem, ephemeral_public_pem = crypto.generate_keypair()
    salt = os.urandom(crypto.SALT_BYTES)
    kek = crypto.derive_shared_key(ephemeral_private_pem, recipient_public_key, salt)

    exchange = models.KeyExchange(
        document_id=document.id,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_public_key=recipient_public_key.strip(),
        recipient_fingerprint=fingerprint,
        ephemeral_public_key=ephemeral_public_pem,
        salt=crypto.b64(salt),
        wrapped_key=crypto.b64(
            crypto.wrap_key(kek, dek, exchange_aad(token, fingerprint))
        ),
    )
    db.add(exchange)
    db.commit()
    db.refresh(exchange)
    return exchange


def unwrap_shared_key(
    *,
    token: str,
    recipient_fingerprint: str,
    ephemeral_public_key: str,
    salt_b64: str,
    wrapped_key_b64: str,
    recipient_private_pem: str,
) -> bytes:
    """Recipient side: re-derive the KEK from the ephemeral public key and unwrap.

    The server cannot do this - it needs the recipient's private key. The CLI
    uses it to show a real end-to-end exchange.
    """
    kek = crypto.derive_shared_key(
        recipient_private_pem, ephemeral_public_key, crypto.unb64(salt_b64)
    )
    return crypto.unwrap_key(
        kek,
        crypto.unb64(wrapped_key_b64),
        exchange_aad(token, recipient_fingerprint),
    )
