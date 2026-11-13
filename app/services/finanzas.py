"""F9 — Ingresos esperados, cobrados, P&L, histórico y proyección (Chat 3).

Esperado del mes = Σ honorarios mensuales vigentes en ese mes
                 + Σ honorarios anuales cuyo mes_generacion = mes
                 − Σ descuentos del mes
- Mensuales: el contrato entra si estuvo activo en algún momento del mes,
  con el honorario vigente en ese mes según el historial.
- Anuales: entran en el mes de generación de sus templates (el menor si
  hay varios). Sin templates no entran (solo se ven al cobrarse).
- Únicos: no entran.

Cobrado del mes = Σ cobros con fecha_cobro dentro del mes (dinero que entró).
Diferencia = Esperado − Cobrado.

P&L: ingresos = cobros del mes + ingresos propios; gastos = gastos propios.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Cliente,
    Cobro,
    Descuento,
    GastoIngresoPropio,
    HonorarioHistorial,
    Servicio,
    ServicioContratado,
)
from app.services import cuentas, fechas, formato

CERO = Decimal("0")


def _contratos(db: Session, solo_activos: bool = False) -> list[tuple]:
    consulta = (
        db.query(ServicioContratado, Servicio, Cliente)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .join(Cliente, Cliente.id == ServicioContratado.cliente_id)
        .filter(Servicio.frecuencia.in_(["mensual", "anual"]))
    )
    if solo_activos:
        consulta = consulta.filter(ServicioContratado.activo.is_(True))
    return consulta.all()


def activo_en_mes(contrato: ServicioContratado, mes: date) -> bool:
    """¿Estuvo activo en algún momento del mes?"""
    if contrato.fecha_inicio > fechas.ultimo_dia_mes(mes):
        return False
    return contrato.fecha_fin is None or contrato.fecha_fin >= fechas.primer_dia_mes(mes)


def _honorario_del_mes(db: Session, contrato: ServicioContratado, mes: date) -> Decimal | None:
    """Honorario vigente en el mes (al cierre del mes, o al fin del contrato
    si terminó antes), igual que en el cálculo de saldo."""
    referencia = fechas.ultimo_dia_mes(mes)
    if contrato.fecha_fin is not None and contrato.fecha_fin < referencia:
        referencia = contrato.fecha_fin
    registros = cuentas.honorarios_del_contrato(db, contrato.id)
    return cuentas.honorario_vigente_en(registros, referencia)


@dataclass
class ResumenMes:
    mes: date
    mensuales: Decimal = CERO
    anuales: Decimal = CERO
    descuentos: Decimal = CERO
    cobrado: Decimal = CERO
    ingresos_propios: Decimal = CERO
    gastos: Decimal = CERO
    gastos_por_categoria: dict = field(default_factory=dict)

    @property
    def esperado(self) -> Decimal:
        return self.mensuales + self.anuales - self.descuentos

    @property
    def diferencia(self) -> Decimal:
        return self.esperado - self.cobrado

    @property
    def ingresos_totales(self) -> Decimal:
        return self.cobrado + self.ingresos_propios

    @property
    def saldo_neto(self) -> Decimal:
        return self.ingresos_totales - self.gastos

    @property
    def porcentaje_cobrado(self) -> int:
        """Para la barra de progreso (0 a 100)."""
        if self.esperado <= 0:
            return 100 if self.cobrado > 0 else 0
        return min(100, int(self.cobrado * 100 / self.esperado))


def resumen_mes(db: Session, mes: date) -> ResumenMes:
    mes = fechas.primer_dia_mes(mes)
    fin = fechas.ultimo_dia_mes(mes)
    resumen = ResumenMes(mes=mes)

    for contrato, servicio, _ in _contratos(db):
        if not activo_en_mes(contrato, mes):
            continue
        if servicio.frecuencia.value == "anual":
            if cuentas.mes_generacion_del_servicio(db, servicio.id) != mes.month:
                continue
            resumen.anuales += _honorario_del_mes(db, contrato, mes) or CERO
        else:
            resumen.mensuales += _honorario_del_mes(db, contrato, mes) or CERO

    resumen.descuentos = sum(
        (d.importe for d in db.query(Descuento).filter(Descuento.fecha.between(mes, fin))), CERO
    )
    resumen.cobrado = sum(
        (c.importe for c in db.query(Cobro).filter(Cobro.fecha_cobro.between(mes, fin))), CERO
    )
    for movimiento in db.query(GastoIngresoPropio).filter(
        GastoIngresoPropio.fecha.between(mes, fin)
    ):
        if movimiento.tipo.value == "ingreso":
            resumen.ingresos_propios += movimiento.importe
        else:
            resumen.gastos += movimiento.importe
            categoria = movimiento.categoria.value
            resumen.gastos_por_categoria[categoria] = (
                resumen.gastos_por_categoria.get(categoria, CERO) + movimiento.importe
            )
    return resumen


def historico(db: Session, hasta: date, meses: int = 12) -> list[ResumenMes]:
    """Los `meses` meses que terminan en `hasta`, del más nuevo al más viejo."""
    resultado = []
    mes = fechas.primer_dia_mes(hasta)
    for _ in range(meses):
        resultado.append(resumen_mes(db, mes))
        mes = fechas.mes_anterior(mes)
    return resultado


@dataclass
class MesProyectado:
    mes: date
    total: Decimal
    observaciones: list[str]


def proyeccion(db: Session, desde: date, meses: int = 6) -> list[MesProyectado]:
    """Próximos meses con la cartera actual sin cambios: contratos activos ×
    honorarios vigentes (incluye cambios ya cargados con vigencia futura) y
    anuales en su mes de generación. No incluye únicos ni descuentos."""
    contratos = _contratos(db, solo_activos=True)
    resultado = []
    mes = fechas.primer_dia_mes(desde)
    for _ in range(meses):
        total = CERO
        observaciones = []
        anuales_del_mes = []
        for contrato, servicio, cliente in contratos:
            if contrato.fecha_inicio > fechas.ultimo_dia_mes(mes):
                continue
            if servicio.frecuencia.value == "anual":
                if cuentas.mes_generacion_del_servicio(db, servicio.id) != mes.month:
                    continue
                anuales_del_mes.append(servicio.nombre)
            total += _honorario_del_mes(db, contrato, mes) or CERO
            # Cambio de honorario ya registrado que empieza en este mes.
            cambio = (
                db.query(HonorarioHistorial)
                .filter(
                    HonorarioHistorial.servicio_contratado_id == contrato.id,
                    HonorarioHistorial.fecha_desde.between(mes, fechas.ultimo_dia_mes(mes)),
                    HonorarioHistorial.fecha_desde > contrato.fecha_inicio,
                )
                .first()
            )
            if cambio is not None:
                observaciones.append(
                    f"{cliente.nombre}: honorario nuevo desde {cambio.fecha_desde:%d/%m}"
                )
        for nombre in sorted(set(anuales_del_mes)):
            cantidad = anuales_del_mes.count(nombre)
            observaciones.append(f"incluye {nombre}" + (f" ({cantidad})" if cantidad > 1 else ""))
        resultado.append(MesProyectado(mes=mes, total=total, observaciones=observaciones))
        mes = fechas.mes_siguiente(mes)
    return resultado


CATEGORIAS_CORTAS = {
    "cjppu": "CJPPU",
    "aportes_bps": "BPS",
    "gasto_operativo": "operativos",
    "otro": "otros",
}


def detalle_gastos(resumen: ResumenMes) -> str:
    """Ej.: "CJPPU 12.400 · BPS 4.100 · operativos 1.750" (dashboard)."""
    partes = []
    for clave, etiqueta in CATEGORIAS_CORTAS.items():
        if clave in resumen.gastos_por_categoria:
            importe = formato.formato_importe(resumen.gastos_por_categoria[clave])
            partes.append(f"{etiqueta} {importe.removeprefix('$ ')}")
    return " · ".join(partes)
