"""Rutas de F7: vista "Tareas del período", estados (HTMX), ad-hoc, edición."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tarea
from app.plantillas import templates
from app.services import fechas, tareas
from app.services.errores import ErrorValidacion

router = APIRouter()

FILTROS_ESTADO = ("todas", "pendientes", "completadas")


def _filtros(periodo: str | None, cliente: str | None, estado: str | None) -> dict:
    """Normaliza los filtros de la vista (los defaults son los del Chat 3)."""
    periodo_fecha = fechas.parsear_periodo(periodo) or fechas.primer_dia_mes(fechas.hoy())
    return {
        "periodo": periodo_fecha,
        "cliente_id": int(cliente) if cliente and cliente.isdigit() else None,
        "estado": estado if estado in FILTROS_ESTADO else "todas",
    }


def _query(filtros: dict, **cambios) -> str:
    """Query string de la vista con los filtros actuales (y algún cambio)."""
    valores = {
        "periodo": filtros["periodo"].strftime("%Y-%m"),
        "cliente": filtros["cliente_id"] or "",
        "estado": filtros["estado"],
    }
    valores.update(cambios)
    return "&".join(f"{clave}={valor}" for clave, valor in valores.items())


def _contexto_vista(db: Session, filtros: dict) -> dict:
    periodo = filtros["periodo"]
    completadas, total = tareas.progreso_periodo(db, periodo)
    return {
        "seccion": "tareas",
        "filtros": filtros,
        "query": _query(filtros),
        "query_anterior": _query(filtros, periodo=fechas.mes_anterior(periodo).strftime("%Y-%m")),
        "query_siguiente": _query(filtros, periodo=fechas.mes_siguiente(periodo).strftime("%Y-%m")),
        "grupos": tareas.grupos_del_periodo(
            db, periodo, filtros["cliente_id"], filtros["estado"]
        ),
        "clientes_filtro": tareas.clientes_con_tareas(db, periodo),
        "completadas_periodo": completadas,
        "total_periodo": total,
        "query_estado": {
            estado: _query(filtros, estado=estado) for estado in FILTROS_ESTADO
        },
    }


@router.get("/tareas", response_class=HTMLResponse)
def vista(
    request: Request,
    periodo: str | None = None,
    cliente: str | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    filtros = _filtros(periodo, cliente, estado)
    return templates.TemplateResponse(
        request, "tareas_periodo.html", _contexto_vista(db, filtros)
    )


# ---------- Cambios de estado (HTMX) ----------

def _respuesta_grupo(request: Request, db: Session, tarea: Tarea, filtros: dict):
    """Re-dibuja el grupo del cliente (indicador X de Y y semáforo
    incluidos) y el contador del menú lateral."""
    cliente = tareas.cliente_de_tarea(db, tarea)
    grupo = tareas.grupo_de_cliente(db, tarea.periodo, cliente.id, filtros["estado"])
    return templates.TemplateResponse(request, "_grupo_tareas_respuesta.html", {
        "grupo": grupo,
        "cliente_id": cliente.id,
        "filtros": filtros,
        "query": _query(filtros),
    })


@router.post("/tareas/{tarea_id}/avanzar", response_class=HTMLResponse)
async def avanzar(request: Request, tarea_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros(formulario.get("periodo"), formulario.get("cliente"), formulario.get("estado"))
    tarea = tareas.avanzar_estado(db, tarea_id)
    return _respuesta_grupo(request, db, tarea, filtros)


@router.post("/tareas/{tarea_id}/cancelar", response_class=HTMLResponse)
async def cancelar(request: Request, tarea_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros(formulario.get("periodo"), formulario.get("cliente"), formulario.get("estado"))
    try:
        tarea = tareas.cancelar(db, tarea_id)
    except ErrorValidacion:
        tarea = db.get(Tarea, tarea_id)
    return _respuesta_grupo(request, db, tarea, filtros)


# ---------- Tarea ad-hoc (vista 19) ----------

def _contexto_adhoc(db: Session, filtros: dict, valores: dict, errores: dict) -> dict:
    return _contexto_vista(db, filtros) | {
        "contratos": tareas.contratos_para_ad_hoc(db),
        "valores": valores,
        "errores": errores,
    }


@router.get("/tareas/nueva", response_class=HTMLResponse)
def form_adhoc(
    request: Request,
    periodo: str | None = None,
    cliente: str | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    filtros = _filtros(periodo, cliente, estado)
    valores = {"periodo": filtros["periodo"].strftime("%Y-%m")}
    return templates.TemplateResponse(
        request, "tarea_adhoc_form.html", _contexto_adhoc(db, filtros, valores, {})
    )


@router.post("/tareas/nueva")
async def crear_adhoc(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros(formulario.get("f_periodo"), formulario.get("f_cliente"), formulario.get("f_estado"))
    contrato = formulario.get("servicio_contratado_id", "")
    try:
        tarea = tareas.crear_ad_hoc(
            db,
            int(contrato) if contrato.isdigit() else None,
            formulario.get("nombre", ""),
            fechas.parsear_periodo(formulario.get("periodo")),
            formulario.get("requiere_info_cliente") == "1",
            formulario.get("notas", ""),
        )
    except ErrorValidacion as error:
        return templates.TemplateResponse(
            request, "tarea_adhoc_form.html",
            _contexto_adhoc(db, filtros, dict(formulario), error.errores),
            status_code=422,
        )
    # Se vuelve al período de la tarea creada.
    filtros["periodo"] = tarea.periodo
    return RedirectResponse(f"/tareas?{_query(filtros)}", status_code=303)


# ---------- Edición limitada ----------

@router.get("/tareas/{tarea_id}/editar", response_class=HTMLResponse)
def form_editar(
    request: Request,
    tarea_id: int,
    periodo: str | None = None,
    cliente: str | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    tarea = db.get(Tarea, tarea_id)
    if tarea is None:
        return RedirectResponse("/tareas", status_code=303)
    filtros = _filtros(periodo, cliente, estado)
    contexto = _contexto_vista(db, filtros) | {
        "tarea": tarea,
        "cliente_tarea": tareas.cliente_de_tarea(db, tarea),
        "valores": {
            "nombre": tarea.nombre,
            "requiere_info_cliente": tarea.requiere_info_cliente,
            "notas": tarea.notas or "",
        },
        "errores": {},
    }
    return templates.TemplateResponse(request, "tarea_editar_form.html", contexto)


@router.post("/tareas/{tarea_id}/editar")
async def editar(request: Request, tarea_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros(formulario.get("f_periodo"), formulario.get("f_cliente"), formulario.get("f_estado"))
    tarea = db.get(Tarea, tarea_id)
    try:
        tareas.editar_tarea(
            db, tarea_id,
            formulario.get("nombre"),
            formulario.get("requiere_info_cliente") == "1",
            formulario.get("notas", ""),
        )
    except ErrorValidacion as error:
        contexto = _contexto_vista(db, filtros) | {
            "tarea": tarea,
            "cliente_tarea": tareas.cliente_de_tarea(db, tarea),
            "valores": dict(formulario) | {
                "requiere_info_cliente": formulario.get("requiere_info_cliente") == "1"
            },
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "tarea_editar_form.html", contexto, status_code=422
        )
    return RedirectResponse(f"/tareas?{_query(filtros)}", status_code=303)
