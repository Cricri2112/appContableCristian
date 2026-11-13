"""Endpoints de la Etapa 6 — cobertura proporcional."""

from datetime import timedelta

from app.models import Recordatorio, VencimientoCalendario
from app.services import ajustes, fechas, recordatorios
from tests.utilidades import crear_cliente_directo


def _vencimiento_en(db, dias):
    """Un vencimiento recurrente que cae dentro de `dias` días (mismo mes)."""
    fecha = fechas.hoy() + timedelta(days=dias)
    db.add(VencimientoCalendario(descripcion="Aportes mensuales", organismo="bps",
                                 regimen="todos", dia_vencimiento=fecha.day,
                                 mes=fecha.month, anio=fecha.year, activo=True))
    db.commit()


def _con_recordatorio(db):
    crear_cliente_directo(db)
    _vencimiento_en(db, 5)
    recordatorios.generar_vencimientos_proximos(db, fechas.hoy())
    db.commit()
    return db.query(Recordatorio).one()


# ---------- Corte 6a ----------

def test_campanita_muestra_el_contador(sesion, db_temporal):
    _con_recordatorio(db_temporal)
    pagina = sesion.get("/clientes")
    assert 'id="badge-recordatorios"' in pagina.text
    assert 'hx-get="/recordatorios/panel"' in pagina.text


def test_panel_lista_y_silencia(sesion, db_temporal):
    recordatorio = _con_recordatorio(db_temporal)
    panel = sesion.get("/recordatorios/panel")
    assert "Aportes mensuales (BPS) vence el" in panel.text
    assert "Ver calendario" in panel.text

    respuesta = sesion.post(f"/recordatorios/{recordatorio.id}/silenciar", data={"dias": "3"})
    assert respuesta.status_code == 200
    assert "No hay recordatorios activos." in respuesta.text
    db_temporal.refresh(recordatorio)
    assert recordatorio.estado.value == "silenciado"


def test_notificaciones_guarda_el_email(sesion, db_temporal):
    pagina = sesion.get("/configuracion/notificaciones")
    assert pagina.status_code == 200
    assert "Email resumen diario" in pagina.text

    malo = sesion.post("/configuracion/notificaciones", data={"email_destino": "x"})
    assert malo.status_code == 422
    ok = sesion.post("/configuracion/notificaciones", data={"email_destino": "yo@ejemplo.com"},
                     follow_redirects=False)
    assert ok.status_code == 303
    assert ajustes.email_destino(db_temporal) == "yo@ejemplo.com"


# ---------- Corte 6b ----------

def test_dashboard_muestra_los_bloques(sesion):
    pagina = sesion.get("/")
    assert pagina.status_code == 200
    for texto in ("Ingresos del mes", "P&amp;L del mes", "Próximos vencimientos",
                  "Tareas del período", "Mayor saldo deudor"):
        assert texto in pagina.text


def test_historico_y_proyeccion(sesion):
    historico = sesion.get("/finanzas/historico")
    assert historico.status_code == 200
    assert "Histórico · últimos 12 meses" in historico.text
    proyeccion = sesion.get("/finanzas/proyeccion")
    assert proyeccion.status_code == 200
    assert ("Proyección basada en la cartera actual. No incluye trabajos únicos "
            "ni cambios futuros.") in proyeccion.text


def test_abm_de_gastos(sesion, db_temporal):
    from app.models import GastoIngresoPropio

    hoy = fechas.hoy()
    datos = {"tipo": "gasto", "fecha": hoy.isoformat(), "concepto": "Aportes CJPPU",
             "importe": "12.400", "categoria": "cjppu", "notas": "",
             "f_periodo": hoy.strftime("%Y-%m"), "f_tipo": "", "f_categoria": ""}

    malo = sesion.post("/finanzas/gastos/nuevo", data=datos | {"concepto": ""})
    assert malo.status_code == 422
    assert "El concepto no puede estar vacío." in malo.text

    ok = sesion.post("/finanzas/gastos/nuevo", data=datos, follow_redirects=False)
    assert ok.status_code == 303
    movimiento = db_temporal.query(GastoIngresoPropio).one()

    listado = sesion.get(ok.headers["location"])
    assert "Aportes CJPPU" in listado.text

    confirmar = sesion.get(f"/finanzas/gastos/{movimiento.id}/eliminar")
    assert ("¿Confirmás que querés eliminar este registro? Esta acción no se puede "
            "deshacer.") in confirmar.text
    sesion.post(f"/finanzas/gastos/{movimiento.id}/eliminar", data={})
    db_temporal.expire_all()
    assert db_temporal.query(GastoIngresoPropio).count() == 0
