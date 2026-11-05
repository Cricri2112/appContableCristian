"""Rutas de Configuración → Templates de tareas (F7)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Servicio
from app.plantillas import templates
from app.services import templates_tareas
from app.services.errores import ErrorValidacion

router = APIRouter(prefix="/configuracion/templates")


def _contexto_listado(
    db: Session, servicio: str | None = None, regimen: str | None = None
) -> dict:
    filtro_servicio = int(servicio) if servicio and servicio.isdigit() else None
    filtro_regimen = regimen if regimen in templates_tareas.REGIMENES_VALIDOS else None
    return {
        "seccion": "configuracion",
        "filas": templates_tareas.listar_templates(db, filtro_servicio, filtro_regimen),
        "servicios": db.query(Servicio).order_by(Servicio.nombre).all(),
        "regimenes": templates_tareas.REGIMENES_VALIDOS,
        "filtro_servicio": filtro_servicio,
        "filtro_regimen": filtro_regimen,
        "error_listado": None,
    }


def _servicios_para_form(db: Session, incluir_id: int | None = None) -> list[Servicio]:
    """Servicios activos (Chat 3) + el del template editado si está inactivo."""
    servicios = db.query(Servicio).filter(Servicio.activo.is_(True)).all()
    if incluir_id and all(s.id != incluir_id for s in servicios):
        actual = db.get(Servicio, incluir_id)
        if actual is not None:
            servicios.append(actual)
    return sorted(servicios, key=lambda s: s.nombre.lower())


def _datos(formulario) -> dict:
    servicio = formulario.get("servicio_id", "")
    return {
        "servicio_id": int(servicio) if servicio.isdigit() else None,
        "regimen": formulario.get("regimen", ""),
        "nombre": formulario.get("nombre", ""),
        "descripcion": formulario.get("descripcion", ""),
        "orden_texto": formulario.get("orden", ""),
        "mes_texto": formulario.get("mes_generacion", ""),
    }


@router.get("", response_class=HTMLResponse)
def listado(
    request: Request,
    servicio: str | None = None,
    regimen: str | None = None,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request, "configuracion_templates.html", _contexto_listado(db, servicio, regimen)
    )


@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo(request: Request, db: Session = Depends(get_db)):
    contexto = _contexto_listado(db) | {
        "template_editado": None,
        "servicios_form": _servicios_para_form(db),
        "valores": {"regimen": "todos", "orden": "1"},
        "errores": {},
    }
    return templates.TemplateResponse(request, "template_form.html", contexto)


@router.post("/nuevo")
async def crear(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    try:
        templates_tareas.crear_template(db, **_datos(formulario))
    except ErrorValidacion as error:
        contexto = _contexto_listado(db) | {
            "template_editado": None,
            "servicios_form": _servicios_para_form(db),
            "valores": dict(formulario),
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "template_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/templates", status_code=303)


@router.get("/{template_id}/editar", response_class=HTMLResponse)
def form_editar(request: Request, template_id: int, db: Session = Depends(get_db)):
    template = templates_tareas.obtener_template(db, template_id)
    if template is None:
        return RedirectResponse("/configuracion/templates", status_code=303)
    contexto = _contexto_listado(db) | {
        "template_editado": template,
        "servicios_form": _servicios_para_form(db, template.servicio_id),
        "valores": {
            "servicio_id": str(template.servicio_id),
            "regimen": template.regimen.value,
            "nombre": template.nombre,
            "descripcion": template.descripcion or "",
            "orden": str(template.orden),
            "mes_generacion": str(template.mes_generacion or ""),
        },
        "errores": {},
    }
    return templates.TemplateResponse(request, "template_form.html", contexto)


@router.post("/{template_id}/editar")
async def editar(request: Request, template_id: int, db: Session = Depends(get_db)):
    template = templates_tareas.obtener_template(db, template_id)
    formulario = await request.form()
    try:
        templates_tareas.editar_template(db, template_id, **_datos(formulario))
    except ErrorValidacion as error:
        contexto = _contexto_listado(db) | {
            "template_editado": template,
            "servicios_form": _servicios_para_form(db, template.servicio_id),
            "valores": dict(formulario),
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "template_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/templates", status_code=303)


@router.post("/{template_id}/activo")
def cambiar_activo(request: Request, template_id: int, db: Session = Depends(get_db)):
    """Desactivar/reactivar en un clic. Si reactivarlo chocaría con otro
    template activo, se avisa arriba del listado."""
    try:
        templates_tareas.cambiar_activo(db, template_id)
    except ErrorValidacion as error:
        contexto = _contexto_listado(db) | {
            "error_listado": "No se puede reactivar: " + " ".join(error.errores.values()),
        }
        return templates.TemplateResponse(
            request, "configuracion_templates.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/templates", status_code=303)
