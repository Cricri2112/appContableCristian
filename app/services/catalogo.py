"""F3 — Catálogo de servicios (Chat 3).

Toda la lógica de negocio del catálogo: listado ordenado, alta, edición
con restricción de frecuencia, desactivar/reactivar. Sin eliminación física.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Servicio, ServicioContratado
from app.services.errores import ErrorValidacion


def listar_servicios(db: Session) -> list[dict]:
    """Todos los servicios (activos e inactivos), con sus contratos activos.

    Orden del Chat 3: frecuencia ascendente y luego nombre ascendente.
    """
    servicios = (
        db.query(Servicio)
        .order_by(Servicio.frecuencia.asc(), Servicio.nombre.asc())
        .all()
    )
    # Contratos activos por servicio, en una sola consulta.
    conteos = dict(
        db.query(
            ServicioContratado.servicio_id,
            func.count(ServicioContratado.id),
        )
        .filter(ServicioContratado.activo.is_(True))
        .group_by(ServicioContratado.servicio_id)
        .all()
    )
    return [
        {"servicio": s, "contratos_activos": conteos.get(s.id, 0)}
        for s in servicios
    ]


def obtener_servicio(db: Session, servicio_id: int) -> Servicio | None:
    return db.get(Servicio, servicio_id)


def _validar_nombre(db: Session, nombre: str, excluir_id: int | None) -> dict:
    """Nombre no vacío y único entre todos (activos e inactivos)."""
    errores = {}
    if not nombre.strip():
        errores["nombre"] = "El nombre no puede estar vacío."
        return errores
    consulta = db.query(Servicio).filter(Servicio.nombre == nombre.strip())
    if excluir_id is not None:
        consulta = consulta.filter(Servicio.id != excluir_id)
    if consulta.first() is not None:
        errores["nombre"] = "Ya existe un servicio con ese nombre."
    return errores


def crear_servicio(db: Session, nombre: str, frecuencia: str) -> Servicio:
    errores = _validar_nombre(db, nombre, excluir_id=None)
    if errores:
        raise ErrorValidacion(errores)

    servicio = Servicio(nombre=nombre.strip(), frecuencia=frecuencia, activo=True)
    db.add(servicio)
    db.commit()
    return servicio


def tiene_contratos_activos(db: Session, servicio_id: int) -> bool:
    return (
        db.query(ServicioContratado)
        .filter(
            ServicioContratado.servicio_id == servicio_id,
            ServicioContratado.activo.is_(True),
        )
        .first()
        is not None
    )


def editar_servicio(
    db: Session, servicio_id: int, nombre: str, frecuencia: str
) -> Servicio:
    servicio = db.get(Servicio, servicio_id)
    errores = _validar_nombre(db, nombre, excluir_id=servicio_id)

    # Restricción del Chat 3: con contratos activos no se cambia la frecuencia.
    cambia_frecuencia = frecuencia != servicio.frecuencia.value
    if cambia_frecuencia and tiene_contratos_activos(db, servicio_id):
        errores["frecuencia"] = (
            "No se puede cambiar la frecuencia de un servicio con contratos activos."
        )
    if errores:
        raise ErrorValidacion(errores)

    servicio.nombre = nombre.strip()
    servicio.frecuencia = frecuencia
    db.commit()
    return servicio


def cambiar_activo(db: Session, servicio_id: int) -> Servicio:
    """Desactivar/reactivar: un clic, sin confirmación, reversible."""
    servicio = db.get(Servicio, servicio_id)
    servicio.activo = not servicio.activo
    db.commit()
    return servicio
