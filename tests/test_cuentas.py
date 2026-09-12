"""F5 — Cálculo de saldo (enmienda B1) con los casos borde obligatorios
del Chat 5: contrato a mitad de mes, cambio retroactivo, cobro
multi-período, descuento parcial, contrato finalizado con impagos."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Cobro, Descuento, TareaTemplate
from app.services import contratos as sc
from app.services import cuentas, honorarios
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo

# Fecha fija para que los tests no dependan del día real de ejecución.
HOY_FIJO = date(2026, 9, 15)


@pytest.fixture(autouse=True)
def fijar_hoy(monkeypatch):
    monkeypatch.setattr(cuentas, "hoy", lambda: HOY_FIJO)


def _cobro(db, cliente, importe, desde=None, hasta=None, contrato=None,
           fecha=date(2026, 9, 1)):
    cobro = Cobro(
        cliente_id=cliente.id,
        servicio_contratado_id=contrato.id if contrato else None,
        periodo_desde=desde, periodo_hasta=hasta,
        fecha_cobro=fecha, importe=Decimal(importe),
        forma_pago="transferencia", tipo_comprobante="e_ticket",
    )
    db.add(cobro)
    db.commit()
    return cobro


def test_contrato_mensual_iniciado_a_mitad_de_mes(db_temporal):
    """El mes de inicio cuenta completo: feb a set 2026 = 8 períodos."""
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contratar(db_temporal, cliente, servicio, fecha=date(2026, 2, 15), honorario="5000")

    desglose = cuentas.calcular_saldo(db_temporal, cliente.id)
    assert desglose["cargos"] == Decimal("40000")  # 8 × 5.000
    assert desglose["saldo"] == Decimal("40000")


def test_cambio_retroactivo_usa_el_honorario_de_cada_periodo(db_temporal):
    """feb–jun a $5.000 y jul–set a $6.000 tras un cambio con vigencia 01/07."""
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(
        db_temporal, cliente, servicio, fecha=date(2026, 2, 1), honorario="5000"
    )
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6000", date(2026, 7, 1))

    desglose = cuentas.calcular_saldo(db_temporal, cliente.id)
    assert desglose["cargos"] == Decimal("43000")  # 5×5.000 + 3×6.000


def test_cobro_multiperiodo_y_descuento_parcial(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(
        db_temporal, cliente, servicio, fecha=date(2026, 6, 1), honorario="5000"
    )
    # Cobro que cubre jun y jul en un solo registro (Chat 3).
    _cobro(db_temporal, cliente, "10000",
           desde=date(2026, 6, 1), hasta=date(2026, 7, 31), contrato=contrato)
    # Descuento parcial sobre agosto.
    db_temporal.add(Descuento(
        cliente_id=cliente.id, servicio_contratado_id=contrato.id,
        fecha=date(2026, 8, 20), importe=Decimal("2000"), motivo="Bonificación",
    ))
    db_temporal.commit()

    desglose = cuentas.calcular_saldo(db_temporal, cliente.id)
    # Esperado jun-set = 4 × 5.000 = 20.000; − 10.000 cobrado − 2.000 descuento
    assert desglose["saldo"] == Decimal("8000")


def test_contrato_finalizado_conserva_la_deuda(db_temporal):
    """B1(a): finalizar no borra la deuda; computa hasta fecha_fin."""
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(
        db_temporal, cliente, servicio, fecha=date(2026, 2, 1), honorario="5000"
    )
    sc.finalizar(db_temporal, contrato.id, date(2026, 4, 30))

    desglose = cuentas.calcular_saldo(db_temporal, cliente.id)
    assert desglose["cargos"] == Decimal("15000")  # feb, mar y abr
    assert desglose["saldo"] == Decimal("15000")


def test_anual_carga_en_su_mes_de_generacion(db_temporal):
    """B1(b): un cargo por año en el menor mes_generacion de sus templates."""
    cliente = crear_cliente_directo(db_temporal)
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    contratar(db_temporal, cliente, anual, fecha=date(2025, 3, 1), honorario="12000")

    # Sin templates: sin cargo esperado.
    assert cuentas.calcular_saldo(db_temporal, cliente.id)["cargos"] == Decimal("0")

    # Con templates (mes 6 y mes 8): usa el menor (junio) → 2025 y 2026.
    db_temporal.add(TareaTemplate(
        servicio_id=anual.id, regimen="todos", nombre="Preparar DDJJ",
        orden=1, mes_generacion=6, activo=True,
    ))
    db_temporal.add(TareaTemplate(
        servicio_id=anual.id, regimen="todos", nombre="Presentar DDJJ",
        orden=2, mes_generacion=8, activo=True,
    ))
    db_temporal.commit()

    assert cuentas.calcular_saldo(db_temporal, cliente.id)["cargos"] == Decimal("24000")


def test_anual_no_carga_el_anio_previo_al_contrato(db_temporal):
    """Contrato de julio 2026 con mes_generacion junio: recién carga en 2027."""
    cliente = crear_cliente_directo(db_temporal)
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    db_temporal.add(TareaTemplate(
        servicio_id=anual.id, regimen="todos", nombre="Preparar",
        orden=1, mes_generacion=6, activo=True,
    ))
    db_temporal.commit()
    contratar(db_temporal, cliente, anual, fecha=date(2026, 7, 1), honorario="12000")

    assert cuentas.calcular_saldo(db_temporal, cliente.id)["cargos"] == Decimal("0")


def test_unico_carga_desde_fecha_inicio(db_temporal):
    """B1(c): cargo único con el honorario vigente a la fecha de inicio."""
    cliente = crear_cliente_directo(db_temporal)
    unico = crear_servicio_directo(db_temporal, "Certificado de ingresos", "unico")
    contratar(db_temporal, cliente, unico, fecha=date(2026, 8, 10), honorario="4500")

    assert cuentas.calcular_saldo(db_temporal, cliente.id)["saldo"] == Decimal("4500")


def test_mapa_de_periodos_marca_cubiertos(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contratar(db_temporal, cliente, servicio, fecha=date(2026, 6, 1), honorario="5000")
    _cobro(db_temporal, cliente, "5000",
           desde=date(2026, 6, 1), hasta=date(2026, 6, 30))

    mapas = cuentas.mapa_periodos(db_temporal, cliente.id)
    assert len(mapas) == 1
    celdas = {c["periodo"]: c["cubierto"] for c in mapas[0]["celdas"]}
    # jun a set (mes de HOY_FIJO): solo junio cubierto
    assert celdas[date(2026, 6, 1)] is True
    assert celdas[date(2026, 7, 1)] is False
    assert celdas[date(2026, 9, 1)] is False
    assert len(celdas) == 4


def test_situacion_y_texto_de_periodos(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contratar(db_temporal, cliente, servicio, fecha=date(2026, 7, 1), honorario="5000")

    saldo = cuentas.calcular_saldo(db_temporal, cliente.id)["saldo"]
    impagos = cuentas.contar_periodos_impagos(db_temporal, cliente.id)
    assert cuentas.situacion(saldo, impagos) == "Debe · 3 períodos"  # jul, ago, set
    assert cuentas.situacion(Decimal("0"), 0) == "Al día"
    assert cuentas.situacion(Decimal("-100"), 0) == "Saldo a favor"


def test_vista_global_ordena_por_saldo_y_suma_totales(db_temporal):
    """H-04: totales de cabecera; orden por saldo descendente."""
    servicio = crear_servicio_directo(db_temporal)
    deudor = crear_cliente_directo(db_temporal, nombre="Deudor")
    contratar(db_temporal, deudor, servicio, fecha=date(2026, 8, 1), honorario="5000")
    a_favor = crear_cliente_directo(db_temporal, nombre="A Favor")
    _cobro(db_temporal, a_favor, "3000")
    inactivo = crear_cliente_directo(db_temporal, nombre="Inactivo", activo=False)

    resultado = cuentas.saldos_de_clientes_activos(db_temporal)
    nombres = [f["cliente"].nombre for f in resultado["filas"]]
    assert nombres == ["Deudor", "A Favor"]  # inactivo excluido
    assert resultado["total_adeudado"] == Decimal("10000")  # ago + set
    assert resultado["total_a_favor"] == Decimal("3000")
