"""F8 — Calendario de vencimientos (Chat 3 + adenda Etapa 1, H-05).

Regla de aplicabilidad: un vencimiento aplica a un cliente en un período si
- su régimen es el vigente del cliente, o `todos`;
- su mes es el del período, o null (todos los meses);
- su año es el del período, o null (recurrente);
- está activo.

Si el día no existe en un mes (31 en abril), se toma el último día real.
La conexión con las tareas (fecha límite y semáforo) se deriva al consultar:
no hay claves foráneas entre tareas y vencimientos.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Cliente, VencimientoCalendario
from app.models.enums import Organismo, Regimen, RegimenAplicable
from app.services import fechas
from app.services.errores import ErrorValidacion

REGIMENES_CLIENTE = [r.value for r in Regimen]
REGIMENES_APLICABLES = [r.value for r in RegimenAplicable]
ORGANISMOS = [o.value for o in Organismo]
ORGANISMOS_LEGIBLES = {"dgi": "DGI", "bps": "BPS", "otro": "Otro"}

# Días de anticipación que separan amarillo de rojo en el semáforo (F8).
DIAS_ALERTA = 5


@dataclass
class Ocurrencia:
    """Un vencimiento ubicado en una fecha concreta."""

    vencimiento: VencimientoCalendario
    fecha: date
    regimenes: list[str] = field(default_factory=list)  # regímenes alcanzados
    clientes: list[Cliente] = field(default_factory=list)  # clientes activos alcanzados

    @property
    def descripcion(self) -> str:
        return self.vencimiento.descripcion

    @property
    def organismo(self) -> str:
        return ORGANISMOS_LEGIBLES[self.vencimiento.organismo.value]


# ---------- Reglas ----------

def regimenes_alcanzados(vencimiento: VencimientoCalendario) -> list[str]:
    if vencimiento.regimen.value == "todos":
        return list(REGIMENES_CLIENTE)
    return [vencimiento.regimen.value]


def fecha_en_mes(vencimiento: VencimientoCalendario, periodo: date) -> date | None:
    """Fecha del vencimiento en el mes del período, o None si no aplica a ese mes."""
    if not vencimiento.activo:
        return None
    if vencimiento.mes is not None and vencimiento.mes != periodo.month:
        return None
    if vencimiento.anio is not None and vencimiento.anio != periodo.year:
        return None
    return fechas.dia_en_mes(periodo.year, periodo.month, vencimiento.dia_vencimiento)


def ocurrencias_entre(db: Session, desde: date, hasta: date) -> list[Ocurrencia]:
    """Todas las ocurrencias de vencimientos activos en el rango [desde, hasta],
    con sus regímenes y clientes activos alcanzados. Orden por fecha."""
    vencimientos = (
        db.query(VencimientoCalendario)
        .filter(VencimientoCalendario.activo.is_(True))
        .all()
    )
    clientes_activos = (
        db.query(Cliente).filter(Cliente.activo.is_(True)).order_by(Cliente.nombre).all()
    )
    ocurrencias = []
    periodo = fechas.primer_dia_mes(desde)
    while periodo <= hasta:
        for vencimiento in vencimientos:
            fecha = fecha_en_mes(vencimiento, periodo)
            if fecha is None or not desde <= fecha <= hasta:
                continue
            regimenes = regimenes_alcanzados(vencimiento)
            ocurrencias.append(Ocurrencia(
                vencimiento=vencimiento,
                fecha=fecha,
                regimenes=regimenes,
                clientes=[c for c in clientes_activos if c.regimen.value in regimenes],
            ))
        periodo = fechas.mes_siguiente(periodo)
    ocurrencias.sort(key=lambda o: (o.fecha, o.vencimiento.descripcion.lower()))
    return ocurrencias


def ocurrencias_del_mes(db: Session, periodo: date) -> list[Ocurrencia]:
    return ocurrencias_entre(
        db, fechas.primer_dia_mes(periodo), fechas.ultimo_dia_mes(periodo)
    )


def proximos_dias(db: Session, dias: int, desde: date | None = None) -> list[Ocurrencia]:
    """Vencimientos de hoy a hoy + N días (vista 2: N = 15)."""
    inicio = desde or fechas.hoy()
    return ocurrencias_entre(db, inicio, inicio + timedelta(days=dias))


def proximos_del_cliente(db: Session, cliente: Cliente, dias: int = 30) -> list[Ocurrencia]:
    """Vista 3 (ficha): aplicables por régimen vigente, próximos 30 días."""
    return [
        o for o in proximos_dias(db, dias)
        if cliente.regimen.value in o.regimenes
    ]


# ---------- Conexión con las tareas (F7) ----------

@dataclass
class FechaLimite:
    fecha: date
    organismo: str
    dias_restantes: int

    @property
    def texto_dias(self) -> str:
        if self.dias_restantes < 0:
            return "vencida"
        if self.dias_restantes == 0:
            return "vence hoy"
        if self.dias_restantes == 1:
            return "falta 1 día"
        return f"faltan {self.dias_restantes} días"


def vencimientos_del_cliente_en_periodo(
    db: Session, regimen: str, periodo: date
) -> list[Ocurrencia]:
    return [o for o in ocurrencias_del_mes(db, periodo) if regimen in o.regimenes]


def fecha_limite(
    ocurrencias_cliente: list[Ocurrencia], hoy: date | None = None
) -> FechaLimite | None:
    """Fecha límite del cliente en el período visualizado.

    Se toma el vencimiento aplicable más próximo a hoy que todavía no pasó;
    si todos los del período ya pasaron, el último (la fecha queda vencida).
    Sin vencimientos aplicables: sin fecha límite.
    """
    if not ocurrencias_cliente:
        return None
    hoy = hoy or fechas.hoy()
    futuras = [o for o in ocurrencias_cliente if o.fecha >= hoy]
    elegida = futuras[0] if futuras else ocurrencias_cliente[-1]
    return FechaLimite(
        fecha=elegida.fecha,
        organismo=elegida.organismo,
        dias_restantes=(elegida.fecha - hoy).days,
    )


def semaforo(limite: FechaLimite | None, tareas_abiertas: int) -> str | None:
    """Verde: todas completadas o canceladas. Amarillo: pendientes y faltan
    más de 5 días. Rojo: pendientes y faltan 5 días o menos (o ya pasó).
    Sin fecha límite: sin semáforo."""
    if limite is None:
        return None
    if tareas_abiertas == 0:
        return "verde"
    if limite.dias_restantes > DIAS_ALERTA:
        return "amarillo"
    return "rojo"


def completar_grupos_con_limite(db: Session, grupos: list[dict], periodo: date) -> None:
    """Agrega fecha límite, semáforo y vencimientos del período a cada grupo
    de la vista de tareas (modifica los diccionarios recibidos)."""
    del_mes = ocurrencias_del_mes(db, periodo)
    for grupo in grupos:
        regimen = grupo["cliente"].regimen.value
        propias = [o for o in del_mes if regimen in o.regimenes]
        limite = fecha_limite(propias)
        grupo["vencimientos_periodo"] = propias
        grupo["limite"] = limite
        grupo["semaforo"] = semaforo(limite, grupo["abiertas"])


# ---------- Administración (Configuración → Vencimientos) ----------

def listar_vencimientos(
    db: Session,
    anio: str = "actual",
    organismo: str | None = None,
    regimen: str | None = None,
) -> list[VencimientoCalendario]:
    """Listado con filtros. `anio`: "actual" (año en curso + recurrentes),
    "todos", o un año puntual. Orden por mes y día (los de todos los meses
    primero)."""
    consulta = db.query(VencimientoCalendario)
    if anio == "actual":
        consulta = consulta.filter(
            (VencimientoCalendario.anio.is_(None))
            | (VencimientoCalendario.anio == fechas.hoy().year)
        )
    elif anio and anio.isdigit():
        consulta = consulta.filter(VencimientoCalendario.anio == int(anio))
    if organismo in ORGANISMOS:
        consulta = consulta.filter(VencimientoCalendario.organismo == organismo)
    if regimen in REGIMENES_APLICABLES:
        consulta = consulta.filter(VencimientoCalendario.regimen == regimen)
    return sorted(
        consulta.all(),
        key=lambda v: (v.mes or 0, v.dia_vencimiento, v.descripcion.lower()),
    )


def anios_cargados(db: Session) -> list[int]:
    return sorted(
        {a for (a,) in db.query(VencimientoCalendario.anio).distinct() if a is not None},
        reverse=True,
    )


def _entero_opcional(texto: str) -> tuple[int | None, bool]:
    """'' → (None, True); '12' → (12, True); 'x' → (None, False)."""
    texto = (texto or "").strip()
    if not texto:
        return None, True
    return (int(texto), True) if texto.isdigit() else (None, False)


def _validar(datos: dict) -> tuple[dict, dict]:
    errores = {}
    limpios = {}

    descripcion = datos.get("descripcion", "").strip()
    if not descripcion:
        errores["descripcion"] = "La descripción no puede estar vacía."
    limpios["descripcion"] = descripcion

    organismo = datos.get("organismo", "")
    if organismo not in ORGANISMOS:
        errores["organismo"] = "Elegí el organismo."
    limpios["organismo"] = organismo

    regimen = datos.get("regimen", "")
    if regimen not in REGIMENES_APLICABLES:
        errores["regimen"] = "Elegí el régimen."
    limpios["regimen"] = regimen

    mes, ok = _entero_opcional(datos.get("mes", ""))
    if not ok or (mes is not None and not 1 <= mes <= 12):
        errores["mes"] = "Elegí un mes válido."
    limpios["mes"] = mes

    dia, ok = _entero_opcional(datos.get("dia_vencimiento", ""))
    if not ok or dia is None or not 1 <= dia <= 31:
        errores["dia_vencimiento"] = "El día debe ser un número entre 1 y 31."
    limpios["dia_vencimiento"] = dia

    anio, ok = _entero_opcional(datos.get("anio", ""))
    if not ok or (anio is not None and not 2000 <= anio <= 2100):
        errores["anio"] = "Ingresá un año válido o dejalo vacío (recurrente)."
    limpios["anio"] = anio

    return limpios, errores


def crear_vencimiento(db: Session, datos: dict) -> VencimientoCalendario:
    """No se valida duplicado exacto (Chat 3: responsabilidad del contador)."""
    limpios, errores = _validar(datos)
    if errores:
        raise ErrorValidacion(errores)
    vencimiento = VencimientoCalendario(**limpios, activo=True)
    db.add(vencimiento)
    db.commit()
    return vencimiento


def editar_vencimiento(db: Session, vencimiento_id: int, datos: dict) -> VencimientoCalendario:
    limpios, errores = _validar(datos)
    if errores:
        raise ErrorValidacion(errores)
    vencimiento = db.get(VencimientoCalendario, vencimiento_id)
    for campo, valor in limpios.items():
        setattr(vencimiento, campo, valor)
    db.commit()
    return vencimiento


def cambiar_activo(db: Session, vencimiento_id: int) -> VencimientoCalendario:
    vencimiento = db.get(VencimientoCalendario, vencimiento_id)
    vencimiento.activo = not vencimiento.activo
    db.commit()
    return vencimiento


# ---------- Grilla del calendario ----------

def semanas_del_mes(periodo: date) -> list[list[date | None]]:
    """Semanas de lunes a domingo; None para los huecos antes/después."""
    primero = fechas.primer_dia_mes(periodo)
    ultimo = fechas.ultimo_dia_mes(periodo)
    semanas = []
    semana: list[date | None] = [None] * primero.weekday()
    dia = primero
    while dia <= ultimo:
        semana.append(dia)
        if len(semana) == 7:
            semanas.append(semana)
            semana = []
        dia += timedelta(days=1)
    if semana:
        semanas.append(semana + [None] * (7 - len(semana)))
    return semanas
