"""Rutas de F9: histórico mensual, proyección y gastos/ingresos propios."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GastoIngresoPropio
from app.plantillas import templates
from app.services import fechas, finanzas, gastos
from app.services.errores import ErrorValidacion

router = APIRouter(prefix="/finanzas")


# ---------- Histórico y proyección (vistas 24a y 24b) ----------

@router.get("/historico", response_class=HTMLResponse)
def historico(request: Request, hasta: str | None = None, db: Session = Depends(get_db)):
    mes_actual = fechas.primer_dia_mes(fechas.hoy())
    fin = fechas.parsear_periodo(hasta) or mes_actual
    fin = min(fin, mes_actual)  # no se navega hacia el futuro
    filas = finanzas.historico(db, fin, 12)
    anterior = fin
    for _ in range(12):
        anterior = fechas.mes_anterior(anterior)
    siguiente = fin
    for _ in range(12):
        siguiente = fechas.mes_siguiente(siguiente)
    return templates.TemplateResponse(request, "finanzas_historico.html", {
        "seccion": "dashboard",
        "pestana": "historico",
        "filas": filas,
        "mes_actual": mes_actual,
        "rango": (filas[-1].mes, filas[0].mes),
        "hasta_anterior": anterior.strftime("%Y-%m"),
        "hasta_siguiente": min(siguiente, mes_actual).strftime("%Y-%m"),
        "hay_siguiente": fin < mes_actual,
    })


@router.get("/proyeccion", response_class=HTMLResponse)
def proyeccion(request: Request, db: Session = Depends(get_db)):
    desde = fechas.mes_siguiente(fechas.primer_dia_mes(fechas.hoy()))
    return templates.TemplateResponse(request, "finanzas_proyeccion.html", {
        "seccion": "dashboard",
        "pestana": "proyeccion",
        "filas": finanzas.proyeccion(db, desde, 6),
    })


# ---------- Gastos e ingresos propios (vistas 25 y 25b) ----------

def _filtros(periodo: str | None, tipo: str | None, categoria: str | None) -> dict:
    return {
        "periodo": fechas.parsear_periodo(periodo) or fechas.primer_dia_mes(fechas.hoy()),
        "tipo": tipo if tipo in gastos.TIPOS else "",
        "categoria": categoria if categoria in gastos.CATEGORIAS else "",
    }


def _query(filtros: dict, **cambios) -> str:
    valores = {
        "periodo": filtros["periodo"].strftime("%Y-%m"),
        "tipo": filtros["tipo"],
        "categoria": filtros["categoria"],
    } | cambios
    return "&".join(f"{k}={v}" for k, v in valores.items())


def _contexto_gastos(db: Session, filtros: dict) -> dict:
    periodo = filtros["periodo"]
    return {
        "seccion": "dashboard",
        "filtros": filtros,
        "query": _query(filtros),
        "query_anterior": _query(filtros, periodo=fechas.mes_anterior(periodo).strftime("%Y-%m")),
        "query_siguiente": _query(filtros, periodo=fechas.mes_siguiente(periodo).strftime("%Y-%m")),
        "query_tipo": {t: _query(filtros, tipo=t) for t in ("", "gasto", "ingreso")},
        "categorias_legibles": gastos.CATEGORIAS_LEGIBLES,
        **gastos.listar(db, periodo, filtros["tipo"], filtros["categoria"]),
    }


@router.get("/gastos", response_class=HTMLResponse)
def listado_gastos(
    request: Request,
    periodo: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request, "finanzas_gastos.html",
        _contexto_gastos(db, _filtros(periodo, tipo, categoria)),
    )


def _datos(formulario) -> dict:
    fecha = formulario.get("fecha", "")
    try:
        fecha = date.fromisoformat(fecha) if fecha else None
    except ValueError:
        fecha = None
    return {
        "fecha": fecha,
        "tipo": formulario.get("tipo", ""),
        "concepto": formulario.get("concepto", ""),
        "importe": formulario.get("importe", ""),
        "categoria": formulario.get("categoria", ""),
        "notas": formulario.get("notas", ""),
    }


def _form(request, db, filtros, movimiento, valores, errores, status=200):
    contexto = _contexto_gastos(db, filtros) | {
        "movimiento": movimiento,
        "valores": valores,
        "errores": errores,
    }
    return templates.TemplateResponse(
        request, "gasto_form.html", contexto, status_code=status
    )


def _filtros_de_form(formulario) -> dict:
    return _filtros(formulario.get("f_periodo"), formulario.get("f_tipo"), formulario.get("f_categoria"))


@router.get("/gastos/nuevo", response_class=HTMLResponse)
def form_nuevo(
    request: Request,
    periodo: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
    db: Session = Depends(get_db),
):
    filtros = _filtros(periodo, tipo, categoria)
    valores = {"tipo": "gasto", "categoria": "cjppu", "fecha": fechas.hoy().isoformat()}
    return _form(request, db, filtros, None, valores, {})


@router.post("/gastos/nuevo")
async def crear(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros_de_form(formulario)
    try:
        movimiento = gastos.crear(db, _datos(formulario))
    except ErrorValidacion as error:
        return _form(request, db, filtros, None, dict(formulario), error.errores, 422)
    filtros["periodo"] = fechas.primer_dia_mes(movimiento.fecha)
    return RedirectResponse(f"/finanzas/gastos?{_query(filtros)}", status_code=303)


@router.get("/gastos/{movimiento_id}/editar", response_class=HTMLResponse)
def form_editar(
    request: Request,
    movimiento_id: int,
    periodo: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
    db: Session = Depends(get_db),
):
    movimiento = db.get(GastoIngresoPropio, movimiento_id)
    if movimiento is None:
        return RedirectResponse("/finanzas/gastos", status_code=303)
    valores = {
        "fecha": movimiento.fecha.isoformat(),
        "tipo": movimiento.tipo.value,
        "concepto": movimiento.concepto,
        "importe": str(movimiento.importe).replace(".", ","),
        "categoria": movimiento.categoria.value,
        "notas": movimiento.notas or "",
    }
    return _form(request, db, _filtros(periodo, tipo, categoria), movimiento, valores, {})


@router.post("/gastos/{movimiento_id}/editar")
async def editar(request: Request, movimiento_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros_de_form(formulario)
    movimiento = db.get(GastoIngresoPropio, movimiento_id)
    if movimiento is None:
        return RedirectResponse(f"/finanzas/gastos?{_query(filtros)}", status_code=303)
    try:
        gastos.editar(db, movimiento_id, _datos(formulario))
    except ErrorValidacion as error:
        return _form(request, db, filtros, movimiento, dict(formulario), error.errores, 422)
    return RedirectResponse(f"/finanzas/gastos?{_query(filtros)}", status_code=303)


@router.get("/gastos/{movimiento_id}/eliminar", response_class=HTMLResponse)
def confirmar_eliminar(
    request: Request,
    movimiento_id: int,
    periodo: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
    db: Session = Depends(get_db),
):
    filtros = _filtros(periodo, tipo, categoria)
    contexto = _contexto_gastos(db, filtros) | {"movimiento_a_eliminar": movimiento_id}
    return templates.TemplateResponse(request, "gasto_eliminar.html", contexto)


@router.post("/gastos/{movimiento_id}/eliminar")
async def eliminar(request: Request, movimiento_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    filtros = _filtros_de_form(formulario)
    if db.get(GastoIngresoPropio, movimiento_id) is not None:
        gastos.eliminar(db, movimiento_id)
    return RedirectResponse(f"/finanzas/gastos?{_query(filtros)}", status_code=303)
