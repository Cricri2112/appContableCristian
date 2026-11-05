"""Arranque de la aplicación FastAPI.

Incluye el middleware que exige sesión en toda ruta salvo el login
(criterio de terminado 4 de la Etapa 0) y el arranque del scheduler de
procesos programados (Etapa 5).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — registra los modelos y activa la auditoría
from app.routes import (
    autenticacion,
    clientes,
    cobros,
    configuracion,
    credenciales,
    honorarios,
    inicio,
    tareas,
    templates_tareas,
    vencimientos,
)
from app.config import settings
from app.services import cifrado, scheduler
from app.services.autenticacion import generar_token_sesion, verificar_token_sesion

# Sin FERNET_KEY válida la app NO arranca (Chat 5, Etapa 4): así nunca se
# guarda una credencial sin cifrar ni se intenta descifrar sin clave.
cifrado.verificar_clave()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Al arrancar: recupera el proceso mensual si no corrió este mes y
    arranca el scheduler. Al apagar: lo detiene."""
    if settings.scheduler_activo:
        scheduler.iniciar()
    yield
    if settings.scheduler_activo:
        scheduler.detener()


app = FastAPI(title="App de gestión del estudio contable", lifespan=ciclo_de_vida)

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
app.include_router(cobros.router)
app.include_router(honorarios.router)
app.include_router(credenciales.router)
app.include_router(tareas.router)
app.include_router(templates_tareas.router)
app.include_router(vencimientos.router)
