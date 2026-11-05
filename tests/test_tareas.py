"""F7 — Templates, generación de tareas (día 1 y al contratar), estados,
ad-hoc y casos borde (Etapa 5, corte 5a)."""

from datetime import date

import pytest

from app.models import Tarea, TareaTemplate
from app.services import clientes as servicio_clientes
from app.services import contratos as sc
from app.services import fechas, tareas, templates_tareas
from app.services.errores import ErrorValidacion
from tests.utilidades import (
    contratar,
    crear_cliente_directo,
    crear_servicio_directo,
    datos_cliente,
)

HOY_FIJO = date(2026, 11, 15)
NOVIEMBRE = date(2026, 11, 1)


@pytest.fixture(autouse=True)
def fijar_hoy(monkeypatch):
    # Cada servicio tiene su propia función hoy(): se fijan todas.
    for modulo in (fechas, servicio_clientes, sc):
        monkeypatch.setattr(modulo, "hoy", lambda: HOY_FIJO)


def _template(db, servicio, nombre, regimen="todos", orden=1, mes=None, activo=True):
    t = TareaTemplate(servicio_id=servicio.id, regimen=regimen, nombre=nombre,
                      orden=orden, mes_generacion=mes, activo=activo)
    db.add(t)
    db.commit()
    return t


def _tareas(db, periodo=NOVIEMBRE):
    return db.query(Tarea).filter(Tarea.periodo == periodo).order_by(Tarea.id).all()


# ---------- Templates ----------

def test_template_anual_exige_mes_de_generacion(db_temporal):
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    with pytest.raises(ErrorValidacion) as error:
        templates_tareas.crear_template(db_temporal, anual.id, "todos", "Preparar", "", "1", "")
    assert "mes_generacion" in error.value.errores

    t = templates_tareas.crear_template(db_temporal, anual.id, "todos", "Preparar", "", "1", "6")
    assert t.mes_generacion == 6


