"""Rutas de F6: cambio individual de honorario y aumento global (wizard).

El wizard de 3 pasos no guarda estado en el servidor: los parámetros
viajan entre pasos como campos ocultos del formulario.
"""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.routes.clientes import _contexto_ficha, _contexto_servicios
from app.services import catalogo, contratos, honorarios
from app.services.errores import ErrorValidacion

router = APIRouter()


def _fecha_o_none(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


# ---------- Cambio individual (vista 17) ----------

def _contexto_form_honorario(db: Session, contrato_id: int) -> dict | None:
    contrato = contratos.obtener_contrato(db, contrato_id)
    if contrato is None:
        return None
    vigente = honorarios.honorario_vigente(db, contrato_id)
    contexto = _contexto_ficha(db, contrato.cliente_id)
    contexto |= _contexto_servicios(db, contrato.cliente_id, False)
    contexto |= {
        "contrato": contrato,
        "servicio": catalogo.obtener_servicio(db, contrato.servicio_id),
        "vigente": vigente,
        "opciones_vigencia": honorarios.opciones_vigencia(
            cantidad=9,
            desde=vigente.fecha_desde if vigente else None,
        ),
        "vigencia_default": honorarios.vigencia_default(),
        "mes_actual": honorarios.hoy().replace(day=1),
        "errores": {},
        "valores": {},
    }
    return contexto


@router.get("/contratos/{contrato_id}/honorario", response_class=HTMLResponse)
def form_honorario(request: Request, contrato_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_form_honorario(db, contrato_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    return templates.TemplateResponse(request, "honorario_form.html", contexto)


@router.post("/contratos/{contrato_id}/honorario")
async def cambiar_honorario(
    request: Request, contrato_id: int, db: Session = Depends(get_db)
):
    contrato = contratos.obtener_contrato(db, contrato_id)
    formulario = await request.form()
    try:
        honorarios.cambiar_honorario(
            db,
            contrato_id,
            formulario.get("honorario", ""),
            _fecha_o_none(formulario.get("fecha_vigencia", "")),
        )
    except ErrorValidacion as error:
        contexto = _contexto_form_honorario(db, contrato_id)
        contexto |= {"errores": error.errores, "valores": dict(formulario)}
        return templates.TemplateResponse(
            request, "honorario_form.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{contrato.cliente_id}/servicios", status_code=303)


# ---------- Aumento global (vistas 18a-d) ----------

@router.get("/aumento-global", response_class=HTMLResponse)
def paso1(request: Request):
    return templates.TemplateResponse(request, "aumento_paso1.html", {
        "seccion": "cobros",
        "opciones_vigencia": honorarios.opciones_vigencia(
            cantidad=6, desde=honorarios.hoy().replace(day=1)
        ),
        "vigencia_default": honorarios.vigencia_default(),
        "errores": {},
        "valores": {},
    })


def _parametros(formulario) -> tuple:
    """Valida porcentaje y vigencia (comunes a los pasos 2 y 3)."""
    errores = {}
    porcentaje, error_pct = honorarios.parsear_porcentaje(
        formulario.get("porcentaje", "")
    )
    if error_pct:
        errores["porcentaje"] = error_pct
    vigencia = _fecha_o_none(formulario.get("fecha_vigencia", ""))
    if vigencia is None or vigencia.day != 1:
        errores["fecha_vigencia"] = "La fecha de vigencia debe ser el primer día de un mes."
    return porcentaje, vigencia, errores


@router.post("/aumento-global/paso2", response_class=HTMLResponse)
async def paso2(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    porcentaje, vigencia, errores = _parametros(formulario)
    if errores:
        return templates.TemplateResponse(request, "aumento_paso1.html", {
            "seccion": "cobros",
            "opciones_vigencia": honorarios.opciones_vigencia(
                cantidad=6, desde=honorarios.hoy().replace(day=1)
            ),
            "vigencia_default": honorarios.vigencia_default(),
            "errores": errores,
            "valores": dict(formulario),
        }, status_code=422)

    return templates.TemplateResponse(request, "aumento_paso2.html", {
        "seccion": "cobros",
        "porcentaje": formulario.get("porcentaje"),
        "vigencia": vigencia,
        "candidatos": honorarios.candidatos_aumento(db, porcentaje, vigencia),
        "error_seleccion": None,
    })


def _seleccion_desde_form(formulario) -> list[dict]:
    return [
        {
            "contrato_id": int(contrato_id),
            "nuevo_texto": formulario.get(f"nuevo_{contrato_id}", ""),
        }
        for contrato_id in formulario.getlist("seleccion")
    ]


@router.post("/aumento-global/paso3", response_class=HTMLResponse)
async def paso3(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    porcentaje, vigencia, _ = _parametros(formulario)
    seleccion = _seleccion_desde_form(formulario)

    candidatos = honorarios.candidatos_aumento(db, porcentaje, vigencia)
    por_contrato = {c["contrato"].id: c for c in candidatos}

    # Validación del paso 2: al menos uno y todos los importes válidos.
    errores_paso2 = None
    if not seleccion:
        errores_paso2 = "Seleccioná al menos un servicio."
    resumen = []
    from app.services.importes import parsear_importe
    for item in seleccion:
        candidato = por_contrato.get(item["contrato_id"])
        nuevo, error_importe = parsear_importe(item["nuevo_texto"], "honorario")
        if candidato is None or not candidato["valida"] or error_importe:
            errores_paso2 = errores_paso2 or (
                error_importe or "Hay filas seleccionadas con datos inválidos."
            )
            break
        resumen.append(candidato | {"nuevo": nuevo})

    if errores_paso2:
        return templates.TemplateResponse(request, "aumento_paso2.html", {
            "seccion": "cobros",
            "porcentaje": formulario.get("porcentaje"),
            "vigencia": vigencia,
            "candidatos": candidatos,
            "error_seleccion": errores_paso2,
        }, status_code=422)

    total_vigente = sum(fila["vigente"] for fila in resumen)
    total_nuevo = sum(fila["nuevo"] for fila in resumen)
    return templates.TemplateResponse(request, "aumento_paso3.html", {
        "seccion": "cobros",
        "porcentaje": formulario.get("porcentaje"),
        "vigencia": vigencia,
        "resumen": resumen,
        "total_vigente": total_vigente,
        "total_nuevo": total_nuevo,
    })


@router.post("/aumento-global/confirmar", response_class=HTMLResponse)
async def confirmar(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    _, vigencia, _ = _parametros(formulario)
    seleccion = _seleccion_desde_form(formulario)
    try:
        aplicados = honorarios.aplicar_aumento_global(db, seleccion, vigencia)
    except ErrorValidacion:
        # Estado inesperado (los pasos previos ya validaron): se reinicia.
        return RedirectResponse("/aumento-global", status_code=303)
    return templates.TemplateResponse(request, "aumento_listo.html", {
        "seccion": "cobros",
        "aplicados": aplicados,
        "vigencia": vigencia,
    })
