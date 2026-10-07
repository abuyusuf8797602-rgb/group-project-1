"""One-shot setup: create tables and generate the service signing material."""

from . import models, signing
from .database import Base, SessionLocal, engine


def run() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(models.SigningKey).count() == 0:
            db.add(models.SigningKey(**signing.generate_signing_material()))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Database ready.")
