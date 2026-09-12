"""Auditoría automática vía event listeners de SQLAlchemy.

Requisito transversal 6: toda creación, edición y eliminación en cualquier
tabla queda registrada en `auditoria` con los datos antes/después en JSON.

Reglas (Chat 4 + enmienda A2):
- Se configura una sola vez y aplica a todas las tablas.
- Única excepción técnica: la propia tabla `auditoria` no se audita a sí
  misma (auditar la auditoría generaría registros en cadena sin fin).
- Los campos cifrados de `credenciales` se registran como "[cifrado]",
  nunca con el valor (ni cifrado ni en claro).
- Los intentos fallidos de login se registran con accion = `login_fallido`
  (los escribe el servicio de autenticación, no un listener).
"""

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import event, inspect, select

# Nota: los modelos se importan DENTRO de las funciones (y no acá arriba)
# para evitar una importación circular: `app/models/__init__.py` importa
# este módulo para activar la auditoría, y este módulo necesita los modelos.

# Campos que jamás se registran con su valor real en la auditoría.
CAMPOS_ENMASCARADOS: dict[str, list[str]] = {
    "credenciales": ["usuario", "password", "notas"],
}

# Tablas excluidas de los listeners (solo la propia auditoría).
TABLAS_SIN_AUDITORIA = {"auditoria"}

# Evita registrar los listeners dos veces (por ejemplo, en tests).
_configurada = False


def _valor_serializable(valor):
    """Convierte un valor de columna a algo representable en JSON."""
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, Enum):
        return valor.value
    return valor  # str, int, float, bool o None


def _snapshot_actual(target) -> dict:
    """Diccionario con los valores actuales de todas las columnas del objeto."""
    mapper = inspect(target).mapper
    return {
        attr.key: _valor_serializable(getattr(target, attr.key))
        for attr in mapper.column_attrs
    }


def _snapshot_anterior(connection, mapper, target) -> dict | None:
    """Valores de la fila ANTES del update en curso.

    Se lee la fila directamente de la base usando la conexión del flush:
    el UPDATE todavía no se ejecutó, así que lo que hay en la base son
    exactamente los valores previos. (El historial en memoria de SQLAlchemy
    no sirve acá: si el objeto viene de un commit anterior está "expirado"
    y el valor viejo ya no se conoce.)
    """
    tabla = mapper.local_table
    fila = (
        connection.execute(select(tabla).where(tabla.c.id == target.id))
        .mappings()
        .first()
    )
    if fila is None:
        return None
    return {clave: _valor_serializable(valor) for clave, valor in fila.items()}


def _enmascarar(tabla: str, datos: dict | None) -> dict | None:
    """Reemplaza los campos sensibles por "[cifrado]" (si tienen valor)."""
    if datos is None or tabla not in CAMPOS_ENMASCARADOS:
        return datos
    for campo in CAMPOS_ENMASCARADOS[tabla]:
        if datos.get(campo) is not None:
            datos[campo] = "[cifrado]"
    return datos


def _registrar(connection, tabla: str, registro_id: int, accion: str,
               datos_antes: dict | None, datos_despues: dict | None):
    """Inserta la fila de auditoría usando la conexión del flush en curso.

    Se usa la conexión directamente (SQL Core, no ORM) para que este insert
    no dispare a su vez los listeners.
    """
    from app.models.base import ahora_montevideo
    from app.models.sistema import Auditoria

    datos_antes = _enmascarar(tabla, datos_antes)
    datos_despues = _enmascarar(tabla, datos_despues)
    connection.execute(
        Auditoria.__table__.insert().values(
            fecha=ahora_montevideo(),
            tabla=tabla,
            registro_id=registro_id,
            accion=accion,
            datos_antes=json.dumps(datos_antes, ensure_ascii=False)
            if datos_antes is not None else None,
            datos_despues=json.dumps(datos_despues, ensure_ascii=False)
            if datos_despues is not None else None,
        )
    )


def _despues_de_insertar(mapper, connection, target):
    _registrar(
        connection, target.__tablename__, target.id, "creacion",
        datos_antes=None, datos_despues=_snapshot_actual(target),
    )


def _antes_de_actualizar(mapper, connection, target):
    """Captura los valores previos antes de que se ejecute el UPDATE."""
    target._auditoria_datos_antes = _snapshot_anterior(connection, mapper, target)


def _despues_de_actualizar(mapper, connection, target):
    antes = getattr(target, "_auditoria_datos_antes", None)
    if antes is None:
        return
    del target._auditoria_datos_antes
    despues = _snapshot_actual(target)
    if antes == despues:
        return  # flush sin cambios reales: no se audita
    _registrar(
        connection, target.__tablename__, target.id, "edicion",
        datos_antes=antes, datos_despues=despues,
    )


def _despues_de_borrar(mapper, connection, target):
    _registrar(
        connection, target.__tablename__, target.id, "eliminacion",
        datos_antes=_snapshot_actual(target), datos_despues=None,
    )


def configurar_auditoria():
    """Registra los listeners en todos los modelos (una sola vez)."""
    from app.models.base import Base

    global _configurada
    if _configurada:
        return
    for mapper in Base.registry.mappers:
        modelo = mapper.class_
        if modelo.__tablename__ in TABLAS_SIN_AUDITORIA:
            continue
        event.listen(modelo, "after_insert", _despues_de_insertar)
        event.listen(modelo, "before_update", _antes_de_actualizar)
        event.listen(modelo, "after_update", _despues_de_actualizar)
        event.listen(modelo, "after_delete", _despues_de_borrar)
    _configurada = True
