from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema() -> None:
    """Apply small forward-compatible schema changes for existing databases."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "users" not in tables and "batches" not in tables:
        return

    statements = []
    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "terms_accepted" not in user_columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN terms_accepted "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )

    if "batches" in tables:
        batch_columns = {column["name"] for column in inspector.get_columns("batches")}
        if "category" not in batch_columns:
            statements.append(
                "ALTER TABLE batches ADD COLUMN category "
                "VARCHAR(20) NOT NULL DEFAULT 'CEBA_INTENSIVA'"
            )

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
