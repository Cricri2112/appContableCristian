"""F6 — Mecánica append-only, cambio individual y aumento global."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import honorarios
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _contrato_mensual(db, honorario="5700", fecha=date(2026, 1, 1), nombre="Cliente"):
    cliente = crear_cliente_directo(db, nombre=nombre)
    servicio = crear_servicio_directo(db)
    return contratar(db, cliente, servicio, fecha=fecha, honorario=honorario)


# ---------- Mecánica común y cambio individual ----------

def test_mecanica_append_only(db_temporal):
    contrato = _contrato_mensual(db_temporal)

    honorarios.cambiar_honorario(db_temporal, contrato.id, "6200", date(2026, 7, 1))

    historial = honorarios.historial_por_contrato(db_temporal, contrato.id)
    assert len(historial) == 2
    # Nuevo vigente
    assert historial[0].honorario == Decimal("6200")
    assert historial[0].fecha_desde == date(2026, 7, 1)
    assert historial[0].fecha_hasta is None
    # El anterior quedó cerrado el día previo a la vigencia
    assert historial[1].fecha_hasta == date(2026, 6, 30)


def test_nuevo_honorario_igual_al_vigente(db_temporal):
    contrato = _contrato_mensual(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        honorarios.cambiar_honorario(db_temporal, contrato.id, "5.700", date(2026, 7, 1))
    assert error.value.errores["honorario"] == "El nuevo honorario es igual al vigente."


def test_vigencia_debe_ser_primer_dia_de_mes(db_temporal):
    contrato = _contrato_mensual(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        honorarios.cambiar_honorario(db_temporal, contrato.id, "6200", date(2026, 7, 15))
    assert "primer día" in error.value.errores["fecha_vigencia"]


def test_vigencia_no_anterior_al_vigente(db_temporal):
    contrato = _contrato_mensual(db_temporal, fecha=date(2026, 3, 1))
    with pytest.raises(ErrorValidacion) as error:
        honorarios.cambiar_honorario(db_temporal, contrato.id, "6200", date(2026, 2, 1))
    assert "anterior" in error.value.errores["fecha_vigencia"]


def test_es_retroactivo(monkeypatch):
    monkeypatch.setattr(honorarios, "hoy", lambda: date(2026, 9, 15))
    assert honorarios.es_retroactivo(date(2026, 8, 1)) is True
    assert honorarios.es_retroactivo(date(2026, 9, 1)) is False
    assert honorarios.es_retroactivo(date(2026, 10, 1)) is False


# ---------- Aumento global ----------

def test_redondeo_hacia_arriba_a_multiplo_de_10():
    """Ejemplo del Chat 3: $5.700 × 8,5% = $6.184,50 → $6.190."""
    resultado = honorarios.redondear_arriba_a_10(
        Decimal("5700") * (1 + Decimal("8.5") / 100)
    )
    assert resultado == Decimal("6190")
    # Un múltiplo exacto no se toca.
    assert honorarios.redondear_arriba_a_10(Decimal("5500")) == Decimal("5500")


def test_candidatos_excluye_unicos_y_finalizados(db_temporal):
    from app.services import contratos as sc

    mensual = _contrato_mensual(db_temporal, nombre="B Cliente")
    cliente = crear_cliente_directo(db_temporal, nombre="A Cliente")
    unico = crear_servicio_directo(db_temporal, "Gestión ante DGI", "unico")
    contratar(db_temporal, cliente, unico)
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    contratar(db_temporal, cliente, anual, fecha=date(2026, 1, 1), honorario="12000")
    finalizado = _contrato_mensual(db_temporal, nombre="C Cliente")
    sc.finalizar(db_temporal, finalizado.id, date(2026, 8, 31))

    candidatos = honorarios.candidatos_aumento(
        db_temporal, Decimal("10"), date(2026, 10, 1)
    )
    # Solo el mensual activo y el anual; orden mensual → anual.
    assert [c["servicio"].frecuencia.value for c in candidatos] == ["mensual", "anual"]
    assert all(c["valida"] for c in candidatos)


def test_fila_invalida_si_la_vigencia_pisa_al_vigente(db_temporal):
    contrato = _contrato_mensual(db_temporal)
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6200", date(2026, 8, 1))

    candidatos = honorarios.candidatos_aumento(
        db_temporal, Decimal("10"), date(2026, 7, 1)
    )
    assert candidatos[0]["valida"] is False


def test_aplicar_aumento_exige_seleccion(db_temporal):
    with pytest.raises(ErrorValidacion) as error:
        honorarios.aplicar_aumento_global(db_temporal, [], date(2026, 10, 1))
    assert error.value.errores["seleccion"] == "Seleccioná al menos un servicio."


def test_aplicar_aumento_respeta_importe_editado_a_mano(db_temporal):
    contrato = _contrato_mensual(db_temporal)  # vigente 5.700

    honorarios.aplicar_aumento_global(
        db_temporal,
        [{"contrato_id": contrato.id, "nuevo_texto": "6.195"}],  # sin redondeo extra
        date(2026, 10, 1),
    )

    vigente = honorarios.honorario_vigente(db_temporal, contrato.id)
    assert vigente.honorario == Decimal("6195")
    assert vigente.fecha_desde == date(2026, 10, 1)
    historial = honorarios.historial_por_contrato(db_temporal, contrato.id)
    assert historial[1].fecha_hasta == date(2026, 9, 30)


def test_historial_consolidado_ordenado(db_temporal):
    contrato = _contrato_mensual(db_temporal)
    honorarios.cambiar_honorario(db_temporal, contrato.id, "6200", date(2026, 7, 1))

    filas = honorarios.historial_consolidado(db_temporal, contrato.cliente_id)
    assert len(filas) == 2
    assert filas[0].get("registro").fecha_desde == date(2026, 7, 1)
    assert filas[0].get("registro").fecha_hasta is None
