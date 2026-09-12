"""F4 — Servicios contratados por cliente (Chat 3 + adenda B2).

Contratar (con primer honorario del historial), editar fecha de inicio,
finalizar. La generación de tareas al contratar queda como función vacía:
punto de integración diferido a la Etapa 5 (Chat 5).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Cobro,
    HonorarioHistorial,
    Servicio,
    ServicioContratado,
    Tarea,
)
from app.models.base import ahora_montevideo
from app.services.errores import ErrorValidacion
from app.services.importes import parsear_importe

# Orden de presentación por frecuencia (Chat 3): mensual → anual → único.
ORDEN_FRECUENCIA = {"mensual": 0, "anual": 1, "unico": 2}


def hoy() -> date:
    return ahora_montevideo().date()


def listar_contratos(
    db: Session, cliente_id: int, incluir_finalizados: bool = False
) -> list[dict]:
    """Contratos del cliente con su servicio y honorario vigente.

    Orden: frecuencia (mensual → anual → único), luego fecha_inicio
    descendente. Con la adenda B2, el toggle suma los finalizados
    (solo lectura, con su fecha_fin).
    """
    consulta = (
        db.query(ServicioContratado, Servicio)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(ServicioContratado.cliente_id == cliente_id)
    )
    if not incluir_finalizados:
        consulta = consulta.filter(ServicioContratado.activo.is_(True))

    filas = [
        {
            "contrato": contrato,
            "servicio": servicio,
            # Activo: honorario vigente. Finalizado: el último honorario
            # (quedó cerrado al finalizar), según la adenda B2.
            "honorario_vigente": honorario_vigente(db, contrato.id)
            or _ultimo_honorario(db, contrato.id),
        }
        for contrato, servicio in consulta.all()
    ]
    filas.sort(
        key=lambda f: (
            ORDEN_FRECUENCIA[f["servicio"].frecuencia.value],
            # fecha_inicio descendente: se invierte con el ordinal negativo
            -f["contrato"].fecha_inicio.toordinal(),
        )
    )
    return filas


def contar_contratos(db: Session, cliente_id: int) -> dict:
    """Cantidad de contratos activos y finalizados (para pestañas y toggle)."""
    contratos = (
        db.query(ServicioContratado)
        .filter(ServicioContratado.cliente_id == cliente_id)
        .all()
    )
    activos = sum(1 for c in contratos if c.activo)
    return {"activos": activos, "finalizados": len(contratos) - activos}


def obtener_contrato(db: Session, contrato_id: int) -> ServicioContratado | None:
    return db.get(ServicioContratado, contrato_id)


def honorario_vigente(db: Session, contrato_id: int) -> Decimal | None:
    """Registro de honorarios_historial con fecha_hasta = null."""
    registro = (
        db.query(HonorarioHistorial)
        .filter(
            HonorarioHistorial.servicio_contratado_id == contrato_id,
            HonorarioHistorial.fecha_hasta.is_(None),
        )
        .first()
    )
    return registro.honorario if registro else None


def _ultimo_honorario(db: Session, contrato_id: int) -> Decimal | None:
    """Honorario más reciente de un contrato, vigente o cerrado."""
    registro = (
        db.query(HonorarioHistorial)
        .filter(HonorarioHistorial.servicio_contratado_id == contrato_id)
        .order_by(HonorarioHistorial.fecha_desde.desc())
        .first()
    )
    return registro.honorario if registro else None


def _parsear_honorario(honorario_texto: str) -> tuple[Decimal | None, str | None]:
    """Convierte el texto del formulario a Decimal (formato local)."""
    return parsear_importe(honorario_texto, "honorario")


def contratar(
    db: Session,
    cliente_id: int,
    servicio_id: int | None,
    fecha_inicio: date | None,
    honorario_texto: str,
) -> ServicioContratado:
    errores = {}

    servicio = db.get(Servicio, servicio_id) if servicio_id else None
    if servicio is None or not servicio.activo:
        errores["servicio_id"] = "Elegí un servicio."

    if fecha_inicio is None:
        errores["fecha_inicio"] = "Ingresá la fecha de inicio."
    elif fecha_inicio > hoy():
        errores["fecha_inicio"] = "La fecha de inicio no puede ser futura."

    honorario, error_honorario = _parsear_honorario(honorario_texto)
    if error_honorario:
        errores["honorario"] = error_honorario

    # Mensual/anual: no puede haber otro contrato activo del mismo servicio.
    # Único: sin restricción de duplicados.
    if servicio is not None and servicio.frecuencia.value in ("mensual", "anual"):
        duplicado = (
            db.query(ServicioContratado)
            .filter(
                ServicioContratado.cliente_id == cliente_id,
                ServicioContratado.servicio_id == servicio.id,
                ServicioContratado.activo.is_(True),
            )
            .first()
        )
        if duplicado is not None:
            errores["servicio_id"] = "El cliente ya tiene ese servicio contratado activo."

    if errores:
        raise ErrorValidacion(errores)

    contrato = ServicioContratado(
        cliente_id=cliente_id,
        servicio_id=servicio.id,
        fecha_inicio=fecha_inicio,
        fecha_fin=None,
        activo=True,
    )
    db.add(contrato)
    db.flush()  # asigna el id para el historial de honorarios

    # Primer registro del historial de honorarios (F4 → F6).
    db.add(
        HonorarioHistorial(
            servicio_contratado_id=contrato.id,
            honorario=honorario,
            fecha_desde=fecha_inicio,
            fecha_hasta=None,
        )
    )

    generar_tareas_al_contratar(db, contrato)
    db.commit()
    return contrato


def generar_tareas_al_contratar(db: Session, contrato: ServicioContratado) -> None:
    """Punto de integración diferido (Chat 5, E2 → E5).

    En la Etapa 5 acá se generan las tareas según F7: mensual a mitad de
    mes genera el período en curso; único genera desde templates si
    existen; anual no genera al contratar. Por ahora no hace nada.
    """


def puede_editar_fecha_inicio(db: Session, contrato_id: int) -> bool:
    """Solo si el contrato no tiene tareas ni cobros asociados (F4)."""
    tiene_tareas = (
        db.query(Tarea).filter(Tarea.servicio_contratado_id == contrato_id).first()
        is not None
    )
    tiene_cobros = (
        db.query(Cobro).filter(Cobro.servicio_contratado_id == contrato_id).first()
        is not None
    )
    return not (tiene_tareas or tiene_cobros)


def editar_fecha_inicio(
    db: Session, contrato_id: int, nueva_fecha: date | None
) -> ServicioContratado:
    contrato = db.get(ServicioContratado, contrato_id)
    errores = {}

    if not puede_editar_fecha_inicio(db, contrato_id):
        errores["fecha_inicio"] = (
            "No se puede modificar la fecha de inicio porque existen tareas o cobros asociados."
        )
    elif nueva_fecha is None:
        errores["fecha_inicio"] = "Ingresá la fecha de inicio."
    elif nueva_fecha > hoy():
        errores["fecha_inicio"] = "La fecha de inicio no puede ser futura."

    if errores:
        raise ErrorValidacion(errores)

    # El primer honorario se creó con fecha_desde = fecha_inicio del
    # contrato; se mantiene esa correspondencia al corregir la fecha.
    primer_honorario = (
        db.query(HonorarioHistorial)
        .filter(
            HonorarioHistorial.servicio_contratado_id == contrato_id,
            HonorarioHistorial.fecha_desde == contrato.fecha_inicio,
        )
        .first()
    )
    if primer_honorario is not None:
        primer_honorario.fecha_desde = nueva_fecha

    contrato.fecha_inicio = nueva_fecha
    db.commit()
    return contrato


def finalizar(
    db: Session, contrato_id: int, fecha_fin: date | None
) -> ServicioContratado:
    """Finaliza el contrato (Chat 3): fecha_fin, activo=False y cierre del
    honorario vigente. Las tareas pendientes no se tocan; la deuda no se borra."""
    contrato = db.get(ServicioContratado, contrato_id)
    errores = {}

    if fecha_fin is None:
        errores["fecha_fin"] = "Ingresá la fecha de finalización."
    elif fecha_fin < contrato.fecha_inicio:
        errores["fecha_fin"] = (
            "La fecha de finalización no puede ser anterior al inicio del contrato."
        )

    if errores:
        raise ErrorValidacion(errores)

    contrato.fecha_fin = fecha_fin
    contrato.activo = False

    vigente = (
        db.query(HonorarioHistorial)
        .filter(
            HonorarioHistorial.servicio_contratado_id == contrato_id,
            HonorarioHistorial.fecha_hasta.is_(None),
        )
        .first()
    )
    if vigente is not None:
        vigente.fecha_hasta = fecha_fin

    db.commit()
    return contrato
