"""Rutas de F1 (clientes) y F4 (servicios contratados).

Los endpoints arman el contexto llamando a los servicios y devuelven HTML;
las validaciones y la lógica viven en app/services/.
"""

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.schemas.clientes import FormularioCliente
from app.services import catalogo, clientes, contratos
from app.services.errores import ErrorValidacion

router = APIRouter()


def _fecha_o_none(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


# ---------- Listado (vista 02) ----------

def _contexto_listado(db: Session, inactivos: bool) -> dict:
    listado = clientes.listar_clientes(db, incluir_inactivos=inactivos)
    return {
        "seccion": "clientes",
        "mensuales": listado["mensuales"],
        "eventuales": listado["eventuales"],
        "mostrar_inactivos": inactivos,
    }


@router.get("/clientes", response_class=HTMLResponse)
def listado(request: Request, inactivos: int = 0, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "clientes_listado.html", _contexto_listado(db, bool(inactivos))
    )


# ---------- Crear cliente (vista 13, diálogo sobre el listado) ----------

@router.get("/clientes/nuevo", response_class=HTMLResponse)
def form_crear(request: Request, db: Session = Depends(get_db)):
    contexto = _contexto_listado(db, False) | {
        "cliente": None,
        "valores": {"fecha_inicio": clientes.hoy().isoformat()},
        "errores": {},
    }
    return templates.TemplateResponse(request, "cliente_form_nuevo.html", contexto)


@router.post("/clientes/nuevo")
async def crear(request: Request, db: Session = Depends(get_db)):
    formulario = await request.form()
    datos = FormularioCliente(**formulario)
    try:
        cliente = clientes.crear_cliente(db, datos)
    except ErrorValidacion as error:
        contexto = _contexto_listado(db, False) | {
            "cliente": None,
            "valores": dict(formulario),
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "cliente_form_nuevo.html", contexto, status_code=422
        )
    # Redirección a la ficha del cliente creado (Chat 3).
    return RedirectResponse(f"/clientes/{cliente.id}", status_code=303)


# ---------- Ficha (vistas 07 y 08) ----------

def _contexto_ficha(db: Session, cliente_id: int) -> dict | None:
    cliente = clientes.obtener_cliente(db, cliente_id)
    if cliente is None:
        return None
    return {
        "seccion": "clientes",
        "cliente": cliente,
        "es_mensual": clientes.es_mensual(db, cliente_id),
        "conteos_contratos": contratos.contar_contratos(db, cliente_id),
    }


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
def ficha_datos(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "pestana": "datos",
        "historial": clientes.historial_regimenes(db, cliente_id),
    }
    return templates.TemplateResponse(request, "ficha_datos.html", contexto)


@router.get("/clientes/{cliente_id}/servicios", response_class=HTMLResponse)
def ficha_servicios(
    request: Request,
    cliente_id: int,
    finalizados: int = 0,
    db: Session = Depends(get_db),
):
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= _contexto_servicios(db, cliente_id, bool(finalizados))
    return templates.TemplateResponse(request, "ficha_servicios.html", contexto)


def _contexto_servicios(db: Session, cliente_id: int, finalizados: bool) -> dict:
    return {
        "pestana": "servicios",
        "filas_contratos": contratos.listar_contratos(
            db, cliente_id, incluir_finalizados=finalizados
        ),
        "mostrar_finalizados": finalizados,
    }


# ---------- Editar cliente (vista 13, diálogo sobre la ficha) ----------

def _valores_de_cliente(cliente) -> dict:
    return {
        "nombre": cliente.nombre,
        "regimen": cliente.regimen.value,
        "rut": cliente.rut or "",
        "ci": cliente.ci or "",
        "fecha_nacimiento": cliente.fecha_nacimiento.isoformat()
        if cliente.fecha_nacimiento else "",
        "email": cliente.email or "",
        "telefono": cliente.telefono or "",
        "notas": cliente.notas or "",
    }


@router.get("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def form_editar(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "pestana": "datos",
        "historial": clientes.historial_regimenes(db, cliente_id),
        "valores": _valores_de_cliente(contexto["cliente"]),
        "errores": {},
        "fecha_cambio_default": clientes.hoy().isoformat(),
    }
    return templates.TemplateResponse(request, "cliente_form_editar.html", contexto)


@router.post("/clientes/{cliente_id}/editar")
async def editar(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    formulario = await request.form()
    datos = FormularioCliente(**formulario)
    try:
        clientes.editar_cliente(
            db,
            cliente_id,
            datos,
            _fecha_o_none(formulario.get("fecha_cambio_regimen", "")),
        )
    except ErrorValidacion as error:
        contexto = _contexto_ficha(db, cliente_id) | {
            "pestana": "datos",
            "historial": clientes.historial_regimenes(db, cliente_id),
            "valores": dict(formulario),
            "errores": error.errores,
            "fecha_cambio_default": clientes.hoy().isoformat(),
        }
        return templates.TemplateResponse(
            request, "cliente_form_editar.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{cliente_id}", status_code=303)


@router.post("/clientes/{cliente_id}/activo")
def cambiar_activo(cliente_id: int, db: Session = Depends(get_db)):
    """Desactivar/reactivar: un clic, sin diálogo (adenda Etapa 1)."""
    clientes.cambiar_activo(db, cliente_id)
    return RedirectResponse(f"/clientes/{cliente_id}", status_code=303)


# ---------- F4: contratar / detalle / finalizar ----------

@router.get("/clientes/{cliente_id}/servicios/contratar", response_class=HTMLResponse)
def form_contratar(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= _contexto_servicios(db, cliente_id, False) | {
        "servicios_activos": [
            f["servicio"] for f in catalogo.listar_servicios(db) if f["servicio"].activo
        ],
        "valores": {"fecha_inicio": contratos.hoy().isoformat()},
        "errores": {},
    }
    return templates.TemplateResponse(request, "contratar_form.html", contexto)


@router.post("/clientes/{cliente_id}/servicios/contratar")
def contratar(
    request: Request,
    cliente_id: int,
    servicio_id: str = Form(""),
    fecha_inicio: str = Form(""),
    honorario: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        contratos.contratar(
            db,
            cliente_id,
            int(servicio_id) if servicio_id else None,
            _fecha_o_none(fecha_inicio),
            honorario,
        )
    except ErrorValidacion as error:
        contexto = _contexto_ficha(db, cliente_id) | _contexto_servicios(
            db, cliente_id, False
        ) | {
            "servicios_activos": [
                f["servicio"]
                for f in catalogo.listar_servicios(db)
                if f["servicio"].activo
            ],
            "valores": {
                "servicio_id": servicio_id,
                "fecha_inicio": fecha_inicio,
                "honorario": honorario,
            },
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "contratar_form.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{cliente_id}/servicios", status_code=303)


def _contexto_dialogo_contrato(db: Session, contrato_id: int) -> dict | None:
    """Contexto común de los diálogos que operan sobre un contrato."""
    contrato = contratos.obtener_contrato(db, contrato_id)
    if contrato is None:
        return None
    base = _contexto_ficha(db, contrato.cliente_id)
    return base | _contexto_servicios(db, contrato.cliente_id, False) | {
        "contrato": contrato,
        "servicio": catalogo.obtener_servicio(db, contrato.servicio_id),
        "honorario_vigente": contratos.honorario_vigente(db, contrato_id),
    }


@router.get("/contratos/{contrato_id}", response_class=HTMLResponse)
def detalle_contrato(request: Request, contrato_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_dialogo_contrato(db, contrato_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "puede_editar_fecha": contratos.puede_editar_fecha_inicio(db, contrato_id),
        "errores": {},
    }
    return templates.TemplateResponse(request, "contrato_detalle.html", contexto)


@router.post("/contratos/{contrato_id}/fecha-inicio")
def editar_fecha_inicio(
    request: Request,
    contrato_id: int,
    fecha_inicio: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = contratos.obtener_contrato(db, contrato_id)
    try:
        contratos.editar_fecha_inicio(db, contrato_id, _fecha_o_none(fecha_inicio))
    except ErrorValidacion as error:
        contexto = _contexto_dialogo_contrato(db, contrato_id) | {
            "puede_editar_fecha": contratos.puede_editar_fecha_inicio(db, contrato_id),
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "contrato_detalle.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{contrato.cliente_id}/servicios", status_code=303)


@router.get("/contratos/{contrato_id}/finalizar", response_class=HTMLResponse)
def form_finalizar(request: Request, contrato_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_dialogo_contrato(db, contrato_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "valores": {"fecha_fin": contratos.hoy().isoformat()},
        "errores": {},
    }
    return templates.TemplateResponse(request, "finalizar_form.html", contexto)


@router.post("/contratos/{contrato_id}/finalizar")
def finalizar(
    request: Request,
    contrato_id: int,
    fecha_fin: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = contratos.obtener_contrato(db, contrato_id)
    try:
        contratos.finalizar(db, contrato_id, _fecha_o_none(fecha_fin))
    except ErrorValidacion as error:
        contexto = _contexto_dialogo_contrato(db, contrato_id) | {
            "valores": {"fecha_fin": fecha_fin},
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "finalizar_form.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{contrato.cliente_id}/servicios", status_code=303)
