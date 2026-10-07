from fastapi import FastAPI

from .routers import documents, encryption, verification

app = FastAPI(title="Group Project 1 - Document Signing and Verification")

app.include_router(documents.router)
app.include_router(encryption.router)
app.include_router(verification.router)
