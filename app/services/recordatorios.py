"""F10 — Recordatorios persistentes (Chat 3 + enmienda A1 + adenda Etapa 1).

Tres tipos, con sus reglas fijas del MVP:
- tarea_pendiente: una tarea lleva 10 días corridos pendiente o en proceso
  desde su creación. Repite cada 24 hs. Se cierra al completarla o cancelarla.
- vencimiento_proximo: 5, 2 y 1 día antes de cada vencimiento aplicable a
  al menos un cliente activo. No repite. Se cierra al pasar la fecha.
- cobro_pendiente: un período mensual sigue impago un mes completo después
  de terminado (se evalúa el día 1, en el proceso mensual). Repite cada
  24 hs. Se cierra cuando el período queda cubierto.

Estados: pendiente (generado), enviado (ya fue en un email), silenciado
(hasta `silenciado_hasta` inclusive), cerrado (su causa desapareció; no se
muestra más y queda como historial).

La fecha del vencimiento de un `vencimiento_proximo` no tiene columna
propia: como se genera exactamente N días antes, es
fecha_programada + umbral_dias (A1: anti-duplicado por vencimiento +
umbral + fecha).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Cliente,
    Recordatorio,
    Servicio,
    ServicioContratado,
    Tarea,
)
from app.models.base import ahora_montevideo
from app.services import cuentas, fechas, formato, vencimientos
from app.services.errores import ErrorValidacion

DIAS_TAREA_PENDIENTE = 10
UMBRALES_VENCIMIENTO = (5, 2, 1)
OPCIONES_SILENCIO = (3, 5, 7)
INTERVALO_REPETICION_HORAS = 24

MENSAJE_NO_SILENCIABLE = (
    "Este recordatorio no se puede silenciar porque el vencimiento está "
    "demasiado próximo."
)


# ---------- Utilidades ----------

def fecha_del_vencimiento(recordatorio: Recordatorio) -> date:
    """Fecha del vencimiento de un `vencimiento_proximo` (ver docstring)."""
    return recordatorio.fecha_programada.date() + timedelta(days=recordatorio.umbral_dias)


def _no_cerrados(db: Session, tipo: str):
    return db.query(Recordatorio).filter(
        Recordatorio.tipo == tipo, Recordatorio.estado != "cerrado"
    )


def _nuevo(db: Session, hoy: date, **campos) -> Recordatorio:
    # fecha_programada = "ahora" (Chat 3), pero tomando el día evaluado:
    # de esta fecha se deduce la del vencimiento (ver docstring del módulo).
    recordatorio = Recordatorio(
        estado="pendiente",
        fecha_programada=datetime.combine(hoy, ahora_montevideo().time()),
        fecha_enviada=None,
        **campos,
    )
    db.add(recordatorio)
    db.flush()
    return recordatorio


def periodo_cubierto(db: Session, cliente_id: int, periodo: date) -> bool:
    """Un período está cubierto si algún cobro del cliente lo incluye, o si
    el saldo del cliente quedó en cero o a favor (un descuento o una edición
    que lo lleve a cubierto, Chat 3)."""
    if cuentas.periodo_cubierto(db, cliente_id, periodo):
        return True
    return cuentas.calcular_saldo(db, cliente_id)["saldo"] <= 0


# ---------- Generación ----------

def generar_tareas_pendientes(db: Session, hoy: date) -> int:
    limite = hoy - timedelta(days=DIAS_TAREA_PENDIENTE)
    abiertas = (
        db.query(Tarea, Cliente)
        .join(ServicioContratado, ServicioContratado.id == Tarea.servicio_contratado_id)
        .join(Cliente, Cliente.id == ServicioContratado.cliente_id)
        .filter(Tarea.estado.in_(["pendiente", "en_proceso"]))
        .all()
    )
    creados = 0
    for tarea, cliente in abiertas:
        if tarea.fecha_creacion.date() > limite:
            continue
        # Anti-duplicado: uno por tarea mientras haya uno no cerrado.
        if _no_cerrados(db, "tarea_pendiente").filter(
            Recordatorio.tarea_id == tarea.id
        ).first():
            continue
        _nuevo(
            db,
            hoy,
            tipo="tarea_pendiente",
            tarea_id=tarea.id,
            mensaje=f"La tarea {tarea.nombre} de {cliente.nombre} lleva 10 días sin completarse.",
            repetir_hasta_completar=True,
            intervalo_repeticion_horas=INTERVALO_REPETICION_HORAS,
        )
        creados += 1
    return creados


def _mensaje_vencimiento(ocurrencia, dias: int) -> str:
    falta = "falta 1 día" if dias == 1 else f"faltan {dias} días"
    cantidad = len(ocurrencia.clientes)
    afecta = "1 cliente" if cantidad == 1 else f"{cantidad} clientes"
    return (
        f"{ocurrencia.descripcion} ({ocurrencia.organismo}) vence el "
        f"{formato.formato_fecha(ocurrencia.fecha)} — {falta}. Afecta a {afecta}."
    )


def generar_vencimientos_proximos(db: Session, hoy: date) -> int:
    creados = 0
    proximas = vencimientos.ocurrencias_entre(
        db, hoy + timedelta(days=1), hoy + timedelta(days=max(UMBRALES_VENCIMIENTO))
    )
    for ocurrencia in proximas:
        dias = (ocurrencia.fecha - hoy).days
        if dias not in UMBRALES_VENCIMIENTO or not ocurrencia.clientes:
            continue
        # Anti-duplicado por vencimiento + umbral + fecha (A1).
        existentes = db.query(Recordatorio).filter(
            Recordatorio.tipo == "vencimiento_proximo",
            Recordatorio.vencimiento_id == ocurrencia.vencimiento.id,
            Recordatorio.umbral_dias == dias,
        ).all()
        if any(fecha_del_vencimiento(r) == ocurrencia.fecha for r in existentes):
            continue
        _nuevo(
            db,
            hoy,
            tipo="vencimiento_proximo",
            vencimiento_id=ocurrencia.vencimiento.id,
            umbral_dias=dias,
            mensaje=_mensaje_vencimiento(ocurrencia, dias),
            repetir_hasta_completar=False,
            intervalo_repeticion_horas=None,
        )
        creados += 1
    return creados


def generar_cobros_pendientes(db: Session, hoy: date) -> int:
    """Proceso mensual (día 1): el período de hace dos meses debe estar
    cubierto. Ej.: el 01/09 se evalúa julio."""
    periodo = fechas.mes_anterior(fechas.mes_anterior(fechas.primer_dia_mes(hoy)))
    clientes = (
        db.query(Cliente)
        .join(ServicioContratado, ServicioContratado.cliente_id == Cliente.id)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(
            ServicioContratado.activo.is_(True),
            Servicio.frecuencia == "mensual",
            ServicioContratado.fecha_inicio <= fechas.ultimo_dia_mes(periodo),
        )
        .distinct()
        .all()
    )
    creados = 0
    for cliente in clientes:
        if periodo_cubierto(db, cliente.id, periodo):
            continue
        if _no_cerrados(db, "cobro_pendiente").filter(
            Recordatorio.cliente_id == cliente.id, Recordatorio.periodo == periodo
        ).first():
            continue
        saldo = cuentas.calcular_saldo(db, cliente.id)["saldo"]
        _nuevo(
            db,
            hoy,
            tipo="cobro_pendiente",
            cliente_id=cliente.id,
            periodo=periodo,
            mensaje=(
                f"{cliente.nombre} tiene pendiente el pago de {formato.mes_corto(periodo)}. "
                f"Saldo actual: {formato.formato_importe(saldo)}."
            ),
            repetir_hasta_completar=True,
            intervalo_repeticion_horas=INTERVALO_REPETICION_HORAS,
        )
        creados += 1
    return creados


# ---------- Cierre automático y reapertura ----------

def _cerrar(recordatorio: Recordatorio) -> None:
    recordatorio.estado = "cerrado"


def cerrar_resueltos(db: Session, hoy: date) -> int:
    """Cierra los recordatorios cuya causa desapareció. No hace commit."""
    cerrados = 0
    for recordatorio in db.query(Recordatorio).filter(Recordatorio.estado != "cerrado").all():
        tipo = recordatorio.tipo.value
        if tipo == "tarea_pendiente":
            tarea = db.get(Tarea, recordatorio.tarea_id)
            resuelto = tarea is None or tarea.estado.value in ("completada", "cancelada")
        elif tipo == "vencimiento_proximo":
            resuelto = hoy > fecha_del_vencimiento(recordatorio)
        else:
            resuelto = periodo_cubierto(db, recordatorio.cliente_id, recordatorio.periodo)
        if resuelto:
            _cerrar(recordatorio)
            cerrados += 1
    return cerrados


def cerrar_de_tarea(db: Session, tarea: Tarea) -> None:
    """Al completar o cancelar una tarea su recordatorio se cierra en el
    momento (sin esperar al ciclo diario). No hace commit."""
    # Recién asignado, el estado todavía es texto (no el enum).
    estado = getattr(tarea.estado, "value", tarea.estado)
    if estado not in ("completada", "cancelada"):
        return
    for recordatorio in _no_cerrados(db, "tarea_pendiente").filter(
        Recordatorio.tarea_id == tarea.id
    ):
        _cerrar(recordatorio)


def cerrar_cobros_cubiertos(db: Session, cliente_id: int) -> None:
    """Reevaluación al registrar/editar/eliminar cobros o descuentos (F5 → F10).
    Hace commit."""
    for recordatorio in _no_cerrados(db, "cobro_pendiente").filter(
        Recordatorio.cliente_id == cliente_id
    ):
        if periodo_cubierto(db, cliente_id, recordatorio.periodo):
            _cerrar(recordatorio)
    db.commit()


def reabrir_silenciados(db: Session, hoy: date) -> int:
    """Silencio vencido (silenciado_hasta < hoy) → vuelve a pendiente."""
    reabiertos = 0
    for recordatorio in db.query(Recordatorio).filter(
        Recordatorio.estado == "silenciado", Recordatorio.silenciado_hasta < hoy
    ):
        recordatorio.estado = "pendiente"
        recordatorio.silenciado_hasta = None
        reabiertos += 1
    return reabiertos


def evaluar(db: Session, hoy: date) -> dict:
    """Evaluación del ciclo diario: cierra, reabre y genera. No hace commit."""
    return {
        "cerrados": cerrar_resueltos(db, hoy),
        "reabiertos": reabrir_silenciados(db, hoy),
        "tareas": generar_tareas_pendientes(db, hoy),
        "vencimientos": generar_vencimientos_proximos(db, hoy),
    }


# ---------- Panel (campanita) ----------

def _silenciado(recordatorio: Recordatorio, hoy: date) -> bool:
    return recordatorio.silenciado_hasta is not None and recordatorio.silenciado_hasta >= hoy


def _activos(db: Session, hoy: date) -> list[Recordatorio]:
    """No cerrados, no silenciados y con su causa vigente. Los vencimientos
    ya pasados se excluyen aunque el ciclo diario todavía no los cerró."""
    activos = []
    for r in db.query(Recordatorio).filter(Recordatorio.estado != "cerrado").all():
        if _silenciado(r, hoy):
            continue
        if r.tipo.value == "vencimiento_proximo" and hoy > fecha_del_vencimiento(r):
            continue
        activos.append(r)
    return activos


def _clave_orden(recordatorio: Recordatorio) -> tuple:
    """vencimiento_proximo por fecha ascendente; después tarea_pendiente y
    cobro_pendiente por antigüedad (el más viejo primero)."""
    if recordatorio.tipo.value == "vencimiento_proximo":
        return (0, fecha_del_vencimiento(recordatorio), recordatorio.id)
    return (1, recordatorio.fecha_programada.date(), recordatorio.id)


def contar_activos(db: Session, hoy: date | None = None) -> int:
    return len(_activos(db, hoy or fechas.hoy()))


def fecha_tope(db: Session, recordatorio: Recordatorio, hoy: date) -> date | None:
    """Fecha que no se puede pasar al silenciar (F10), o None si no hay tope."""
    tipo = recordatorio.tipo.value
    if tipo == "vencimiento_proximo":
        return fecha_del_vencimiento(recordatorio)
    if tipo == "tarea_pendiente":
        tarea = db.get(Tarea, recordatorio.tarea_id)
        contrato = db.get(ServicioContratado, tarea.servicio_contratado_id)
        cliente = db.get(Cliente, contrato.cliente_id)
        propias = vencimientos.vencimientos_del_cliente_en_periodo(
            db, cliente.regimen.value, tarea.periodo
        )
        limite = vencimientos.fecha_limite(propias, hoy)
        return limite.fecha if limite else None
    return None  # cobro_pendiente: sin restricción


def opciones_silencio(db: Session, recordatorio: Recordatorio, hoy: date) -> list[tuple[int, bool]]:
    """[(días, habilitada)]: se deshabilita si hoy + N supera la fecha tope."""
    tope = fecha_tope(db, recordatorio, hoy)
    return [
        (dias, tope is None or hoy + timedelta(days=dias) <= tope)
        for dias in OPCIONES_SILENCIO
    ]


def _antiguedad(recordatorio: Recordatorio, hoy: date) -> str:
    dias = (hoy - recordatorio.fecha_programada.date()).days
    if dias <= 0:
        return "hoy"
    return "hace 1 día" if dias == 1 else f"hace {dias} días"


def _destino(db: Session, recordatorio: Recordatorio) -> tuple[str, str]:
    """(url, etiqueta) de "ir al elemento relacionado" (adenda H-03)."""
    tipo = recordatorio.tipo.value
    if tipo == "vencimiento_proximo":
        fecha = fecha_del_vencimiento(recordatorio)
        return (
            f"/vencimientos?periodo={fecha:%Y-%m}&sel={recordatorio.vencimiento_id}&dia={fecha.isoformat()}",
            "Ver calendario",
        )
    if tipo == "tarea_pendiente":
        tarea = db.get(Tarea, recordatorio.tarea_id)
        contrato = db.get(ServicioContratado, tarea.servicio_contratado_id)
        return (f"/tareas?periodo={tarea.periodo:%Y-%m}&cliente={contrato.cliente_id}", "Ver tarea")
    return (f"/clientes/{recordatorio.cliente_id}/cobros/nuevo", "Registrar cobro")


@dataclass
class ItemPanel:
    recordatorio: Recordatorio
    antiguedad: str
    url: str
    etiqueta_url: str
    opciones: list[tuple[int, bool]] = field(default_factory=list)

    @property
    def silenciable(self) -> bool:
        return any(habilitada for _, habilitada in self.opciones)


def panel(db: Session, hoy: date | None = None) -> list[ItemPanel]:
    hoy = hoy or fechas.hoy()
    items = []
    for recordatorio in sorted(_activos(db, hoy), key=_clave_orden):
        url, etiqueta = _destino(db, recordatorio)
        items.append(ItemPanel(
            recordatorio=recordatorio,
            antiguedad=_antiguedad(recordatorio, hoy),
            url=url,
            etiqueta_url=etiqueta,
            opciones=opciones_silencio(db, recordatorio, hoy),
        ))
    return items


def silenciar(db: Session, recordatorio_id: int, dias: int, hoy: date | None = None) -> Recordatorio:
    hoy = hoy or fechas.hoy()
    recordatorio = db.get(Recordatorio, recordatorio_id)
    habilitadas = dict(opciones_silencio(db, recordatorio, hoy))
    if not habilitadas.get(dias):
        raise ErrorValidacion({"dias": MENSAJE_NO_SILENCIABLE})
    recordatorio.silenciado_hasta = hoy + timedelta(days=dias)
    recordatorio.estado = "silenciado"
    db.commit()
    return recordatorio


# ---------- Email resumen ----------

GRUPOS_EMAIL = (
    ("vencimiento_proximo", "Vencimientos próximos"),
    ("tarea_pendiente", "Tareas atrasadas"),
    ("cobro_pendiente", "Cobros pendientes"),
)


def para_email(db: Session, hoy: date) -> list[Recordatorio]:
    """Activos no silenciados que van en el email de hoy: los que repiten
    (cada 24 hs) y los que no repiten pero todavía no se enviaron."""
    return [
        r for r in sorted(_activos(db, hoy), key=_clave_orden)
        if r.repetir_hasta_completar or r.fecha_enviada is None
    ]


def agrupar_para_email(recordatorios: list[Recordatorio]) -> list[tuple[str, list[Recordatorio]]]:
    """Mismo orden que el panel: vencimientos → tareas → cobros."""
    grupos = []
    for tipo, titulo in GRUPOS_EMAIL:
        del_tipo = [r for r in recordatorios if r.tipo.value == tipo]
        if del_tipo:
            grupos.append((titulo, del_tipo))
    return grupos


def marcar_enviados(recordatorios: list[Recordatorio], momento: datetime) -> None:
    """Registra el envío. No hace commit."""
    for recordatorio in recordatorios:
        recordatorio.fecha_enviada = momento
        recordatorio.estado = "enviado"
