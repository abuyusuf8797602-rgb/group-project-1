"""Cryptographic primitives used by the signing service.

Everything here is built on the `cryptography` library only, and each primitive
is used the way its designers intend:

Confidentiality + integrity (AEAD)
    AES-256-GCM. A fresh 96-bit nonce comes from the OS CSPRNG for every single
    encryption, and every document gets a brand-new 256-bit key, so a nonce is
    never reused with the same key. GCM's authentication tag protects the
    ciphertext, and the optional ``aad`` binds public context (which document,
    which recipient) into that tag - a wrapped key cannot be replayed onto a
    different document.

Key agreement
    X25519 (ECDH) between a fresh ephemeral keypair and the recipient's public
    key. The raw ECDH output is never used as a key: it is run through
    HKDF-SHA256 with a random salt and a fixed ``info`` string, which is the
    correct way to turn a Diffie-Hellman secret into key material.

Key material
    All keys and nonces come from the OS CSPRNG (``os.urandom`` /
    ``AESGCM.generate_key``). No key is derived from a password, and the
    library's tag comparison is constant time.

Document framing
    ``seal_document``/``unseal_document`` wrap a payload as
    ``MAGIC || version || nonce || ciphertext || tag`` so a stored file is
    self-describing and tampering with the header is detected rather than
    silently misparsed.
"""

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # 96 bits: the nonce size GCM is specified for
TAG_BYTES = 16
SALT_BYTES = 32

MAGIC = b"B44DOC1"
VERSION = 1

HKDF_INFO = b"b44/document-key-exchange/v1"

__all__ = [
    "InvalidTag",
    "KEY_BYTES",
    "NONCE_BYTES",
    "SALT_BYTES",
    "MAGIC",
    "new_key",
    "encrypt",
    "decrypt",
    "wrap_key",
    "unwrap_key",
    "b64",
    "unb64",
    "sha256_hex",
    "generate_keypair",
    "public_key_from_private",
    "derive_shared_key",
    "fingerprint",
    "seal_document",
    "unseal_document",
]


def new_key() -> bytes:
    """A fresh 256-bit key from the OS CSPRNG."""
    return AESGCM.generate_key(bit_length=KEY_BYTES * 8)


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """AES-256-GCM encrypt. Returns ``nonce || ciphertext || tag``."""
    if len(key) != KEY_BYTES:
        raise ValueError("AES-256-GCM needs a 32 byte key")
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """AES-256-GCM decrypt.

    Raises ``InvalidTag`` if the key is wrong or the ciphertext, tag or
    associated data has been altered - the caller never sees unauthenticated
    plaintext.
    """
    if len(key) != KEY_BYTES:
        raise ValueError("AES-256-GCM needs a 32 byte key")
    if len(blob) < NONCE_BYTES + TAG_BYTES:
        raise InvalidTag("ciphertext is truncated")
    return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad)


def wrap_key(kek: bytes, key: bytes, aad: bytes = b"") -> bytes:
    """Wrap (encrypt) key material with a key-encryption key."""
    return encrypt(kek, key, aad)


def unwrap_key(kek: bytes, wrapped: bytes, aad: bytes = b"") -> bytes:
    """Unwrap key material produced by :func:`wrap_key`."""
    key = decrypt(kek, wrapped, aad)
    if len(key) != KEY_BYTES:
        raise InvalidTag("wrapped key has the wrong size")
    return key


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def unb64(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_keypair() -> tuple[str, str]:
    """A fresh X25519 keypair as ``(private_pem, public_pem)``."""
    private_key = X25519PrivateKey.generate()
    return _private_pem(private_key), _public_pem(private_key.public_key())


def public_key_from_private(private_pem: str) -> str:
    return _public_pem(_load_private(private_pem).public_key())


def derive_shared_key(private_pem: str, peer_public_pem: str, salt: bytes) -> bytes:
    """X25519 ECDH + HKDF-SHA256 -> a 32 byte key both sides can compute.

    The ECDH result is key material, not a key: HKDF expands it with the
    caller's random salt so the derived key is bound to this exchange.
    """
    shared_secret = _load_private(private_pem).exchange(
        _load_x25519_public(peer_public_pem)
    )
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=salt,
        info=HKDF_INFO,
    ).derive(shared_secret)


def fingerprint(public_pem: str) -> str:
    """SHA-256 of the DER public key - a short id for the key itself."""
    der = _load_x25519_public(public_pem).public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def seal_document(data: bytes, key: bytes) -> bytes:
    """Frame a document as an authenticated encrypted envelope."""
    return MAGIC + bytes([VERSION]) + encrypt(key, data)


def unseal_document(blob: bytes, key: bytes) -> tuple[bytes, bool]:
    """Open an envelope produced by :func:`seal_document`.

    Returns ``(plaintext, was_encrypted)``. Bytes that do not carry the magic
    header are returned unchanged with ``was_encrypted = False`` so uploads
    stored before encryption existed stay readable.
    """
    if not blob.startswith(MAGIC):
        return blob, False
    if len(blob) <= len(MAGIC) + 1 or blob[len(MAGIC)] != VERSION:
        raise ValueError("unsupported document envelope version")
    return decrypt(key, blob[len(MAGIC) + 1 :]), True


def _private_pem(private_key) -> str:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _public_pem(public_key) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def _load_private(private_pem: str):
    return serialization.load_pem_private_key(private_pem.encode(), password=None)


def _load_public(public_pem: str):
    return serialization.load_pem_public_key(public_pem.encode())


def _load_x25519_public(public_pem: str) -> X25519PublicKey:
    """Load a public key, refusing anything that is not X25519.

    Raises ValueError (not a bare TypeError from inside the library) so callers
    can turn a bad recipient key into a clean 400.
    """
    public_key = _load_public(public_pem)
    if not isinstance(public_key, X25519PublicKey):
        raise ValueError("expected an X25519 public key")
    return public_key
