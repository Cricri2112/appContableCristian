"""Conexión a la base de datos y manejo de sesiones de SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# check_same_thread=False: FastAPI puede atender cada request en un hilo
# distinto; SQLite por defecto no lo permite y hay que habilitarlo.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
