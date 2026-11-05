"""F7 — Checklist de tareas por régimen (Chat 3).

Regla central de matching: para un contrato se usan los templates ACTIVOS
cuyo servicio coincide con el del contrato y cuyo régimen es el vigente
del cliente o `todos`.

Anti-duplicado: nunca se crean dos tareas con el mismo
servicio_contratado_id + template_id + período. Toda generación es
re-ejecutable sin riesgo.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import Cliente, Servicio, ServicioContratado, Tarea, TareaTemplate
from app.models.base import ahora_montevideo
from app.services import fechas
from app.services.errores import ErrorValidacion

# Orden de los servicios dentro del grupo de un cliente.
ORDEN_FRECUENCIA = {"mensual": 0, "anual": 1, "unico": 2}

# Estados que todavía no están terminados.
ESTADOS_ABIERTOS = ("pendiente", "en_proceso")

# Transición de un clic sobre el tag de estado (adenda Etapa 1, §2):
# pendiente → en proceso → completada; completada/cancelada → pendiente.
SIGUIENTE_ESTADO = {
    "pendiente": "en_proceso",
    "en_proceso": "completada",
    "completada": "pendiente",
    "cancelada": "pendiente",
}


# ---------- Generación ----------

def templates_que_matchean(
    db: Session, contrato: ServicioContratado, regimen_cliente: str
) -> list[TareaTemplate]:
    return (
        db.query(TareaTemplate)
        .filter(
            TareaTemplate.servicio_id == contrato.servicio_id,
            TareaTemplate.activo.is_(True),
            TareaTemplate.regimen.in_([regimen_cliente, "todos"]),
        )
        .order_by(TareaTemplate.orden)
        .all()
    )


def _ya_existe(db: Session, contrato_id: int, template_id: int, periodo: date) -> bool:
    return (
        db.query(Tarea)
        .filter(
            Tarea.servicio_contratado_id == contrato_id,
            Tarea.template_id == template_id,
            Tarea.periodo == periodo,
        )
        .first()
        is not None
    )


def _crear_desde_template(
    db: Session, contrato: ServicioContratado, template: TareaTemplate, periodo: date
) -> bool:
    """Crea la tarea si no existe. Devuelve True si la creó."""
    if _ya_existe(db, contrato.id, template.id, periodo):
        return False
    db.add(
        Tarea(
            servicio_contratado_id=contrato.id,
            template_id=template.id,
            nombre=template.nombre,  # se copia: cambios futuros al template no la tocan
            periodo=periodo,
            estado="pendiente",
            fecha_creacion=ahora_montevideo(),
            requiere_info_cliente=False,
        )
    )
    db.flush()
    return True


def generar_tareas_periodo(db: Session, periodo: date) -> int:
    """Generación automática del día 1 (proceso mensual del scheduler).

    - Mensuales: todo contrato activo de servicio mensual.
    - Anuales: todo contrato activo de servicio anual, solo con los
      templates cuyo `mes_generacion` es el mes del período.
    - Únicos: no participan (generan al contratar).
    Devuelve la cantidad de tareas creadas. No hace commit.
    """
    filas = (
        db.query(ServicioContratado, Servicio, Cliente)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .join(Cliente, Cliente.id == ServicioContratado.cliente_id)
        .filter(
            ServicioContratado.activo.is_(True),
            Servicio.frecuencia.in_(["mensual", "anual"]),
        )
        .all()
    )
    creadas = 0
    for contrato, servicio, cliente in filas:
        for template in templates_que_matchean(db, contrato, cliente.regimen.value):
            if (
                servicio.frecuencia.value == "anual"
                and template.mes_generacion != periodo.month
            ):
                continue
            if _crear_desde_template(db, contrato, template, periodo):
                creadas += 1
    return creadas


def generar_al_contratar(db: Session, contrato: ServicioContratado) -> int:
    """Generación al contratar (F4 → F7). No hace commit.

    - Mensual: tareas del período en curso (desde el mes siguiente entra
      al ciclo automático del día 1).
    - Único: desde templates si existen, con período = mes en curso.
    - Anual: no genera al contratar (lo hace en su mes de generación).
    """
    servicio = db.get(Servicio, contrato.servicio_id)
    if servicio.frecuencia.value == "anual":
        return 0
    cliente = db.get(Cliente, contrato.cliente_id)
    periodo = fechas.primer_dia_mes(fechas.hoy())
    creadas = 0
    for template in templates_que_matchean(db, contrato, cliente.regimen.value):
        if _crear_desde_template(db, contrato, template, periodo):
            creadas += 1
    return creadas


# ---------- Tareas ad-hoc y edición ----------

def contratos_para_ad_hoc(db: Session) -> list[dict]:
    """Contratos activos para el selector "Servicio contratado"."""
    filas = (
        db.query(ServicioContratado, Servicio, Cliente)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .join(Cliente, Cliente.id == ServicioContratado.cliente_id)
        .filter(ServicioContratado.activo.is_(True))
        .all()
    )
    filas.sort(key=lambda f: (f[2].nombre.lower(), f[1].nombre.lower()))
    return [{"contrato": c, "servicio": s, "cliente": cl} for c, s, cl in filas]


def crear_ad_hoc(
    db: Session,
    contrato_id: int | None,
    nombre: str,
    periodo: date | None,
    requiere_info_cliente: bool,
    notas: str,
) -> Tarea:
    errores = {}
    contrato = db.get(ServicioContratado, contrato_id) if contrato_id else None
    if contrato is None:
        errores["servicio_contratado_id"] = "Elegí el cliente y el servicio."
    if not nombre.strip():
        errores["nombre"] = "El nombre no puede estar vacío."
    if periodo is None:
        errores["periodo"] = "Elegí el período."
    if errores:
        raise ErrorValidacion(errores)

    tarea = Tarea(
        servicio_contratado_id=contrato.id,
        template_id=None,
        nombre=nombre.strip(),
        periodo=periodo,
        estado="pendiente",
        fecha_creacion=ahora_montevideo(),
        requiere_info_cliente=requiere_info_cliente,
        notas=notas.strip() or None,
    )
    db.add(tarea)
    db.commit()
    return tarea


def editar_tarea(
    db: Session,
    tarea_id: int,
    nombre: str | None,
    requiere_info_cliente: bool,
    notas: str,
) -> Tarea:
    """Editables: nombre (solo ad-hoc), requiere info del cliente y notas.
    Servicio contratado, período y template de origen no se editan."""
    tarea = db.get(Tarea, tarea_id)
    if tarea.template_id is None and nombre is not None:
        if not nombre.strip():
            raise ErrorValidacion({"nombre": "El nombre no puede estar vacío."})
        tarea.nombre = nombre.strip()
    tarea.requiere_info_cliente = requiere_info_cliente
    tarea.notas = notas.strip() or None
    db.commit()
    return tarea


# ---------- Estados ----------

def _aplicar_estado(tarea: Tarea, nuevo: str) -> None:
    tarea.estado = nuevo
    # Al completar se registra cuándo; al reabrir vuelve a null.
    tarea.fecha_completada = ahora_montevideo() if nuevo == "completada" else None


def avanzar_estado(db: Session, tarea_id: int) -> Tarea:
    """Un clic: pendiente → en proceso → completada; terminadas → pendiente."""
    tarea = db.get(Tarea, tarea_id)
    _aplicar_estado(tarea, SIGUIENTE_ESTADO[tarea.estado.value])
    db.commit()
    return tarea


def cancelar(db: Session, tarea_id: int) -> Tarea:
    """Solo desde pendiente o en proceso (la UI pide confirmación)."""
    tarea = db.get(Tarea, tarea_id)
    if tarea.estado.value not in ESTADOS_ABIERTOS:
        raise ErrorValidacion({"estado": "Solo se cancelan tareas pendientes o en proceso."})
    _aplicar_estado(tarea, "cancelada")
    db.commit()
    return tarea


# ---------- Vista "Tareas del período" ----------

def progreso_periodo(db: Session, periodo: date) -> tuple[int, int]:
    """(completadas, total) del período, excluyendo canceladas (H-02)."""
    estados = [
        e.value
        for (e,) in db.query(Tarea.estado).filter(Tarea.periodo == periodo).all()
    ]
    total = sum(1 for e in estados if e != "cancelada")
    completadas = sum(1 for e in estados if e == "completada")
    return completadas, total


def clientes_con_tareas(db: Session, periodo: date) -> list[Cliente]:
    """Clientes con al menos una tarea en el período (filtro de la vista)."""
    return (
        db.query(Cliente)
        .join(ServicioContratado, ServicioContratado.cliente_id == Cliente.id)
        .join(Tarea, Tarea.servicio_contratado_id == ServicioContratado.id)
        .filter(Tarea.periodo == periodo)
        .distinct()
        .order_by(Cliente.nombre)
        .all()
    )


def _filtrar_por_estado(consulta, filtro_estado: str):
    if filtro_estado == "pendientes":
        return consulta.filter(Tarea.estado.in_(ESTADOS_ABIERTOS))
    if filtro_estado == "completadas":
        return consulta.filter(Tarea.estado == "completada")
    return consulta


def grupos_del_periodo(
    db: Session,
    periodo: date,
    cliente_id: int | None = None,
    filtro_estado: str = "todas",
) -> list[dict]:
    """Tareas del período agrupadas por cliente (vista 04).

    Dentro de cada cliente: por servicio (mensual → anual → único) y orden
    del template; las ad-hoc al final, por fecha de creación. El indicador
    "X de Y" cuenta todas las tareas del período del cliente, sin las
    canceladas, aunque haya un filtro de estado aplicado.
    """
    consulta = (
        db.query(Tarea, ServicioContratado, Servicio, Cliente, TareaTemplate)
        .join(ServicioContratado, ServicioContratado.id == Tarea.servicio_contratado_id)
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .join(Cliente, Cliente.id == ServicioContratado.cliente_id)
        .outerjoin(TareaTemplate, TareaTemplate.id == Tarea.template_id)
        .filter(Tarea.periodo == periodo)
    )
    if cliente_id:
        consulta = consulta.filter(Cliente.id == cliente_id)
    todas = consulta.all()
    visibles = {fila[0].id for fila in _filtrar_por_estado(consulta, filtro_estado).all()}

    grupos: dict[int, dict] = {}
    for tarea, contrato, servicio, cliente, template in todas:
        grupo = grupos.setdefault(cliente.id, {
            "cliente": cliente,
            "servicios": [],
            "filas": [],
            "completadas": 0,
            "total": 0,
            "abiertas": 0,
        })
        if servicio.nombre not in grupo["servicios"]:
            grupo["servicios"].append(servicio.nombre)
        if tarea.estado.value != "cancelada":
            grupo["total"] += 1
        if tarea.estado.value == "completada":
            grupo["completadas"] += 1
        if tarea.estado.value in ESTADOS_ABIERTOS:
            grupo["abiertas"] += 1
        if tarea.id in visibles:
            grupo["filas"].append({
                "tarea": tarea,
                "servicio": servicio,
                "clave_orden": (
                    tarea.template_id is None,  # ad-hoc al final
                    ORDEN_FRECUENCIA[servicio.frecuencia.value],
                    template.orden if template else 0,
                    tarea.fecha_creacion,
                    tarea.id,
                ),
            })

    resultado = []
    for grupo in grupos.values():
        if not grupo["filas"]:
            continue  # el filtro de estado dejó al cliente sin tareas visibles
        grupo["filas"].sort(key=lambda f: f["clave_orden"])
        resultado.append(grupo)
    resultado.sort(key=lambda g: g["cliente"].nombre.lower())
    return resultado


def grupo_de_cliente(
    db: Session, periodo: date, cliente_id: int, filtro_estado: str
) -> dict | None:
    """Un solo grupo (para refrescarlo por HTMX tras un cambio de estado)."""
    grupos = grupos_del_periodo(db, periodo, cliente_id, filtro_estado)
    return grupos[0] if grupos else None


def cliente_de_tarea(db: Session, tarea: Tarea) -> Cliente:
    contrato = db.get(ServicioContratado, tarea.servicio_contratado_id)
    return db.get(Cliente, contrato.cliente_id)
