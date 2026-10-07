import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, signing, storage
from ..database import get_db

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_document(token: str, db: Session) -> models.Document:
    document = db.execute(
        select(models.Document).where(models.Document.token == token)
    ).scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _signing_key(db: Session) -> models.SigningKey:
    key = db.execute(
        select(models.SigningKey).order_by(models.SigningKey.id)
    ).scalars().first()
    if key is None:
        raise HTTPException(status_code=503, detail="Signing key is not initialised")
    return key


@router.get("", response_model=list[schemas.DocumentDetail])
def list_documents(db: Session = Depends(get_db)):
    return db.execute(
        select(models.Document).order_by(
            models.Document.created_at.desc(), models.Document.id.desc()
        )
    ).scalars().all()


@router.post("", response_model=schemas.DocumentDetail, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(data) > storage.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than {storage.MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    token = secrets.token_urlsafe(24)
    storage.save(token, data)

    document = models.Document(
        token=token,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        sha256=signing.sha256_hex(data),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{token}", response_model=schemas.DocumentDetail)
def get_document(token: str, db: Session = Depends(get_db)):
    return _get_document(token, db)


@router.get("/{token}/download")
def download_document(token: str, db: Session = Depends(get_db)):
    document = _get_document(token, db)
    safe_name = document.filename.replace('"', "").replace("\n", " ")
    return Response(
        content=storage.read(token),
        media_type=document.content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/{token}/sign", response_model=schemas.SignatureOut, status_code=201)
def sign_document(
    token: str,
    payload: schemas.SignRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    document = _get_document(token, db)
    if document.signature is not None:
        raise HTTPException(status_code=409, detail="This document has already been signed")

    key = _signing_key(db)

    signature = models.Signature(
        document_id=document.id,
        signer_name=payload.name.strip(),
        signer_email=str(payload.email),
        signer_ip=request.client.host if request.client else None,
        signed_sha256=document.sha256,
        hmac_signature=signing.sign_hmac(key.hmac_secret, document.sha256),
        rsa_signature=signing.sign_rsa(key.private_key_pem, document.sha256),
        certificate_pem=key.certificate_pem,
    )
    db.add(signature)
    db.commit()
    db.refresh(signature)
    return signature
