"""Conexión a la base de datos y manejo de sesiones de SQLAlchemy."""

from fastapi import Request
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


def get_db(request: Request):
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar.

    La sesión también queda en `request.state.db` para que el cascarón
    pueda mostrar el progreso de tareas del menú lateral (hallazgo H-02).
    """
    db = SessionLocal()
    request.state.db = db
    try:
        yield db
    finally:
        db.close()
