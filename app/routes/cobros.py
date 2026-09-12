"""Rutas de F5: vista global de cobros y CRUD de cobros y descuentos."""

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cliente, Cobro, Descuento
from app.plantillas import templates
from app.routes.clientes import _contexto_cuenta, _contexto_ficha
from app.services import cobros as servicio_cobros
from app.services import cuentas
from app.services.errores import ErrorValidacion

router = APIRouter()


def _fecha_o_none(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


# ---------- Vista global (03) ----------

@router.get("/cobros", response_class=HTMLResponse)
def vista_global(request: Request, db: Session = Depends(get_db)):
    contexto = {"seccion": "cobros"} | cuentas.saldos_de_clientes_activos(db)
    return templates.TemplateResponse(request, "cobros_global.html", contexto)


# ---------- Registrar / editar cobro (16a) ----------

def _contexto_form_cobro(
    db: Session, cliente_id: int, valores: dict, errores: dict, cobro=None
) -> dict:
    contexto = _contexto_ficha(db, cliente_id) | _contexto_cuenta(db, cliente_id)
    contexto |= {
        "clientes_activos": db.query(Cliente)
        .filter(Cliente.activo.is_(True)).order_by(Cliente.nombre).all(),
        "contratos_cliente": servicio_cobros.contratos_activos_del_cliente(
            db, cliente_id
        ),
        "cobro": cobro,
        "valores": valores,
        "errores": errores,
    }
    return contexto


def _datos_cobro_desde_form(formulario) -> dict:
    return {
        "cliente_id": int(formulario.get("cliente_id"))
        if formulario.get("cliente_id") else None,
        "servicio_contratado_id": int(formulario.get("servicio_contratado_id"))
        if formulario.get("servicio_contratado_id") else None,
        "periodo_desde": _fecha_o_none(formulario.get("periodo_desde", "")),
        "periodo_hasta": _fecha_o_none(formulario.get("periodo_hasta", "")),
        "fecha_cobro": _fecha_o_none(formulario.get("fecha_cobro", "")),
        "importe": formulario.get("importe", ""),
        "forma_pago": formulario.get("forma_pago", ""),
        "tipo_comprobante": formulario.get("tipo_comprobante", ""),
        "notas": formulario.get("notas", "").strip(),
    }


@router.get("/clientes/{cliente_id}/cobros/nuevo", response_class=HTMLResponse)
def form_cobro(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    if _contexto_ficha(db, cliente_id) is None:
        return RedirectResponse("/cobros", status_code=303)
    valores = {
        "cliente_id": str(cliente_id),
        "fecha_cobro": servicio_cobros.hoy().isoformat(),
        "forma_pago": "transferencia",
        "tipo_comprobante": "e_ticket",
    }
    return templates.TemplateResponse(
        request, "cobro_form.html",
        _contexto_form_cobro(db, cliente_id, valores, {}),
    )


@router.post("/clientes/{cliente_id}/cobros/nuevo")
async def crear_cobro(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    datos = _datos_cobro_desde_form(formulario)
    try:
        cobro = servicio_cobros.registrar_cobro(db, datos)
    except ErrorValidacion as error:
        return templates.TemplateResponse(
            request, "cobro_form.html",
            _contexto_form_cobro(db, cliente_id, dict(formulario), error.errores),
            status_code=422,
        )
    return RedirectResponse(f"/clientes/{cobro.cliente_id}/cuenta", status_code=303)


def _valores_de_cobro(cobro: Cobro) -> dict:
    return {
        "cliente_id": str(cobro.cliente_id),
        "servicio_contratado_id": str(cobro.servicio_contratado_id or ""),
        "periodo_desde": cobro.periodo_desde.isoformat() if cobro.periodo_desde else "",
        "periodo_hasta": cobro.periodo_hasta.isoformat() if cobro.periodo_hasta else "",
        "fecha_cobro": cobro.fecha_cobro.isoformat(),
        "importe": str(cobro.importe).replace(".", ","),
        "forma_pago": cobro.forma_pago.value,
        "tipo_comprobante": cobro.tipo_comprobante.value,
        "notas": cobro.notas or "",
    }


@router.get("/cobros/{cobro_id}/editar", response_class=HTMLResponse)
def form_editar_cobro(request: Request, cobro_id: int, db: Session = Depends(get_db)):
    cobro = db.get(Cobro, cobro_id)
    if cobro is None:
        return RedirectResponse("/cobros", status_code=303)
    return templates.TemplateResponse(
        request, "cobro_form.html",
        _contexto_form_cobro(
            db, cobro.cliente_id, _valores_de_cobro(cobro), {}, cobro=cobro
        ),
    )


@router.post("/cobros/{cobro_id}/editar")
async def editar_cobro(request: Request, cobro_id: int, db: Session = Depends(get_db)):
    cobro = db.get(Cobro, cobro_id)
    formulario = await request.form()
    datos = _datos_cobro_desde_form(formulario)
    try:
        servicio_cobros.editar_cobro(db, cobro_id, datos)
    except ErrorValidacion as error:
        return templates.TemplateResponse(
            request, "cobro_form.html",
            _contexto_form_cobro(
                db, cobro.cliente_id, dict(formulario), error.errores, cobro=cobro
            ),
            status_code=422,
        )
    return RedirectResponse(f"/clientes/{cobro.cliente_id}/cuenta", status_code=303)


@router.get("/cobros/{cobro_id}/eliminar", response_class=HTMLResponse)
def confirmar_eliminar_cobro(
    request: Request, cobro_id: int, db: Session = Depends(get_db)
):
    cobro = db.get(Cobro, cobro_id)
    if cobro is None:
        return RedirectResponse("/cobros", status_code=303)
    contexto = _contexto_ficha(db, cobro.cliente_id) | _contexto_cuenta(
        db, cobro.cliente_id
    ) | {
        "accion_eliminar": f"/cobros/{cobro_id}/eliminar",
        "volver": f"/clientes/{cobro.cliente_id}/cuenta",
    }
    return templates.TemplateResponse(request, "eliminar_confirmacion.html", contexto)


@router.post("/cobros/{cobro_id}/eliminar")
def eliminar_cobro(cobro_id: int, db: Session = Depends(get_db)):
    cobro = db.get(Cobro, cobro_id)
    cliente_id = cobro.cliente_id
    servicio_cobros.eliminar_cobro(db, cobro_id)
    return RedirectResponse(f"/clientes/{cliente_id}/cuenta", status_code=303)


# ---------- Registrar / editar descuento (16b) ----------

def _contexto_form_descuento(
    db: Session, cliente_id: int, valores: dict, errores: dict, descuento=None
) -> dict:
    contexto = _contexto_ficha(db, cliente_id) | _contexto_cuenta(db, cliente_id)
    contexto |= {
        "contratos_cliente": servicio_cobros.contratos_activos_del_cliente(
            db, cliente_id
        ),
        "descuento": descuento,
        "valores": valores,
        "errores": errores,
    }
    return contexto


def _datos_descuento_desde_form(formulario) -> dict:
    return {
        "servicio_contratado_id": int(formulario.get("servicio_contratado_id"))
        if formulario.get("servicio_contratado_id") else None,
        "fecha": _fecha_o_none(formulario.get("fecha", "")),
        "importe": formulario.get("importe", ""),
        "motivo": formulario.get("motivo", ""),
    }


@router.get("/clientes/{cliente_id}/descuentos/nuevo", response_class=HTMLResponse)
def form_descuento(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    if _contexto_ficha(db, cliente_id) is None:
        return RedirectResponse("/clientes", status_code=303)
    valores = {"fecha": servicio_cobros.hoy().isoformat()}
    return templates.TemplateResponse(
        request, "descuento_form.html",
        _contexto_form_descuento(db, cliente_id, valores, {}),
    )


@router.post("/clientes/{cliente_id}/descuentos/nuevo")
async def crear_descuento(
    request: Request, cliente_id: int, db: Session = Depends(get_db)
):
    formulario = await request.form()
    try:
        servicio_cobros.registrar_descuento(
            db, cliente_id, _datos_descuento_desde_form(formulario)
        )
    except ErrorValidacion as error:
        return templates.TemplateResponse(
            request, "descuento_form.html",
            _contexto_form_descuento(db, cliente_id, dict(formulario), error.errores),
            status_code=422,
        )
    return RedirectResponse(f"/clientes/{cliente_id}/cuenta", status_code=303)


def _valores_de_descuento(descuento: Descuento) -> dict:
    return {
        "servicio_contratado_id": str(descuento.servicio_contratado_id or ""),
        "fecha": descuento.fecha.isoformat(),
        "importe": str(descuento.importe).replace(".", ","),
        "motivo": descuento.motivo,
    }


@router.get("/descuentos/{descuento_id}/editar", response_class=HTMLResponse)
def form_editar_descuento(
    request: Request, descuento_id: int, db: Session = Depends(get_db)
):
    descuento = db.get(Descuento, descuento_id)
    if descuento is None:
        return RedirectResponse("/cobros", status_code=303)
    return templates.TemplateResponse(
        request, "descuento_form.html",
        _contexto_form_descuento(
            db, descuento.cliente_id, _valores_de_descuento(descuento), {},
            descuento=descuento,
        ),
    )


@router.post("/descuentos/{descuento_id}/editar")
async def editar_descuento(
    request: Request, descuento_id: int, db: Session = Depends(get_db)
):
    descuento = db.get(Descuento, descuento_id)
    formulario = await request.form()
    try:
        servicio_cobros.editar_descuento(
            db, descuento_id, _datos_descuento_desde_form(formulario)
        )
    except ErrorValidacion as error:
        return templates.TemplateResponse(
            request, "descuento_form.html",
            _contexto_form_descuento(
                db, descuento.cliente_id, dict(formulario), error.errores,
                descuento=descuento,
            ),
            status_code=422,
        )
    return RedirectResponse(f"/clientes/{descuento.cliente_id}/cuenta", status_code=303)


@router.get("/descuentos/{descuento_id}/eliminar", response_class=HTMLResponse)
def confirmar_eliminar_descuento(
    request: Request, descuento_id: int, db: Session = Depends(get_db)
):
    descuento = db.get(Descuento, descuento_id)
    if descuento is None:
        return RedirectResponse("/cobros", status_code=303)
    contexto = _contexto_ficha(db, descuento.cliente_id) | _contexto_cuenta(
        db, descuento.cliente_id
    ) | {
        "accion_eliminar": f"/descuentos/{descuento_id}/eliminar",
        "volver": f"/clientes/{descuento.cliente_id}/cuenta",
    }
    return templates.TemplateResponse(request, "eliminar_confirmacion.html", contexto)


@router.post("/descuentos/{descuento_id}/eliminar")
def eliminar_descuento(descuento_id: int, db: Session = Depends(get_db)):
    descuento = db.get(Descuento, descuento_id)
    cliente_id = descuento.cliente_id
    servicio_cobros.eliminar_descuento(db, descuento_id)
    return RedirectResponse(f"/clientes/{cliente_id}/cuenta", status_code=303)
