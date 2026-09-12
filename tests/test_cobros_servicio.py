"""F5 — Validaciones y CRUD de cobros y descuentos."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Auditoria, Cobro
from app.services import cobros
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _datos_cobro(cliente, **cambios) -> dict:
    base = {
        "cliente_id": cliente.id,
        "servicio_contratado_id": None,
        "periodo_desde": None,
        "periodo_hasta": None,
        "fecha_cobro": date(2026, 9, 1),
        "importe": "5.000",
        "forma_pago": "transferencia",
        "tipo_comprobante": "e_ticket",
        "notas": "",
    }
    base.update(cambios)
    return base


def test_registrar_cobro_parsea_importe_local(db_temporal):
    """"5.000" es cinco mil (punto de miles), no cinco."""
    cliente = crear_cliente_directo(db_temporal)
    cobro = cobros.registrar_cobro(db_temporal, _datos_cobro(cliente))
    assert cobro.importe == Decimal("5000")


def test_periodos_van_juntos(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_cobro(
            db_temporal,
            _datos_cobro(cliente, periodo_desde=date(2026, 6, 1)),
        )
    assert "van juntos" in error.value.errores["periodo_desde"]


def test_periodo_hasta_no_anterior_al_desde(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_cobro(
            db_temporal,
            _datos_cobro(
                cliente,
                periodo_desde=date(2026, 6, 1),
                periodo_hasta=date(2026, 5, 31),
            ),
        )
    assert "anterior" in error.value.errores["periodo_hasta"]


def test_adenda_c1_unico_con_ambas_fechas_iguales(db_temporal):
    """C1: en únicos ambas fechas llevan la fecha real del trabajo."""
    cliente = crear_cliente_directo(db_temporal)
    cobro = cobros.registrar_cobro(
        db_temporal,
        _datos_cobro(
            cliente,
            periodo_desde=date(2026, 2, 27),
            periodo_hasta=date(2026, 2, 27),
        ),
    )
    assert cobro.periodo_desde == cobro.periodo_hasta == date(2026, 2, 27)


def test_validaciones_basicas_de_cobro(db_temporal):
    cliente = crear_cliente_directo(db_temporal)

    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_cobro(db_temporal, _datos_cobro(cliente, importe="0"))
    assert error.value.errores["importe"] == "El importe debe ser mayor a cero."

    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_cobro(
            db_temporal, _datos_cobro(cliente, fecha_cobro=date(2100, 1, 1))
        )
    assert error.value.errores["fecha_cobro"] == "La fecha de cobro no puede ser futura."


def test_servicio_de_otro_cliente_rechazado(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    otro = crear_cliente_directo(db_temporal, nombre="Otro")
    servicio = crear_servicio_directo(db_temporal)
    contrato_ajeno = contratar(db_temporal, otro, servicio)

    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_cobro(
            db_temporal,
            _datos_cobro(cliente, servicio_contratado_id=contrato_ajeno.id),
        )
    assert "servicio_contratado_id" in error.value.errores


def test_editar_cobro_todos_los_campos(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    cobro = cobros.registrar_cobro(db_temporal, _datos_cobro(cliente))

    cobros.editar_cobro(
        db_temporal, cobro.id,
        _datos_cobro(cliente, importe="7.500", forma_pago="efectivo"),
    )
    assert cobro.importe == Decimal("7500")
    assert cobro.forma_pago.value == "efectivo"


def test_eliminar_cobro_deja_rastro_en_auditoria(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    cobro = cobros.registrar_cobro(db_temporal, _datos_cobro(cliente))
    id_cobro = cobro.id

    cobros.eliminar_cobro(db_temporal, id_cobro)

    assert db_temporal.get(Cobro, id_cobro) is None
    rastro = (
        db_temporal.query(Auditoria)
        .filter(
            Auditoria.tabla == "cobros",
            Auditoria.registro_id == id_cobro,
            Auditoria.accion == "eliminacion",
        )
        .first()
    )
    assert rastro is not None
    assert rastro.datos_antes is not None


def test_descuento_validaciones_y_alta(db_temporal):
    cliente = crear_cliente_directo(db_temporal)

    with pytest.raises(ErrorValidacion) as error:
        cobros.registrar_descuento(db_temporal, cliente.id, {
            "servicio_contratado_id": None,
            "fecha": date(2026, 9, 1),
            "importe": "2.000",
            "motivo": "   ",
        })
    assert error.value.errores["motivo"] == "Ingresá el motivo."

    descuento = cobros.registrar_descuento(db_temporal, cliente.id, {
        "servicio_contratado_id": None,
        "fecha": date(2026, 9, 1),
        "importe": "2.000",
        "motivo": "Bonificación",
    })
    assert descuento.importe == Decimal("2000")
