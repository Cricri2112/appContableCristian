"""Scheduler — proceso mensual, registro en scheduler_ejecuciones y
recuperación al arranque (criterios 2 y 5 del corte 5a)."""

from datetime import date

from app.models import SchedulerEjecucion, Tarea, TareaTemplate
from app.models.base import ahora_montevideo
from app.services import fechas, scheduler, tareas
from tests.utilidades import contratar, crear_cliente_directo, crear_servicio_directo


def _preparar(db):
    servicio = crear_servicio_directo(db)
    db.add(TareaTemplate(servicio_id=servicio.id, regimen="todos", nombre="Liquidar",
                         orden=1, activo=True))
    db.commit()
    cliente = crear_cliente_directo(db, fecha_inicio=date(2026, 1, 1))
    contratar(db, cliente, servicio, fecha=date(2026, 1, 1))
    db.query(Tarea).delete()  # se borra la generada al contratar
    db.commit()


def _ejecuciones(db):
    return db.query(SchedulerEjecucion).order_by(SchedulerEjecucion.id).all()


def test_proceso_mensual_genera_y_registra_ok(db_temporal):
    _preparar(db_temporal)

    assert scheduler.ejecutar_proceso_mensual(db_temporal) == "ok"
    assert db_temporal.query(Tarea).count() == 1

    registro = _ejecuciones(db_temporal)[-1]
    assert registro.proceso.value == "mensual"
    assert registro.resultado == "ok"


def test_segunda_ejecucion_no_duplica(db_temporal):
    _preparar(db_temporal)
    scheduler.ejecutar_proceso_mensual(db_temporal)
    scheduler.ejecutar_proceso_mensual(db_temporal)
    assert db_temporal.query(Tarea).count() == 1
    assert len(_ejecuciones(db_temporal)) == 2


def test_una_falla_se_registra_sin_propagarse(db_temporal, monkeypatch):
    def explotar(db, periodo):
        raise RuntimeError("base no disponible")

    monkeypatch.setattr(tareas, "generar_tareas_periodo", explotar)
    resultado = scheduler.ejecutar_proceso_mensual(db_temporal)

    assert resultado.startswith("error")
    assert "base no disponible" in _ejecuciones(db_temporal)[-1].resultado
    assert scheduler.mensual_corrio_este_mes(db_temporal) is False


def test_recuperacion_al_arranque(db_temporal):
    """Criterio 5: sin registro del mensual este mes → se ejecuta solo."""
    _preparar(db_temporal)
    assert scheduler.mensual_corrio_este_mes(db_temporal) is False

    assert scheduler.recuperar_al_arranque(db_temporal) is True
    assert db_temporal.query(Tarea).count() == 1

    # Ya corrió: al volver a arrancar no hace nada.
    assert scheduler.recuperar_al_arranque(db_temporal) is False
    assert len(_ejecuciones(db_temporal)) == 1


def test_una_ejecucion_del_mes_anterior_no_cuenta(db_temporal):
    mes_pasado = fechas.mes_anterior(fechas.primer_dia_mes(fechas.hoy()))
    db_temporal.add(SchedulerEjecucion(
        proceso="mensual",
        fecha_ejecucion=ahora_montevideo().replace(
            year=mes_pasado.year, month=mes_pasado.month, day=1
        ),
        resultado="ok",
    ))
    db_temporal.commit()
    assert scheduler.mensual_corrio_este_mes(db_temporal) is False
