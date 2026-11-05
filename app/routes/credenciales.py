"""Rutas de F2 — vault de credenciales en la ficha del cliente."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.routes.clientes import _contexto_ficha
from app.services import vault
from app.services.errores import ErrorValidacion

router = APIRouter()


def _contexto_credenciales(
    db: Session, cliente_id: int, detalle_id: int | None = None
) -> dict | None:
    contexto = _contexto_ficha(db, cliente_id)
    if contexto is None:
        return None
    contexto |= {
        "pestana": "credenciales",
        "credenciales": vault.listar_credenciales(db, cliente_id),
        "tipos_legibles": vault.TIPOS_LEGIBLES,
        "detalle": None,
    }
    if detalle_id is not None:
        credencial = vault.obtener_credencial(db, detalle_id)
        if credencial is not None and credencial.cliente_id == cliente_id:
            contexto["detalle"] = vault.detalle(db, detalle_id)
    return contexto


@router.get("/clientes/{cliente_id}/credenciales", response_class=HTMLResponse)
def listado(
    request: Request,
    cliente_id: int,
    detalle: int | None = None,
    db: Session = Depends(get_db),
):
    contexto = _contexto_credenciales(db, cliente_id, detalle)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    return templates.TemplateResponse(request, "ficha_credenciales.html", contexto)


# ---------- Revelar / ocultar contraseña (HTMX) ----------

@router.get("/credenciales/{credencial_id}/password", response_class=HTMLResponse)
def celda_password(
    request: Request,
    credencial_id: int,
    mostrar: int = 0,
    lugar: str = "fila",
    db: Session = Depends(get_db),
):
    """Devuelve el fragmento de la celda de contraseña.

    El descifrado ocurre acá, en el servidor, y SOLO cuando mostrar=1.
    """
    credencial = vault.obtener_credencial(db, credencial_id)
    if credencial is None:
        return HTMLResponse("", status_code=404)
    texto = vault.revelar_password(db, credencial_id) if mostrar else None
    return templates.TemplateResponse(request, "_password_celda.html", {
        "credencial": credencial,
        "texto": texto,
        "mostrar": bool(mostrar),
        "lugar": lugar,
    })


# ---------- Crear / editar (vista 14) ----------

def _form(formulario) -> dict:
    return {
        "tipo": formulario.get("tipo", ""),
        "usuario": formulario.get("usuario", ""),
        "password": formulario.get("password", ""),
        "notas": formulario.get("notas", ""),
    }


@router.get("/clientes/{cliente_id}/credenciales/nueva", response_class=HTMLResponse)
def form_nueva(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    contexto = _contexto_credenciales(db, cliente_id)
    if contexto is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto |= {
        "credencial_editada": None,
        "valores": {"tipo": "dgi"},
        "errores": {},
        "fecha_actualizacion": vault.hoy(),
    }
    return templates.TemplateResponse(request, "credencial_form.html", contexto)


@router.post("/clientes/{cliente_id}/credenciales/nueva")
async def crear(request: Request, cliente_id: int, db: Session = Depends(get_db)):
    datos = _form(await request.form())
    try:
        vault.crear_credencial(db, cliente_id, **datos)
    except ErrorValidacion as error:
        contexto = _contexto_credenciales(db, cliente_id) | {
            "credencial_editada": None,
            # La contraseña tipeada no se devuelve al navegador en el error.
            "valores": datos | {"password": ""},
            "errores": error.errores,
            "fecha_actualizacion": vault.hoy(),
        }
        return templates.TemplateResponse(
            request, "credencial_form.html", contexto, status_code=422
        )
    return RedirectResponse(f"/clientes/{cliente_id}/credenciales", status_code=303)


@router.get("/credenciales/{credencial_id}/editar", response_class=HTMLResponse)
def form_editar(request: Request, credencial_id: int, db: Session = Depends(get_db)):
    credencial = vault.obtener_credencial(db, credencial_id)
    if credencial is None:
        return RedirectResponse("/clientes", status_code=303)
    datos = vault.detalle(db, credencial_id)
    contexto = _contexto_credenciales(db, credencial.cliente_id) | {
        "credencial_editada": credencial,
        "valores": {
            "tipo": credencial.tipo.value,
            "usuario": datos["usuario"] if datos["ok"] else "",
            "notas": datos["notas"] if datos["ok"] else "",
        },
        "errores": {},
        "fecha_actualizacion": credencial.ultima_actualizacion,
    }
    return templates.TemplateResponse(request, "credencial_form.html", contexto)


@router.post("/credenciales/{credencial_id}/editar")
async def editar(request: Request, credencial_id: int, db: Session = Depends(get_db)):
    credencial = vault.obtener_credencial(db, credencial_id)
    datos = _form(await request.form())
    try:
        vault.editar_credencial(
            db, credencial_id,
            tipo=datos["tipo"], usuario=datos["usuario"],
            password_nueva=datos["password"], notas=datos["notas"],
        )
    except ErrorValidacion as error:
        contexto = _contexto_credenciales(db, credencial.cliente_id) | {
            "credencial_editada": credencial,
            "valores": datos | {"password": ""},
            "errores": error.errores,
            "fecha_actualizacion": credencial.ultima_actualizacion,
        }
        return templates.TemplateResponse(
            request, "credencial_form.html", contexto, status_code=422
        )
    return RedirectResponse(
        f"/clientes/{credencial.cliente_id}/credenciales?detalle={credencial_id}",
        status_code=303,
    )


# ---------- Eliminar (con confirmación) ----------

@router.get("/credenciales/{credencial_id}/eliminar", response_class=HTMLResponse)
def confirmar_eliminar(
    request: Request, credencial_id: int, db: Session = Depends(get_db)
):
    credencial = vault.obtener_credencial(db, credencial_id)
    if credencial is None:
        return RedirectResponse("/clientes", status_code=303)
    contexto = _contexto_credenciales(db, credencial.cliente_id) | {
        "credencial_a_eliminar": credencial,
    }
    return templates.TemplateResponse(request, "credencial_eliminar.html", contexto)


@router.post("/credenciales/{credencial_id}/eliminar")
def eliminar(credencial_id: int, db: Session = Depends(get_db)):
    credencial = vault.obtener_credencial(db, credencial_id)
    if credencial is None:
        return RedirectResponse("/clientes", status_code=303)
    cliente_id = credencial.cliente_id
    vault.eliminar_credencial(db, credencial_id)
    return RedirectResponse(f"/clientes/{cliente_id}/credenciales", status_code=303)
