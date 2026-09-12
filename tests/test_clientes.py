"""F1 — servicios de clientes: derivación, validaciones, regímenes."""

from datetime import date

import pytest

from app.models import ClienteRegimenHistorial
from app.services import clientes
from app.services.errores import ErrorValidacion
from tests.utilidades import (
    contratar,
    crear_cliente_directo,
    crear_servicio_directo,
    datos_cliente,
)


# ---------- Alta ----------

def test_crear_cliente_inserta_primer_regimen(db_temporal):
    cliente = clientes.crear_cliente(db_temporal, datos_cliente())

    historial = clientes.historial_regimenes(db_temporal, cliente.id)
    assert len(historial) == 1
    assert historial[0].regimen.value == "monotributo"
    assert historial[0].fecha_desde == date(2026, 1, 15)
    assert historial[0].fecha_hasta is None


def test_rut_debe_tener_12_digitos(db_temporal):
    with pytest.raises(ErrorValidacion) as error:
        clientes.crear_cliente(db_temporal, datos_cliente(rut="123"))
    assert error.value.errores["rut"] == "El RUT debe tener 12 dígitos numéricos."

    with pytest.raises(ErrorValidacion) as error:
        clientes.crear_cliente(db_temporal, datos_cliente(rut="12345678901X"))
    assert error.value.errores["rut"] == "El RUT debe tener 12 dígitos numéricos."


def test_rut_unico_incluye_inactivos(db_temporal):
    crear_cliente_directo(db_temporal, rut="123456789012", activo=False)
    with pytest.raises(ErrorValidacion) as error:
        clientes.crear_cliente(db_temporal, datos_cliente(rut="123456789012"))
    assert error.value.errores["rut"] == "Ya existe un cliente con ese RUT."


def test_ci_unica(db_temporal):
    crear_cliente_directo(db_temporal, ci="4.512.336-7")
    with pytest.raises(ErrorValidacion) as error:
        clientes.crear_cliente(db_temporal, datos_cliente(ci="4.512.336-7"))
    assert error.value.errores["ci"] == "Ya existe un cliente con esa CI."


def test_fecha_inicio_no_futura(db_temporal):
    futura = date(2100, 1, 1)
    with pytest.raises(ErrorValidacion) as error:
        clientes.crear_cliente(db_temporal, datos_cliente(fecha_inicio=futura))
    assert "futura" in error.value.errores["fecha_inicio"]


# ---------- Derivación mensual/eventual y listado ----------

def test_cliente_con_contrato_mensual_activo_es_mensual(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal, frecuencia="mensual")
    contratar(db_temporal, cliente, servicio)
    assert clientes.es_mensual(db_temporal, cliente.id) is True


def test_cliente_sin_contratos_o_solo_anuales_es_eventual(db_temporal):
    sin_contratos = crear_cliente_directo(db_temporal)
    con_anual = crear_cliente_directo(db_temporal, nombre="Otro")
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    contratar(db_temporal, con_anual, anual)

    assert clientes.es_mensual(db_temporal, sin_contratos.id) is False
    assert clientes.es_mensual(db_temporal, con_anual.id) is False


def test_contrato_mensual_finalizado_vuelve_a_eventual(db_temporal):
    from app.services import contratos as sc

    cliente = crear_cliente_directo(db_temporal)
    servicio = crear_servicio_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio)
    assert clientes.es_mensual(db_temporal, cliente.id) is True

    sc.finalizar(db_temporal, contrato.id, date(2026, 8, 31))
    assert clientes.es_mensual(db_temporal, cliente.id) is False


