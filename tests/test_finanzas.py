"""F9 — Esperado, cobrado, diferencia, P&L, histórico, proyección y ABM de
gastos/ingresos propios (Etapa 6, corte 6b)."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Cobro, Descuento, GastoIngresoPropio, TareaTemplate
from app.services import contratos, cuentas, fechas, finanzas, gastos, honorarios
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo

HOY = date(2026, 11, 20)
NOV = date(2026, 11, 1)


@pytest.fixture(autouse=True)
def fijar_hoy(monkeypatch):
    for modulo in (fechas, cuentas, contratos, honorarios):
        monkeypatch.setattr(modulo, "hoy", lambda: HOY)


def _cobro(db, cliente, importe, fecha):
    db.add(Cobro(cliente_id=cliente.id, fecha_cobro=fecha, importe=Decimal(importe),
                 forma_pago="transferencia", tipo_comprobante="e_ticket"))
    db.commit()


def _movimiento(db, tipo, importe, categoria="gasto_operativo", fecha=date(2026, 11, 5)):
    db.add(GastoIngresoPropio(fecha=fecha, tipo=tipo, concepto="x", importe=Decimal(importe),
                              categoria=categoria))
    db.commit()


# ---------- Esperado / cobrado / diferencia ----------

def test_esperado_suma_mensuales_menos_descuentos(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    a = crear_cliente_directo(db_temporal, nombre="A")
    b = crear_cliente_directo(db_temporal, nombre="B")
    contratar(db_temporal, a, servicio, honorario="5000")
    contratar(db_temporal, b, servicio, honorario="3000")
    db_temporal.add(Descuento(cliente_id=a.id, fecha=date(2026, 11, 3),
                              importe=Decimal("500"), motivo="Bonificación"))
    _cobro(db_temporal, a, "4500", date(2026, 11, 10))
    _cobro(db_temporal, b, "3000", date(2026, 10, 30))  # otro mes: no cuenta

    resumen = finanzas.resumen_mes(db_temporal, NOV)
    assert resumen.esperado == Decimal("7500")
    assert resumen.cobrado == Decimal("4500")
    assert resumen.diferencia == Decimal("3000")
    assert resumen.porcentaje_cobrado == 60


def test_contrato_iniciado_despues_del_mes_no_entra(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, servicio, fecha=date(2026, 11, 1), honorario="5000")
    assert finanzas.resumen_mes(db_temporal, date(2026, 10, 1)).esperado == 0
    assert finanzas.resumen_mes(db_temporal, NOV).esperado == Decimal("5000")


def test_anual_entra_solo_en_su_mes_de_generacion(db_temporal):
    anual = crear_servicio_directo(db_temporal, "DDJJ anual", "anual")
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, anual, fecha=date(2026, 1, 1), honorario="12000")
    db_temporal.add(TareaTemplate(servicio_id=anual.id, regimen="todos", nombre="DDJJ",
                                  orden=1, mes_generacion=5, activo=True))
    db_temporal.commit()

    assert finanzas.resumen_mes(db_temporal, date(2026, 5, 1)).anuales == Decimal("12000")
    assert finanzas.resumen_mes(db_temporal, NOV).anuales == 0


def test_historico_usa_el_honorario_vigente_de_cada_mes(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    cliente = crear_cliente_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio, fecha=date(2026, 2, 1), honorario="5000")
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6000", date(2026, 7, 1))

    filas = finanzas.historico(db_temporal, NOV, 12)
    assert len(filas) == 12
    assert filas[0].mes == NOV and filas[-1].mes == date(2025, 12, 1)
    por_mes = {f.mes: f.esperado for f in filas}
    assert por_mes[date(2026, 1, 1)] == 0
    assert por_mes[date(2026, 6, 1)] == Decimal("5000")
    assert por_mes[date(2026, 7, 1)] == Decimal("6000")


# ---------- P&L ----------

def test_pyl_del_mes(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    _cobro(db_temporal, cliente, "10000", date(2026, 11, 2))
    _movimiento(db_temporal, "ingreso", "2000", "otro")
    _movimiento(db_temporal, "gasto", "4000", "cjppu")
    _movimiento(db_temporal, "gasto", "1500", "aportes_bps")

    resumen = finanzas.resumen_mes(db_temporal, NOV)
    assert resumen.ingresos_totales == Decimal("12000")
    assert resumen.gastos == Decimal("5500")
    assert resumen.saldo_neto == Decimal("6500")
    assert finanzas.detalle_gastos(resumen) == "CJPPU 4.000 · BPS 1.500"


# ---------- Proyección ----------

def test_proyeccion_con_cambio_futuro_y_anual(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    anual = crear_servicio_directo(db_temporal, "DDJJ anual", "anual")
    cliente = crear_cliente_directo(db_temporal, nombre="Verdulería El Sol")
    contrato = contratar(db_temporal, cliente, mensual, fecha=date(2026, 2, 1), honorario="5000")
    contratar(db_temporal, cliente, anual, fecha=date(2026, 2, 1), honorario="12000")
    db_temporal.add(TareaTemplate(servicio_id=anual.id, regimen="todos", nombre="DDJJ",
                                  orden=1, mes_generacion=2, activo=True))
    db_temporal.commit()
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6000", date(2027, 1, 1))

    filas = finanzas.proyeccion(db_temporal, date(2026, 12, 1), 6)
    assert [f.mes.month for f in filas] == [12, 1, 2, 3, 4, 5]
    assert filas[0].total == Decimal("5000") and filas[0].observaciones == []
    assert filas[1].total == Decimal("6000")
    assert filas[1].observaciones == ["Verdulería El Sol: honorario nuevo desde 01/01"]
    assert filas[2].total == Decimal("18000")
    assert filas[2].observaciones == ["incluye DDJJ anual"]


# ---------- ABM de gastos e ingresos propios ----------

def _datos(**cambios):
    base = {"fecha": date(2026, 11, 5), "tipo": "gasto", "concepto": "Aportes CJPPU",
            "importe": "12.400", "categoria": "cjppu", "notas": ""}
    base.update(cambios)
    return base


def test_crear_editar_y_eliminar(db_temporal):
    movimiento = gastos.crear(db_temporal, _datos())
    assert movimiento.importe == Decimal("12400")
    assert movimiento.notas is None

    gastos.editar(db_temporal, movimiento.id, _datos(importe="13000", notas="ajuste"))
    db_temporal.refresh(movimiento)
    assert movimiento.importe == Decimal("13000") and movimiento.notas == "ajuste"

    gastos.eliminar(db_temporal, movimiento.id)
    assert db_temporal.query(GastoIngresoPropio).count() == 0


@pytest.mark.parametrize("cambios, campo, mensaje", [
    ({"fecha": date(2026, 11, 21)}, "fecha", "La fecha no puede ser futura."),
    ({"concepto": "  "}, "concepto", "El concepto no puede estar vacío."),
    ({"tipo": "otro"}, "tipo", "Elegí si es gasto o ingreso."),
])
def test_validaciones(db_temporal, cambios, campo, mensaje):
    with pytest.raises(ErrorValidacion) as error:
        gastos.crear(db_temporal, _datos(**cambios))
    assert error.value.errores[campo] == mensaje


def test_importe_cero_es_invalido(db_temporal):
    with pytest.raises(ErrorValidacion) as error:
        gastos.crear(db_temporal, _datos(importe="0"))
    assert "importe" in error.value.errores


def test_listar_filtra_y_totaliza(db_temporal):
    _movimiento(db_temporal, "gasto", "4000", "cjppu")
    _movimiento(db_temporal, "gasto", "1000", "gasto_operativo")
    _movimiento(db_temporal, "ingreso", "2500", "otro")
    _movimiento(db_temporal, "gasto", "9999", "cjppu", fecha=date(2026, 10, 5))

    todo = gastos.listar(db_temporal, NOV)
    assert len(todo["movimientos"]) == 3
    assert (todo["ingresos"], todo["gastos"], todo["neto"]) == (
        Decimal("2500"), Decimal("5000"), Decimal("-2500"))

    assert len(gastos.listar(db_temporal, NOV, tipo="ingreso")["movimientos"]) == 1
    assert gastos.listar(db_temporal, NOV, categoria="cjppu")["gastos"] == Decimal("4000")
