"""F7 — Administración de templates de tareas (Configuración → Templates).

Reglas (Chat 3):
- No pueden existir dos templates ACTIVOS con el mismo servicio + régimen + nombre.
- Orden mayor a cero; no se repite dentro de la misma combinación
  servicio + régimen (entre activos), sí entre combinaciones distintas.
- `mes_generacion` (1-12) obligatorio si el servicio es anual; null si es
  mensual o único.
- Los cambios aplican solo a generaciones futuras. Sin eliminación física.
"""

from sqlalchemy.orm import Session

from app.models import Servicio, TareaTemplate
from app.models.enums import RegimenAplicable
from app.services.errores import ErrorValidacion

REGIMENES_VALIDOS = [r.value for r in RegimenAplicable]


def listar_templates(
    db: Session, servicio_id: int | None = None, regimen: str | None = None
) -> list[dict]:
    """Todos los templates con su servicio, ordenados servicio → régimen → orden.

    Dentro de cada servicio, el régimen `todos` va primero (es el genérico).
    """
    consulta = db.query(TareaTemplate, Servicio).join(
        Servicio, Servicio.id == TareaTemplate.servicio_id
    )
    if servicio_id:
        consulta = consulta.filter(TareaTemplate.servicio_id == servicio_id)
    if regimen:
        consulta = consulta.filter(TareaTemplate.regimen == regimen)
    filas = [{"template": t, "servicio": s} for t, s in consulta.all()]
    filas.sort(
        key=lambda f: (
            f["servicio"].nombre.lower(),
            f["template"].regimen.value != "todos",
            f["template"].regimen.value,
            f["template"].orden,
            f["template"].id,
        )
    )
    return filas


def obtener_template(db: Session, template_id: int) -> TareaTemplate | None:
    return db.get(TareaTemplate, template_id)


def _validar(
    db: Session,
    servicio_id: int | None,
    regimen: str,
    nombre: str,
    orden_texto: str,
    mes_texto: str,
    excluir_id: int | None,
    verificar_unicidad: bool = True,
) -> tuple[dict, dict]:
    """Devuelve (valores_limpios, errores).

    `verificar_unicidad=False` se usa al editar un template INACTIVO: no
    choca con los activos hasta que se lo reactive (y ahí se verifica).
    """
    errores = {}
    limpios = {}

    servicio = db.get(Servicio, servicio_id) if servicio_id else None
    if servicio is None:
        errores["servicio_id"] = "Elegí un servicio."
    limpios["servicio_id"] = servicio_id

    if regimen not in REGIMENES_VALIDOS:
        errores["regimen"] = "Elegí un régimen."
    limpios["regimen"] = regimen

    nombre = nombre.strip()
    if not nombre:
        errores["nombre"] = "El nombre no puede estar vacío."
    limpios["nombre"] = nombre

    try:
        orden = int(orden_texto)
    except (TypeError, ValueError):
        orden = 0
    if orden <= 0:
        errores["orden"] = "El orden debe ser un número mayor a cero."
    limpios["orden"] = orden

    # Mes de generación: obligatorio para anuales, ignorado para el resto.
    limpios["mes_generacion"] = None
    if servicio is not None and servicio.frecuencia.value == "anual":
        try:
            mes = int(mes_texto)
        except (TypeError, ValueError):
            mes = 0
        if not 1 <= mes <= 12:
            errores["mes_generacion"] = (
                "El mes de generación es obligatorio para servicios anuales."
            )
        limpios["mes_generacion"] = mes if 1 <= mes <= 12 else None

    # Unicidades contra los templates activos de la misma combinación.
    if verificar_unicidad and not errores:
        mismos = db.query(TareaTemplate).filter(
            TareaTemplate.servicio_id == servicio_id,
            TareaTemplate.regimen == regimen,
            TareaTemplate.activo.is_(True),
        )
        if excluir_id is not None:
            mismos = mismos.filter(TareaTemplate.id != excluir_id)
        mismos = mismos.all()
        if any(t.nombre.strip().lower() == nombre.lower() for t in mismos):
            errores["nombre"] = (
                "Ya existe un template activo con ese servicio, régimen y nombre."
            )
        if any(t.orden == orden for t in mismos):
            errores["orden"] = (
                "Ese orden ya está usado por otro template del mismo servicio y régimen."
            )

    return limpios, errores


def crear_template(
    db: Session,
    servicio_id: int | None,
    regimen: str,
    nombre: str,
    descripcion: str,
    orden_texto: str,
    mes_texto: str,
) -> TareaTemplate:
    limpios, errores = _validar(
        db, servicio_id, regimen, nombre, orden_texto, mes_texto, excluir_id=None
    )
    if errores:
        raise ErrorValidacion(errores)
    template = TareaTemplate(
        **limpios, descripcion=descripcion.strip() or None, activo=True
    )
    db.add(template)
    db.commit()
    return template


def editar_template(
    db: Session,
    template_id: int,
    servicio_id: int | None,
    regimen: str,
    nombre: str,
    descripcion: str,
    orden_texto: str,
    mes_texto: str,
) -> TareaTemplate:
    template = db.get(TareaTemplate, template_id)
    limpios, errores = _validar(
        db, servicio_id, regimen, nombre, orden_texto, mes_texto,
        excluir_id=template_id, verificar_unicidad=template.activo,
    )
    if errores:
        raise ErrorValidacion(errores)
    for campo, valor in limpios.items():
        setattr(template, campo, valor)
    template.descripcion = descripcion.strip() or None
    db.commit()
    return template


def cambiar_activo(db: Session, template_id: int) -> TareaTemplate:
    """Desactivar / reactivar en un clic (sin confirmación).

    Al reactivar se verifica que no choque con otro template activo.
    """
    template = db.get(TareaTemplate, template_id)
    if not template.activo:
        _, errores = _validar(
            db, template.servicio_id, template.regimen.value, template.nombre,
            str(template.orden), str(template.mes_generacion or ""),
            excluir_id=template_id,
        )
        if errores:
            raise ErrorValidacion(errores)
    template.activo = not template.activo
    db.commit()
    return template
