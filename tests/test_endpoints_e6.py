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
