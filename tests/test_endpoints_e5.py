"""Endpoints de la Etapa 5 — cobertura proporcional."""

from app.models import Tarea, TareaTemplate
from app.services import fechas
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _con_tarea(db):
    servicio = crear_servicio_directo(db)
    db.add(TareaTemplate(servicio_id=servicio.id, regimen="todos", nombre="Liquidar IVA",
                         orden=1, activo=True))
    db.commit()
    cliente = crear_cliente_directo(db, nombre="Verdulería El Sol")
    contratar(db, cliente, servicio, fecha=fechas.hoy())
    return cliente, db.query(Tarea).one()


def test_vista_de_tareas_agrupa_por_cliente(sesion, db_temporal):
    _con_tarea(db_temporal)
    pagina = sesion.get("/tareas")
    assert pagina.status_code == 200
    assert "Verdulería El Sol" in pagina.text
    assert "Liquidar IVA" in pagina.text
    assert "0 de 1" in pagina.text


def test_menu_muestra_progreso_del_periodo(sesion, db_temporal):
    _con_tarea(db_temporal)
    pagina = sesion.get("/clientes")
    assert 'id="nav-progreso"' in pagina.text
    assert "0/1" in pagina.text


def test_avanzar_estado_por_htmx_devuelve_el_grupo(sesion, db_temporal):
    _, tarea = _con_tarea(db_temporal)
    respuesta = sesion.post(f"/tareas/{tarea.id}/avanzar", data={"estado": "todas"})
    assert respuesta.status_code == 200
    assert "En proceso" in respuesta.text
    assert 'hx-swap-oob="true"' in respuesta.text


def test_cancelar_pide_confirmacion_literal(sesion, db_temporal):
    _con_tarea(db_temporal)
    pagina = sesion.get("/tareas")
    assert "¿Confirmás que querés cancelar esta tarea?" in pagina.text


def test_crear_tarea_ad_hoc(sesion, db_temporal):
    _, tarea = _con_tarea(db_temporal)
    respuesta = sesion.post("/tareas/nueva", data={
        "servicio_contratado_id": str(tarea.servicio_contratado_id),
        "nombre": "Pedir nota de crédito",
        "periodo": fechas.hoy().strftime("%Y-%m"),
        "requiere_info_cliente": "1",
    }, follow_redirects=False)
    assert respuesta.status_code == 303
    assert db_temporal.query(Tarea).count() == 2


def test_templates_crear_desde_la_web(sesion, db_temporal):
    servicio = crear_servicio_directo(db_temporal, "DDJJ IVA anual", "anual")
    sin_mes = sesion.post("/configuracion/templates/nuevo", data={
        "servicio_id": str(servicio.id), "regimen": "todos",
        "nombre": "Preparar DDJJ", "orden": "1", "mes_generacion": "",
    })
    assert sin_mes.status_code == 422
    assert "mes de generación es obligatorio" in sin_mes.text

    ok = sesion.post("/configuracion/templates/nuevo", data={
        "servicio_id": str(servicio.id), "regimen": "todos",
        "nombre": "Preparar DDJJ", "orden": "1", "mes_generacion": "6",
    }, follow_redirects=False)
    assert ok.status_code == 303
    listado = sesion.get("/configuracion/templates")
    assert "Preparar DDJJ" in listado.text
    assert "junio" in listado.text


# ---------- Corte 5b: vencimientos ----------

def _vencimiento(db, dia, regimen="todos", organismo="dgi"):
    from app.models import VencimientoCalendario
    v = VencimientoCalendario(descripcion="IVA e IRPF mensual", regimen=regimen,
                              organismo=organismo, dia_vencimiento=dia, activo=True)
    db.add(v)
    db.commit()
    return v


def test_tareas_muestran_fecha_limite_y_semaforo(sesion, db_temporal):
    _con_tarea(db_temporal)
    _vencimiento(db_temporal, dia=31)  # último día del mes en curso: nunca pasó
    pagina = sesion.get("/tareas")
    assert "Fecha límite:" in pagina.text
    assert 'title="Semáforo"' in pagina.text


def test_calendario_y_proximos(sesion, db_temporal):
    crear_cliente_directo(db_temporal, nombre="Cliente Alcanzado")
    _vencimiento(db_temporal, dia=31)
    pagina = sesion.get("/vencimientos")
    assert pagina.status_code == 200
    assert "IVA e IRPF mensual" in pagina.text
    assert "Cliente Alcanzado" in pagina.text  # panel de detalle


def test_calendario_vacio_muestra_literal(sesion, db_temporal):
    pagina = sesion.get("/vencimientos")
    assert "No hay vencimientos en los próximos 15 días." in pagina.text


def test_crear_vencimiento_y_ver_en_la_ficha(sesion, db_temporal):
    cliente = crear_cliente_directo(db_temporal, regimen="monotributo")
    respuesta = sesion.post("/configuracion/vencimientos/nuevo", data={
        "descripcion": "Aportes mensuales", "organismo": "bps", "regimen": "monotributo",
        "mes": "", "dia_vencimiento": "31", "anio": "",
    }, follow_redirects=False)
    assert respuesta.status_code == 303
    ficha = sesion.get(f"/clientes/{cliente.id}/vencimientos")
    assert "Aportes mensuales" in ficha.text
