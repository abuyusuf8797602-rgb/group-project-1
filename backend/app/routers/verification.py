from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, signing
from ..database import get_db

router = APIRouter(prefix="/api/verify", tags=["verification"])


@router.post("", response_model=schemas.VerificationResult)
async def verify_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    digest = signing.sha256_hex(data)
    filename = file.filename or "document"

    document = db.execute(
        select(models.Document).where(models.Document.sha256 == digest)
    ).scalars().first()

    if document is None or document.signature is None:
        return schemas.VerificationResult(
            filename=filename, file_sha256=digest, matched=False
        )

    signature = document.signature
    key = db.execute(
        select(models.SigningKey).order_by(models.SigningKey.id)
    ).scalars().first()

    certificate = signing.certificate_info(signature.certificate_pem)
    checks = [
        schemas.LayerCheck(
            name="Document hash",
            passed=digest == signature.signed_sha256,
            detail=f"SHA-256 {digest}",
        ),
        schemas.LayerCheck(
            name="Acknowledgement",
            passed=True,
            detail=(
                f"Signed by {signature.signer_name} <{signature.signer_email}> "
                f"at {signature.signed_at.isoformat()}Z"
            ),
        ),
        schemas.LayerCheck(
            name="HMAC signature",
            passed=signing.verify_hmac(key.hmac_secret, digest, signature.hmac_signature),
            detail="Service keyed signature matches",
        ),
        schemas.LayerCheck(
            name="X.509 signature",
            passed=signing.verify_rsa(
                signature.certificate_pem, digest, signature.rsa_signature
            ),
            detail="RSA signature matches",
        ),
        schemas.LayerCheck(
            name="Certificate",
            passed=not certificate["expired"],
            detail=(
                f"{certificate['subject']} (valid until "
                f"{certificate['not_valid_after']})"
            ),
        ),
    ]

    return schemas.VerificationResult(
        filename=filename,
        file_sha256=digest,
        matched=True,
        verified=all(check.passed for check in checks),
        document=schemas.DocumentOut.model_validate(document),
        signature=schemas.SignatureOut.model_validate(signature),
        checks=checks,
    )
