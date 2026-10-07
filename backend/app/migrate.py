"""One-shot setup: create tables and seed a couple of starter rows."""

from . import models
from .database import Base, SessionLocal, engine


def run() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(models.Item).count() == 0:
            db.add_all(
                [
                    models.Item(
                        title="Welcome to Group Project 1",
                        description="This row was seeded into Postgres on first boot.",
                    ),
                    models.Item(
                        title="Try it out",
                        description="Add an item below, then delete it — the data lives in Postgres.",
                    ),
                ]
            )
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Database ready.")
