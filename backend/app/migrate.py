"""One-shot setup: create tables, generate the service keys and seal old uploads."""

from . import models, signing, vault
from .database import Base, SessionLocal, engine


def run() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(models.SigningKey).count() == 0:
            db.add(models.SigningKey(**signing.generate_signing_material()))
            db.commit()

        # Master key for envelope encryption (created once, kept across runs).
        vault.ensure_master_key(db)

        # Uploads made before encryption existed get sealed so at-rest
        # encryption is not optional. Re-running is a no-op.
        sealed = vault.encrypt_legacy_documents(db)
        if sealed:
            print(f"Encrypted {sealed} previously unencrypted document(s).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Database ready.")
