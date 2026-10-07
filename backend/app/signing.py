"""Cryptographic helpers for the document signing service.

Every signature is built from the same SHA-256 document hash and carries three
layers:

* an acknowledgement record  - signer name/email/time, stored on the row
* an HMAC-SHA256 signature   - keyed with the service's secret, so the service
                               can detect any change to the document
* an RSA (X.509) signature   - verifiable by anyone holding the certificate
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

SERVICE_COMMON_NAME = "Group Project 1 Document Signing Service"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_signing_material() -> dict:
    """Create the service keypair, self-signed certificate and HMAC secret."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, SERVICE_COMMON_NAME),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Group Project 1"),
        ]
    )
    now = datetime.now(timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    return {
        "private_key_pem": private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
        "certificate_pem": certificate.public_bytes(serialization.Encoding.PEM).decode(),
        "hmac_secret": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    }


def sign_hmac(secret: str, document_hash: str) -> str:
    return hmac.new(secret.encode(), document_hash.encode(), hashlib.sha256).hexdigest()


def verify_hmac(secret: str, document_hash: str, signature: str) -> bool:
    return hmac.compare_digest(sign_hmac(secret, document_hash), signature)


def sign_rsa(private_key_pem: str, document_hash: str) -> str:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None
    )
    signature = private_key.sign(
        document_hash.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    return base64.b64encode(signature).decode()


def verify_rsa(certificate_pem: str, document_hash: str, signature_b64: str) -> bool:
    certificate = x509.load_pem_x509_certificate(certificate_pem.encode())
    try:
        certificate.public_key().verify(
            base64.b64decode(signature_b64),
            document_hash.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception:
        return False
    return True


def certificate_info(certificate_pem: str) -> dict:
    certificate = x509.load_pem_x509_certificate(certificate_pem.encode())
    return {
        "subject": certificate.subject.rfc4514_string(),
        "serial_number": str(certificate.serial_number),
        "not_valid_after": certificate.not_valid_after_utc.isoformat(),
        "expired": certificate.not_valid_after_utc < datetime.now(timezone.utc),
    }
