"""F3 — servicios del catálogo: unicidad, orden, restricción de frecuencia."""

from datetime import date

import pytest

from app.services import catalogo
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def test_nombre_unico_incluye_inactivos(db_temporal):
    crear_servicio_directo(db_temporal, "Gestión ante BPS", "unico", activo=False)
    with pytest.raises(ErrorValidacion) as error:
        catalogo.crear_servicio(db_temporal, "Gestión ante BPS", "unico")
    assert error.value.errores["nombre"] == "Ya existe un servicio con ese nombre."


def test_editar_nombre_excluye_al_propio_servicio(db_temporal):
    servicio = crear_servicio_directo(db_temporal, "Liquidación mensual", "mensual")
    crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")

    # Su propio nombre no es duplicado.
    catalogo.editar_servicio(db_temporal, servicio.id, "Liquidación mensual", "mensual")
    # El nombre de otro sí.
    with pytest.raises(ErrorValidacion) as error:
        catalogo.editar_servicio(db_temporal, servicio.id, "DDJJ IVA anual", "mensual")
    assert error.value.errores["nombre"] == "Ya existe un servicio con ese nombre."


def test_orden_por_frecuencia_y_nombre(db_temporal):
    crear_servicio_directo(db_temporal, "Liquidación mensual", "mensual")
    crear_servicio_directo(db_temporal, "Gestión ante DGI", "unico")
    crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    crear_servicio_directo(db_temporal, "DDJJ FONASA", "anual")

    filas = catalogo.listar_servicios(db_temporal)
    assert [f["servicio"].nombre for f in filas] == [
        "DDJJ FONASA", "DDJJ IVA anual",  # anual (alfabético entre sí)
        "Liquidación mensual",            # mensual
        "Gestión ante DGI",               # unico
    ]


def test_no_cambia_frecuencia_con_contratos_activos(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, servicio)

    with pytest.raises(ErrorValidacion) as error:
        catalogo.editar_servicio(db_temporal, servicio.id, "Liquidación mensual", "anual")
    assert error.value.errores["frecuencia"] == (
        "No se puede cambiar la frecuencia de un servicio con contratos activos."
    )
    # El nombre sí puede cambiarse aunque haya contratos.
    catalogo.editar_servicio(db_temporal, servicio.id, "Liquidación", "mensual")
    assert servicio.nombre == "Liquidación"


def test_frecuencia_editable_sin_contratos_activos(db_temporal):
    from app.services import contratos as sc

    servicio = crear_servicio_directo(db_temporal)
    cliente = crear_cliente_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, servicio)
    sc.finalizar(db_temporal, contrato.id, date(2026, 8, 31))

    # Con el contrato finalizado la restricción no aplica.
    catalogo.editar_servicio(db_temporal, servicio.id, "Liquidación mensual", "anual")
    assert servicio.frecuencia.value == "anual"


def test_desactivar_y_reactivar(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    catalogo.cambiar_activo(db_temporal, servicio.id)
    assert servicio.activo is False
    catalogo.cambiar_activo(db_temporal, servicio.id)
    assert servicio.activo is True


def test_conteo_de_contratos_activos(db_temporal):
    servicio = crear_servicio_directo(db_temporal)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, servicio)

    filas = catalogo.listar_servicios(db_temporal)
    assert filas[0]["contratos_activos"] == 1
