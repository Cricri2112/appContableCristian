"""F5 — Estado de cuenta y cálculo de saldo (Chat 3 + enmienda B1).

Fórmula (B1):

    Saldo = Σ cargos esperados (mensuales por período + anuales por año + únicos)
          − Σ descuentos aplicados
          − Σ cobros recibidos

Reglas de la enmienda B1:
(a) Se incluyen contratos activos y finalizados; para los finalizados los
    períodos se computan hasta fecha_fin. Finalizar no borra la deuda.
(b) Anuales: un cargo por año en el mes de `mes_generacion` de sus templates
    (el menor si hay varios), con el honorario vigente en ese mes. Sin
    templates no generan cargo esperado.
(c) Únicos: un cargo único desde la fecha_inicio del contrato, con el
    honorario vigente a esa fecha.

Saldo positivo: el cliente debe (rojo). Cero o negativo: al día / a favor (verde).
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Cliente,
    Cobro,
    Descuento,
    HonorarioHistorial,
    Servicio,
    ServicioContratado,
    TareaTemplate,
)
from app.models.base import ahora_montevideo


def hoy() -> date:
    return ahora_montevideo().date()


def primer_dia_mes(fecha: date) -> date:
    return fecha.replace(day=1)


def ultimo_dia_mes(fecha: date) -> date:
    return fecha.replace(day=monthrange(fecha.year, fecha.month)[1])


def mes_siguiente(fecha: date) -> date:
    if fecha.month == 12:
        return date(fecha.year + 1, 1, 1)
    return date(fecha.year, fecha.month + 1, 1)


@dataclass
class Cargo:
    """Un cargo esperado: el período al que corresponde y su importe."""

    periodo: date  # primer día del mes imputado
    importe: Decimal


def _honorarios_del_contrato(db: Session, contrato_id: int) -> list[HonorarioHistorial]:
    return (
        db.query(HonorarioHistorial)
        .filter(HonorarioHistorial.servicio_contratado_id == contrato_id)
        .order_by(HonorarioHistorial.fecha_desde.asc())
        .all()
    )


def _honorario_vigente_en(
    registros: list[HonorarioHistorial], referencia: date
) -> Decimal | None:
    """Honorario vigente a una fecha: el registro con la mayor fecha_desde
    que no supere la referencia. Los cambios de F6 siempre arrancan el
    primer día de un mes, así que alcanza con comparar por fecha_desde."""
    vigente = None
    for registro in registros:
        if registro.fecha_desde <= referencia:
            vigente = registro
    return vigente.honorario if vigente else None


def _mes_generacion_del_servicio(db: Session, servicio_id: int) -> int | None:
    """Menor `mes_generacion` entre los templates activos del servicio (B1)."""
    meses = [
        mes
        for (mes,) in db.query(TareaTemplate.mes_generacion)
        .filter(
            TareaTemplate.servicio_id == servicio_id,
            TareaTemplate.activo.is_(True),
            TareaTemplate.mes_generacion.isnot(None),
        )
        .all()
    ]
    return min(meses) if meses else None


def cargos_esperados_contrato(
    db: Session, contrato: ServicioContratado, servicio: Servicio
) -> list[Cargo]:
    """Cargos esperados de un contrato según su frecuencia (B1)."""
    registros = _honorarios_del_contrato(db, contrato.id)
    if not registros:
        return []

    # Hasta cuándo computa: hoy, o fecha_fin si el contrato terminó antes.
    limite = hoy()
    if contrato.fecha_fin is not None and contrato.fecha_fin < limite:
        limite = contrato.fecha_fin

    frecuencia = servicio.frecuencia.value

    if frecuencia == "unico":
        # (c) Un cargo único desde la fecha_inicio, honorario vigente a esa fecha.
        importe = _honorario_vigente_en(registros, contrato.fecha_inicio)
        if importe is None or contrato.fecha_inicio > limite:
            return []
        return [Cargo(primer_dia_mes(contrato.fecha_inicio), importe)]

    if frecuencia == "anual":
        # (b) Un cargo por año en el mes de generación de sus templates.
        mes = _mes_generacion_del_servicio(db, servicio.id)
        if mes is None:
            return []  # sin templates no hay cargo esperado
        cargos = []
        for anio in range(contrato.fecha_inicio.year, limite.year + 1):
            imputacion = date(anio, mes, 1)
            # El cargo cuenta si su mes cae dentro de la vida del contrato.
            if contrato.fecha_inicio <= imputacion <= limite:
                importe = _honorario_vigente_en(registros, imputacion)
                if importe is not None:
                    cargos.append(Cargo(imputacion, importe))
        return cargos

    # Mensual: un cargo por cada mes desde el mes de inicio hasta el límite
    # (contrato iniciado a mitad de mes: ese mes cuenta completo, igual que
    # la generación de tareas de F7).
    cargos = []
    periodo = primer_dia_mes(contrato.fecha_inicio)
    while periodo <= limite:
        # Honorario vigente EN ese período: se evalúa al fin del mes, pero
        # sin pasar el límite del contrato (contratos finalizados a mitad
        # de mes conservan el honorario cerrado en fecha_fin).
        referencia = min(ultimo_dia_mes(periodo), limite)
        importe = _honorario_vigente_en(registros, referencia)
        if importe is not None:
            cargos.append(Cargo(periodo, importe))
        periodo = mes_siguiente(periodo)
    return cargos


def calcular_saldo(db: Session, cliente_id: int) -> dict:
    """Saldo del cliente con su desglose (misma fórmula, presentada — H-06)."""
    contratos = (
        db.query(ServicioContratado, Servicio)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(ServicioContratado.cliente_id == cliente_id)
        .all()
    )
    cargos_total = Decimal("0")
    for contrato, servicio in contratos:
        for cargo in cargos_esperados_contrato(db, contrato, servicio):
            cargos_total += cargo.importe

    descuentos_total = sum(
        (d.importe for d in db.query(Descuento).filter(
            Descuento.cliente_id == cliente_id)),
        Decimal("0"),
    )
    cobros_total = sum(
        (c.importe for c in db.query(Cobro).filter(Cobro.cliente_id == cliente_id)),
        Decimal("0"),
    )

    return {
        "cargos": cargos_total,
        "descuentos": descuentos_total,
        "cobros": cobros_total,
        "saldo": cargos_total - descuentos_total - cobros_total,
    }


def _periodo_cubierto(db: Session, cliente_id: int, periodo: date) -> bool:
    """Un período (mes) está cubierto si algún cobro del cliente declara un
    rango de períodos que lo incluye."""
    return (
        db.query(Cobro)
        .filter(
            Cobro.cliente_id == cliente_id,
            Cobro.periodo_desde.isnot(None),
            Cobro.periodo_desde <= ultimo_dia_mes(periodo),
            Cobro.periodo_hasta >= periodo,
        )
        .first()
        is not None
    )


def mapa_periodos(db: Session, cliente_id: int) -> list[dict]:
    """Mapa de períodos del año en curso por contrato mensual activo (H-06).

    Cada celda: mes (primer día) + cubierto (True/False). Se muestran los
    meses del año desde el inicio del contrato hasta el mes en curso.
    """
    contratos = (
        db.query(ServicioContratado, Servicio)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(
            ServicioContratado.cliente_id == cliente_id,
            ServicioContratado.activo.is_(True),
            Servicio.frecuencia == "mensual",
        )
        .all()
    )
    mes_actual = primer_dia_mes(hoy())
    mapas = []
    for contrato, servicio in contratos:
        registros = _honorarios_del_contrato(db, contrato.id)
        celdas = []
        periodo = max(date(mes_actual.year, 1, 1), primer_dia_mes(contrato.fecha_inicio))
        while periodo <= mes_actual:
            celdas.append({
                "periodo": periodo,
                "cubierto": _periodo_cubierto(db, cliente_id, periodo),
            })
            periodo = mes_siguiente(periodo)
        mapas.append({
            "servicio": servicio,
            "celdas": celdas,
            "honorario_vigente": _honorario_vigente_en(registros, hoy()),
        })
    return mapas


def contar_periodos_impagos(db: Session, cliente_id: int) -> int:
    """Meses esperados de contratos mensuales (hasta el mes en curso) sin
    cobros que los cubran. Alimenta el texto "Debe · N períodos"."""
    contratos = (
        db.query(ServicioContratado, Servicio)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(
            ServicioContratado.cliente_id == cliente_id,
            Servicio.frecuencia == "mensual",
        )
        .all()
    )
    impagos: set[date] = set()
    for contrato, servicio in contratos:
        for cargo in cargos_esperados_contrato(db, contrato, servicio):
            if not _periodo_cubierto(db, cliente_id, cargo.periodo):
                impagos.add(cargo.periodo)
    return len(impagos)


def situacion(saldo: Decimal, periodos_impagos: int) -> str:
    """Texto de situación como en las vistas 03 y 07."""
    if saldo > 0:
        if periodos_impagos == 1:
            return "Debe · 1 período"
        if periodos_impagos > 1:
            return f"Debe · {periodos_impagos} períodos"
        return "Debe"
    if saldo < 0:
        return "Saldo a favor"
    return "Al día"


def saldos_de_clientes_activos(db: Session) -> dict:
    """Vista global de cobros: clientes activos por saldo descendente, con
    los totales de cabecera del hallazgo H-04."""
    filas = []
    total_adeudado = Decimal("0")
    total_a_favor = Decimal("0")
    for cliente in db.query(Cliente).filter(Cliente.activo.is_(True)).all():
        saldo = calcular_saldo(db, cliente.id)["saldo"]
        filas.append({
            "cliente": cliente,
            "saldo": saldo,
            "situacion": situacion(saldo, contar_periodos_impagos(db, cliente.id)),
        })
        if saldo > 0:
            total_adeudado += saldo
        elif saldo < 0:
            total_a_favor += -saldo
    filas.sort(key=lambda f: f["saldo"], reverse=True)
    return {
        "filas": filas,
        "total_adeudado": total_adeudado,
        "total_a_favor": total_a_favor,
    }
