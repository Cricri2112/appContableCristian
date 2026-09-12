"""F4 — servicios contratados: contratar, duplicados, fecha de inicio, finalizar."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Cobro, HonorarioHistorial, Tarea
from app.models.base import ahora_montevideo
from app.services import contratos
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _honorarios(db, contrato_id):
    return (
        db.query(HonorarioHistorial)
        .filter(HonorarioHistorial.servicio_contratado_id == contrato_id)
        .all()
    )


# ---------- Contratar ----------

def test_contratar_crea_primer_honorario(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)

    contrato = contratos.contratar(
        db_temporal, cliente.id, servicio.id, date(2026, 2, 1), "5700"
    )

    assert contrato.activo is True
    assert contrato.fecha_fin is None
    registros = _honorarios(db_temporal, contrato.id)
    assert len(registros) == 1
    assert registros[0].honorario == Decimal("5700")
    assert registros[0].fecha_desde == date(2026, 2, 1)
    assert registros[0].fecha_hasta is None


def test_no_duplica_mensual_ni_anual_activo(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    mensual = crear_servicio_directo(db_temporal)
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    contratar(db_temporal, cliente, mensual)
    contratar(db_temporal, cliente, anual)

    for servicio in (mensual, anual):
        with pytest.raises(ErrorValidacion) as error:
            contratar(db_temporal, cliente, servicio)
        assert error.value.errores["servicio_id"] == (
            "El cliente ya tiene ese servicio contratado activo."
        )


def test_unico_se_puede_contratar_varias_veces(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    unico = crear_servicio_directo(db_temporal, "Certificado de ingresos", "unico")
    contratar(db_temporal, cliente, unico)
    contratar(db_temporal, cliente, unico)  # sin restricción de duplicados

    filas = contratos.listar_contratos(db_temporal, cliente.id)
    assert len(filas) == 2


def test_mensual_finalizado_permite_contratar_de_nuevo(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio)
    contratos.finalizar(db_temporal, contrato.id, date(2026, 8, 31))

    nuevo = contratar(db_temporal, cliente, servicio, fecha=date(2026, 9, 1))
    assert nuevo.id != contrato.id


def test_validaciones_de_contratar(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)

    with pytest.raises(ErrorValidacion) as error:
        contratos.contratar(db_temporal, cliente.id, servicio.id, date(2100, 1, 1), "5000")
    assert error.value.errores["fecha_inicio"] == "La fecha de inicio no puede ser futura."

    with pytest.raises(ErrorValidacion) as error:
        contratos.contratar(db_temporal, cliente.id, servicio.id, date(2026, 2, 1), "0")
    assert error.value.errores["honorario"] == "El honorario debe ser mayor a cero."

    with pytest.raises(ErrorValidacion) as error:
        contratos.contratar(db_temporal, cliente.id, servicio.id, date(2026, 2, 1), "abc")
    assert "honorario" in error.value.errores

    inactivo = crear_servicio_directo(db_temporal, "Viejo", "unico", activo=False)
    with pytest.raises(ErrorValidacion) as error:
        contratos.contratar(db_temporal, cliente.id, inactivo.id, date(2026, 2, 1), "5000")
    assert "servicio_id" in error.value.errores


# ---------- Editar fecha de inicio ----------

def test_editar_fecha_inicio_actualiza_contrato_y_primer_honorario(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio, fecha=date(2026, 2, 1))

    contratos.editar_fecha_inicio(db_temporal, contrato.id, date(2026, 3, 1))

    assert contrato.fecha_inicio == date(2026, 3, 1)
    registros = _honorarios(db_temporal, contrato.id)
    assert registros[0].fecha_desde == date(2026, 3, 1)


def test_fecha_inicio_bloqueada_con_tareas_o_cobros(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    con_tarea = contratar(db_temporal, cliente, servicio)
    unico = crear_servicio_directo(db_temporal, "Gestión ante DGI", "unico")
    con_cobro = contratar(db_temporal, cliente, unico)

    db_temporal.add(Tarea(
        servicio_contratado_id=con_tarea.id, nombre="Tarea", periodo=date(2026, 2, 1),
        estado="pendiente", fecha_creacion=ahora_montevideo(),
    ))
    db_temporal.add(Cobro(
        cliente_id=cliente.id, servicio_contratado_id=con_cobro.id,
        fecha_cobro=date(2026, 3, 1), importe=Decimal("5000"),
        forma_pago="transferencia", tipo_comprobante="sin_comprobante",
    ))
    db_temporal.commit()

    mensaje = "No se puede modificar la fecha de inicio porque existen tareas o cobros asociados."
    for contrato in (con_tarea, con_cobro):
        with pytest.raises(ErrorValidacion) as error:
            contratos.editar_fecha_inicio(db_temporal, contrato.id, date(2026, 3, 1))
        assert error.value.errores["fecha_inicio"] == mensaje


# ---------- Finalizar ----------

def test_finalizar_cierra_contrato_y_honorario(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio, fecha=date(2026, 2, 1))

    contratos.finalizar(db_temporal, contrato.id, date(2026, 8, 31))

    assert contrato.activo is False
    assert contrato.fecha_fin == date(2026, 8, 31)
    registros = _honorarios(db_temporal, contrato.id)
    assert registros[0].fecha_hasta == date(2026, 8, 31)


def test_finalizar_no_anterior_al_inicio(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio, fecha=date(2026, 2, 1))

    with pytest.raises(ErrorValidacion) as error:
        contratos.finalizar(db_temporal, contrato.id, date(2026, 1, 31))
    assert "anterior al inicio" in error.value.errores["fecha_fin"]


def test_finalizar_no_toca_tareas_pendientes(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio)
    tarea = Tarea(
        servicio_contratado_id=contrato.id, nombre="Tarea", periodo=date(2026, 2, 1),
        estado="pendiente", fecha_creacion=ahora_montevideo(),
    )
    db_temporal.add(tarea)
    db_temporal.commit()

    contratos.finalizar(db_temporal, contrato.id, date(2026, 8, 31))
    assert tarea.estado.value == "pendiente"


# ---------- Listado ----------

def test_listado_orden_y_toggle_finalizados(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    mensual = crear_servicio_directo(db_temporal)
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    unico = crear_servicio_directo(db_temporal, "Gestión ante DGI", "unico")

    finalizado = contratar(db_temporal, cliente, unico, fecha=date(2026, 1, 10))
    contratos.finalizar(db_temporal, finalizado.id, date(2026, 1, 27))
    contratar(db_temporal, cliente, anual, fecha=date(2026, 3, 1))
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 2, 1))

    # Sin finalizados: mensual → anual.
    filas = contratos.listar_contratos(db_temporal, cliente.id)
    assert [f["servicio"].frecuencia.value for f in filas] == ["mensual", "anual"]

    # Con finalizados: aparece el único con su fecha_fin.
    todas = contratos.listar_contratos(db_temporal, cliente.id, incluir_finalizados=True)
    assert [f["servicio"].frecuencia.value for f in todas] == ["mensual", "anual", "unico"]
    assert todas[-1]["contrato"].fecha_fin == date(2026, 1, 27)

    conteos = contratos.contar_contratos(db_temporal, cliente.id)
    assert conteos == {"activos": 2, "finalizados": 1}