def test_template_mensual_ignora_mes_de_generacion(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    t = templates_tareas.crear_template(db_temporal, mensual.id, "todos", "Liquidar", "", "1", "6")
    assert t.mes_generacion is None


def test_unicidad_servicio_regimen_nombre_entre_activos(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    templates_tareas.crear_template(db_temporal, mensual.id, "monotributo", "Boleto BPS", "", "1", "")
    with pytest.raises(ErrorValidacion) as error:
        templates_tareas.crear_template(db_temporal, mensual.id, "monotributo", "Boleto BPS", "", "2", "")
    assert "nombre" in error.value.errores
    # Mismo nombre en OTRO régimen: permitido.
    templates_tareas.crear_template(db_temporal, mensual.id, "regimen_general", "Boleto BPS", "", "1", "")


def test_orden_no_se_repite_en_la_misma_combinacion(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    templates_tareas.crear_template(db_temporal, mensual.id, "monotributo", "A", "", "1", "")
    with pytest.raises(ErrorValidacion) as error:
        templates_tareas.crear_template(db_temporal, mensual.id, "monotributo", "B", "", "1", "")
    assert "orden" in error.value.errores
    with pytest.raises(ErrorValidacion):
        templates_tareas.crear_template(db_temporal, mensual.id, "monotributo", "C", "", "0", "")


def test_reactivar_no_puede_duplicar(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    viejo = templates_tareas.crear_template(db_temporal, mensual.id, "todos", "A", "", "1", "")
    templates_tareas.cambiar_activo(db_temporal, viejo.id)  # desactivar
    templates_tareas.crear_template(db_temporal, mensual.id, "todos", "A", "", "2", "")
    with pytest.raises(ErrorValidacion):
        templates_tareas.cambiar_activo(db_temporal, viejo.id)


# ---------- Generación del día 1 ----------

def test_generacion_mensual_matchea_regimen_y_todos(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Genérica", regimen="todos", orden=1)
    _template(db_temporal, mensual, "Solo monotributo", regimen="monotributo", orden=2)
    _template(db_temporal, mensual, "Solo general", regimen="regimen_general", orden=3)
    _template(db_temporal, mensual, "Inactiva", regimen="todos", orden=4, activo=False)
    cliente = crear_cliente_directo(db_temporal, regimen="monotributo")
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 1, 1))
    db_temporal.query(Tarea).delete()  # la de "al contratar" no interesa acá
    db_temporal.commit()

    creadas = tareas.generar_tareas_periodo(db_temporal, NOVIEMBRE)
    db_temporal.commit()

    assert creadas == 2
    nombres = {t.nombre for t in _tareas(db_temporal)}
    assert nombres == {"Genérica", "Solo monotributo"}
    tarea = _tareas(db_temporal)[0]
    assert tarea.estado.value == "pendiente"
    assert tarea.requiere_info_cliente is False


def test_generacion_es_re_ejecutable_sin_duplicar(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Liquidar")
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 1, 1))

    tareas.generar_tareas_periodo(db_temporal, NOVIEMBRE)
    tareas.generar_tareas_periodo(db_temporal, NOVIEMBRE)
    db_temporal.commit()
    assert len(_tareas(db_temporal)) == 1


def test_anual_solo_en_su_mes_de_generacion(db_temporal):
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    _template(db_temporal, anual, "Preparar DDJJ", mes=11)
    _template(db_temporal, anual, "Otra en junio", mes=6, orden=2)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, anual, fecha=date(2026, 1, 1))

    tareas.generar_tareas_periodo(db_temporal, NOVIEMBRE)
    db_temporal.commit()
    assert [t.nombre for t in _tareas(db_temporal)] == ["Preparar DDJJ"]

    tareas.generar_tareas_periodo(db_temporal, date(2026, 12, 1))
    db_temporal.commit()
    assert _tareas(db_temporal, date(2026, 12, 1)) == []


def test_contrato_finalizado_no_genera(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Liquidar")
    cliente = crear_cliente_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, mensual, fecha=date(2026, 1, 1))
    sc.finalizar(db_temporal, contrato.id, date(2026, 10, 31))

    tareas.generar_tareas_periodo(db_temporal, date(2026, 12, 1))
    db_temporal.commit()
    assert _tareas(db_temporal, date(2026, 12, 1)) == []


def test_cambio_de_regimen_aplica_a_la_siguiente_generacion(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Boleto monotributo", regimen="monotributo")
    _template(db_temporal, mensual, "Boleto general", regimen="regimen_general")
    cliente = servicio_clientes.crear_cliente(
        db_temporal, datos_cliente(regimen="monotributo", fecha_inicio=date(2026, 1, 1))
    )
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 1, 1))
    assert [t.nombre for t in _tareas(db_temporal)] == ["Boleto monotributo"]

    servicio_clientes.editar_cliente(
        db_temporal, cliente.id, datos_cliente(regimen="regimen_general"), date(2026, 11, 10)
    )
    tareas.generar_tareas_periodo(db_temporal, date(2026, 12, 1))
    db_temporal.commit()
    # Las de noviembre no se tocan; diciembre usa el nuevo régimen.
    assert [t.nombre for t in _tareas(db_temporal)] == ["Boleto monotributo"]
    assert [t.nombre for t in _tareas(db_temporal, date(2026, 12, 1))] == ["Boleto general"]


def test_template_desactivado_no_genera_y_no_toca_las_existentes(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    template = _template(db_temporal, mensual, "Liquidar")
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 1, 1))
    templates_tareas.cambiar_activo(db_temporal, template.id)

    tareas.generar_tareas_periodo(db_temporal, date(2026, 12, 1))
    db_temporal.commit()
    assert _tareas(db_temporal, date(2026, 12, 1)) == []
    assert len(_tareas(db_temporal)) == 1  # la de noviembre sigue ahí


# ---------- Generación al contratar ----------

def test_contratar_mensual_genera_el_periodo_en_curso(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Liquidar")
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 11, 14))
    assert [t.periodo for t in _tareas(db_temporal)] == [NOVIEMBRE]


def test_contratar_unico_genera_si_hay_templates(db_temporal):
    unico = crear_servicio_directo(db_temporal, "Certificado de ingresos", "unico")
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, unico, fecha=date(2026, 11, 3))
    assert _tareas(db_temporal) == []  # sin templates: sin tareas

    _template(db_temporal, unico, "Emitir certificado")
    contratar(db_temporal, cliente, unico, fecha=date(2026, 11, 3))
    assert [t.nombre for t in _tareas(db_temporal)] == ["Emitir certificado"]


