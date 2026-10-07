from fastapi import FastAPI

from .routers import documents, verification

app = FastAPI(title="Group Project 1 - Document Signing and Verification")

app.include_router(documents.router)
app.include_router(verification.router)