def test_listado_orden_y_filtro_de_inactivos(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    # Mensuales con regímenes desordenados: el orden es alfabético del enum.
    c_regimen_general = crear_cliente_directo(
        db_temporal, nombre="B", regimen="regimen_general"
    )
    c_monotributo = crear_cliente_directo(db_temporal, nombre="A", regimen="monotributo")
    contratar(db_temporal, c_regimen_general, mensual)
    contratar(db_temporal, c_monotributo, mensual)
    # Eventuales: uno activo y uno inactivo.
    eventual = crear_cliente_directo(db_temporal, nombre="Eventual")
    inactivo = crear_cliente_directo(db_temporal, nombre="Inactivo", activo=False)

    listado = clientes.listar_clientes(db_temporal)
    assert [c.regimen.value for c in listado["mensuales"]] == [
        "monotributo", "regimen_general",
    ]
    assert [c.id for c in listado["eventuales"]] == [eventual.id]

    con_inactivos = clientes.listar_clientes(db_temporal, incluir_inactivos=True)
    assert inactivo.id in [c.id for c in con_inactivos["eventuales"]]


# ---------- Edición y cambio de régimen ----------

def test_editar_sin_cambiar_regimen_no_toca_historial(db_temporal):
    cliente = clientes.crear_cliente(db_temporal, datos_cliente())
    clientes.editar_cliente(
        db_temporal, cliente.id, datos_cliente(nombre="Nuevo Nombre"), None
    )
    assert cliente.nombre == "Nuevo Nombre"
    assert len(clientes.historial_regimenes(db_temporal, cliente.id)) == 1


def test_cambio_de_regimen_cierra_y_abre_historial(db_temporal):
    cliente = clientes.crear_cliente(db_temporal, datos_cliente())
    fecha_cambio = date(2026, 6, 1)

    clientes.editar_cliente(
        db_temporal, cliente.id,
        datos_cliente(regimen="regimen_general"),
        fecha_cambio,
    )

    assert cliente.regimen.value == "regimen_general"
    historial = clientes.historial_regimenes(db_temporal, cliente.id)
    assert len(historial) == 2
    # Nuevo vigente (orden descendente: primero el más nuevo)
    assert historial[0].regimen.value == "regimen_general"
    assert historial[0].fecha_desde == fecha_cambio
    assert historial[0].fecha_hasta is None
    # El anterior queda cerrado el día previo al cambio
    assert historial[1].fecha_hasta == date(2026, 5, 31)


def test_cambio_de_regimen_exige_fecha_valida(db_temporal):
    cliente = clientes.crear_cliente(db_temporal, datos_cliente())

    # Sin fecha
    with pytest.raises(ErrorValidacion) as error:
        clientes.editar_cliente(
            db_temporal, cliente.id, datos_cliente(regimen="regimen_general"), None
        )
    assert "fecha_cambio_regimen" in error.value.errores

    # Anterior al inicio del régimen vigente (2026-01-15)
    with pytest.raises(ErrorValidacion) as error:
        clientes.editar_cliente(
            db_temporal, cliente.id,
            datos_cliente(regimen="regimen_general"), date(2026, 1, 1),
        )
    assert "anterior" in error.value.errores["fecha_cambio_regimen"]

    # Futura
    with pytest.raises(ErrorValidacion) as error:
        clientes.editar_cliente(
            db_temporal, cliente.id,
            datos_cliente(regimen="regimen_general"), date(2100, 1, 1),
        )
    assert "futura" in error.value.errores["fecha_cambio_regimen"]


def test_unicidad_en_edicion_excluye_al_propio_cliente(db_temporal):
    cliente = clientes.crear_cliente(
        db_temporal, datos_cliente(rut="123456789012", ci="1.234.567-8")
    )
    # Guardar con su propio RUT/CI no es un duplicado.
    clientes.editar_cliente(
        db_temporal, cliente.id,
        datos_cliente(rut="123456789012", ci="1.234.567-8"), None,
    )
    # Pero chocar contra otro cliente sí.
    crear_cliente_directo(db_temporal, nombre="Otro", rut="999999999999")
    with pytest.raises(ErrorValidacion) as error:
        clientes.editar_cliente(
            db_temporal, cliente.id, datos_cliente(rut="999999999999"), None
        )
    assert error.value.errores["rut"] == "Ya existe un cliente con ese RUT."


def test_desactivar_y_reactivar(db_temporal):
    cliente = crear_cliente_directo(db_temporal)
    clientes.cambiar_activo(db_temporal, cliente.id)
    assert cliente.activo is False
    clientes.cambiar_activo(db_temporal, cliente.id)
    assert cliente.activo is True
