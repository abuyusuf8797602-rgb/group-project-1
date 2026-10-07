"""Key exchange and ciphertext endpoints for encrypted documents.

All routes stay behind the document's signing token: the ciphertext is private
and only useful together with a wrapped data key.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import schemas, storage, vault
from ..database import get_db
from .documents import get_document_by_token

router = APIRouter(prefix="/api/documents/{token}", tags=["encryption"])


def _master_key(db: Session) -> bytes:
    try:
        return vault.get_master_key(db)
    except vault.MasterKeyMissing:
        raise HTTPException(status_code=503, detail="Service encryption key is not initialised")


@router.get("/key-exchange", response_model=schemas.KeyExchangeOut)
def get_key_exchange(token: str, db: Session = Depends(get_db)):
    document = get_document_by_token(token, db)
    if document.key_exchange is None:
        raise HTTPException(status_code=404, detail="No key exchange for this document")
    return document.key_exchange


@router.post("/key-exchange", response_model=schemas.KeyExchangeOut, status_code=201)
def create_key_exchange(
    token: str, payload: schemas.KeyExchangeRequest, db: Session = Depends(get_db)
):
    document = get_document_by_token(token, db)
    if document.key_exchange is not None:
        raise HTTPException(
            status_code=409, detail="This document has already been shared with a recipient"
        )

    try:
        return vault.create_exchange(
            db,
            document,
            payload.recipient_name.strip(),
            str(payload.recipient_email),
            payload.recipient_public_key,
            _master_key(db),
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="recipient_public_key must be a PEM-encoded X25519 public key",
        )
    except vault.MasterKeyMissing as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.get("/ciphertext")
def download_ciphertext(token: str, db: Session = Depends(get_db)):
    """The AES-256-GCM envelope exactly as stored, for a key-holding recipient."""
    document = get_document_by_token(token, db)
    if document.document_key is None:
        raise HTTPException(status_code=409, detail="This document is not stored encrypted")
    safe_name = document.filename.replace('"', "").replace("\n", " ")
    return Response(
        content=storage.read(token),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.enc"'},
    )
