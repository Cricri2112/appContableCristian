"""Scheduler de procesos programados (Chat 4, decisión 5).

APScheduler corre dentro del mismo proceso de la app, con dos procesos:

- MENSUAL (día 1, 05:55): generación automática de tareas (F7) y, desde la
  Etapa 6, evaluación de `cobro_pendiente` (F10, enmienda C2).
- DIARIO (todos los días, 06:00): evaluación de recordatorios (cierre,
  reapertura de silenciados, generación), email resumen y respaldo de la
  base. Una falla del email o del respaldo NO corta el ciclo: queda
  registrada en el resultado.

Cada ejecución queda en `scheduler_ejecuciones`. Al arrancar la app se
verifica si el mensual corrió este mes y si el diario corrió hoy (pasadas
las 06:00); si no, se ejecutan en ese momento. Es seguro porque toda la
generación es re-ejecutable (anti-duplicados), y el diario no se repite el
mismo día salvo que se lo fuerce a mano.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.models import SchedulerEjecucion
from app.models.base import ZONA_HORARIA, ahora_montevideo
from app.services import fechas, recordatorios, resumen_diario, respaldo, tareas
from app.services.email import ErrorEmail

log = logging.getLogger("scheduler")

# El mensual corre el día 1 a las 05:55, antes del diario de las 06:00
# (Chat 4: "Día 1, antes del diario"), así el diario evalúa recordatorios
# sobre las tareas recién generadas.
HORA_MENSUAL = 5
MINUTO_MENSUAL = 55
HORA_DIARIO = 6
MINUTO_DIARIO = 0

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


def ultima_ejecucion(db: Session, proceso: str) -> SchedulerEjecucion | None:
    """Para Configuración → Notificaciones (hallazgo H-10)."""
    return (
        db.query(SchedulerEjecucion)
        .filter(SchedulerEjecucion.proceso == proceso)
        .order_by(SchedulerEjecucion.fecha_ejecucion.desc(), SchedulerEjecucion.id.desc())
        .first()
    )


# ---------- Proceso mensual ----------

def ejecutar_proceso_mensual(db: Session) -> str:
    """Genera las tareas del mes y evalúa los cobros pendientes.

    Una falla no se propaga: se registra el error y el ciclo sigue.
    Devuelve el texto registrado como resultado.
    """
    hoy = fechas.hoy()
    periodo = fechas.primer_dia_mes(hoy)
    try:
        creadas = tareas.generar_tareas_periodo(db, periodo)
        cobros = recordatorios.generar_cobros_pendientes(db, hoy)
        db.commit()
        resultado = "ok"
        log.info("Proceso mensual %s: %s tareas, %s cobros pendientes", periodo, creadas, cobros)
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


def recuperar_mensual(db: Session) -> bool:
    """Si el mensual no corrió este mes (app caída el día 1), corre ya.
    Devuelve True si tuvo que ejecutarlo."""
    if mensual_corrio_este_mes(db):
        return False
    log.info("El proceso mensual no corrió este mes: se ejecuta ahora.")
    ejecutar_proceso_mensual(db)
    return True


# ---------- Proceso diario ----------

def diario_corrio_hoy(db: Session) -> bool:
    """¿Hay una ejecución del diario hoy cuya evaluación salió bien?

    El resultado empieza con "ok" aunque haya fallado el email o el
    respaldo: esas fallas se registran, pero no obligan a repetir el ciclo.
    """
    inicio_dia = datetime.combine(fechas.hoy(), datetime.min.time())
    return (
        db.query(SchedulerEjecucion)
        .filter(
            SchedulerEjecucion.proceso == "diario",
            SchedulerEjecucion.resultado.like("ok%"),
            SchedulerEjecucion.fecha_ejecucion >= inicio_dia,
        )
        .first()
        is not None
    )


def ejecutar_proceso_diario(db: Session, forzar: bool = False) -> str:
    """Evaluación de recordatorios + email resumen + respaldo.

    Si ya corrió hoy, no hace nada (evita mandar dos emails el mismo día),
    salvo `forzar=True` (herramienta de desarrollo).
    """
    if not forzar and diario_corrio_hoy(db):
        return "ya corrió hoy"

    hoy = fechas.hoy()
    try:
        cambios = recordatorios.evaluar(db, hoy)
        db.commit()
    except Exception as error:  # noqa: BLE001
        db.rollback()
        resultado = f"error en la evaluación de recordatorios: {error}"
        log.exception("Falló el proceso diario")
        _registrar(db, "diario", resultado)
        return resultado

    partes = [
        f"recordatorios: {cambios['tareas'] + cambios['vencimientos']} nuevos, "
        f"{cambios['cerrados']} cerrados"
    ]

    # Email: una falla queda registrada y el ciclo sigue (Chat 4, decisión 7).
    try:
        partes.append(resumen_diario.enviar_resumen(db, hoy))
    except ErrorEmail as error:
        db.rollback()
        partes.append(f"email: ERROR — {error}")
        log.warning("Falló el email diario: %s", error)

    # Respaldo de la base: también se registra sin cortar el ciclo.
    try:
        destino = respaldo.hacer_respaldo(hoy)
        partes.append(f"respaldo: {destino.name}")
    except Exception as error:  # noqa: BLE001
        partes.append(f"respaldo: ERROR — {error}")
        log.warning("Falló el respaldo diario: %s", error)

    resultado = "ok · " + " · ".join(partes)
    _registrar(db, "diario", resultado)
    return resultado


def recuperar_diario(db: Session, ahora: datetime | None = None) -> bool:
    """Si ya pasaron las 06:00 y el diario no corrió hoy, corre ya."""
    ahora = ahora or ahora_montevideo()
    if (ahora.hour, ahora.minute) < (HORA_DIARIO, MINUTO_DIARIO):
        return False
    if diario_corrio_hoy(db):
        return False
    log.info("El proceso diario no corrió hoy: se ejecuta ahora.")
    ejecutar_proceso_diario(db)
    return True


# ---------- Arranque del scheduler ----------

def _con_sesion(funcion) -> None:
    """Lo que dispara APScheduler: cada proceso abre su propia sesión."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        funcion(db)
    finally:
        db.close()


def iniciar() -> None:
    """Recupera lo que no corrió y arranca el scheduler (lo llama app/main.py)."""
    global _scheduler
    if _scheduler is not None:
        return
    _con_sesion(recuperar_mensual)  # primero el mensual, como el día 1
    _con_sesion(recuperar_diario)

    _scheduler = BackgroundScheduler(timezone=ZONA_HORARIA)
    _scheduler.add_job(
        _con_sesion,
        CronTrigger(day=1, hour=HORA_MENSUAL, minute=MINUTO_MENSUAL, timezone=ZONA_HORARIA),
        args=[ejecutar_proceso_mensual],
        id="mensual",
        replace_existing=True,
    )
    _scheduler.add_job(
        _con_sesion,
        CronTrigger(hour=HORA_DIARIO, minute=MINUTO_DIARIO, timezone=ZONA_HORARIA),
        args=[ejecutar_proceso_diario],
        id="diario",
        replace_existing=True,
    )
    _scheduler.start()


def detener() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
