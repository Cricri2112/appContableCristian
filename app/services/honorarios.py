"""F6 — Historial de honorarios (Chat 3).

Mecánica común append-only de todo cambio (individual o global):
1. Se cierra el registro vigente: fecha_hasta = fecha_de_vigencia − 1 día.
2. Se inserta uno nuevo: fecha_desde = fecha_de_vigencia, fecha_hasta = null.

Los registros históricos nunca se modifican ni eliminan desde la app.
El saldo es derivado, así que el "recálculo" tras un cambio retroactivo
es automático (services/cuentas.py usa el honorario vigente por período).
"""

from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy.orm import Session

from app.models import (
    Cliente,
    HonorarioHistorial,
    Servicio,
    ServicioContratado,
)
from app.models.base import ahora_montevideo
from app.services.errores import ErrorValidacion
from app.services.importes import parsear_importe


def hoy() -> date:
    return ahora_montevideo().date()


def honorario_vigente(db: Session, contrato_id: int) -> HonorarioHistorial | None:
    return (
        db.query(HonorarioHistorial)
        .filter(
            HonorarioHistorial.servicio_contratado_id == contrato_id,
            HonorarioHistorial.fecha_hasta.is_(None),
        )
        .first()
    )


def historial_por_contrato(db: Session, contrato_id: int) -> list[HonorarioHistorial]:
    """Historial completo de un contrato, fecha_desde descendente (F6)."""
    return (
        db.query(HonorarioHistorial)
        .filter(HonorarioHistorial.servicio_contratado_id == contrato_id)
        .order_by(HonorarioHistorial.fecha_desde.desc())
        .all()
    )


def historial_consolidado(db: Session, cliente_id: int) -> list[dict]:
    """Registros de todos los contratos del cliente (activos y finalizados),
    ordenados por fecha_desde descendente (vista 11)."""
    filas = (
        db.query(HonorarioHistorial, Servicio)
        .join(
            ServicioContratado,
            ServicioContratado.id == HonorarioHistorial.servicio_contratado_id,
        )
        .join(Servicio, Servicio.id == ServicioContratado.servicio_id)
        .filter(ServicioContratado.cliente_id == cliente_id)
        .order_by(HonorarioHistorial.fecha_desde.desc(), HonorarioHistorial.id.desc())
        .all()
    )
    return [{"registro": registro, "servicio": servicio} for registro, servicio in filas]


def _aplicar_mecanica(
    db: Session, contrato_id: int, nuevo: Decimal, vigencia: date
) -> None:
    """La mecánica común: cierra el vigente e inserta el nuevo registro."""
    vigente = honorario_vigente(db, contrato_id)
    if vigente is not None:
        vigente.fecha_hasta = vigencia - timedelta(days=1)
    db.add(
        HonorarioHistorial(
            servicio_contratado_id=contrato_id,
            honorario=nuevo,
            fecha_desde=vigencia,
            fecha_hasta=None,
        )
    )


def es_retroactivo(vigencia: date) -> bool:
    """Retroactivo = anterior al mes en curso (dispara la advertencia)."""
    return vigencia < hoy().replace(day=1)


def _validar_vigencia(vigencia: date | None, vigente: HonorarioHistorial | None) -> str | None:
    if vigencia is None:
        return "Ingresá la fecha de vigencia."
    if vigencia.day != 1:
        return "La fecha de vigencia debe ser el primer día de un mes."
    # Evita superposición con registros ya cerrados (Chat 3).
    if vigente is not None and vigencia < vigente.fecha_desde:
        return "La fecha de vigencia no puede ser anterior al inicio del honorario vigente."
    return None


def cambiar_honorario(
    db: Session, contrato_id: int, nuevo_texto: str, vigencia: date | None
) -> HonorarioHistorial:
    """Cambio individual (vista 17)."""
    errores = {}
    vigente = honorario_vigente(db, contrato_id)

    nuevo, error_importe = parsear_importe(nuevo_texto, "honorario")
    if error_importe:
        errores["honorario"] = error_importe
    elif vigente is not None and nuevo == vigente.honorario:
        errores["honorario"] = "El nuevo honorario es igual al vigente."

    error_vigencia = _validar_vigencia(vigencia, vigente)
    if error_vigencia:
        errores["fecha_vigencia"] = error_vigencia

    if errores:
        raise ErrorValidacion(errores)

    _aplicar_mecanica(db, contrato_id, nuevo, vigencia)
    db.commit()
    return honorario_vigente(db, contrato_id)


