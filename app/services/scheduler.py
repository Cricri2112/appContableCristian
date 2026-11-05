"""Scheduler de procesos programados (Chat 4, decisión 5).

APScheduler corre dentro del mismo proceso de la app. En la Etapa 5 existe
solo el proceso MENSUAL (día 1): generación automática de tareas (F7).
El proceso diario (recordatorios, email, respaldo) se suma en la Etapa 6.

Cada ejecución queda registrada en `scheduler_ejecuciones` con su
resultado ("ok" o el detalle del error). Al arrancar la app se verifica
si el mensual corrió este mes; si no, se ejecuta en ese momento. Es seguro
porque la generación es re-ejecutable (anti-duplicados).
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.models import SchedulerEjecucion
from app.models.base import ZONA_HORARIA, ahora_montevideo
from app.services import fechas, tareas

log = logging.getLogger("scheduler")

# El mensual corre el día 1 a las 05:55, antes del diario de las 06:00
# (Chat 4: "Día 1, antes del diario"), así el diario evalúa recordatorios
# sobre las tareas recién generadas.
HORA_MENSUAL = 5
MINUTO_MENSUAL = 55

_scheduler: BackgroundScheduler | None = None


def _registrar(db: Session, proceso: str, resultado: str) -> None:
    db.add(
        SchedulerEjecucion(
            proceso=proceso,
            fecha_ejecucion=ahora_montevideo(),
            resultado=resultado,
        )
    )
    db.commit()


def ejecutar_proceso_mensual(db: Session) -> str:
    """Genera las tareas del mes en curso y registra el resultado.

    Una falla no se propaga: se registra el error y el ciclo sigue.
    Devuelve el texto registrado como resultado.
    """
    periodo = fechas.primer_dia_mes(fechas.hoy())
    try:
        creadas = tareas.generar_tareas_periodo(db, periodo)
        db.commit()
        resultado = "ok"
        log.info("Proceso mensual %s: %s tareas creadas", periodo, creadas)
    except Exception as error:  # noqa: BLE001 — se registra cualquier falla
        db.rollback()
        resultado = f"error: {error}"
        log.exception("Falló el proceso mensual")
    _registrar(db, "mensual", resultado)
    return resultado


def mensual_corrio_este_mes(db: Session) -> bool:
    """¿Hay una ejecución exitosa del mensual en el mes en curso?"""
    inicio_mes = fechas.primer_dia_mes(fechas.hoy())
    return (
        db.query(SchedulerEjecucion)
        .filter(
            SchedulerEjecucion.proceso == "mensual",
            SchedulerEjecucion.resultado == "ok",
            SchedulerEjecucion.fecha_ejecucion >= inicio_mes,
        )
        .first()
        is not None
    )


def recuperar_al_arranque(db: Session) -> bool:
    """Si el mensual no corrió este mes (app caída el día 1), corre ya.

    Devuelve True si tuvo que ejecutarlo.
    """
    if mensual_corrio_este_mes(db):
        return False
    log.info("El proceso mensual no corrió este mes: se ejecuta ahora.")
    ejecutar_proceso_mensual(db)
    return True


def _tarea_mensual() -> None:
    """Lo que dispara APScheduler: abre su propia sesión de base."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ejecutar_proceso_mensual(db)
    finally:
        db.close()


def iniciar() -> None:
    """Arranca el scheduler en segundo plano (lo llama app/main.py)."""
    global _scheduler
    if _scheduler is not None:
        return
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        recuperar_al_arranque(db)
    finally:
        db.close()

    _scheduler = BackgroundScheduler(timezone=ZONA_HORARIA)
    _scheduler.add_job(
        _tarea_mensual,
        CronTrigger(day=1, hour=HORA_MENSUAL, minute=MINUTO_MENSUAL, timezone=ZONA_HORARIA),
        id="mensual",
        replace_existing=True,
    )
    _scheduler.start()


def detener() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
