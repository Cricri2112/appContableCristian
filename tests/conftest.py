"""Fixtures compartidas: base SQLite temporal y cliente de pruebas.

Los tests nunca tocan la base real (`estudio.db`): cada test corre contra
un archivo SQLite temporal que se descarta al terminar.
"""

import os
import tempfile
from pathlib import Path

import pytest

# La configuración se define ANTES de importar la app: los tests no dependen
# del .env local.
os.environ["SECRET_KEY"] = "secreto-solo-para-tests"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, UsuarioLogin
from app.services.autenticacion import hashear_password


@pytest.fixture
def db_temporal():
    """Sesión de SQLAlchemy sobre una base SQLite temporal con el esquema creado.

    La limpieza cierra sesión y engine ANTES de borrar el directorio:
    Windows no permite borrar un archivo SQLite con conexiones abiertas.
    """
    directorio = tempfile.TemporaryDirectory()
    try:
        ruta_db = Path(directorio.name) / "test.db"
        engine = create_engine(
            f"sqlite:///{ruta_db}", connect_args={"check_same_thread": False}
        )
        try:
            Base.metadata.create_all(engine)
            Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            sesion = Sesion()
            try:
                yield sesion
            finally:
                sesion.close()
        finally:
            engine.dispose()
    finally:
        directorio.cleanup()


@pytest.fixture
def cliente_web(db_temporal):
    """Cliente de pruebas de FastAPI usando la base temporal.

    base_url con https: la cookie de sesión lleva la marca `Secure` y el
    cliente de pruebas no la enviaría sobre http.
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def get_db_de_prueba():
        yield db_temporal

    app.dependency_overrides[get_db] = get_db_de_prueba
    with TestClient(app, base_url="https://testserver") as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def sesion(cliente_web, usuario_de_prueba):
    """Cliente de pruebas con la sesión ya iniciada."""
    respuesta = cliente_web.post(
        "/login",
        data={"usuario": "contador", "password": "clave-correcta"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return cliente_web


@pytest.fixture
def usuario_de_prueba(db_temporal):
    """Usuario único de la app, con contraseña conocida por los tests."""
    usuario = UsuarioLogin(
        usuario="contador",
        password_hash=hashear_password("clave-correcta"),
    )
    db_temporal.add(usuario)
    db_temporal.commit()
    return usuario