def test_contratar_anual_no_genera(db_temporal):
    anual = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    _template(db_temporal, anual, "Preparar", mes=11)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, anual, fecha=date(2026, 11, 3))
    assert _tareas(db_temporal) == []


# ---------- Estados ----------

def _una_tarea(db):
    mensual = crear_servicio_directo(db)
    _template(db, mensual, "Liquidar")
    cliente = crear_cliente_directo(db)
    contratar(db, cliente, mensual, fecha=date(2026, 11, 1))
    return _tareas(db)[0]


def test_ciclo_de_estados_y_reapertura(db_temporal):
    tarea = _una_tarea(db_temporal)

    tareas.avanzar_estado(db_temporal, tarea.id)
    assert tarea.estado.value == "en_proceso"
    tareas.avanzar_estado(db_temporal, tarea.id)
    assert tarea.estado.value == "completada"
    assert tarea.fecha_completada is not None
    tareas.avanzar_estado(db_temporal, tarea.id)  # reabrir
    assert tarea.estado.value == "pendiente"
    assert tarea.fecha_completada is None


def test_cancelar_y_reabrir(db_temporal):
    tarea = _una_tarea(db_temporal)
    tareas.cancelar(db_temporal, tarea.id)
    assert tarea.estado.value == "cancelada"
    with pytest.raises(ErrorValidacion):
        tareas.cancelar(db_temporal, tarea.id)  # ya terminada
    tareas.avanzar_estado(db_temporal, tarea.id)
    assert tarea.estado.value == "pendiente"


def test_progreso_excluye_canceladas(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    for orden, nombre in enumerate(["A", "B", "C"], start=1):
        _template(db_temporal, mensual, nombre, orden=orden)
    cliente = crear_cliente_directo(db_temporal)
    contratar(db_temporal, cliente, mensual, fecha=date(2026, 11, 1))
    a, b, _ = _tareas(db_temporal)
    tareas.cancelar(db_temporal, a.id)
    tareas.avanzar_estado(db_temporal, b.id)
    tareas.avanzar_estado(db_temporal, b.id)

    assert tareas.progreso_periodo(db_temporal, NOVIEMBRE) == (1, 2)


# ---------- Ad-hoc, edición y agrupado ----------

def test_ad_hoc_y_orden_en_el_grupo(db_temporal):
    mensual = crear_servicio_directo(db_temporal)
    _template(db_temporal, mensual, "Segunda", orden=2)
    _template(db_temporal, mensual, "Primera", orden=1)
    cliente = crear_cliente_directo(db_temporal)
    contrato = contratar(db_temporal, cliente, mensual, fecha=date(2026, 11, 1))
    tareas.crear_ad_hoc(db_temporal, contrato.id, "Pedir nota de crédito", NOVIEMBRE, True, "")

    grupos = tareas.grupos_del_periodo(db_temporal, NOVIEMBRE)
    assert len(grupos) == 1
    nombres = [f["tarea"].nombre for f in grupos[0]["filas"]]
    assert nombres == ["Primera", "Segunda", "Pedir nota de crédito"]
    assert grupos[0]["total"] == 3


def test_ad_hoc_validaciones(db_temporal):
    with pytest.raises(ErrorValidacion) as error:
        tareas.crear_ad_hoc(db_temporal, None, " ", None, False, "")
    assert set(error.value.errores) == {"servicio_contratado_id", "nombre", "periodo"}


def test_edicion_limitada(db_temporal):
    tarea = _una_tarea(db_temporal)  # viene de template
    tareas.editar_tarea(db_temporal, tarea.id, "Nombre nuevo", True, "una nota")
    assert tarea.nombre == "Liquidar"  # no cambia: no es ad-hoc
    assert tarea.requiere_info_cliente is True
    assert tarea.notas == "una nota"


def test_filtro_pendientes(db_temporal):
    tarea = _una_tarea(db_temporal)
    tareas.avanzar_estado(db_temporal, tarea.id)
    tareas.avanzar_estado(db_temporal, tarea.id)  # completada
    assert tareas.grupos_del_periodo(db_temporal, NOVIEMBRE, filtro_estado="pendientes") == []
    assert len(tareas.grupos_del_periodo(db_temporal, NOVIEMBRE, filtro_estado="completadas")) == 1
