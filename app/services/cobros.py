"""F5 — Registrar, editar y eliminar cobros y descuentos (Chat 3 + C1).

El saldo es derivado (services/cuentas.py), así que "recalcular" es
automático: cualquier alta/edición/baja lo refleja en la próxima consulta.
La eliminación es física, con confirmación en la UI y rastro en `auditoria`.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Cliente, Cobro, Descuento, Servicio, ServicioContratado
from app.models.base import ahora_montevideo
from app.models.enums import FormaPago, TipoComprobante
from app.services.errores import ErrorValidacion
from app.services.importes import parsear_importe


def hoy() -> date:
    return ahora_montevideo().date()


def contratos_activos_del_cliente(db: Session, cliente_id: int) -> list[dict]:
    """Contratos activos para el selector "Servicio contratado"."""
    filas = (
        db.query(ServicioContratado, Servicio)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(
            ServicioContratado.cliente_id == cliente_id,
            ServicioContratado.activo.is_(True),
        )
        .all()
    )
    return [{"contrato": contrato, "servicio": servicio} for contrato, servicio in filas]


def listar_cobros(db: Session, cliente_id: int) -> list[dict]:
    """Cobros del cliente por fecha descendente, con su servicio si tiene."""
    filas = (
        db.query(Cobro, Servicio)
        .outerjoin(
            ServicioContratado, ServicioContratado.id == Cobro.servicio_contratado_id
        )
        .outerjoin(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(Cobro.cliente_id == cliente_id)
        .order_by(Cobro.fecha_cobro.desc(), Cobro.id.desc())
        .all()
    )
    return [{"cobro": cobro, "servicio": servicio} for cobro, servicio in filas]


def listar_descuentos(db: Session, cliente_id: int) -> list[dict]:
    filas = (
        db.query(Descuento, Servicio)
        .outerjoin(
            ServicioContratado,
            ServicioContratado.id == Descuento.servicio_contratado_id,
        )
        .outerjoin(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(Descuento.cliente_id == cliente_id)
        .order_by(Descuento.fecha.desc(), Descuento.id.desc())
        .all()
    )
    return [{"descuento": descuento, "servicio": servicio} for descuento, servicio in filas]


def _parsear_importe(texto: str) -> tuple[Decimal | None, str | None]:
    """El importe llega como texto del formulario ("14.000" o "14.000,50")."""
    return parsear_importe(texto, "importe")


def _validar_datos_cobro(db: Session, datos: dict) -> tuple[dict, dict]:
    """Validaciones de F5 para crear/editar un cobro.

    Devuelve (valores_limpios, errores).
    """
    errores = {}
    limpios = {}

    cliente = db.get(Cliente, datos["cliente_id"]) if datos["cliente_id"] else None
    if cliente is None:
        errores["cliente_id"] = "Elegí un cliente."
    limpios["cliente_id"] = datos["cliente_id"]

    # Servicio contratado: opcional; si viene, debe ser del cliente.
    limpios["servicio_contratado_id"] = None
    if datos["servicio_contratado_id"]:
        contrato = db.get(ServicioContratado, datos["servicio_contratado_id"])
        if contrato is None or contrato.cliente_id != datos["cliente_id"]:
            errores["servicio_contratado_id"] = "Elegí un servicio del cliente."
        else:
            limpios["servicio_contratado_id"] = contrato.id

    # Períodos: van juntos, hasta >= desde (C1: en únicos ambos llevan la
    # fecha real del trabajo y la única validación es hasta >= desde).
    desde, hasta = datos["periodo_desde"], datos["periodo_hasta"]
    if (desde is None) != (hasta is None):
        errores["periodo_desde"] = "Período desde y período hasta van juntos: completá los dos."
    elif desde is not None and hasta < desde:
        errores["periodo_hasta"] = "El período hasta no puede ser anterior al período desde."
    limpios["periodo_desde"], limpios["periodo_hasta"] = desde, hasta

    if datos["fecha_cobro"] is None:
        errores["fecha_cobro"] = "Ingresá la fecha de cobro."
    elif datos["fecha_cobro"] > hoy():
        errores["fecha_cobro"] = "La fecha de cobro no puede ser futura."
    limpios["fecha_cobro"] = datos["fecha_cobro"]

    importe, error_importe = _parsear_importe(datos["importe"])
    if error_importe:
        errores["importe"] = error_importe
    limpios["importe"] = importe

    if datos["forma_pago"] not in [f.value for f in FormaPago]:
        errores["forma_pago"] = "Elegí la forma de pago."
    limpios["forma_pago"] = datos["forma_pago"]

    if datos["tipo_comprobante"] not in [t.value for t in TipoComprobante]:
        errores["tipo_comprobante"] = "Elegí el tipo de comprobante."
    limpios["tipo_comprobante"] = datos["tipo_comprobante"]

    limpios["notas"] = datos["notas"] or None
    return limpios, errores


def registrar_cobro(db: Session, datos: dict) -> Cobro:
    limpios, errores = _validar_datos_cobro(db, datos)
    if errores:
        raise ErrorValidacion(errores)
    cobro = Cobro(**limpios)
    db.add(cobro)
    db.commit()
    return cobro


def editar_cobro(db: Session, cobro_id: int, datos: dict) -> Cobro:
    """Todos los campos son editables (Chat 3)."""
    limpios, errores = _validar_datos_cobro(db, datos)
    if errores:
        raise ErrorValidacion(errores)
    cobro = db.get(Cobro, cobro_id)
    for campo, valor in limpios.items():
        setattr(cobro, campo, valor)
    db.commit()
    return cobro


def eliminar_cobro(db: Session, cobro_id: int) -> None:
    """Eliminación física; el registro queda en auditoria (datos_antes)."""
    cobro = db.get(Cobro, cobro_id)
    db.delete(cobro)
    db.commit()


def _validar_datos_descuento(db: Session, cliente_id: int, datos: dict) -> tuple[dict, dict]:
    errores = {}
    limpios = {"cliente_id": cliente_id}

    limpios["servicio_contratado_id"] = None
    if datos["servicio_contratado_id"]:
        contrato = db.get(ServicioContratado, datos["servicio_contratado_id"])
        if contrato is None or contrato.cliente_id != cliente_id:
            errores["servicio_contratado_id"] = "Elegí un servicio del cliente."
        else:
            limpios["servicio_contratado_id"] = contrato.id

    if datos["fecha"] is None:
        errores["fecha"] = "Ingresá la fecha."
    elif datos["fecha"] > hoy():
        errores["fecha"] = "La fecha no puede ser futura."
    limpios["fecha"] = datos["fecha"]

    importe, error_importe = _parsear_importe(datos["importe"])
    if error_importe:
        errores["importe"] = error_importe
    limpios["importe"] = importe

    if not datos["motivo"].strip():
        errores["motivo"] = "Ingresá el motivo."
    limpios["motivo"] = datos["motivo"].strip()

    return limpios, errores


def registrar_descuento(db: Session, cliente_id: int, datos: dict) -> Descuento:
    limpios, errores = _validar_datos_descuento(db, cliente_id, datos)
    if errores:
        raise ErrorValidacion(errores)
    descuento = Descuento(**limpios)
    db.add(descuento)
    db.commit()
    return descuento


def editar_descuento(db: Session, descuento_id: int, datos: dict) -> Descuento:
    descuento = db.get(Descuento, descuento_id)
    limpios, errores = _validar_datos_descuento(db, descuento.cliente_id, datos)
    if errores:
        raise ErrorValidacion(errores)
    for campo, valor in limpios.items():
        setattr(descuento, campo, valor)
    db.commit()
    return descuento


def eliminar_descuento(db: Session, descuento_id: int) -> None:
    descuento = db.get(Descuento, descuento_id)
    db.delete(descuento)
    db.commit()
