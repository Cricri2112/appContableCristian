"""Rutas de login y logout.

Los endpoints solo reciben el request, llaman al servicio y devuelven HTML
(requisito transversal 1: la lógica vive en la capa de servicios).
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.schemas.autenticacion import FormularioLogin
from app.services import autenticacion as servicio_auth

router = APIRouter()

NOMBRE_COOKIE = "sesion"
MAX_AGE_COOKIE = servicio_auth.DIAS_EXPIRACION_SESION * 24 * 60 * 60


def poner_cookie_sesion(respuesta, token: str):
    """Setea la cookie de sesión firmada: Secure + HttpOnly, 7 días."""
    respuesta.set_cookie(
        key=NOMBRE_COOKIE,
        value=token,
        max_age=MAX_AGE_COOKIE,
        httponly=True,   # no accesible desde JavaScript
        secure=True,     # solo viaja por HTTPS
        samesite="lax",
    )


@router.get("/login", response_class=HTMLResponse)
def ver_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def procesar_login(
    request: Request,
    usuario: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    formulario = FormularioLogin(usuario=usuario, password=password)
    resultado = servicio_auth.iniciar_sesion(db, formulario.usuario, formulario.password)

    if not resultado.exitoso:
        return templates.TemplateResponse(
            request, "login.html", {"error": resultado.mensaje}, status_code=401
        )

    respuesta = RedirectResponse(url="/", status_code=303)
    poner_cookie_sesion(respuesta, servicio_auth.generar_token_sesion(resultado.usuario_id))
    return respuesta


@router.post("/logout")
def cerrar_sesion():
    respuesta = RedirectResponse(url="/login", status_code=303)
    respuesta.delete_cookie(NOMBRE_COOKIE)
    return respuesta
