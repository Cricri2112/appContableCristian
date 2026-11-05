"""Rutas de F8: calendario mensual, Configuración → Vencimientos y la
pestaña "Próximos vencimientos" de la ficha del cliente."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import VencimientoCalendario
from app.plantillas import templates
from app.routes.clientes import _contexto_ficha
from app.services import fechas, vencimientos
from app.services.errores import ErrorValidacion

router = APIRouter()


# ---------- Calendario (vista 05 + H-05) ----------

@router.get("/vencimientos", response_class=HTMLResponse)
def calendario(
    request: Request,
    periodo: str | None = None,
    sel: int | None = None,
    dia: str | None = None,
    db: Session = Depends(get_db),
):
    hoy = fechas.hoy()
    mes = fechas.parsear_periodo(periodo) or fechas.primer_dia_mes(hoy)
    del_mes = vencimientos.ocurrencias_del_mes(db, mes)
    proximos = vencimientos.proximos_dias(db, 15)

    # Detalle seleccionado: el que se clickeó, o el próximo desde hoy.
    seleccionada = None
    if sel is not None:
        try:
            fecha_sel = date.fromisoformat(dia) if dia else None
        except ValueError:
            fecha_sel = None
        for o in del_mes + proximos:
            if o.vencimiento.id == sel and (fecha_sel is None or o.fecha == fecha_sel):
                seleccionada = o
                break
    if seleccionada is None:
        futuras = [o for o in del_mes if o.fecha >= hoy]
        seleccionada = futuras[0] if futuras else (del_mes[0] if del_mes else None)

    por_dia: dict[date, list] = {}
    for o in del_mes:
        por_dia.setdefault(o.fecha, []).append(o)

    return templates.TemplateResponse(request, "calendario.html", {
        "seccion": "vencimientos",
        "mes": mes,
        "fecha_hoy": hoy,
        "semanas": vencimientos.semanas_del_mes(mes),
        "por_dia": por_dia,
        "seleccionada": seleccionada,
        "proximos": proximos,
        "mes_anterior": fechas.mes_anterior(mes).strftime("%Y-%m"),
        "mes_siguiente": fechas.mes_siguiente(mes).strftime("%Y-%m"),
    })


# ---------- Ficha del cliente: próximos 30 días (vista 12) ----------

@router.get("/clientes/{cliente_id}/vencimientos", response_class=HTMLResponse)
def ficha_vencimientos(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "pestana": "vencimientos",
        "proximos_cliente": vencimientos.proximos_del_cliente(db, contexto["cliente"]),
    }
    return templates.TemplateResponse(request, "ficha_vencimientos.html", contexto)


# ---------- Configuración → Vencimientos (vistas 22 y 22b) ----------

def _contexto_config(
    db: Session, anio: str | None = None, organismo: str | None = None,
    regimen: str | None = None,
) -> dict:
    filtro_anio = anio or "actual"
    return {
        "seccion": "configuracion",
        "vencimientos": vencimientos.listar_vencimientos(db, filtro_anio, organismo, regimen),
        "anios": vencimientos.anios_cargados(db),
        "anio_actual": fechas.hoy().year,
        "filtro_anio": filtro_anio,
        "filtro_organismo": organismo or "",
        "filtro_regimen": regimen or "",
        "regimenes": vencimientos.REGIMENES_APLICABLES,
        "organismos_legibles": vencimientos.ORGANISMOS_LEGIBLES,
    }


@router.get("/configuracion/vencimientos", response_class=HTMLResponse)
def config_listado(
    request: Request,
    anio: str | None = None,
    organismo: str | None = None,
    regimen: str | None = None,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request, "configuracion_vencimientos.html",
        _contexto_config(db, anio, organismo, regimen),
    )


@router.get("/configuracion/vencimientos/nuevo", response_class=HTMLResponse)
def form_nuevo(request: Request, db: Session = Depends(get_db)):
    contexto = _contexto_config(db) | {
        "vencimiento_editado": None,
        "valores": {"organismo": "dgi", "regimen": "todos"},
        "errores": {},
    }
    return templates.TemplateResponse(request, "vencimiento_form.html", contexto)


@router.post("/configuracion/vencimientos/nuevo")
async def crear(request: Request, db: Session = Depends(get_db)):
    formulario = dict(await request.form())
    try:
        vencimientos.crear_vencimiento(db, formulario)
    except ErrorValidacion as error:
        contexto = _contexto_config(db) | {
            "vencimiento_editado": None,
            "valores": formulario,
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "vencimiento_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/vencimientos", status_code=303)


@router.get("/configuracion/vencimientos/{vencimiento_id}/editar", response_class=HTMLResponse)
def form_editar(request: Request, vencimiento_id: int, db: Session = Depends(get_db)):
    vencimiento = db.get(VencimientoCalendario, vencimiento_id)
    if vencimiento is None:
        return RedirectResponse("/configuracion/vencimientos", status_code=303)
    contexto = _contexto_config(db) | {
        "vencimiento_editado": vencimiento,
        "valores": {
            "descripcion": vencimiento.descripcion,
            "organismo": vencimiento.organismo.value,
            "regimen": vencimiento.regimen.value,
            "mes": str(vencimiento.mes or ""),
            "dia_vencimiento": str(vencimiento.dia_vencimiento),
            "anio": str(vencimiento.anio or ""),
        },
        "errores": {},
    }
    return templates.TemplateResponse(request, "vencimiento_form.html", contexto)


@router.post("/configuracion/vencimientos/{vencimiento_id}/editar")
async def editar(request: Request, vencimiento_id: int, db: Session = Depends(get_db)):
    vencimiento = db.get(VencimientoCalendario, vencimiento_id)
    formulario = dict(await request.form())
    try:
        vencimientos.editar_vencimiento(db, vencimiento_id, formulario)
    except ErrorValidacion as error:
        contexto = _contexto_config(db) | {
            "vencimiento_editado": vencimiento,
            "valores": formulario,
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "vencimiento_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/vencimientos", status_code=303)


@router.post("/configuracion/vencimientos/{vencimiento_id}/activo")
def cambiar_activo(vencimiento_id: int, db: Session = Depends(get_db)):
    """Desactivar/reactivar en un clic, sin diálogo."""
    vencimientos.cambiar_activo(db, vencimiento_id)
    return RedirectResponse("/configuracion/vencimientos", status_code=303)
