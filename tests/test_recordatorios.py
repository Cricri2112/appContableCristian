"""F10 — Recordatorios: reglas de los tres tipos, anti-duplicados,
silenciar con restricciones, cierre automático, proceso diario, email y
respaldo (Etapa 6, corte 6a)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.config import settings
from app.models import (
    Cobro,
    Recordatorio,
    SchedulerEjecucion,
    Tarea,
    TareaTemplate,
    VencimientoCalendario,
)
from app.services import (
    ajustes,
    cobros,
    email,
    fechas,
    recordatorios,
    respaldo,
    scheduler,
    tareas,
)
from app.services.errores import ErrorValidacion
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo

HOY = date(2026, 11, 20)


@pytest.fixture(autouse=True)
def fijar_hoy(monkeypatch, tmp_path):
    monkeypatch.setattr(fechas, "hoy", lambda: HOY)
    # Las ejecuciones del scheduler se registran con la hora "actual".
    monkeypatch.setattr(scheduler, "ahora_montevideo", lambda: datetime(2026, 11, 20, 7, 0))
    monkeypatch.setattr(settings, "respaldos_dir", str(tmp_path / "respaldos"))


def _activos(db, tipo=None):
    consulta = db.query(Recordatorio).filter(Recordatorio.estado != "cerrado")
    if tipo:
        consulta = consulta.filter(Recordatorio.tipo == tipo)
    return consulta.all()


# ---------- tarea_pendiente ----------

def _tarea(db, dias_desde_creacion, cliente_nombre="Verdulería El Sol"):
    servicio = crear_servicio_directo(db, nombre=f"Servicio {dias_desde_creacion}")
    cliente = crear_cliente_directo(db, nombre=cliente_nombre)
    contrato = contratar(db, cliente, servicio, fecha=date(2026, 1, 1))
    tarea = Tarea(
        servicio_contratado_id=contrato.id, nombre="Liquidar IVA",
        periodo=date(2026, 11, 1), estado="pendiente",
        fecha_creacion=datetime.combine(HOY - timedelta(days=dias_desde_creacion), datetime.min.time()),
    )
    db.add(tarea)
    db.commit()
    return tarea


def test_tarea_pendiente_a_los_10_dias(db_temporal):
    _tarea(db_temporal, 9)
    vieja = _tarea(db_temporal, 10)
    assert recordatorios.generar_tareas_pendientes(db_temporal, HOY) == 1
    db_temporal.commit()
    r = _activos(db_temporal, "tarea_pendiente")[0]
    assert r.tarea_id == vieja.id
    assert r.mensaje == "La tarea Liquidar IVA de Verdulería El Sol lleva 10 días sin completarse."
    assert r.repetir_hasta_completar is True
    assert r.intervalo_repeticion_horas == 24
    # Anti-duplicado
    assert recordatorios.generar_tareas_pendientes(db_temporal, HOY) == 0


def test_completar_la_tarea_cierra_el_recordatorio_y_reabrirla_genera_otro(db_temporal):
    tarea = _tarea(db_temporal, 12)
    recordatorios.generar_tareas_pendientes(db_temporal, HOY)
    db_temporal.commit()

    tareas.avanzar_estado(db_temporal, tarea.id)  # en proceso: sigue abierto
    assert len(_activos(db_temporal, "tarea_pendiente")) == 1
    tareas.avanzar_estado(db_temporal, tarea.id)  # completada: se cierra solo
    assert _activos(db_temporal, "tarea_pendiente") == []

    tareas.avanzar_estado(db_temporal, tarea.id)  # reabierta
    assert recordatorios.generar_tareas_pendientes(db_temporal, HOY) == 1


# ---------- vencimiento_proximo ----------

def _vencimiento(db, dia, regimen="todos"):
    v = VencimientoCalendario(descripcion="Aportes mensuales", organismo="bps",
                              regimen=regimen, dia_vencimiento=dia, activo=True)
    db.add(v)
    db.commit()
    return v


def test_vencimiento_a_5_2_y_1_dias(db_temporal):
    crear_cliente_directo(db_temporal)
    _vencimiento(db_temporal, 25)  # HOY 20 → faltan 5
    _vencimiento(db_temporal, 22)  # faltan 2
    _vencimiento(db_temporal, 24)  # faltan 4: no genera

    assert recordatorios.generar_vencimientos_proximos(db_temporal, HOY) == 2
    db_temporal.commit()
    mensajes = sorted(r.mensaje for r in _activos(db_temporal, "vencimiento_proximo"))
    assert mensajes == [
        "Aportes mensuales (BPS) vence el 22/11/2026 — faltan 2 días. Afecta a 1 cliente.",
        "Aportes mensuales (BPS) vence el 25/11/2026 — faltan 5 días. Afecta a 1 cliente.",
    ]
    assert all(r.repetir_hasta_completar is False for r in _activos(db_temporal))
    assert recordatorios.generar_vencimientos_proximos(db_temporal, HOY) == 0  # anti-duplicado


def test_vencimiento_sin_clientes_activos_no_genera(db_temporal):
    crear_cliente_directo(db_temporal, regimen="monotributo")
    _vencimiento(db_temporal, 25, regimen="regimen_general")
    assert recordatorios.generar_vencimientos_proximos(db_temporal, HOY) == 0


def test_vencimiento_se_cierra_al_pasar_la_fecha(db_temporal):
    crear_cliente_directo(db_temporal)
    _vencimiento(db_temporal, 21)  # falta 1 día
    recordatorios.generar_vencimientos_proximos(db_temporal, HOY)
    db_temporal.commit()
    assert recordatorios.cerrar_resueltos(db_temporal, date(2026, 11, 21)) == 0
    assert recordatorios.cerrar_resueltos(db_temporal, date(2026, 11, 22)) == 1


# ---------- cobro_pendiente ----------

def _cliente_mensual(db, desde=date(2026, 1, 1)):
    servicio = crear_servicio_directo(db)
    cliente = crear_cliente_directo(db, nombre="Rodríguez, Martín")
    contrato = contratar(db, cliente, servicio, fecha=desde, honorario="5700")
    return cliente, contrato


def test_cobro_pendiente_evalua_el_periodo_de_hace_dos_meses(db_temporal):
    cliente, _ = _cliente_mensual(db_temporal)
    # HOY 20/11 → se evalúa setiembre.
    assert recordatorios.generar_cobros_pendientes(db_temporal, HOY) == 1
    db_temporal.commit()
    r = _activos(db_temporal, "cobro_pendiente")[0]
    assert r.periodo == date(2026, 9, 1)
    assert r.cliente_id == cliente.id
    assert r.mensaje.startswith("Rodríguez, Martín tiene pendiente el pago de set 2026. Saldo actual: $ ")
    assert recordatorios.generar_cobros_pendientes(db_temporal, HOY) == 0  # anti-duplicado


def test_contrato_posterior_al_periodo_no_genera(db_temporal):
    _cliente_mensual(db_temporal, desde=date(2026, 10, 1))
    assert recordatorios.generar_cobros_pendientes(db_temporal, HOY) == 0


def test_registrar_cobro_que_cubre_el_periodo_cierra_el_recordatorio(db_temporal):
    cliente, contrato = _cliente_mensual(db_temporal)
    recordatorios.generar_cobros_pendientes(db_temporal, HOY)
    db_temporal.commit()

    cobros.registrar_cobro(db_temporal, {
        "cliente_id": cliente.id, "servicio_contratado_id": contrato.id,
        "periodo_desde": date(2026, 9, 1), "periodo_hasta": date(2026, 9, 30),
        "fecha_cobro": date(2026, 11, 5), "importe": "5.700",
        "forma_pago": "transferencia", "tipo_comprobante": "e_ticket", "notas": "",
    })
    assert _activos(db_temporal, "cobro_pendiente") == []


# ---------- Silenciar ----------

def test_silenciar_vencimiento_respeta_la_fecha(db_temporal):
    crear_cliente_directo(db_temporal)
    _vencimiento(db_temporal, 25)  # faltan 5
    recordatorios.generar_vencimientos_proximos(db_temporal, HOY)
    db_temporal.commit()
    r = _activos(db_temporal)[0]

    assert recordatorios.opciones_silencio(db_temporal, r, HOY) == [(3, True), (5, True), (7, False)]
    with pytest.raises(ErrorValidacion):
        recordatorios.silenciar(db_temporal, r.id, 7)

    recordatorios.silenciar(db_temporal, r.id, 3)
    assert r.estado.value == "silenciado"
    assert r.silenciado_hasta == date(2026, 11, 23)
    assert recordatorios.contar_activos(db_temporal) == 0


def test_vencimiento_a_1_dia_no_se_puede_silenciar(db_temporal):
    crear_cliente_directo(db_temporal)
    _vencimiento(db_temporal, 21)
    recordatorios.generar_vencimientos_proximos(db_temporal, HOY)
    db_temporal.commit()
    item = recordatorios.panel(db_temporal)[0]
    assert item.silenciable is False


def test_cobro_pendiente_siempre_silenciable_y_reaparece(db_temporal):
    _cliente_mensual(db_temporal)
    recordatorios.generar_cobros_pendientes(db_temporal, HOY)
    db_temporal.commit()
    r = _activos(db_temporal)[0]
    assert all(h for _, h in recordatorios.opciones_silencio(db_temporal, r, HOY))

    recordatorios.silenciar(db_temporal, r.id, 3)  # hasta el 23
    assert recordatorios.reabrir_silenciados(db_temporal, date(2026, 11, 23)) == 0
    assert recordatorios.reabrir_silenciados(db_temporal, date(2026, 11, 24)) == 1
    db_temporal.commit()
    assert r.estado.value == "pendiente"


def test_tarea_se_silencia_hasta_su_fecha_limite(db_temporal):
    tarea = _tarea(db_temporal, 12)
    _vencimiento(db_temporal, 24)  # fecha límite del cliente: 24/11
    recordatorios.generar_tareas_pendientes(db_temporal, HOY)
    db_temporal.commit()
    r = _activos(db_temporal, "tarea_pendiente")[0]
    assert r.tarea_id == tarea.id
    assert recordatorios.opciones_silencio(db_temporal, r, HOY) == [(3, True), (5, False), (7, False)]


# ---------- Panel ----------

def test_orden_del_panel(db_temporal):
    _tarea(db_temporal, 15)
    _cliente_mensual(db_temporal)
    _vencimiento(db_temporal, 25)
    _vencimiento(db_temporal, 22)
    recordatorios.generar_tareas_pendientes(db_temporal, HOY)
    recordatorios.generar_cobros_pendientes(db_temporal, HOY)
    recordatorios.generar_vencimientos_proximos(db_temporal, HOY)
    db_temporal.commit()

    tipos = [i.recordatorio.tipo.value for i in recordatorios.panel(db_temporal)]
    assert tipos[:2] == ["vencimiento_proximo", "vencimiento_proximo"]
    assert set(tipos[2:]) == {"tarea_pendiente", "cobro_pendiente"}
    primero = recordatorios.panel(db_temporal)[0]
    assert "22/11/2026" in primero.recordatorio.mensaje  # el más cercano primero
    cobro = [i for i in recordatorios.panel(db_temporal) if i.recordatorio.tipo.value == "cobro_pendiente"][0]
    assert cobro.etiqueta_url == "Registrar cobro"  # H-03


# ---------- Proceso diario, email y respaldo ----------

@pytest.fixture
def base_en_settings(db_temporal, monkeypatch):
    """El respaldo copia la base de settings.database_url: se apunta a la temporal."""
    monkeypatch.setattr(settings, "database_url", str(db_temporal.get_bind().url))
    return db_temporal


@pytest.fixture
def email_falso(monkeypatch):
    enviados = []
    monkeypatch.setattr(email, "enviar_email",
                        lambda destino, asunto, html: enviados.append((destino, asunto, html)))
    return enviados


def test_diario_envia_un_email_agrupado_y_marca_enviados(base_en_settings, email_falso):
    db = base_en_settings
    ajustes.guardar_email_destino(db, "contador@ejemplo.com")
    _tarea(db, 11)
    crear_cliente_directo(db, nombre="Otro")
    _vencimiento(db, 25)

    resultado = scheduler.ejecutar_proceso_diario(db)
    assert resultado.startswith("ok")
    assert len(email_falso) == 1
    destino, asunto, html = email_falso[0]
    assert destino == "contador@ejemplo.com"
    assert asunto == "Estudio: 2 recordatorios activos"
    assert html.index("Vencimientos próximos") < html.index("Tareas atrasadas")
    assert all(r.fecha_enviada is not None for r in _activos(db))

    # El mismo día no se repite (salvo forzado).
    assert scheduler.ejecutar_proceso_diario(db) == "ya corrió hoy"
    assert len(email_falso) == 1


def test_diario_forzado_repite_solo_lo_que_repite(base_en_settings, email_falso):
    db = base_en_settings
    ajustes.guardar_email_destino(db, "contador@ejemplo.com")
    _tarea(db, 11)
    crear_cliente_directo(db, nombre="Otro")
    _vencimiento(db, 25)
    scheduler.ejecutar_proceso_diario(db)
    scheduler.ejecutar_proceso_diario(db, forzar=True)

    assert len(email_falso) == 2
    assert email_falso[1][1] == "Estudio: 1 recordatorio activo"  # el vencimiento no repite
    assert len(_activos(db)) == 2  # no se duplicaron


def test_sin_activos_no_se_envia_email(base_en_settings, email_falso):
    resultado = scheduler.ejecutar_proceso_diario(base_en_settings)
    assert email_falso == []
    assert "sin recordatorios activos" in resultado


def test_falla_del_email_no_corta_el_ciclo(base_en_settings, monkeypatch):
    db = base_en_settings
    _tarea(db, 11)

    def falla(destino, asunto, html):
        raise email.ErrorEmail("clave inválida")

    monkeypatch.setattr(email, "enviar_email", falla)
    resultado = scheduler.ejecutar_proceso_diario(db)

    assert resultado.startswith("ok")
    assert "email: ERROR — clave inválida" in resultado
    assert "respaldo: estudio-2026-11-20.db" in resultado  # el respaldo se hizo igual
    assert len(_activos(db, "tarea_pendiente")) == 1
    registro = db.query(SchedulerEjecucion).filter(SchedulerEjecucion.proceso == "diario").one()
    assert "clave inválida" in registro.resultado


def test_recuperacion_del_diario_solo_despues_de_las_6(base_en_settings, email_falso):
    db = base_en_settings
    assert scheduler.recuperar_diario(db, datetime(2026, 11, 20, 5, 30)) is False
    assert scheduler.recuperar_diario(db, datetime(2026, 11, 20, 9, 0)) is True
    assert scheduler.recuperar_diario(db, datetime(2026, 11, 20, 10, 0)) is False


def test_mensual_genera_cobros_pendientes(db_temporal):
    _cliente_mensual(db_temporal)
    db_temporal.add(TareaTemplate(servicio_id=1, regimen="todos", nombre="X", orden=1, activo=True))
    db_temporal.commit()
    assert scheduler.ejecutar_proceso_mensual(db_temporal) == "ok"
    assert len(_activos(db_temporal, "cobro_pendiente")) == 1


def test_retencion_de_respaldos(tmp_path):
    carpeta = tmp_path / "r"
    carpeta.mkdir()
    for fecha in ["2026-08-01", "2026-08-15", "2026-09-03", "2026-10-25", "2026-11-19"]:
        (carpeta / f"estudio-{fecha}.db").write_text("x")
    respaldo.aplicar_retencion(carpeta, HOY)
    quedan = sorted(p.name for p in carpeta.iterdir())
    # Se borra solo 2026-08-15: tiene más de 30 días y no es el primero de su mes.
    assert quedan == [
        "estudio-2026-08-01.db", "estudio-2026-09-03.db",
        "estudio-2026-10-25.db", "estudio-2026-11-19.db",
    ]


def test_respaldo_copia_la_base(base_en_settings):
    destino = respaldo.hacer_respaldo(HOY)
    assert destino.name == "estudio-2026-11-20.db"
    assert Path(destino).stat().st_size > 0


# ---------- Ajustes ----------

def test_email_de_destino(db_temporal):
    assert ajustes.email_destino(db_temporal) is None
    with pytest.raises(ErrorValidacion):
        ajustes.guardar_email_destino(db_temporal, "no-es-un-email")
    ajustes.guardar_email_destino(db_temporal, "  yo@ejemplo.com ")
    ajustes.guardar_email_destino(db_temporal, "otro@ejemplo.com")
    assert ajustes.email_destino(db_temporal) == "otro@ejemplo.com"


def test_email_sin_configurar_lanza_error(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", None)
    with pytest.raises(email.ErrorEmail):
        email.enviar_email("a@b.com", "x", "<p>x</p>")


def test_cobro_suelto_no_vinculado_igual_cubre_si_declara_periodo(db_temporal):
    cliente, _ = _cliente_mensual(db_temporal)
    db_temporal.add(Cobro(cliente_id=cliente.id, periodo_desde=date(2026, 9, 1),
                          periodo_hasta=date(2026, 9, 30), fecha_cobro=date(2026, 10, 2),
                          importe=Decimal("5700"), forma_pago="efectivo",
                          tipo_comprobante="sin_comprobante"))
    db_temporal.commit()
    assert recordatorios.generar_cobros_pendientes(db_temporal, HOY) == 0
