"""Criterio de terminado 1 de la Etapa 0: `alembic upgrade head` sobre base
vacía crea el esquema completo. Eran 16 tablas; la Etapa 6 sumó
`configuracion` (email de destino del resumen diario), total 17."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

TABLAS_ESPERADAS = {
    "clientes",
    "clientes_regimen_historial",
    "servicios",
    "servicios_contratados",
    "honorarios_historial",
    "cobros",
    "descuentos",
    "credenciales",
    "tarea_templates",
    "tareas",
    "recordatorios",
    "vencimientos_calendario",
    "gastos_ingresos_propios",
    "auditoria",
    "scheduler_ejecuciones",
    "usuario_login",
    "configuracion",
}

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


def test_migraciones_crean_todas_las_tablas(monkeypatch):
    with tempfile.TemporaryDirectory() as directorio:
        url = f"sqlite:///{directorio}/migracion.db"

        # env.py lee la URL de la configuración de la app; se apunta a la temporal.
        from app.config import settings
        monkeypatch.setattr(settings, "database_url", url)

        config = Config(str(RAIZ_PROYECTO / "alembic.ini"))
        config.set_main_option("script_location", str(RAIZ_PROYECTO / "alembic"))
        command.upgrade(config, "head")

        # try/finally: el engine se libera SIEMPRE (aunque un assert falle)
        # antes de salir del `with`, porque Windows no puede borrar el
        # directorio temporal si el archivo SQLite sigue en uso.
        engine = create_engine(url)
        try:
            tablas = set(inspect(engine).get_table_names())

            assert TABLAS_ESPERADAS <= tablas, (
                f"Faltan tablas: {TABLAS_ESPERADAS - tablas}"
            )
            assert len(TABLAS_ESPERADAS) == 17
        finally:
            engine.dispose()


def test_esquema_de_modelos_coincide_con_las_migraciones():
    """Los modelos SQLAlchemy definen exactamente las mismas tablas."""
    from app.models import Base

    assert set(Base.metadata.tables.keys()) == TABLAS_ESPERADAS
