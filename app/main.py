"""Arranque de la aplicación FastAPI — Etapa 0.

Incluye el middleware que exige sesión en toda ruta salvo el login
(criterio de terminado 4 de la Etapa 0).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — registra los modelos y activa la auditoría
from app.routes import autenticacion, clientes, configuracion, inicio
from app.services.autenticacion import generar_token_sesion, verificar_token_sesion

app = FastAPI(title="App de gestión del estudio contable")

# Rutas que NO exigen sesión.
RUTAS_PUBLICAS = {"/login"}


@app.middleware("http")
async def exigir_sesion(request: Request, call_next):
    """Toda ruta salvo el login (y los estáticos) requiere sesión válida."""
    ruta = request.url.path
    if ruta in RUTAS_PUBLICAS or ruta.startswith("/static"):
        return await call_next(request)

    usuario_id = verificar_token_sesion(request.cookies.get(autenticacion.NOMBRE_COOKIE))
    if usuario_id is None:
        return RedirectResponse(url="/login", status_code=303)

    request.state.usuario_id = usuario_id
    respuesta = await call_next(request)

    # Expiración "7 días sin uso": cada request autenticado renueva la cookie.
    # Excepción: si la ruta ya tocó la cookie (el logout la borra), no se pisa.
    ya_toco_cookie = any(
        valor.startswith(f"{autenticacion.NOMBRE_COOKIE}=")
        for valor in respuesta.headers.getlist("set-cookie")
    )
    if not ya_toco_cookie:
        autenticacion.poner_cookie_sesion(respuesta, generar_token_sesion(usuario_id))
    return respuesta


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

app.include_router(autenticacion.router)
app.include_router(inicio.router)
app.include_router(clientes.router)
app.include_router(configuracion.router)
