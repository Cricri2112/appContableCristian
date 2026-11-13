"""F9 — ABM de gastos e ingresos propios del estudio (Chat 3).

- tipo = gasto: CJPPU, aportes BPS, operativos, otros.
- tipo = ingreso: SOLO ingresos que no vienen de clientes (los cobros de
  F5 ya cuentan como ingresos; no se duplican acá).
Eliminación física con confirmación; queda rastro en `auditoria`.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import GastoIngresoPropio
from app.models.enums import CategoriaMovimientoPropio, TipoMovimientoPropio
from app.services import fechas
from app.services.errores import ErrorValidacion
from app.services.importes import parsear_importe

TIPOS = [t.value for t in TipoMovimientoPropio]
CATEGORIAS = [c.value for c in CategoriaMovimientoPropio]
CATEGORIAS_LEGIBLES = {
    "cjppu": "CJPPU",
    "aportes_bps": "Aportes BPS",
    "gasto_operativo": "Gasto operativo",
    "otro": "Otro",
}


def listar(
    db: Session, mes: date, tipo: str | None = None, categoria: str | None = None
) -> dict:
    """Movimientos del mes con filtros, por fecha descendente, y los
    totales del filtro: ingresos, gastos y neto."""
    consulta = db.query(GastoIngresoPropio).filter(
        GastoIngresoPropio.fecha.between(
            fechas.primer_dia_mes(mes), fechas.ultimo_dia_mes(mes)
        )
    )
    if tipo in TIPOS:
        consulta = consulta.filter(GastoIngresoPropio.tipo == tipo)
    if categoria in CATEGORIAS:
        consulta = consulta.filter(GastoIngresoPropio.categoria == categoria)
    movimientos = consulta.order_by(
        GastoIngresoPropio.fecha.desc(), GastoIngresoPropio.id.desc()
    ).all()

    ingresos = sum((m.importe for m in movimientos if m.tipo.value == "ingreso"), Decimal("0"))
    gastos = sum((m.importe for m in movimientos if m.tipo.value == "gasto"), Decimal("0"))
    return {
        "movimientos": movimientos,
        "ingresos": ingresos,
        "gastos": gastos,
        "neto": ingresos - gastos,
    }


def _validar(datos: dict) -> tuple[dict, dict]:
    errores = {}
    limpios = {}

    fecha = datos.get("fecha")
    if fecha is None:
        errores["fecha"] = "Ingresá la fecha."
    elif fecha > fechas.hoy():
        errores["fecha"] = "La fecha no puede ser futura."
    limpios["fecha"] = fecha

    if datos.get("tipo") not in TIPOS:
        errores["tipo"] = "Elegí si es gasto o ingreso."
    limpios["tipo"] = datos.get("tipo")

    concepto = (datos.get("concepto") or "").strip()
    if not concepto:
        errores["concepto"] = "El concepto no puede estar vacío."
    limpios["concepto"] = concepto

    importe, error = parsear_importe(datos.get("importe") or "", "importe")
    if error:
        errores["importe"] = error
    limpios["importe"] = importe

    if datos.get("categoria") not in CATEGORIAS:
        errores["categoria"] = "Elegí la categoría."
    limpios["categoria"] = datos.get("categoria")

    limpios["notas"] = (datos.get("notas") or "").strip() or None
    return limpios, errores


def crear(db: Session, datos: dict) -> GastoIngresoPropio:
    limpios, errores = _validar(datos)
    if errores:
        raise ErrorValidacion(errores)
    movimiento = GastoIngresoPropio(**limpios)
    db.add(movimiento)
    db.commit()
    return movimiento


def editar(db: Session, movimiento_id: int, datos: dict) -> GastoIngresoPropio:
    limpios, errores = _validar(datos)
    if errores:
        raise ErrorValidacion(errores)
    movimiento = db.get(GastoIngresoPropio, movimiento_id)
    for campo, valor in limpios.items():
        setattr(movimiento, campo, valor)
    db.commit()
    return movimiento


def eliminar(db: Session, movimiento_id: int) -> None:
    db.delete(db.get(GastoIngresoPropio, movimiento_id))
    db.commit()