# ---------- Aumento global (vistas 18a-d) ----------

def redondear_arriba_a_10(valor: Decimal) -> Decimal:
    """Redondeo hacia arriba al múltiplo de 10 (Chat 3).

    Ej.: 5.700 × 1,085 = 6.184,50 → 6.190.
    """
    return (valor / 10).quantize(Decimal("1"), rounding=ROUND_CEILING) * 10


def parsear_porcentaje(texto: str) -> tuple[Decimal | None, str | None]:
    limpio = texto.strip().replace("%", "").replace(",", ".")
    if not limpio:
        return None, "Ingresá el porcentaje de aumento."
    try:
        valor = Decimal(limpio)
    except ArithmeticError:
        return None, "Ingresá un porcentaje válido."
    if valor <= 0:
        return None, "El porcentaje debe ser mayor a cero."
    return valor, None


def candidatos_aumento(db: Session, porcentaje: Decimal, vigencia: date) -> list[dict]:
    """Contratos activos mensuales y anuales con el nuevo honorario calculado.

    Orden: frecuencia (mensual → anual), luego cliente. Los únicos quedan
    excluidos (ya cotizados). Una fila es inválida si la vigencia es
    anterior a la fecha_desde de su honorario vigente.
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
    candidatos = []
    for contrato, servicio, cliente in filas:
        vigente = honorario_vigente(db, contrato.id)
        if vigente is None:
            continue
        candidatos.append({
            "contrato": contrato,
            "servicio": servicio,
            "cliente": cliente,
            "vigente": vigente.honorario,
            "nuevo": redondear_arriba_a_10(
                vigente.honorario * (1 + porcentaje / 100)
            ),
            # Fila inválida: la vigencia elegida pisa el registro vigente.
            "valida": vigencia >= vigente.fecha_desde,
        })
    orden_frecuencia = {"mensual": 0, "anual": 1}
    candidatos.sort(
        key=lambda c: (
            orden_frecuencia[c["servicio"].frecuencia.value],
            c["cliente"].nombre.lower(),
        )
    )
    return candidatos


def aplicar_aumento_global(
    db: Session, seleccion: list[dict], vigencia: date
) -> int:
    """Aplica la mecánica común a cada contrato seleccionado.

    `seleccion`: [{"contrato_id": int, "nuevo_texto": str}]. Los importes
    editados a mano reemplazan al calculado sin redondeo adicional.
    """
    errores = {}
    if not seleccion:
        raise ErrorValidacion({"seleccion": "Seleccioná al menos un servicio."})

    aplicables = []
    for item in seleccion:
        vigente = honorario_vigente(db, item["contrato_id"])
        nuevo, error_importe = parsear_importe(item["nuevo_texto"], "honorario")
        if error_importe:
            errores[f"nuevo_{item['contrato_id']}"] = error_importe
            continue
        error_vigencia = _validar_vigencia(vigencia, vigente)
        if error_vigencia:
            errores[f"nuevo_{item['contrato_id']}"] = error_vigencia
            continue
        aplicables.append((item["contrato_id"], nuevo))

    if errores:
        raise ErrorValidacion(errores)

    for contrato_id, nuevo in aplicables:
        _aplicar_mecanica(db, contrato_id, nuevo, vigencia)
    db.commit()
    return len(aplicables)


def opciones_vigencia(cantidad: int = 6, desde: date | None = None) -> list[date]:
    """Primeros días de mes para el selector de vigencia.

    Arranca en el mes indicado (o unos meses atrás del actual, para permitir
    cambios retroactivos) y cubre `cantidad` meses.
    """
    if desde is None:
        base = hoy().replace(day=1)
        # Tres meses hacia atrás para habilitar retroactivos recientes.
        for _ in range(3):
            base = (base - timedelta(days=1)).replace(day=1)
    else:
        base = desde.replace(day=1)
    opciones = []
    actual = base
    for _ in range(cantidad):
        opciones.append(actual)
        if actual.month == 12:
            actual = date(actual.year + 1, 1, 1)
        else:
            actual = date(actual.year, actual.month + 1, 1)
    return opciones


def vigencia_default() -> date:
    """Primer día del mes siguiente (default del Chat 3)."""
    base = hoy().replace(day=1)
    if base.month == 12:
        return date(base.year + 1, 1, 1)
    return date(base.year, base.month + 1, 1)
