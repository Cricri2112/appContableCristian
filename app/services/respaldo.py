"""Respaldo diario de la base (Chat 4, decisión 4).

Copia el archivo SQLite a la carpeta RESPALDOS_DIR usando la API de
respaldo de SQLite (copia consistente aunque la app esté escribiendo).

Retención: los respaldos de los últimos 30 días + el primero de cada mes
(histórico mensual). En desarrollo la carpeta es local; el destino externo
real (R2 o B2) se configura en la Etapa 7.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.config import settings
from app.services import fechas

PREFIJO = "estudio-"
DIAS_RETENCION = 30


def _ruta_base() -> Path:
    url = settings.database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("El respaldo automático solo está implementado para SQLite.")
    return Path(url.removeprefix("sqlite:///"))


def _fecha_de(archivo: Path) -> date | None:
    try:
        return date.fromisoformat(archivo.stem.removeprefix(PREFIJO))
    except ValueError:
        return None


def hacer_respaldo(hoy: date | None = None) -> Path:
    """Crea el respaldo del día (lo pisa si ya existía) y aplica la retención."""
    hoy = hoy or fechas.hoy()
    carpeta = Path(settings.respaldos_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{PREFIJO}{hoy.isoformat()}.db"

    origen = sqlite3.connect(_ruta_base())
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()

    aplicar_retencion(carpeta, hoy)
    return destino


def aplicar_retencion(carpeta: Path, hoy: date) -> list[Path]:
    """Borra los respaldos viejos que no hay que conservar. Devuelve los borrados."""
    respaldos = {}
    for archivo in carpeta.glob(f"{PREFIJO}*.db"):
        fecha = _fecha_de(archivo)
        if fecha is not None:
            respaldos[archivo] = fecha

    # El primer respaldo de cada mes se conserva como histórico mensual.
    primeros_del_mes = {}
    for archivo, fecha in respaldos.items():
        clave = (fecha.year, fecha.month)
        if clave not in primeros_del_mes or fecha < respaldos[primeros_del_mes[clave]]:
            primeros_del_mes[clave] = archivo

    limite = hoy - timedelta(days=DIAS_RETENCION)
    borrados = []
    for archivo, fecha in respaldos.items():
        if fecha < limite and archivo not in primeros_del_mes.values():
            archivo.unlink()
            borrados.append(archivo)
    return borrados
